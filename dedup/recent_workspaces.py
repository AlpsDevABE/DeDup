import os
import json
from typing import List, Dict
from PyQt6.QtCore import QSettings

class RecentWorkspaces:
    def __init__(self):
        self.settings = QSettings("DeDup", "DuplicateFileFinder")
        self.max_recent = 10
        
    def add_workspace(self, workspace_path: str, workspace_name: str = None):
        """Add a workspace to the recent list."""
        if not os.path.exists(workspace_path):
            return
            
        recent_list = self.get_recent_workspaces()
        
        # Create workspace entry
        workspace_entry = {
            "path": os.path.abspath(workspace_path),
            "name": workspace_name or os.path.basename(workspace_path),
            "last_opened": self._get_current_timestamp()
        }
        
        # Remove if already exists (to avoid duplicates)
        recent_list = [w for w in recent_list if w["path"] != workspace_entry["path"]]
        
        # Add to front of list
        recent_list.insert(0, workspace_entry)
        
        # Keep only max_recent items
        recent_list = recent_list[:self.max_recent]
        
        # Save to settings
        self.settings.setValue("recent_workspaces", json.dumps(recent_list))
        
    def get_recent_workspaces(self) -> List[Dict]:
        """Get list of recent workspaces, filtering out non-existent ones."""
        recent_json = self.settings.value("recent_workspaces", "[]")
        
        try:
            recent_list = json.loads(recent_json)
        except (json.JSONDecodeError, TypeError):
            recent_list = []
            
        # Filter out non-existent workspaces
        valid_workspaces = []
        for workspace in recent_list:
            if isinstance(workspace, dict) and "path" in workspace:
                if os.path.exists(workspace["path"]):
                    valid_workspaces.append(workspace)
        
        # Save cleaned list back to settings
        if len(valid_workspaces) != len(recent_list):
            self.settings.setValue("recent_workspaces", json.dumps(valid_workspaces))
            
        return valid_workspaces
    
    def get_last_workspace(self) -> str:
        """Get the path of the most recently opened workspace."""
        recent = self.get_recent_workspaces()
        if recent and len(recent) > 0:
            return recent[0]["path"]
        return None
        
    def remove_workspace(self, workspace_path: str):
        """Remove a workspace from the recent list."""
        recent_list = self.get_recent_workspaces()
        recent_list = [w for w in recent_list if w["path"] != workspace_path]
        self.settings.setValue("recent_workspaces", json.dumps(recent_list))
        
    def clear_recent_workspaces(self):
        """Clear all recent workspaces."""
        self.settings.setValue("recent_workspaces", "[]")
        
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as string."""
        from datetime import datetime
        return datetime.now().isoformat()