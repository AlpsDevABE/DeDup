import os
import sqlite3
import json
from typing import List, Dict

class Workspace:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                size INTEGER,
                modified INTEGER,
                xxhash TEXT,
                md5 TEXT,
                sha1 TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS workspace_config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS workspace_metadata (
                id INTEGER PRIMARY KEY,
                workspace_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scan TIMESTAMP,
                total_files INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                duplicate_groups INTEGER DEFAULT 0
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS workspace_directories (
                id INTEGER PRIMARY KEY,
                directory_path TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scanned TIMESTAMP
            )
        ''')
        # Create indexes for better performance
        cur.execute('CREATE INDEX IF NOT EXISTS idx_files_xxhash ON files(xxhash)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_files_md5 ON files(md5)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_files_size ON files(size)')
        self.conn.commit()

    def add_file(self, path: str, size: int, modified: int, xxhash: str, md5: str = None, sha1: str = None, status: str = "present"):
        cur = self.conn.cursor()
        # Update or insert file
        cur.execute('''
            INSERT OR REPLACE INTO files (path, size, modified, xxhash, md5, sha1, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (path, size, modified, xxhash, md5, sha1, status))
        self.conn.commit()

    def get_files(self) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM files')
        rows = cur.fetchall()
        return [dict(zip([column[0] for column in cur.description], row)) for row in rows]

    def save_directories(self, directories: List[str]):
        """Save the list of directories to the workspace."""
        cur = self.conn.cursor()
        
        # Clear existing directories
        cur.execute('DELETE FROM workspace_directories')
        
        # Insert new directories
        for directory in directories:
            cur.execute('''
                INSERT INTO workspace_directories (directory_path)
                VALUES (?)
            ''', (directory,))
        
        # Also keep the old method for backward compatibility
        cur.execute('''
            INSERT OR REPLACE INTO workspace_config (key, value)
            VALUES (?, ?)
        ''', ('directories', json.dumps(directories)))
        
        self.conn.commit()

    def load_directories(self) -> List[str]:
        """Load the list of directories from the workspace."""
        cur = self.conn.cursor()
        
        # Try new method first
        cur.execute('SELECT directory_path FROM workspace_directories ORDER BY added_at')
        rows = cur.fetchall()
        if rows:
            return [row[0] for row in rows]
        
        # Fall back to old method for backward compatibility
        cur.execute('SELECT value FROM workspace_config WHERE key = ?', ('directories',))
        row = cur.fetchone()
        if row:
            return json.loads(row[0])
        return []
    
    def update_workspace_metadata(self, name: str = None):
        """Update workspace metadata with current stats."""
        cur = self.conn.cursor()
        
        # Get current stats
        cur.execute('SELECT COUNT(*), SUM(size) FROM files')
        total_files, total_size = cur.fetchone()
        total_size = total_size or 0
        
        # Count duplicate groups (files with same xxhash that appear more than once)
        cur.execute('''
            SELECT COUNT(*) FROM (
                SELECT xxhash FROM files 
                WHERE xxhash IS NOT NULL 
                GROUP BY xxhash 
                HAVING COUNT(*) > 1
            )
        ''')
        duplicate_groups = cur.fetchone()[0]
        
        # Update or insert metadata
        cur.execute('''
            INSERT OR REPLACE INTO workspace_metadata 
            (id, workspace_name, last_scan, total_files, total_size, duplicate_groups)
            VALUES (1, ?, CURRENT_TIMESTAMP, ?, ?, ?)
        ''', (name or os.path.basename(self.db_path), total_files, total_size, duplicate_groups))
        
        self.conn.commit()
    
    def get_workspace_stats(self) -> Dict:
        """Get workspace statistics."""
        cur = self.conn.cursor()
        cur.execute('SELECT * FROM workspace_metadata WHERE id = 1')
        row = cur.fetchone()
        
        if row:
            columns = [description[0] for description in cur.description]
            return dict(zip(columns, row))
        
        return {
            'workspace_name': os.path.basename(self.db_path),
            'total_files': 0,
            'total_size': 0,
            'duplicate_groups': 0,
            'created_at': None,
            'last_scan': None
        }

    def clear_files(self):
        """Clear all files from the workspace."""
        cur = self.conn.cursor()
        cur.execute('DELETE FROM files')
        self.conn.commit()

    @staticmethod
    def create_workspace(workspace_path: str) -> 'Workspace':
        """Create a new workspace file."""
        return Workspace(workspace_path)

    @staticmethod
    def load_workspace(workspace_path: str) -> 'Workspace':
        """Load an existing workspace file."""
        if not os.path.exists(workspace_path):
            raise FileNotFoundError(f"Workspace file not found: {workspace_path}")
        return Workspace(workspace_path)

    def close(self):
        self.conn.close()
