
import time
import threading
import psutil
import os
import logging

class ResourceMonitor:
    def __init__(self, interval=0.5):
        self.interval = interval
        self.running = False
        self.peak_ram_mb = 0.0
        self.peak_cpu_percent = 0.0
        self.thread = None
        self._process = psutil.Process(os.getpid())

    def _monitor(self):
        # Prime CPU counter (first call returns 0.0 or irrelevant data)
        self._process.cpu_percent(interval=None)
        
        while self.running:
            try:
                # RAM (Resident Set Size)
                mem_info = self._process.memory_info()
                ram_mb = mem_info.rss / (1024 * 1024)
                if ram_mb > self.peak_ram_mb:
                    self.peak_ram_mb = ram_mb
                
                # CPU (Since last call)
                # interval=None is non-blocking
                cpu = self._process.cpu_percent(interval=None)
                if cpu > self.peak_cpu_percent:
                    self.peak_cpu_percent = cpu
                
            except Exception:
                pass # Evitar crash del monitor
            
            time.sleep(self.interval)

    def start(self):
        if self.running:
            return
        self.running = True
        self.peak_ram_mb = 0.0
        self.peak_cpu_percent = 0.0
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        return {
            "peak_ram_mb": round(self.peak_ram_mb, 2),
            "peak_cpu_percent": round(self.peak_cpu_percent, 2)
        }

