import os
from typing import List, Callable, Optional
from dedup.workspace import Workspace
from dedup.scanner import scan_directories
from dedup.parallel_processor import ParallelProcessor
from dedup.deduper import Deduper
from dedup.hasher import compute_xxhash

class DedupEngine:
    def __init__(self, workspace_path: str):
        self.workspace = Workspace(workspace_path)
        self.processor = ParallelProcessor()
        self.deduper = Deduper(self.workspace)
        self.directories = []
        
    def add_directory(self, directory: str):
        """Add a directory to be scanned."""
        if os.path.exists(directory):
            self.directories.append(directory)
            return True
        return False
        
    def remove_directory(self, directory: str):
        """Remove a directory from scan list."""
        if directory in self.directories:
            self.directories.remove(directory)
            return True
        return False
    
    def scan_and_hash(self, progress_callback: Optional[Callable] = None):
        """
        Scan directories and compute initial xxHash for all files.
        """
        if not self.directories:
            raise ValueError("No directories to scan")
            
        # Step 1: Scan directories for files
        files = scan_directories(self.directories)
        total_files = len(files)
        
        if progress_callback:
            progress_callback("Scanning completed. Found {} files. Starting hashing...".format(total_files))
        
        # Step 2: Compute xxHash in parallel
        def progress_wrapper(processed, total):
            if progress_callback:
                progress = int((processed / total) * 100)
                progress_callback(f"Hashing: {processed}/{total} ({progress}%)")
        
        hash_results = self.processor.process_files_parallel(
            files, 
            compute_xxhash, 
            progress_wrapper
        )
        
        # Step 3: Store results in workspace
        file_dict = {f[0]: (f[1], f[2]) for f in files}  # path -> (size, modified)
        
        for filepath, xxhash in hash_results:
            if filepath in file_dict:
                size, modified = file_dict[filepath]
                self.workspace.add_file(filepath, size, modified, xxhash)
        
        if progress_callback:
            progress_callback(f"Hashing completed. Processed {len(hash_results)} files.")
    
    def find_duplicates(self, progress_callback: Optional[Callable] = None):
        """
        Find and confirm duplicate files using xxHash and MD5.
        """
        if progress_callback:
            progress_callback("Finding potential duplicates...")
            
        potential_groups = self.deduper.find_potential_duplicates()
        
        if progress_callback:
            progress_callback(f"Found {len(potential_groups)} potential duplicate groups. Confirming with MD5...")
        
        confirmed_duplicates = self.deduper.confirm_duplicates(potential_groups)
        
        if progress_callback:
            progress_callback(f"Confirmed {len(confirmed_duplicates)} duplicate groups.")
            
        return confirmed_duplicates
    
    def get_all_files(self):
        """Get all files from workspace."""
        return self.workspace.get_files()
    
    def close(self):
        """Close the workspace."""
        self.workspace.close()