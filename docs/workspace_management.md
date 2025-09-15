# Workspace Management

## Overview
DeDup uses a workspace-based approach to manage duplicate file detection projects. Each workspace is a self-contained `.dedupe` file that includes:

- SQLite database with file metadata
- Directory list for scanning
- Workspace statistics and settings
- Complete scan history

## Workspace Structure

### Database Tables

#### 1. `files` table
Stores metadata for all scanned files:
- `path`: Full file path
- `size`: File size in bytes
- `modified`: Last modification timestamp
- `xxhash`: Fast hash for initial duplicate detection
- `md5`: Confirmation hash for duplicates
- `sha1`: Additional hash if needed
- `status`: File status (present, missing, duplicate)
- `created_at`: When file was added to workspace

#### 2. `workspace_directories` table
Manages directories included in workspace:
- `directory_path`: Full path to directory
- `added_at`: When directory was added
- `last_scanned`: Last scan timestamp for this directory

#### 3. `workspace_metadata` table
Stores workspace statistics:
- `workspace_name`: Display name
- `total_files`: Count of all files
- `total_size`: Total size of all files
- `duplicate_groups`: Number of duplicate file groups
- `last_scan`: Timestamp of most recent scan

#### 4. `workspace_config` table
General configuration key-value pairs

## File Menu Operations

### New Workspace
- Creates empty workspace in memory
- Clears all UI elements
- Sets window title to "New Workspace"

### Open Workspace
- Prompts user to select `.dedupe` file
- Loads directories from database
- Populates UI with existing data
- Updates window title with filename

### Save Workspace
- Saves current workspace to existing file path
- Creates new file if none exists (prompts for location)
- Updates all database tables with current state

### Save Workspace As
- Prompts for new file location
- Creates new `.dedupe` file
- Copies all data from current workspace

## Auto-Save Features

### Directory Changes
- Automatically saves when directories are added
- Updates `workspace_directories` table
- No manual save required

### Scan Completion
- Updates workspace metadata automatically
- Saves directory list
- Calculates and stores statistics

## Data Persistence

### Benefits of This Implementation
1. **Complete Isolation**: Each workspace is completely independent
2. **Portable**: `.dedupe` files can be moved between machines
3. **Versioning**: Multiple workspaces for different projects
4. **Backup**: Easy to backup individual workspace files
5. **Performance**: SQLite indexes optimize duplicate detection

### Database Performance
- Indexes on `xxhash`, `md5`, and `size` columns
- Efficient duplicate group counting
- Fast workspace statistics calculation

## Recent Workspaces System

### Automatic Workspace Tracking
- **Last 10 Workspaces**: Remembers the 10 most recently opened workspaces
- **File Validation**: Automatically removes workspaces that no longer exist
- **Auto-Restore**: Opens the last used workspace when application starts
- **Persistent Storage**: Uses QSettings for cross-platform storage

### Recent Workspaces Tab
- **Workspace List**: Displays name, path, and last opened date
- **Double-Click Open**: Quick access to recent workspaces
- **Refresh Button**: Manually validate and refresh the list
- **Clear All**: Remove all recent workspace entries

### Storage Location
Recent workspaces are stored in platform-specific locations:
- **Windows**: Registry under `HKEY_CURRENT_USER\Software\DeDup\DuplicateFileFinder`
- **macOS**: `~/Library/Preferences/com.DeDup.DuplicateFileFinder.plist`
- **Linux**: `~/.config/DeDup/DuplicateFileFinder.conf`

## Usage Workflow

1. **Start Application**: Automatically loads last workspace or creates new one
2. **Recent Workspaces Tab**: Quick access to previously used workspaces
3. **Add Directories**: Use "Add Directory" button, auto-saved to workspace
4. **Save Workspace**: Use File → Save As to create `.dedupe` file
5. **Scan Files**: Background scanning with real-time progress
6. **Review Results**: View files and duplicates in Results tab
7. **Switch Workspaces**: Use Recent Workspaces tab or File menu

## Technical Advantages

- **Database-Driven**: All workspace state stored in SQLite
- **Atomic Operations**: Database transactions ensure consistency
- **Scalable**: Handles large file collections efficiently
- **Resumable**: Can reopen and continue previous work
- **Auditable**: Complete history of scans and changes
- **Smart Restoration**: Automatically loads last workspace on startup
- **File Validation**: Removes invalid workspace references automatically
- **Cross-Platform**: Recent workspaces work on Windows, macOS, and Linux

## Recent Workspaces Implementation

### Data Structure
```json
{
  "path": "/full/path/to/workspace.dedupe",
  "name": "workspace.dedupe",
  "last_opened": "2025-09-15T14:30:45.123456"
}
```

### Automatic Cleanup
- Validates workspace file existence on each access
- Removes invalid entries automatically
- Maintains maximum of 10 recent workspaces
- Updates timestamps on workspace access

### User Experience
- **Seamless Restoration**: Last workspace opens automatically
- **Quick Access**: Recent Workspaces tab for easy switching
- **Visual Feedback**: Shows last opened date and workspace name
- **Error Handling**: Graceful handling of missing workspace files