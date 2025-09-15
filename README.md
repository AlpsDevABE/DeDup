# DeDup - Python Duplicate File Finder

A fast, efficient duplicate file finder with a modern GUI built using Python and PyQt6.

## Features

- **Fast duplicate detection** using xxHash for initial screening and MD5 for confirmation
- **Multi-core processing** with separate handling for large and small files
- **Modern GUI** with tabbed interface and progress tracking
- **Workspace management** - save and load scanning configurations
- **Cross-platform** support (Windows, macOS, Linux)

## Installation

### From Source

1. Clone the repository:
```bash
git clone <repository-url>
cd dedup
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python dedup/main.py
```

   Alternative methods:
```bash
# Run as a module from project root
python -m dedup.main

# Or install in development mode first
pip install -e .
python -m dedup.main
```

### Using pip (when available)

```bash
pip install dedup
dedup
```

## Usage

1. **Create or load a workspace**: Start by creating a new workspace file (.dedupe) or loading an existing one
2. **Add directories**: Select directories to scan for duplicate files
3. **Start scan**: Begin the scanning and hashing process
4. **Review results**: View duplicate files in the Results tab
5. **Manage duplicates**: Use the interface to handle duplicate files

## Architecture

The application is built with the following components:

- **Scanner**: Recursively scans directories for files
- **Hasher**: Computes xxHash, MD5, and SHA-1 hashes
- **Parallel Processor**: Uses ThreadPoolExecutor and ProcessPoolExecutor for multi-core hashing
- **Deduper**: Finds and confirms duplicate files
- **Workspace**: SQLite-based storage for file metadata and workspace configuration
- **GUI**: PyQt6-based interface with tabbed layout

## Requirements

- Python 3.12+
- PyQt6 6.5.0+
- xxhash 3.2.0+

## License

MIT License - see LICENSE file for details.