import os
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Tuple, Callable, Dict
from dedup.hasher import compute_xxhash, compute_md5, compute_sha1

class ParallelProcessor:
    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers
        self.large_file_threshold = 50 * 1024 * 1024  # 50MB
        self.core_activity = {}  # Track what each core is doing
        self.activity_lock = threading.Lock()
        
    def process_files_parallel(self, files: List[Tuple[str, int, int]], 
                             hash_func: Callable, 
                             progress_callback: Callable = None) -> List[Tuple[str, str]]:
        """
        Process files in parallel using appropriate executors for large/small files.
        Returns list of (filepath, hash) tuples.
        """
        large_files = [(f, s, m) for f, s, m in files if s >= self.large_file_threshold]
        small_files = [(f, s, m) for f, s, m in files if s < self.large_file_threshold]
        
        results = []
        total_files = len(files)
        processed = 0
        
        # Process large files with ProcessPoolExecutor
        if large_files:
            with ProcessPoolExecutor(max_workers=min(4, self.max_workers)) as executor:
                future_to_file = {
                    executor.submit(hash_func, f[0]): f[0] 
                    for f in large_files
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        hash_result = future.result()
                        if hash_result:
                            results.append((filepath, hash_result))
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")
                    
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_files)
        
        # Process small files with ThreadPoolExecutor
        if small_files:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(hash_func, f[0]): f[0] 
                    for f in small_files
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        hash_result = future.result()
                        if hash_result:
                            results.append((filepath, hash_result))
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")
                    
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_files)
        
        return results
    
    def process_files_with_core_tracking(self, files: List[Tuple[str, int, int]], 
                                       hash_func: Callable,
                                       core_callback: Callable = None,
                                       progress_callback: Callable = None) -> List[Tuple[str, str]]:
        """
        Process files in parallel with detailed core activity tracking.
        """
        large_files = [(f, s, m) for f, s, m in files if s >= self.large_file_threshold]
        small_files = [(f, s, m) for f, s, m in files if s < self.large_file_threshold]
        
        results = []
        total_files = len(files)
        processed = 0
        
        # Initialize core tracking
        max_cores = min(self.max_workers, multiprocessing.cpu_count())
        for i in range(max_cores):
            self.core_activity[i] = {"status": "Idle", "file": None}
        
        if core_callback:
            self._update_core_display(core_callback)
        
        # Process large files with ProcessPoolExecutor (2-4 cores as per design)
        if large_files:
            large_cores = min(4, max(2, max_cores // 2))
            
            with ProcessPoolExecutor(max_workers=large_cores) as executor:
                # Submit all large files
                future_to_file = {}
                for i, file_info in enumerate(large_files):
                    if len(future_to_file) < large_cores:  # Don't overwhelm
                        future = executor.submit(hash_func, file_info[0])
                        future_to_file[future] = (file_info[0], i % large_cores)
                        
                        # Update core status
                        core_id = i % large_cores
                        self.core_activity[core_id] = {"status": "Hashing (Large)", "file": file_info[0]}
                        
                        if core_callback:
                            self._update_core_display(core_callback)
                
                # Process completed futures
                for future in as_completed(future_to_file):
                    filepath, core_id = future_to_file[future]
                    
                    try:
                        hash_result = future.result()
                        if hash_result:
                            results.append((filepath, hash_result))
                    except Exception as e:
                        print(f"Error processing {filepath}: {e}")
                    
                    # Mark core as idle
                    self.core_activity[core_id] = {"status": "Idle", "file": None}
                    
                    processed += 1
                    if progress_callback:
                        progress_callback(processed, total_files)
                    if core_callback:
                        self._update_core_display(core_callback)
        
        # Process small files with ThreadPoolExecutor (up to 8 cores)
        if small_files:
            small_cores = min(self.max_workers, max_cores)
            
            with ThreadPoolExecutor(max_workers=small_cores) as executor:
                # Submit small files in batches
                future_to_file = {}
                file_index = 0
                
                while file_index < len(small_files) or future_to_file:
                    # Submit new files if we have capacity
                    while len(future_to_file) < small_cores and file_index < len(small_files):
                        file_info = small_files[file_index]
                        future = executor.submit(hash_func, file_info[0])
                        core_id = file_index % small_cores
                        future_to_file[future] = (file_info[0], core_id)
                        
                        # Update core status
                        self.core_activity[core_id] = {"status": "Hashing (Small)", "file": file_info[0]}
                        
                        file_index += 1
                        if core_callback:
                            self._update_core_display(core_callback)
                    
                    # Wait for at least one to complete
                    if future_to_file:
                        done_futures = []
                        for future in list(future_to_file.keys()):
                            if future.done():
                                done_futures.append(future)
                        
                        if not done_futures:
                            # Wait for first one to complete
                            done_futures = [next(as_completed(future_to_file.keys(), timeout=0.1))]
                        
                        for future in done_futures:
                            filepath, core_id = future_to_file.pop(future)
                            
                            try:
                                hash_result = future.result()
                                if hash_result:
                                    results.append((filepath, hash_result))
                            except Exception as e:
                                print(f"Error processing {filepath}: {e}")
                            
                            # Mark core as idle
                            self.core_activity[core_id] = {"status": "Idle", "file": None}
                            
                            processed += 1
                            if progress_callback:
                                progress_callback(processed, total_files)
                            if core_callback:
                                self._update_core_display(core_callback)
        
        return results
    
    def _update_core_display(self, core_callback):
        """Update the UI with current core activity."""
        with self.activity_lock:
            core_data = []
            for core_id, activity in self.core_activity.items():
                status = activity["status"]
                current_file = activity["file"]
                core_data.append((core_id, status, current_file))
            
            core_callback(core_data)