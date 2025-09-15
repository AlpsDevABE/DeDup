# DeDup Application Features

## 1. Efficient Duplicate Detection
- Uses xxHash for fast initial checks
- MD5/SHA-1 for confirming duplicates
- Handles large and small files differently for performance

## 2. Workspace Management
- Users create and manage workspaces (.dedupe files)
- Add/remove directories to scan
- Save/load workspace state

## 3. Indexing & Metadata
- **Parallel directory scanning** using multiple cores for file discovery
- **Parallel hashing** with separate core allocation for large/small files
- Stores file paths, sizes, modified times, hash values, and status in SQLite database
- Real-time progress display showing current folder being scanned
- Live file counter during scanning process

## 4. Parallel Processing
- **Two-Phase Parallel Processing**:
  - **Phase 1**: Multi-core directory scanning (up to 8 cores for file discovery)
  - **Phase 2**: Multi-core hashing (2-4 cores for large files, up to 8 for small files)
- Utilizes ThreadPoolExecutor and ProcessPoolExecutor
- Real-time core activity monitoring showing which directories/files each core is processing
- Background scanning with cancellation support
- Visual core status display with color-coded activity states

## 5. Desktop GUI
- Built with PyQt6
- Tabbed interface
- Spreadsheet-like views for file management
- Real-time progress indicators
- Cancel button for stopping long-running operations

## 6. User Actions
- Initiate scan with real-time progress feedback
- Cancel ongoing scans
- Review duplicates in organized tables
- Manage files (delete, move, etc.)

## 7. Data Storage
- SQLite database for persistent file metadata storage
- Efficient indexing for fast duplicate detection
- Workspace files (.dedupe) contain complete scan history

## 8. Extensibility
- Modular design for future features
- Cross-platform support (Windows, macOS, Linux)
- Threaded architecture for responsive UI
