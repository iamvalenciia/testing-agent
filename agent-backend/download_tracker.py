"""
Download Tracker - Monitors the downloads folder for new .xlsm files.

This service watches for hammer file downloads and provides the file path
for the HammerIndexer to process.
"""
import os
import glob
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class DownloadTracker:
    """
    Tracks downloads folder for new .xlsm (hammer) files.
    
    The tracker maintains state about known files and can detect
    when new hammer files appear in the downloads directory.
    """
    
    # Default downloads path - can be overridden
    DEFAULT_DOWNLOADS_PATH = os.path.expanduser("~/Downloads")
    
    def __init__(self, downloads_path: str = None):
        """
        Initialize the download tracker.
        
        Args:
            downloads_path: Path to monitor. Defaults to user's Downloads folder.
        """
        self.downloads_path = downloads_path or self.DEFAULT_DOWNLOADS_PATH
        self.known_files: set = set()
        self._refresh_known_files()
        print(f"📁 DownloadTracker initialized: {self.downloads_path}")
    
    def _refresh_known_files(self):
        """Update the set of known .xlsm files."""
        pattern = os.path.join(self.downloads_path, "*.xlsm")
        self.known_files = set(glob.glob(pattern))
        print(f"   Found {len(self.known_files)} existing .xlsm files")
    
    def get_all_xlsm_files(self) -> List[str]:
        """Get all .xlsm files in downloads folder, sorted by modification time."""
        pattern = os.path.join(self.downloads_path, "*.xlsm")
        files = glob.glob(pattern)
        # Sort by modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        return files
    
    def get_latest_xlsm(self) -> Optional[str]:
        """Get the most recently modified .xlsm file."""
        files = self.get_all_xlsm_files()
        if files:
            latest = files[0]
            mod_time = datetime.fromtimestamp(os.path.getmtime(latest))
            print(f"📄 Latest hammer file: {os.path.basename(latest)}")
            print(f"   Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return latest
        return None
    
    def check_for_new_hammer(self) -> Optional[str]:
        """
        Check if a new .xlsm file has appeared since last check.
        
        Returns:
            Path to new file if found, None otherwise.
        """
        pattern = os.path.join(self.downloads_path, "*.xlsm")
        current_files = set(glob.glob(pattern))
        
        new_files = current_files - self.known_files
        
        if new_files:
            # Get the newest of the new files
            newest = max(new_files, key=os.path.getmtime)
            self.known_files = current_files  # Update known files
            
            file_name = os.path.basename(newest)
            file_size = os.path.getsize(newest) / 1024  # KB
            print(f"📥 NEW HAMMER DETECTED: {file_name} ({file_size:.1f} KB)")
            return newest
        
        return None
    
    def get_hammer_info(self, file_path: str) -> dict:
        """
        Get information about a hammer file.
        
        Args:
            file_path: Path to the .xlsm file
            
        Returns:
            dict with file information
        """
        if not os.path.exists(file_path):
            return {"error": "File not found"}
        
        stat = os.stat(file_path)
        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size_kb": stat.st_size / 1024,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }
    
    def find_hammer_by_client_id(self, client_id: str) -> Optional[str]:
        """
        Find a hammer file that matches a client ID in its name.
        
        Args:
            client_id: Client ID to search for (e.g., "US66254")
            
        Returns:
            Path to matching file or None
        """
        files = self.get_all_xlsm_files()
        
        for file_path in files:
            file_name = os.path.basename(file_path).lower()
            if client_id.lower() in file_name:
                print(f"🔍 Found hammer for {client_id}: {os.path.basename(file_path)}")
                return file_path
        
        print(f"❌ No hammer file found for client: {client_id}")
        return None


# Singleton instance
_tracker: Optional[DownloadTracker] = None

def get_download_tracker() -> DownloadTracker:
    """Get the singleton DownloadTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = DownloadTracker()
    return _tracker


if __name__ == "__main__":
    # Test the tracker
    tracker = DownloadTracker()
    print("\n--- All .xlsm files ---")
    for f in tracker.get_all_xlsm_files():
        info = tracker.get_hammer_info(f)
        print(f"  {info['name']} - {info['size_kb']:.1f} KB - {info['modified']}")
    
    print("\n--- Latest hammer ---")
    latest = tracker.get_latest_xlsm()
    if latest:
        print(f"  {latest}")
