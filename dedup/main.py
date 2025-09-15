"""
DeDup: Python Duplicate File Finder
Entry point for the application.
"""
import sys
import os

# Add the parent directory to the Python path so we can import dedup modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from dedup.gui import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
