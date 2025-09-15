import os
from typing import List, Tuple, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

def scan_directories(directories: List[str]) -> List[Tuple[str, int, int]]:
    """
    Scans the given directories and returns a list of (path, size, modified_time) for each file.
    """
    files = []
    for directory in directories:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                path = os.path.join(root, filename)
                try:
                    stat = os.stat(path)
                    files.append((path, stat.st_size, int(stat.st_mtime)))
                except Exception:
                    continue
    return files

def scan_directories_parallel(directories: List[str], 
                            progress_callback: Optional[Callable] = None,
                            core_callback: Optional[Callable] = None) -> List[Tuple[str, int, int]]:
    """
    Scans directories in parallel using multiple cores.
    """
    if not directories:
        return []
    
    max_workers = min(8, multiprocessing.cpu_count(), len(directories))
    all_files = []
    
    def scan_single_directory(directory_info):
        """Scan a single directory and return (directory, files_list)."""
        directory, core_id = directory_info
        directory_files = []
        
        try:
            for root, _, filenames in os.walk(directory):
                for filename in filenames:
                    path = os.path.join(root, filename)
                    try:
                        stat = os.stat(path)
                        directory_files.append((path, stat.st_size, int(stat.st_mtime)))
                    except Exception:
                        continue
        except Exception:
            pass
        
        return directory, directory_files, core_id
    
    # Prepare directory assignments with core IDs
    directory_assignments = [(dir_path, i % max_workers) for i, dir_path in enumerate(directories)]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all directories
        future_to_dir = {
            executor.submit(scan_single_directory, assignment): assignment[0] 
            for assignment in directory_assignments
        }
        
        # Update initial core status
        if core_callback:
            core_data = [(i, "Scanning" if i < len(directories) else "Idle", 
                         directories[i] if i < len(directories) else None) 
                         for i in range(max_workers)]
            core_callback(core_data)
        
        completed_dirs = 0
        
        # Process completed scans
        for future in as_completed(future_to_dir):
            directory_path = future_to_dir[future]
            
            try:
                directory, directory_files, core_id = future.result()
                all_files.extend(directory_files)
                completed_dirs += 1
                
                if progress_callback:
                    progress_callback(f"Scanned {directory}: {len(directory_files)} files", 
                                    completed_dirs, len(directories))
                
                if core_callback:
                    # Update core status
                    core_data = []
                    for i in range(max_workers):
                        if i == core_id:
                            core_data.append((i, "Completed", None))
                        elif completed_dirs + i < len(directories):
                            core_data.append((i, "Scanning", directories[completed_dirs + i]))
                        else:
                            core_data.append((i, "Idle", None))
                    core_callback(core_data)
                    
            except Exception as e:
                if progress_callback:
                    progress_callback(f"Error scanning {directory_path}: {str(e)}", 
                                    completed_dirs, len(directories))
    
    return all_files
