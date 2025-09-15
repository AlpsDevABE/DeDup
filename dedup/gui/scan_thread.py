from PyQt6.QtCore import QThread, pyqtSignal
import os
import sqlite3
import threading
from dedup.scanner import scan_directories
from dedup.hasher import compute_xxhash

def hash_single_file(file_info):
    """
    Standalone function for ProcessPoolExecutor to hash a single file.
    Returns (filepath, xxhash_result, process_id) or (filepath, None, process_id) on error.
    """
    filepath, size, modified = file_info
    try:
        import os
        process_id = os.getpid()  # Get actual process ID
        xxhash = compute_xxhash(filepath)
        return filepath, xxhash, process_id
    except Exception as e:
        return filepath, None, os.getpid()

class ScanThread(QThread):
    # Signals for updating UI
    progress_updated = pyqtSignal(int, int)  # current, total
    folder_changed = pyqtSignal(str)  # current folder
    file_counted = pyqtSignal(int)  # total files found so far
    status_updated = pyqtSignal(str)  # status message
    core_activity_updated = pyqtSignal(list)  # list of (core_id, status, current_file)
    hash_progress_updated = pyqtSignal(int, int)  # hashed, total
    scan_completed = pyqtSignal(list)  # list of files with hashes
    
    def __init__(self, directories, workspace_path, skip_hashed=False):
        super().__init__()
        self.directories = directories
        self.workspace_path = workspace_path
        self.skip_hashed = skip_hashed
        self.cancelled = False
        self.thread_conn = None
        self.core_status = {}  # Track core activity
        self.global_file_count = 0  # Thread-safe global counter
        self.count_lock = threading.Lock()  # Lock for thread safety
        self.log_callback = None  # Will be set by MainWindow
    
    def log_event(self, event_type, message):
        """Log event if callback is available."""
        if self.log_callback:
            self.log_callback(event_type, message)
    
    def _update_core_display(self):
        """Update the core activity display based on current core status."""
        if hasattr(self, 'core_status'):
            core_data = []
            for core_id in sorted(self.core_status.keys()):
                status, current_item = self.core_status[core_id]
                core_data.append((core_id, status, current_item))
            self.core_activity_updated.emit(core_data)
    
    def _filter_unhashed_files(self, all_files):
        """Filter out files that already have hashes in the database."""
        if not self.thread_conn:
            return all_files
        
        files_to_hash = []
        cursor = self.thread_conn.cursor()
        
        for filepath, size, modified in all_files:
            # Check if file already has a hash and hasn't been modified
            cursor.execute('''
                SELECT xxhash, modified FROM files 
                WHERE path = ? AND size = ? AND xxhash IS NOT NULL
            ''', (filepath, size))
            
            result = cursor.fetchone()
            if result is None:
                # File not in database or no hash - needs hashing
                files_to_hash.append((filepath, size, modified))
            else:
                existing_xxhash, existing_modified = result
                if existing_modified != modified:
                    # File has been modified since last scan - needs rehashing
                    files_to_hash.append((filepath, size, modified))
                # else: file already hashed and unchanged - skip it
        
        return files_to_hash
        
    def cancel(self):
        self.cancelled = True
        
    def update_global_file_count(self, increment):
        """Thread-safe method to update global file count."""
        with self.count_lock:
            self.global_file_count += increment
            self.file_counted.emit(self.global_file_count)
        
    def run(self):
        try:
            # Create a new SQLite connection for this thread
            self.thread_conn = sqlite3.connect(self.workspace_path)
            
            self.status_updated.emit("Starting scan...")
            self.log_event("SCAN", f"Starting scan of {len(self.directories)} directories")
            if self.skip_hashed:
                self.log_event("SCAN", "Skip hashed files option enabled - will resume from previous scan")
            
            # Phase 1: File discovery with real-time UI updates
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import multiprocessing
            import time
            
            all_files = []
            file_count = 0
            
            # Reset global counter
            with self.count_lock:
                self.global_file_count = 0
            
            # Reserve cores for UI responsiveness
            available_cores = multiprocessing.cpu_count()
            reserved_for_ui = 1  # Keep one core free for UI responsiveness
            # Use ALL available cores for folder-level work-stealing from the shared pool
            max_scan_cores = available_cores - reserved_for_ui
            max_scan_cores = max(2, max_scan_cores)  # Ensure at least 2 cores
            
            self.log_event("CORE", f"System has {available_cores} cores, reserving {reserved_for_ui} for UI")
            self.log_event("CORE", f"Allocated {max_scan_cores} cores for directory scanning")
            
            def scan_single_directory_with_updates(directory):
                """Scan a single directory with periodic updates."""
                directory_files = []
                last_update = time.time()
                local_count = 0
                last_count_update = 0
                
                try:
                    for root, dirs, filenames in os.walk(directory):
                        if self.cancelled:
                            return directory_files
                        
                        # Update UI periodically during scanning
                        current_time = time.time()
                        if current_time - last_update > 0.5:  # Update every 500ms
                            self.folder_changed.emit(f"Scanning: {root}")
                            self.status_updated.emit(f"Found {local_count} files in {os.path.basename(directory)}...")
                            last_update = current_time
                            
                        for filename in filenames:
                            if self.cancelled:
                                return directory_files
                                
                            path = os.path.join(root, filename)
                            try:
                                stat = os.stat(path)
                                directory_files.append((path, stat.st_size, int(stat.st_mtime)))
                                local_count += 1
                                
                                # Update global file count every 50 files for responsiveness
                                if local_count - last_count_update >= 50:
                                    increment = local_count - last_count_update
                                    self.update_global_file_count(increment)
                                    last_count_update = local_count
                                    
                            except Exception:
                                continue
                                
                except Exception as e:
                    self.status_updated.emit(f"Error in {directory}: {str(e)}")
                
                # Update with any remaining count
                if local_count > last_count_update:
                    increment = local_count - last_count_update
                    self.update_global_file_count(increment)
                
                return directory_files
            
            # NEW APPROACH: Folder-level work-stealing parallelism
            self.log_event("SCAN", f"Using folder-level work-stealing with {max_scan_cores} cores")
            
            # Phase 1A: Discover all folders from all directories
            self.status_updated.emit("Discovering all folders...")
            all_folders = []
            
            for directory in self.directories:
                if self.cancelled:
                    break
                try:
                    for root, dirs, files in os.walk(directory):
                        if self.cancelled:
                            break
                        if files:  # Only add folders that contain files
                            all_folders.append(root)
                except Exception as e:
                    self.status_updated.emit(f"Error discovering folders in {directory}: {str(e)}")
                    continue
            
            if not all_folders:
                self.status_updated.emit("No folders with files found")
                return
            
            folder_count = len(all_folders)
            self.log_event("SCAN", f"Discovered {folder_count} folders across all directories")
            self.status_updated.emit(f"Found {folder_count} folders. Starting parallel scan...")
            
            # Phase 1B: Parallel folder scanning with work-stealing
            self.log_event("CORE", f"Creating shared work queue with {folder_count} folders for {max_scan_cores} cores")
            self.log_event("CORE", f"Folder-level parallelism: {folder_count} folders will be distributed across {max_scan_cores} cores dynamically")
            from queue import Queue
            import threading
            
            folder_queue = Queue()
            for folder in all_folders:
                folder_queue.put(folder)
            
            results_lock = threading.Lock()
            core_status_lock = threading.Lock()
            
            def scan_folder_worker(core_id):
                """Worker function that processes folders from shared queue."""
                worker_files = []
                folders_processed_by_core = 0
                
                self.log_event("CORE", f"Scan worker {core_id} started")
                
                while not self.cancelled:
                    try:
                        folder = folder_queue.get_nowait()
                    except:
                        # No more work in queue
                        with core_status_lock:
                            self.core_status[core_id] = ("Complete", None)
                            self._update_core_display()
                        self.log_event("CORE", f"Scan worker {core_id} finished - processed {folders_processed_by_core} folders")
                        break
                    
                    try:
                        # Update core status
                        with core_status_lock:
                            self.core_status[core_id] = ("Scanning", folder)
                            self._update_core_display()
                        
                        # Log significant folder pickups (avoid too much noise)
                        if folder_queue.qsize() % 10 == 0:  # Log every 10th folder pickup
                            self.log_event("CORE", f"Core {core_id} processing folder, {folder_queue.qsize()} remaining in queue")
                        
                        # Scan this folder
                        folder_files = []
                        try:
                            for filename in os.listdir(folder):
                                if self.cancelled:
                                    break
                                    
                                filepath = os.path.join(folder, filename)
                                if os.path.isfile(filepath):
                                    try:
                                        stat = os.stat(filepath)
                                        folder_files.append((filepath, stat.st_size, int(stat.st_mtime)))
                                    except Exception:
                                        continue
                        except Exception:
                            continue
                        
                        # Add to results thread-safely
                        with results_lock:
                            worker_files.extend(folder_files)
                            folders_processed_by_core += 1
                            # Update global count periodically
                            if len(folder_files) > 0:
                                self.update_global_file_count(len(folder_files))
                        
                    finally:
                        folder_queue.task_done()
                
                return worker_files
            
            # Initialize core status tracking
            self.core_status = {}
            for i in range(max_scan_cores):
                self.core_status[i] = ("Ready", None)
            self._update_core_display()
            
            try:
                with ThreadPoolExecutor(max_workers=max_scan_cores) as executor:
                    # Submit all workers
                    futures = []
                    for core_id in range(max_scan_cores):
                        future = executor.submit(scan_folder_worker, core_id)
                        futures.append(future)
                    
                    # Collect results
                    for future in as_completed(futures, timeout=300):
                        if self.cancelled:
                            break
                        try:
                            worker_files = future.result(timeout=60)
                            all_files.extend(worker_files)
                            file_count += len(worker_files)
                        except Exception as e:
                            self.log_event("ERROR", f"Worker thread error: {str(e)}")
                    
                    # Wait for all folders to be processed
                    folder_queue.join()
                    
            except Exception as e:
                self.log_event("ERROR", f"Parallel scanning failed: {str(e)}")
                self.status_updated.emit(f"Error in parallel scanning: {str(e)}")
                # Fall back to sequential scanning
                all_files = []
                for directory in self.directories:
                    if self.cancelled:
                        break
                    directory_files = scan_single_directory_with_updates(directory)
                    all_files.extend(directory_files)
                    file_count = len(all_files)
                    self.file_counted.emit(file_count)
            
            if self.cancelled:
                return
            
            # Filter out already hashed files if skip option is enabled
            if self.skip_hashed:
                original_count = len(all_files)
                files_to_hash = self._filter_unhashed_files(all_files)
                skipped_count = original_count - len(files_to_hash)
                
                self.log_event("SCAN", f"Skip mode: Found {skipped_count} already hashed files, {len(files_to_hash)} files need hashing")
                self.status_updated.emit(f"Found {original_count} files, {len(files_to_hash)} need hashing (skipped {skipped_count})")
                all_files = files_to_hash
            else:
                self.status_updated.emit(f"Found {len(all_files)} files. Starting parallel hash computation...")
                self.log_event("SCAN", f"Completed file discovery: {len(all_files)} files found")
            
            # Phase 2: Compute hashes using parallel processing with core tracking
            from dedup.parallel_processor import ParallelProcessor
            
            processor = ParallelProcessor(max_workers=8)  # As per design document
            
            def core_update_callback(core_data):
                """Callback to update UI with core activity."""
                if not self.cancelled:
                    self.core_activity_updated.emit(core_data)
            
            def progress_update_callback(processed, total):
                """Callback to update progress."""
                if not self.cancelled:
                    self.progress_updated.emit(processed, total)
            
            # Phase 2: Parallel hashing with real core activity display
            self.status_updated.emit(f"Starting parallel hashing of {len(all_files)} files...")
            
            hash_results = []
            
            # NEW APPROACH: Shared file pool with ProcessPoolExecutor for true multi-core
            available_cores_for_hash = multiprocessing.cpu_count() - 1  # Reserve 1 for UI
            max_hash_cores = available_cores_for_hash  # Use ALL available cores
            
            self.status_updated.emit(f"Using {max_hash_cores} cores for hashing")
            self.log_event("CORE", f"Reserved 1 core for UI, using {max_hash_cores} of {multiprocessing.cpu_count()} cores for hashing")
            self.log_event("CORE", f"Switching to ProcessPoolExecutor for true multi-core processing (avoiding GIL)")
            
            # ALL files go into shared pool - no separation by size initially
            self.log_event("CORE", f"Creating shared file pool with {len(all_files)} files for {max_hash_cores} cores")
            
            # Split files by size for logging only
            large_files = [(f, s, m) for f, s, m in all_files if s >= 50 * 1024 * 1024]  # >50MB
            small_files = [(f, s, m) for f, s, m in all_files if s < 50 * 1024 * 1024]
            
            self.status_updated.emit(f"Found {len(large_files)} large files and {len(small_files)} small files")
            self.log_event("CORE", f"File distribution: {len(large_files)} large files (>50MB), {len(small_files)} small files")
            self.log_event("CORE", f"All files will be processed from shared pool by {max_hash_cores} processes")
            
            # Track which files are being processed by which cores
            active_cores = {}
            core_lock = threading.Lock()
            
            # Track unique cores that have been used
            cores_ever_used = set()
            cores_lock = threading.Lock()
            
            def hash_file_with_core_tracking(file_info_and_core):
                """Hash a single file and track which core is doing it."""
                (filepath, size, modified), assigned_core_id = file_info_and_core
                
                # Use thread ID as actual core identifier
                import threading
                actual_thread_id = threading.get_ident() % max_hash_cores
                
                # Track which cores are actually being used
                with cores_lock:
                    if actual_thread_id not in cores_ever_used:
                        cores_ever_used.add(actual_thread_id)
                        self.log_event("CORE", f"Core {actual_thread_id} started working (Total active cores: {len(cores_ever_used)})")
                
                with core_lock:
                    active_cores[actual_thread_id] = {
                        'status': f"Hashing ({size//1024//1024}MB)" if size > 1024*1024 else "Hashing (Small)",
                        'file': os.path.basename(filepath)
                    }
                    
                    # Build complete core display
                    core_data = []
                    for i in range(max_hash_cores):
                        if i in active_cores:
                            core_data.append((i, active_cores[i]['status'], active_cores[i]['file']))
                        else:
                            core_data.append((i, "Idle", None))
                    core_update_callback(core_data)
                
                try:
                    xxhash = compute_xxhash(filepath)
                    
                    # Remove from active cores when done
                    with core_lock:
                        if actual_thread_id in active_cores:
                            del active_cores[actual_thread_id]
                        
                        # Update display to show completion
                        core_data = []
                        for i in range(max_hash_cores):
                            if i in active_cores:
                                core_data.append((i, active_cores[i]['status'], active_cores[i]['file']))
                            else:
                                core_data.append((i, "Idle", None))
                        core_update_callback(core_data)
                    
                    return filepath, xxhash, actual_thread_id
                except Exception as e:
                    # Remove from active cores on error
                    with core_lock:
                        if actual_thread_id in active_cores:
                            del active_cores[actual_thread_id]
                    return filepath, None, actual_thread_id
            
            # Process ALL files using ProcessPoolExecutor for true multi-core
            self.status_updated.emit(f"Starting parallel hashing with {max_hash_cores} worker processes...")
            self.log_event("CORE", f"Creating ProcessPoolExecutor with {max_hash_cores} workers")
            
            # Initialize hash progress display
            self.hash_progress_updated.emit(0, len(file_list))
            
            # Create simple file list for processing (no pre-assignment to cores)
            file_list = [(f, s, m) for f, s, m in all_files]
            self.log_event("CORE", f"Prepared {len(file_list)} files for shared pool processing")
            
            from concurrent.futures import ProcessPoolExecutor
            
            # Track process IDs to monitor core utilization
            processes_used = set()
            completed = 0
            
            try:
                with ProcessPoolExecutor(max_workers=max_hash_cores) as executor:
                    self.log_event("CORE", f"ProcessPoolExecutor created successfully with max_workers={max_hash_cores}")
                    
                    # Submit ALL files to the shared process pool
                    self.status_updated.emit(f"Submitting {len(file_list)} files to {max_hash_cores} processes...")
                    self.log_event("CORE", f"Starting to submit {len(file_list)} files to ProcessPoolExecutor")
                    
                    # Submit all files at once for better distribution
                    future_to_file = {}
                    for file_info in file_list:
                        if self.cancelled:
                            break
                        future = executor.submit(hash_single_file, file_info)
                        future_to_file[future] = file_info[0]  # Store filepath
                    
                    self.log_event("CORE", f"Successfully submitted all {len(future_to_file)} files to ProcessPoolExecutor")
                    self.status_updated.emit(f"Hashing {len(future_to_file)} files with {max_hash_cores} processes...")
                    
                    # Process results as they complete
                    for future in as_completed(future_to_file):
                        if self.cancelled:
                            break
                            
                        try:
                            filepath, xxhash, process_id = future.result()
                            completed += 1
                            
                            # Track which processes are being used
                            if process_id not in processes_used:
                                processes_used.add(process_id)
                                self.log_event("CORE", f"Process {process_id} started working (Total active processes: {len(processes_used)})")
                            
                            if xxhash:
                                hash_results.append((filepath, xxhash))
                            
                            # Update progress more frequently for better UI responsiveness
                            if completed % 5 == 0 or completed == len(file_list):  # Update every 5 files
                                progress_update_callback(completed, len(file_list))
                                # Also update hash progress display
                                self.hash_progress_updated.emit(completed, len(file_list))
                                
                            # Log progress and update status periodically
                            if completed % 100 == 0:
                                self.log_event("CORE", f"Progress: {completed}/{len(file_list)} files, using {len(processes_used)} processes")
                                percentage = (completed / len(file_list)) * 100
                                self.status_updated.emit(f"Hashing progress: {completed:,}/{len(file_list):,} files ({percentage:.1f}%)")
                                
                            if completed % 1000 == 0:
                                self.status_updated.emit(f"Hashed {completed}/{len(file_list)} files ({(completed/len(file_list)*100):.1f}%)")
                                
                        except Exception as e:
                            self.log_event("ERROR", f"Error processing file: {str(e)}")
                            completed += 1
                    
                    # Log final process utilization
                    self.log_event("CORE", f"ProcessPoolExecutor completed - Used {len(processes_used)} processes total")
                    
            except Exception as e:
                self.log_event("ERROR", f"ProcessPoolExecutor failed: {str(e)}")
                self.status_updated.emit(f"Error in parallel hashing: {str(e)}")
                # Fall back to sequential processing if needed
                hash_results = []
            
            # Store results in database
            hashed_files = []
            for filepath, xxhash in hash_results:
                if self.cancelled:
                    return
                    
                # Find the original file info
                file_info = next((f for f in all_files if f[0] == filepath), None)
                if file_info:
                    path, size, modified = file_info
                    hashed_files.append((path, size, modified, xxhash))
                    self._add_file_to_db(path, size, modified, xxhash)
            
            if not self.cancelled:
                # Log final process utilization summary  
                total_processes_used = len(processes_used)
                self.log_event("CORE", f"Hashing completed - Used {total_processes_used}/{max_hash_cores} processes total")
                if total_processes_used < max_hash_cores:
                    self.log_event("CORE", f"WARNING: Only {total_processes_used} processes were utilized out of {max_hash_cores} allocated")
                
                self.scan_completed.emit(hashed_files)
                self.status_updated.emit(f"Scan completed. Processed {len(hashed_files)} files.")
                self.log_event("SCAN", f"Scan completed successfully: {len(hashed_files)} files processed")
            else:
                self.status_updated.emit("Scan was cancelled.")
                self.log_event("SCAN", "Scan cancelled by user")
                
        except Exception as e:
            self.status_updated.emit(f"Error during scan: {str(e)}")
            import traceback
            print(f"Full error traceback: {traceback.format_exc()}")
        finally:
            # Clear core activity display
            self.core_activity_updated.emit([])
            
            # Always close the thread connection
            if self.thread_conn:
                self.thread_conn.close()
    
    def _add_file_to_db(self, path: str, size: int, modified: int, xxhash: str, 
                        md5: str = None, sha1: str = None, status: str = "present"):
        """Add file to database using the thread's own connection."""
        if not self.thread_conn:
            return
            
        cur = self.thread_conn.cursor()
        cur.execute('''
            INSERT OR REPLACE INTO files (path, size, modified, xxhash, md5, sha1, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (path, size, modified, xxhash, md5, sha1, status))
        self.thread_conn.commit()