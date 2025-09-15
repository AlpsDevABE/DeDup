# Python Duplicate File Finder Design Document

## 1. Overview

The goal of this application is to efficiently find duplicate files on a user-specified set of directories using a hash-based approach. The application:

* Indexes the filesystem metadata and stores it in a database.
* Uses **xxHash** (fast, lightweight) for the initial duplicate check, and computes **MD5/SHA-1** only on potential duplicates.
* Handles large and small files differently to optimize hashing across multiple CPU cores.
* Provides a desktop GUI with a tabbed interface and spreadsheet-like views.
* Allows users to manage a “workspace” of directories and save/load it as a `.dedupe` file.

---

## 2. Platform & Technology

* **Programming Language:** Python 3.12+
* **GUI Framework:** PyQt6 (cross-platform, high-performance, mature)
* **Database:** SQLite (lightweight, cross-platform, file-based)
* **Hashing Libraries:**

  * `xxhash` for initial fast hashing (replaces CRC-32)
  * `hashlib` for MD5 and SHA-1 for duplicates
* **Parallelism:**

  * `concurrent.futures.ThreadPoolExecutor` and `ProcessPoolExecutor` for multi-core hashing
  * Auto-scaled cores for large and small files (up to 8 cores total)

---

## 3. Workflow

### 3.1 Workspace Management

* User creates a workspace (`.dedupe`)
* User selects directories to scan; can add/remove directories anytime
* Workspace stores:

  * Indexed file paths
  * Hash values
  * File metadata (size, modified time, status)

### 3.2 Indexing

* User initiates scan
* Files are **scanned in chunks** (e.g., 100,000 files) to manage memory and UI responsiveness
* **Large files** are hashed first to avoid UI lag
* Metadata stored in SQLite: path, size, last modified, hash values, status (present/missing/duplicate)

### 3.3 Hashing & Duplicate Detection

* **Initial hash:** xxHash
* **Duplicate check:**

  * Only compute MD5/SHA-1 on files with matching xxHash
* **Large vs small file handling:**

  * Rolling average to classify large files (>1 minute to hash)
  * Large files can use 2–4 cores; small files up to 4 cores
* **Database updates:**

  * Insert new files
  * Update changed files (modified time, size)
  * Mark missing files but retain entries
  * Remove entries when duplicates are deleted externally

### 3.4 User Interaction

* Users can access results **while scanning**
* Clicking on a duplicate opens both directories in Explorer/Finder
* Results displayed in **tabbed interface**:

  1. **Duplicates Tab:** Spreadsheet-style view of all flagged duplicates
  2. **Filter/Search Tab:** “Everything”-like interface to search/filter files by name, size, path, or hash
* **Progress Tracking:**

  * Progress bar shows scanning status per chunk
  * Scanning paused after each chunk for user confirmation

---

## 4. Database Schema (SQLite)

```sql
-- Files Table
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    last_modified INTEGER NOT NULL,
    xxhash TEXT,
    md5 TEXT,
    sha1 TEXT,
    status TEXT CHECK(status IN ('present', 'missing', 'duplicate')) DEFAULT 'present',
    workspace_id INTEGER
);

-- Duplicates Table
CREATE TABLE duplicates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    duplicate_of INTEGER NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(id),
    FOREIGN KEY(duplicate_of) REFERENCES files(id)
);

-- Workspaces Table
CREATE TABLE workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
```

**Notes:**

* `xxhash` used for initial duplicate detection
* `md5` and `sha1` only computed for potential duplicates
* Status flags allow tracking missing files without alerting user immediately

---

## 5. Performance & Parallelism

* **Multi-core hashing:**

  * Separate pools for large files and small files
  * Dynamic adjustment based on hashing time
* **Memory optimization:**

  * Chunked scanning to reduce memory footprint
  * Only store hashes for duplicates and metadata for all files
* **Large file prioritization:**

  * Ensures UI remains responsive while scanning huge files

---

## 6. GUI Design

### 6.1 Main Window

* **Menu:** Open Workspace, Save Workspace, Add/Remove Directories, Start Scan
* **Progress Bar:** Shows current scan progress and chunk status
* **Tabs:**

  1. **Duplicates** – spreadsheet with columns: File Path, Size, Last Modified, Duplicate Of, Hashes
  2. **Filter/Search** – “Everything”-style search for name, path, size, or hash

### 6.2 Interaction

* Right-click on a file → Open containing folder
* Select duplicates → Options to ignore/delete (future feature)
* Scan results update live per chunk

---

## 7. Future Enhancements

