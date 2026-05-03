import subprocess
import threading
import time
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime


logger = logging.getLogger(__name__)


@dataclass
class APCData:
    """Data class to hold parsed APC monitor information."""
    raw_data: Dict[str, str]
    timestamp: datetime
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the parsed APC data."""
        return self.raw_data.get(key, default)
    
    def __repr__(self) -> str:
        return f"APCData(timestamp={self.timestamp}, keys={len(self.raw_data)})"


class APCMonitor:
    """Monitor and parse APC UPS status using the apcaccess command."""
    
    def __init__(self, interval: int = 30, command: str = "apcaccess"):
        """
        Initialize the APC Monitor.
        
        Args:
            interval: Interval in seconds between command executions (default: 30)
            command: The command to run (default: "apcaccess")
        """
        self.interval = interval
        self.command = command
        self._data: Optional[APCData] = None
        self._data_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("APCMonitor is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"APCMonitor started with {self.interval}s interval")
    
    def stop(self) -> None:
        """Stop the background monitoring thread."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("APCMonitor stopped")
    
    def _monitor_loop(self) -> None:
        """Background thread loop that runs the command periodically."""
        # Run once immediately
        self._update()
        
        while self._running:
            try:
                time.sleep(self.interval)
                if self._running:
                    self._update()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
    
    def _update(self) -> None:
        """Run the apcaccess command and update the data."""
        try:
            output = subprocess.run(
                [self.command],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if output.returncode != 0:
                logger.error(f"apcaccess command failed: {output.stderr}")
                with self._data_lock:
                    self._data = None
            else:
                parsed_data = self._parse_output(output.stdout)
                
                with self._data_lock:
                    self._data = APCData(
                        raw_data=parsed_data,
                        timestamp=datetime.now()
                    )
                    logger.debug(f"Updated APC data: {len(parsed_data)} fields")
            
        except subprocess.TimeoutExpired:
            logger.error("apcaccess command timed out")
            with self._data_lock:
                self._data = None
        except FileNotFoundError:
            logger.error(f"Command not found: {self.command}")
            with self._data_lock:
                self._data = None
        except Exception as e:
            logger.error(f"Error updating APC data: {e}")
            with self._data_lock:
                self._data = None
    
    @staticmethod
    def _parse_output(output: str) -> Dict[str, str]:
        """
        Parse the apcaccess command output.
        
        Args:
            output: Raw output from apcaccess command
            
        Returns:
            Dictionary with parsed key-value pairs
        """
        data = {}
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Skip the END APC line as it's just a marker
            if key == "END APC":
                continue
            
            data[key] = value
        
        return data
    
    def get_data(self) -> Optional[APCData]:
        """
        Get the latest parsed APC data.
        
        Returns:
            APCData object with the latest data, or None if no data available
        """
        with self._data_lock:
            return self._data
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Convenience method to get a specific value.
        
        Args:
            key: The APC field name
            default: Default value if key not found
            
        Returns:
            The value from the latest APC data
        """
        data = self.get_data()
        if data is None:
            return default
        return data.get(key, default)
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Using context manager
    with APCMonitor(interval=10) as monitor:
        while True:
            time.sleep(1)
            data = monitor.get_data()
            if data:
                print(f"\n=== Update at {data.timestamp} ===")
                print(f"Status: {monitor.get('STATUS')}")
                print(f"Load: {monitor.get('LOADPCT')}")
                print(f"Battery Charge: {monitor.get('BCHARGE')}")
                print(f"Time Left: {monitor.get('TIMELEFT')}")
            
    print("\nMonitoring stopped")
