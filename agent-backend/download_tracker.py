"""
Download Tracker - Monitors the downloads folder for new .xlsm files.

This service watches for hammer file downloads and provides the file path
for the HammerIndexer to process.

ENHANCED: Now includes automatic file watching with indexing triggers.
Cloud-Ready: Supports S3 event integration for cloud deployments.
"""
import os
import glob
import asyncio
import threading
from datetime import datetime
from typing import Optional, List, Callable, Dict, Any
from pathlib import Path


class DownloadTracker:
    """
    Tracks downloads folder for new .xlsm (hammer) files.
    
    The tracker maintains state about known files and can detect
    when new hammer files appear in the downloads directory.
    
    Enhanced Features:
    - Automatic file watching with callbacks
    - Hammer file detection (by name pattern)
    - Cloud-ready S3 event integration stubs
    """
    
    # Default downloads path - can be overridden
    DEFAULT_DOWNLOADS_PATH = os.path.expanduser("~/Downloads")
    
    # Polling interval for file watcher (seconds)
    POLL_INTERVAL = 2.0
    
    def __init__(self, downloads_path: str = None):
        """
        Initialize the download tracker.
        
        Args:
            downloads_path: Path to monitor. Defaults to user's Downloads folder.
        """
        self.downloads_path = downloads_path or self.DEFAULT_DOWNLOADS_PATH
        self.known_files: set = set()
        self._refresh_known_files()
        
        # File watcher state
        self._watching = False
        self._watch_thread: Optional[threading.Thread] = None
        self._on_new_hammer_callbacks: List[Callable[[str], None]] = []
        self._async_callbacks: List[Callable[[str], Any]] = []
        
        # Environment configuration
        self.is_cloud = os.getenv("DEPLOYMENT_ENV", "local") != "local"
        
        print(f"[TRACKER] DownloadTracker initialized: {self.downloads_path}")
    
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
            print(f"[LATEST] Latest hammer file: {os.path.basename(latest)}")
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
            print(f"[NEW] NEW HAMMER DETECTED: {file_name} ({file_size:.1f} KB)")
            return newest
        
        return None
    
    def is_hammer_file(self, file_path: str) -> bool:
        """
        Check if a file looks like a Hammer configuration file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be a Hammer file
        """
        filename = os.path.basename(file_path).lower()
        
        # Must be an Excel macro file
        if not filename.endswith(".xlsm"):
            return False
        
        # Check for hammer-related patterns
        hammer_patterns = [
            "hammer",
            "config",
            "configuration",
            "setup",
            "client",  # Often hammer files include client ID
        ]
        
        return any(pattern in filename for pattern in hammer_patterns)
    
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
            "is_hammer": self.is_hammer_file(file_path),
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
                print(f"[FOUND] Found hammer for {client_id}: {os.path.basename(file_path)}")
                return file_path
        
        print(f"[NOT FOUND] No hammer file found for client: {client_id}")
        return None
    
    # =========================================================================
    # FILE WATCHER - Automatic Detection and Indexing Trigger
    # =========================================================================
    
    def on_new_hammer(self, callback: Callable[[str], None]):
        """
        Register a callback for when a new hammer file is detected.
        
        Args:
            callback: Function that takes the file path as argument
        """
        self._on_new_hammer_callbacks.append(callback)
        print(f"[WATCHER] Registered callback: {callback.__name__}")
    
    def on_new_hammer_async(self, callback: Callable[[str], Any]):
        """
        Register an async callback for when a new hammer file is detected.
        
        Args:
            callback: Async function that takes the file path as argument
        """
        self._async_callbacks.append(callback)
        print(f"[WATCHER] Registered async callback: {callback.__name__}")
    
    def start_watching(self):
        """
        Start watching the downloads folder for new hammer files.
        
        Uses polling-based watching for simplicity and cross-platform support.
        In cloud deployment, this would switch to S3 event triggers.
        """
        if self._watching:
            print("[WATCHER] Already watching")
            return
        
        if self.is_cloud:
            print("[WATCHER] Cloud mode - file watching disabled (use S3 events)")
            return
        
        self._watching = True
        self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watch_thread.start()
        print(f"[WATCHER] Started watching: {self.downloads_path}")
    
    def stop_watching(self):
        """Stop the file watcher."""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)
            self._watch_thread = None
        print("[WATCHER] Stopped watching")
    
    def _watch_loop(self):
        """
        Main file watching loop.
        
        Polls for new files at regular intervals and triggers callbacks
        when new hammer files are detected.
        """
        print("[WATCHER] Watch loop started")
        
        while self._watching:
            try:
                new_file = self.check_for_new_hammer()
                
                if new_file and self.is_hammer_file(new_file):
                    print(f"[WATCHER] Hammer file detected: {os.path.basename(new_file)}")
                    self._trigger_callbacks(new_file)
                
            except Exception as e:
                print(f"[WATCHER] Error in watch loop: {e}")
            
            # Sleep for polling interval
            import time
            time.sleep(self.POLL_INTERVAL)
        
        print("[WATCHER] Watch loop ended")
    
    def _trigger_callbacks(self, file_path: str):
        """Trigger all registered callbacks for a new hammer file."""
        # Sync callbacks
        for callback in self._on_new_hammer_callbacks:
            try:
                callback(file_path)
            except Exception as e:
                print(f"[WATCHER] Callback error: {e}")
        
        # Async callbacks - run in event loop
        for async_callback in self._async_callbacks:
            try:
                # Try to get running event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(async_callback(file_path))
                else:
                    loop.run_until_complete(async_callback(file_path))
            except RuntimeError:
                # No event loop - create new one
                asyncio.run(async_callback(file_path))
            except Exception as e:
                print(f"[WATCHER] Async callback error: {e}")
    
    # =========================================================================
    # CLOUD-READY: S3 Event Integration
    # =========================================================================
    
    def handle_s3_event(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Handle S3 event notification for new hammer files.
        
        This method is designed for AWS Lambda integration.
        
        Args:
            event: S3 event notification (from Lambda trigger)
            
        Returns:
            S3 key of the hammer file if valid, None otherwise
        """
        try:
            # Parse S3 event
            records = event.get("Records", [])
            
            for record in records:
                s3_info = record.get("s3", {})
                bucket = s3_info.get("bucket", {}).get("name")
                key = s3_info.get("object", {}).get("key")
                
                if not bucket or not key:
                    continue
                
                # Check if it's a hammer file
                filename = key.split("/")[-1]
                if self.is_hammer_file(filename):
                    print(f"[S3] Hammer file detected: s3://{bucket}/{key}")
                    return key
            
            return None
            
        except Exception as e:
            print(f"[S3] Error parsing S3 event: {e}")
            return None


# Singleton instance
_tracker: Optional[DownloadTracker] = None

def get_download_tracker() -> DownloadTracker:
    """Get the singleton DownloadTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = DownloadTracker()
    return _tracker


# =========================================================================
# AUTO-INDEXING INTEGRATION
# =========================================================================

def setup_auto_indexing():
    """
    Set up automatic hammer indexing when new files are detected.
    
    Call this at application startup to enable auto-indexing.
    """
    from hammer_indexer import get_hammer_indexer
    
    tracker = get_download_tracker()
    
    def on_hammer_detected(file_path: str):
        """Callback when a hammer file is detected."""
        print(f"\n{'='*60}")
        print("[AUTO-INDEX] Hammer file detected - starting indexing workflow")
        print(f"{'='*60}")
        
        try:
            indexer = get_hammer_indexer()
            result = indexer.index_hammer(file_path, clear_existing=True)
            
            if result.get("success"):
                print(f"[AUTO-INDEX] [SUCCESS] Indexed {result.get('records_count')} records")
            else:
                print(f"[AUTO-INDEX] [FAILED] {result.get('error')}")
                
        except Exception as e:
            print(f"[AUTO-INDEX] [ERROR] {e}")
    
    tracker.on_new_hammer(on_hammer_detected)
    tracker.start_watching()
    
    print("[AUTO-INDEX] Automatic hammer indexing enabled")


if __name__ == "__main__":
    # Test the tracker
    tracker = DownloadTracker()
    print("\n--- All .xlsm files ---")
    for f in tracker.get_all_xlsm_files():
        info = tracker.get_hammer_info(f)
        print(f"  {info['name']} - {info['size_kb']:.1f} KB - {info['modified']} - Hammer: {info['is_hammer']}")
    
    print("\n--- Latest hammer ---")
    latest = tracker.get_latest_xlsm()
    if latest:
        print(f"  {latest}")
    
    print("\n--- Testing auto-indexing (30 seconds) ---")
    print("Drop a hammer .xlsm file in Downloads to test...")
    
    def test_callback(path):
        print(f"[TEST] Would index: {path}")
    
    tracker.on_new_hammer(test_callback)
    tracker.start_watching()
    
    import time
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    
    tracker.stop_watching()