* Real-time file monitoring
* Automatic duplicate removal
* Network drives support
* Advanced filtering (file type, date range, etc.)
* Cloud sync for workspace

---

# Architecture & Pseudocode Draft

## 1. High-Level Architecture

```
+------------------------------------------------+
|                  Main GUI (PyQt6)             |
|------------------------------------------------|
|  Menu: Workspace | Directories | Scan         |
|  Tabs: Duplicates | Filter/Search             |
|  Progress Bar / Chunk Controls                 |
+------------------------------------------------+
             |
             v
+------------------------------------------------+
|              Scan Controller                  |
|------------------------------------------------|
|  - Manages scanning queue                     |
|  - Determines large vs small files           |
|  - Dispatches hashing jobs to Hash Manager   |
|  - Updates progress bar and UI                |
+------------------------------------------------+
             |
             v
+------------------------------------------------+
|                Hash Manager                    |
|------------------------------------------------|
|  - Multi-core hashing pool                     |
|    * Large files pool                          |
|    * Small files pool                          |
|  - Hash computation logic                      |
|    * xxHash (all files)                        |
|    * MD5/SHA1 (only for xxHash duplicates)    |
|  - Rolling average time per file               |
+------------------------------------------------+
             |
             v
+------------------------------------------------+
|                Database Layer                 |
|------------------------------------------------|
|  - SQLite database                             |
|  - Tables: files, duplicates, workspaces      |
|  - Efficient storage of hashes & metadata     |
|  - Update logic: insert/update/mark missing  |
+------------------------------------------------+
             |
             v
+------------------------------------------------+
|           File System Interaction             |
|------------------------------------------------|
|  - Recursive directory traversal               |
|  - Chunked scanning for memory/performance    |
|  - Open containing folder (Explorer/Finder)   |
+------------------------------------------------+
```

## 2. Pseudocode

```python
# Main Scan Flow
start_scan(workspace)
  files_to_scan = gather_files(workspace.directories)
  chunks = chunk_files(files_to_scan, chunk_size=100000)

  for chunk in chunks:
      scan_chunk(chunk, workspace)
      update_progress(chunk)
      if user_pauses():
          wait_for_user()

# Chunk Scanning
scan_chunk(files, workspace)
  files.sort(key=lambda f: f.size, reverse=True)
  large_files, small_files = classify_files(files)
  hash_results_large = hash_files_multi_core(large_files, cores_for_large)
  hash_results_small = hash_files_multi_core(small_files, cores_for_small)

  for file_path, xxhash_value in results:
      process_file_hash(file_path, xxhash_value, workspace)

# Hash Computation
hash_files_multi_core(files, core_count)
  with ProcessPoolExecutor(max_workers=core_count) as executor:
      future_to_file = {executor.submit(hash_file, f): f for f in files}
      for future in as_completed(future_to_file):
          results[file_path] = future.result()

hash_file(file_path)
  start_time = now()
  xxhash_value = xxhash(file_path)
  update_rolling_average(file_path, elapsed_time)
  return file_path, xxhash_value

# Duplicate Handling
process_file_hash(file_path, xxhash_value, workspace)
  duplicate = db_lookup_xxhash(xxhash_value, workspace)
  if duplicate:
      md5_val, sha1_val = compute_md5_sha1(file_path)
      db_insert_duplicate(file_path, duplicate.id, md5_val, sha1_val)
      db_update_file(file_path, xxhash_value, md5_val, sha1_val, status='duplicate')
  else:
      db_insert_file(file_path, xxhash_value)

# File Gathering
gather_files(directories)
  all_files = []
  for dir in directories:
      all_files.extend(recursive_scan(dir))
  return all_files

recursive_scan(directory)
  return [os.path.join(dp, f) for dp, dn, filenames in os.walk(directory) for f in filenames]
```

## 3. Multi-Core Strategy

* Large files: 2–4 cores depending on availability
* Small files: 1–4 cores (auto-scaled)
* Large vs small classification updated dynamically using rolling average
* Chunked scanning to maintain UI responsiveness

## 4. Database Efficiency

* Only store MD5/SHA1 for duplicates
* Index on `xxhash` and `path` for fast lookup
* Integer timestamps to reduce space
* Missing files retained until found or confirmed deleted

## 5. UI/UX Features

* Tabbed Interface: Duplicates and Filter/Search
* Right-click to open containing folder
* Partial results live during scanning
* Progress bar and chunk-based scan pausing
* `.dedupe` workspaces store directories, database path, and last scan metadata

