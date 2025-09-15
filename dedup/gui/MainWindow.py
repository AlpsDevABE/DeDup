from PyQt6.QtWidgets import (QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QListWidget, QProgressBar, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox,
                             QMenuBar, QMenu, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont
from dedup.workspace import Workspace
from dedup.gui.scan_thread import ScanThread
from dedup.recent_workspaces import RecentWorkspaces
import os
import tempfile
from datetime import datetime

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeDup - Duplicate File Finder")
        self.setGeometry(100, 100, 1200, 800)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.directories = []
        self.workspace = None
        self.scan_thread = None
        self.current_workspace_path = None
        self.recent_workspaces = RecentWorkspaces()
        self.init_menu()
        self.init_tabs()
        self.load_last_workspace()  # Try to load last workspace, or create new one
        
        # Initialize logging with welcome message
        self.log_event("SYSTEM", "DeDup application started")
        import multiprocessing
        self.log_event("SYSTEM", f"Detected {multiprocessing.cpu_count()} CPU cores available")

    def init_tabs(self):
        self.tabs.addTab(self.create_logging_tab(), "Logging")
        self.tabs.addTab(self.create_recent_workspaces_tab(), "Recent Workspaces")
        self.tabs.addTab(self.create_workspace_tab(), "Workspace")
        self.tabs.addTab(self.create_results_tab(), "Results")

    def create_workspace_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Directory selection section
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Directories to scan:"))
        self.add_dir_btn = QPushButton("Add Directory")
        self.add_dir_btn.clicked.connect(self.add_directory)
        dir_layout.addWidget(self.add_dir_btn)
        layout.addLayout(dir_layout)
        
        # Directory list
        self.dir_list = QListWidget()
        layout.addWidget(self.dir_list)
        
        # Scan controls
        controls_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Start Scan")
        self.scan_btn.clicked.connect(self.start_scan)
        controls_layout.addWidget(self.scan_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.cancel_btn.setEnabled(False)
        controls_layout.addWidget(self.cancel_btn)
        
        self.progress_bar = QProgressBar()
        controls_layout.addWidget(self.progress_bar)
        layout.addLayout(controls_layout)
        
        # Resume scan option
        resume_layout = QHBoxLayout()
        from PyQt6.QtWidgets import QCheckBox
        self.skip_hashed_checkbox = QCheckBox("Don't rescan hashed files (resume from where left off)")
        self.skip_hashed_checkbox.setToolTip("Skip files that already have hashes in the database")
        resume_layout.addWidget(self.skip_hashed_checkbox)
        layout.addLayout(resume_layout)
        
        # Progress information
        progress_info_layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready to scan")
        progress_info_layout.addWidget(self.status_label)
        
        self.current_folder_label = QLabel("")
        progress_info_layout.addWidget(self.current_folder_label)
        
        self.file_count_label = QLabel("")
        progress_info_layout.addWidget(self.file_count_label)
        
        self.hash_progress_label = QLabel("")
        progress_info_layout.addWidget(self.hash_progress_label)
        
        layout.addLayout(progress_info_layout)
        
        # Core activity section
        core_activity_layout = QVBoxLayout()
        core_activity_layout.addWidget(QLabel("Core Activity:"))
        
        self.core_activity_table = QTableWidget()
        self.core_activity_table.setColumnCount(3)
        self.core_activity_table.setHorizontalHeaderLabels(['Core', 'Status', 'Current File'])
        self.core_activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.core_activity_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.core_activity_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.core_activity_table.setMaximumHeight(200)
        core_activity_layout.addWidget(self.core_activity_table)
        
        layout.addLayout(core_activity_layout)
        
        tab.setLayout(layout)
        return tab
        
    def init_menu(self):
        """Initialize the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        new_action = QAction('New Workspace', self)
        new_action.triggered.connect(self.new_workspace)
        file_menu.addAction(new_action)
        
        open_action = QAction('Open Workspace...', self)
        open_action.triggered.connect(self.open_workspace)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction('Save Workspace', self)
        save_action.triggered.connect(self.save_workspace)
        file_menu.addAction(save_action)
        
        save_as_action = QAction('Save Workspace As...', self)
        save_as_action.triggered.connect(self.save_workspace_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def create_logging_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header with controls
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("System Log"))
        
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(clear_btn)
        
        auto_scroll_btn = QPushButton("Auto Scroll: ON")
        auto_scroll_btn.setCheckable(True)
        auto_scroll_btn.setChecked(True)
        auto_scroll_btn.clicked.connect(lambda checked: self.toggle_auto_scroll(auto_scroll_btn, checked))
        header_layout.addWidget(auto_scroll_btn)
        
        layout.addLayout(header_layout)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Courier", 9))  # Monospace font
        # Note: setMaximumBlockCount not available in QTextEdit, will manage manually
        layout.addWidget(self.log_display)
        
        # Status
        self.log_status = QLabel("Ready")
        self.log_status.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.log_status)
        
        tab.setLayout(layout)
        self.auto_scroll_enabled = True
        return tab

    def create_recent_workspaces_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Recent Workspaces"))
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_recent_workspaces)
        header_layout.addWidget(refresh_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_recent_workspaces)
        header_layout.addWidget(clear_btn)
        
        layout.addLayout(header_layout)
        
        # Recent workspaces table
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(['Workspace Name', 'Path', 'Last Opened', 'Actions'])
        self.recent_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.recent_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.cellDoubleClicked.connect(self.open_recent_workspace)
        layout.addWidget(self.recent_table)
        
        # Instructions
        instructions = QLabel("Double-click a workspace to open it, or use the Open button.")
        instructions.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(instructions)
        
        tab.setLayout(layout)
        return tab

    def create_results_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(['File Path', 'Size', 'Modified', 'xxHash', 'Status'])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table)
        
        tab.setLayout(layout)
        return tab
        
    def add_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory and directory not in self.directories:
            self.directories.append(directory)
            self.dir_list.addItem(directory)
            
            # Auto-save directories if we have a workspace
            if self.workspace:
                self.workspace.save_directories(self.directories)
                self.status_label.setText(f"Added directory: {os.path.basename(directory)}")
                self.log_event("WORKSPACE", f"Added directory: {directory}")
            
    def start_scan(self):
        if not self.directories:
            self.status_label.setText("No directories selected")
            return
            
        # Ensure we have a workspace
        if not self.workspace:
            QMessageBox.warning(self, "No Workspace", "Please create or open a workspace first.")
            return
            
        # Clear previous results
        self.workspace.clear_files()
        
        self.scan_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Start scanning in background thread
        workspace_path = self.current_workspace_path if self.current_workspace_path else self.workspace.db_path
        skip_hashed = self.skip_hashed_checkbox.isChecked()
        self.scan_thread = ScanThread(self.directories, workspace_path, skip_hashed)
        
        # Connect logging callback
        self.scan_thread.log_callback = self.log_event
        
        self.scan_thread.progress_updated.connect(self.update_progress)
        self.scan_thread.folder_changed.connect(self.update_current_folder)
        self.scan_thread.file_counted.connect(self.update_file_count)
        self.scan_thread.status_updated.connect(self.update_status)
        self.scan_thread.core_activity_updated.connect(self.update_core_activity)
        self.scan_thread.hash_progress_updated.connect(self.update_hash_progress)
        self.scan_thread.scan_completed.connect(self.scan_finished)
        self.scan_thread.finished.connect(self.reset_scan_ui)
        
        # Log the scan start
        self.log_event("SYSTEM", f"Starting new scan with workspace: {os.path.basename(workspace_path)}")
        
        # Reset hash progress tracking
        if hasattr(self, 'hash_start_time'):
            delattr(self, 'hash_start_time')
        self.hash_progress_label.setText("")
        
        self.scan_thread.start()
        
    def cancel_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.status_label.setText("Cancelling scan...")
            self.cancel_btn.setEnabled(False)
            self.scan_thread.cancel()
            
    def update_progress(self, current, total):
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            
    def update_current_folder(self, folder):
        self.current_folder_label.setText(f"Current folder: {folder}")
        
    def update_file_count(self, count):
        self.file_count_label.setText(f"Files found: {count}")
    
    def update_hash_progress(self, hashed, total):
        """Update the hashing progress display with time estimation."""
        if total > 0:
            percentage = (hashed / total) * 100
            remaining = total - hashed
            
            # Calculate time estimation
            if not hasattr(self, 'hash_start_time'):
                import time
                self.hash_start_time = time.time()
                
            if hashed > 0:
                elapsed_time = time.time() - self.hash_start_time
                rate = hashed / elapsed_time  # files per second
                if rate > 0:
                    eta_seconds = remaining / rate
                    if eta_seconds < 60:
                        eta_str = f"{eta_seconds:.0f}s"
                    elif eta_seconds < 3600:
                        eta_str = f"{eta_seconds/60:.0f}m"
                    else:
                        eta_str = f"{eta_seconds/3600:.1f}h"
                    
                    self.hash_progress_label.setText(
                        f"Hashing: {hashed:,} / {total:,} ({percentage:.1f}%) - {remaining:,} remaining - ETA: {eta_str}"
                    )
                else:
                    self.hash_progress_label.setText(f"Hashing: {hashed:,} / {total:,} ({percentage:.1f}%) - {remaining:,} remaining")
            else:
                self.hash_progress_label.setText(f"Hashing: {hashed:,} / {total:,} ({percentage:.1f}%) - {remaining:,} remaining")
        
    def update_status(self, status):
        self.status_label.setText(status)
        
    def update_core_activity(self, core_data):
        """Update the core activity table with current core status."""
        self.core_activity_table.setRowCount(len(core_data))
        
        for row, (core_id, status, current_file) in enumerate(core_data):
            self.core_activity_table.setItem(row, 0, QTableWidgetItem(f"Core {core_id}"))
            self.core_activity_table.setItem(row, 1, QTableWidgetItem(status))
            
            # Show just the filename for current file
            if current_file:
                filename = os.path.basename(current_file)
                self.core_activity_table.setItem(row, 2, QTableWidgetItem(filename))
            else:
                self.core_activity_table.setItem(row, 2, QTableWidgetItem(""))
        
        # Color coding for status
        from PyQt6.QtGui import QColor
        for row in range(len(core_data)):
            status_item = self.core_activity_table.item(row, 1)
            if status_item:
                status = status_item.text()
                if "Hashing" in status:
                    status_item.setBackground(QColor(144, 238, 144))  # Light green
                elif status == "Idle":
                    status_item.setBackground(QColor(211, 211, 211))  # Light gray
                elif status == "Waiting" or status == "Scanning":
                    status_item.setBackground(QColor(255, 255, 0))    # Yellow
                elif status == "Completed":
                    status_item.setBackground(QColor(173, 216, 230))  # Light blue
        
    def scan_finished(self, files):
        # Update workspace metadata
        if self.workspace:
            self.workspace.update_workspace_metadata()
            # Auto-save workspace if it has a path
            if self.current_workspace_path:
                self.workspace.save_directories(self.directories)
        
        self.update_results_table()
        
        # Show completion message with stats
        stats = self.workspace.get_workspace_stats() if self.workspace else {}
        total_files = stats.get('total_files', len(files))
        duplicate_groups = stats.get('duplicate_groups', 0)
        
        message = f"Scan completed successfully!\n"
        message += f"Processed {total_files} files.\n"
        if duplicate_groups > 0:
            message += f"Found {duplicate_groups} potential duplicate groups."
        
        QMessageBox.information(self, "Scan Complete", message)
        
    def update_results_table(self):
        files = self.workspace.get_files()
        self.results_table.setRowCount(len(files))
        
        for row, file_data in enumerate(files):
            self.results_table.setItem(row, 0, QTableWidgetItem(file_data['path']))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(file_data['size'])))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(file_data['modified'])))
            self.results_table.setItem(row, 3, QTableWidgetItem(file_data['xxhash'] or ''))
            self.results_table.setItem(row, 4, QTableWidgetItem(file_data['status']))
        
    def reset_scan_ui(self):
        self.scan_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if hasattr(self, 'scan_thread') and self.scan_thread:
            if not self.scan_thread.cancelled:
                self.progress_bar.setValue(100)
            else:
                self.progress_bar.setValue(0)
                self.status_label.setText("Scan cancelled")
                self.current_folder_label.setText("")
                self.file_count_label.setText("")
                self.hash_progress_label.setText("")
        
        # Clear core activity
        self.core_activity_table.setRowCount(0)
    
    def new_workspace(self):
        """Create a new workspace."""
        if self.workspace:
            self.workspace.close()
        
        # Create a temporary workspace for new sessions
        import tempfile
        temp_path = os.path.join(tempfile.gettempdir(), "dedup_temp_workspace.dedupe")
        self.workspace = Workspace.create_workspace(temp_path)
        self.current_workspace_path = temp_path
        
        self.directories = []
        self.dir_list.clear()
        self.results_table.setRowCount(0)
        self.setWindowTitle("DeDup - Duplicate File Finder - New Workspace")
        self.status_label.setText("New workspace created. Add directories to scan.")
        
        self.log_event("WORKSPACE", f"Created new temporary workspace: {os.path.basename(temp_path)}")
        
    def open_workspace(self):
        """Open an existing workspace."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Workspace", "", "DeDup Workspace Files (*.dedupe)"
        )
        
        if file_path:
            try:
                if self.workspace:
                    self.workspace.close()
                
                self.workspace = Workspace.load_workspace(file_path)
                self.current_workspace_path = file_path
                
                # Load directories from workspace
                self.directories = self.workspace.load_directories()
                self.dir_list.clear()
                for directory in self.directories:
                    self.dir_list.addItem(directory)
                
                # Add to recent workspaces
                workspace_name = os.path.basename(file_path)
                self.recent_workspaces.add_workspace(file_path, workspace_name)
                
                # Update UI
                self.setWindowTitle(f"DeDup - {workspace_name}")
                self.update_results_table()
                self.status_label.setText(f"Workspace loaded: {workspace_name}")
                
                self.log_event("WORKSPACE", f"Opened workspace: {workspace_name} ({len(self.directories)} directories)")
                self.refresh_recent_workspaces()
                
            except Exception as e:
                self.log_event("ERROR", f"Failed to open workspace: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to open workspace:\n{str(e)}")
    
    def save_workspace(self):
        """Save the current workspace."""
        if not self.current_workspace_path:
            self.save_workspace_as()
        else:
            self._save_workspace_to_path(self.current_workspace_path)
    
    def save_workspace_as(self):
        """Save the workspace with a new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Workspace As", "", "DeDup Workspace Files (*.dedupe)"
        )
        
        if file_path:
            if not file_path.endswith('.dedupe'):
                file_path += '.dedupe'
            self._save_workspace_to_path(file_path)
    
    def _save_workspace_to_path(self, file_path):
        """Internal method to save workspace to a specific path."""
        try:
            if not self.workspace:
                self.workspace = Workspace.create_workspace(file_path)
            else:
                # If we're saving to a new location, create a new workspace
                if file_path != self.current_workspace_path:
                    old_files = self.workspace.get_files()
                    old_directories = self.directories.copy()
                    self.workspace.close()
                    
                    self.workspace = Workspace.create_workspace(file_path)
                    
                    # Copy data to new workspace
                    for file_data in old_files:
                        self.workspace.add_file(
                            file_data['path'], file_data['size'], file_data['modified'],
                            file_data['xxhash'], file_data['md5'], file_data['sha1'], file_data['status']
                        )
                    self.directories = old_directories
            
            # Save directories
            self.workspace.save_directories(self.directories)
            
            self.current_workspace_path = file_path
            workspace_name = os.path.basename(file_path)
            
            # Add to recent workspaces
            self.recent_workspaces.add_workspace(file_path, workspace_name)
            
            self.setWindowTitle(f"DeDup - {workspace_name}")
            self.status_label.setText(f"Workspace saved: {workspace_name}")
            self.refresh_recent_workspaces()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save workspace:\n{str(e)}")
    
    def load_last_workspace(self):
        """Load the most recently used workspace, or create new one."""
        last_workspace_path = self.recent_workspaces.get_last_workspace()
        
        if last_workspace_path and os.path.exists(last_workspace_path):
            try:
                self.workspace = Workspace.load_workspace(last_workspace_path)
                self.current_workspace_path = last_workspace_path
                
                # Load directories from workspace
                self.directories = self.workspace.load_directories()
                self.dir_list.clear()
                for directory in self.directories:
                    self.dir_list.addItem(directory)
                
                # Update UI
                self.setWindowTitle(f"DeDup - {os.path.basename(last_workspace_path)}")
                self.update_results_table()
                self.status_label.setText(f"Loaded workspace: {os.path.basename(last_workspace_path)}")
                self.refresh_recent_workspaces()
                return
                
            except Exception as e:
                QMessageBox.warning(self, "Error Loading Workspace", 
                                  f"Could not load last workspace:\n{str(e)}\n\nStarting with new workspace.")
        
        # Fall back to new workspace
        self.new_workspace()
    
    def refresh_recent_workspaces(self):
        """Refresh the recent workspaces table."""
        recent_workspaces = self.recent_workspaces.get_recent_workspaces()
        self.recent_table.setRowCount(len(recent_workspaces))
        
        for row, workspace in enumerate(recent_workspaces):
            # Workspace name
            self.recent_table.setItem(row, 0, QTableWidgetItem(workspace.get('name', 'Unknown')))
            
            # Path
            self.recent_table.setItem(row, 1, QTableWidgetItem(workspace.get('path', '')))
            
            # Last opened (formatted)
            last_opened = workspace.get('last_opened', '')
            if last_opened:
                try:
                    dt = datetime.fromisoformat(last_opened)
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = last_opened
            else:
                formatted_date = 'Unknown'
            self.recent_table.setItem(row, 2, QTableWidgetItem(formatted_date))
            
            # Open button
            open_btn = QPushButton("Open")
            open_btn.clicked.connect(lambda checked, path=workspace.get('path'): self.open_workspace_by_path(path))
            self.recent_table.setCellWidget(row, 3, open_btn)
    
    def open_recent_workspace(self, row, column):
        """Open workspace when double-clicked."""
        if row < self.recent_table.rowCount():
            path_item = self.recent_table.item(row, 1)
            if path_item:
                self.open_workspace_by_path(path_item.text())
    
    def open_workspace_by_path(self, workspace_path):
        """Open a specific workspace by path."""
        if not workspace_path or not os.path.exists(workspace_path):
            QMessageBox.warning(self, "File Not Found", 
                              f"Workspace file not found:\n{workspace_path}")
            self.recent_workspaces.remove_workspace(workspace_path)
            self.refresh_recent_workspaces()
            return
            
        try:
            if self.workspace:
                self.workspace.close()
            
            self.workspace = Workspace.load_workspace(workspace_path)
            self.current_workspace_path = workspace_path
            
            # Load directories from workspace
            self.directories = self.workspace.load_directories()
            self.dir_list.clear()
            for directory in self.directories:
                self.dir_list.addItem(directory)
            
            # Update recent workspaces
            workspace_name = os.path.basename(workspace_path)
            self.recent_workspaces.add_workspace(workspace_path, workspace_name)
            
            # Update UI
            self.setWindowTitle(f"DeDup - {workspace_name}")
            self.update_results_table()
            self.status_label.setText(f"Workspace loaded: {workspace_name}")
            self.refresh_recent_workspaces()
            
            # Switch to workspace tab
            self.tabs.setCurrentIndex(1)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open workspace:\n{str(e)}")
    
    def clear_recent_workspaces(self):
        """Clear all recent workspaces after confirmation."""
        reply = QMessageBox.question(self, "Clear Recent Workspaces", 
                                   "Are you sure you want to clear all recent workspaces?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.recent_workspaces.clear_recent_workspaces()
            self.refresh_recent_workspaces()
    
    def log_event(self, event_type, message):
        """Add an event to the logging tab with timestamp."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
        
        # Color coding for different event types
        color_map = {
            "SYSTEM": "blue",
            "SCAN": "green", 
            "CORE": "orange",
            "ERROR": "red",
            "WORKSPACE": "purple",
            "PROGRESS": "gray"
        }
        
        color = color_map.get(event_type, "black")
        log_line = f'<span style="color: {color};">[{timestamp}] {event_type}: {message}</span>'
        
        self.log_display.append(log_line)
        
        if self.auto_scroll_enabled:
            cursor = self.log_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_display.setTextCursor(cursor)
        
        # Update status
        self.log_status.setText(f"Last: {event_type} at {timestamp}")
    
    def clear_log(self):
        """Clear the log display."""
        self.log_display.clear()
        self.log_status.setText("Log cleared")
        self.log_event("SYSTEM", "Log cleared by user")
    
    def toggle_auto_scroll(self, button, checked):
        """Toggle auto-scroll for log display."""
        self.auto_scroll_enabled = checked
        button.setText(f"Auto Scroll: {'ON' if checked else 'OFF'}")
        self.log_event("SYSTEM", f"Auto-scroll {'enabled' if checked else 'disabled'}")
