"""
NetKit - Network Speed Monitor (Enhanced Version)
Features: Dynamic arc display, page navigation, year-long storage
"""

import tkinter as tk
from tkinter import Menu
import psutil
import time
import threading
import os
import json
import queue
import socket
import http.server
import socketserver
import webbrowser
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from multiprocessing import Process
import tempfile
import sys
from collections import deque
import subprocess

# =========================================================
# Resource Path Helper (PyInstaller Support)
# =========================================================
def resource_path(rel_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)


# =========================================================
# Path Configuration
# =========================================================
DATA_DIR = os.path.expanduser("~/NetSpeedData")
USAGE_FILE = os.path.join(DATA_DIR, "usage.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
DASHBOARD_HTML = os.path.join(DATA_DIR, "dashboard.html")

# Resource paths
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
LOGO_SVG = resource_path("assets/logo_light.svg")
ICON_BLACK_ICO = resource_path("assets/icon_black.ico")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# Copy bundled resources
def copy_bundled_resources():
    """Copy bundled resources to data directory"""
    resources = [
        ("assets/logo_light.svg", os.path.join(ASSETS_DIR, "logo_light.svg")),
        ("assets/icon_black.ico", os.path.join(ASSETS_DIR, "icon_black.ico")),
    ]
    
    for src_name, dst_path in resources:
        try:
            src_path = resource_path(src_name)
            if os.path.exists(src_path):
                import shutil
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
        except Exception as e:
            print(f"Warning: Could not copy {src_name}: {e}")

copy_bundled_resources()


# =========================================================
# Utilities
# =========================================================
def get_network_name():
    """Get actual network SSID/name with cross-platform support"""
    try:
        if os.name == 'nt':  # Windows
            try:
                result = subprocess.run(
                    ['netsh', 'wlan', 'show', 'interfaces'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'SSID' in line and 'BSSID' not in line:
                            ssid = line.split(':')[1].strip()
                            if ssid and ssid != "":
                                return ssid
            except:
                pass
            
            return socket.gethostname()
            
        else:  # Linux/Mac
            try:
                result = subprocess.run(
                    ['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('yes:'):
                            return line.split(':')[1].strip()
            except:
                pass
            
            return socket.gethostname()
            
    except Exception as e:
        print(f"Network detection error: {e}")
        return "Unknown Network"


def human_bytes(x):
    """Format bytes to human-readable"""
    if x <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while x >= 1024 and i < len(units) - 1:
        x /= 1024.0
        i += 1
    
    if x >= 100:
        return f"{x:.0f} {units[i]}"
    elif x >= 10:
        return f"{x:.1f} {units[i]}"
    else:
        return f"{x:.2f} {units[i]}"


def human_Bps(x):
    """Format bytes/sec to human-readable"""
    if x <= 0:
        return "0 B/s"
    
    if x >= 1024 * 1024:
        mbs = x / (1024 * 1024)
        if mbs >= 100:
            return f"{mbs:.0f} MB/s"
        elif mbs >= 10:
            return f"{mbs:.1f} MB/s"
        else:
            return f"{mbs:.2f} MB/s"
    
    if x >= 1024:
        kbps = x / 1024
        if kbps >= 100:
            return f"{kbps:.0f} KB/s"
        elif kbps >= 10:
            return f"{kbps:.1f} KB/s"
        else:
            return f"{kbps:.2f} KB/s"
    
    return f"{x:.0f} B/s"


def safe_json_load(path, default):
    """Safely load JSON with error handling"""
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return default


def safe_json_dump(path, obj):
    """Atomic JSON write"""
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print(f"Error writing {path}: {e}")


# =========================================================
# Data Storage with Year-Long Support
# =========================================================
class DataStore:
    """Handles persistent storage with 1-year retention"""
    
    MAX_RECORDS = 525600  # 365 days * 24 hours * 60 minutes
    
    def __init__(self, path):
        self.path = path
        self.cache = deque(maxlen=self.MAX_RECORDS)
        self.lock = threading.Lock()
        self._load_data()
    
    def _load_data(self):
        """Load existing data into memory"""
        data = safe_json_load(self.path, [])
        with self.lock:
            self.cache.extend(data[-self.MAX_RECORDS:])
    
    def add_record(self, record):
        """Add record to cache"""
        with self.lock:
            self.cache.append(record)
    
    def persist(self):
        """Write cache to disk"""
        with self.lock:
            data = list(self.cache)
        safe_json_dump(self.path, data)
    
    def get_range(self, hours):
        """Get records within time range"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        results = []
        
        with self.lock:
            for record in self.cache:
                try:
                    timestamp = datetime.fromisoformat(record["timestamp"])
                    if start_time <= timestamp <= end_time:
                        results.append(record)
                except Exception:
                    continue
        
        return results
    
    def cleanup_old(self):
        """Remove data older than 1 year"""
        cutoff = datetime.now() - timedelta(days=365)
        
        with self.lock:
            to_keep = []
            for record in self.cache:
                try:
                    timestamp = datetime.fromisoformat(record["timestamp"])
                    if timestamp >= cutoff:
                        to_keep.append(record)
                except Exception:
                    continue
            
            removed = len(self.cache) - len(to_keep)
            self.cache.clear()
            self.cache.extend(to_keep)
        
        if removed > 0:
            print(f"Cleaned {removed} old records")
            self.persist()


# =========================================================
# Network Monitor
# =========================================================
class NetMonitor:
    """Monitors network traffic with optimized performance"""
    
    def __init__(self):
        self.prev_recv = 0
        self.prev_sent = 0
        self.down_Bps = 0.0
        self.up_Bps = 0.0
        self.total_down = 0
        self.total_up = 0
        self.running = True
        self.lock = threading.Lock()
        self.store = DataStore(HISTORY_FILE)
        self.record_queue = queue.Queue()
        
        try:
            counters = psutil.net_io_counters()
            self.prev_recv = counters.bytes_recv
            self.prev_sent = counters.bytes_sent
        except Exception as e:
            print(f"Error initializing: {e}")
        
        self._load_usage()
        
        threading.Thread(target=self._monitor_loop, daemon=True).start()
        threading.Thread(target=self._persist_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()
    
    def _load_usage(self):
        """Load today's usage"""
        today = datetime.now().date().isoformat()
        data = safe_json_load(USAGE_FILE, {"date": today, "down": 0, "up": 0})
        
        if data.get("date") == today:
            self.total_down = int(data.get("down", 0))
            self.total_up = int(data.get("up", 0))
        else:
            self.total_down = 0
            self.total_up = 0
            self._save_usage()
    
    def _save_usage(self):
        """Save current usage"""
        today = datetime.now().date().isoformat()
        safe_json_dump(USAGE_FILE, {
            "date": today,
            "down": self.total_down,
            "up": self.total_up,
            "total": self.total_down + self.total_up
        })
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                counters = psutil.net_io_counters()
                
                with self.lock:
                    down_delta = max(0, counters.bytes_recv - self.prev_recv)
                    up_delta = max(0, counters.bytes_sent - self.prev_sent)
                    
                    self.down_Bps = down_delta
                    self.up_Bps = up_delta
                    self.total_down += down_delta
                    self.total_up += up_delta
                    
                    self.prev_recv = counters.bytes_recv
                    self.prev_sent = counters.bytes_sent
                    
                    self.record_queue.put({
                        "timestamp": datetime.now().isoformat(),
                        "down": down_delta,
                        "up": up_delta,
                        "total_down": self.total_down,
                        "total_up": self.total_up
                    })
            except Exception as e:
                print(f"Monitor error: {e}")
            
            time.sleep(1.0)
    
    def _persist_loop(self):
        """Persistence loop"""
        last_save = time.time()
        
        while self.running:
            try:
                while not self.record_queue.empty():
                    try:
                        record = self.record_queue.get_nowait()
                        self.store.add_record(record)
                    except queue.Empty:
                        break
                    except Exception as e:
                        print(f"Queue error: {e}")
                
                if time.time() - last_save >= 30:
                    self.store.persist()
                    self._save_usage()
                    last_save = time.time()
            except Exception as e:
                print(f"Persist error: {e}")
            
            time.sleep(1.0)
    
    def _cleanup_loop(self):
        """Cleanup old data weekly"""
        while self.running:
            try:
                self.store.cleanup_old()
            except Exception as e:
                print(f"Cleanup error: {e}")
            
            time.sleep(604800)
    
    def get_live(self):
        """Get current stats"""
        with self.lock:
            return {
                "down_bps": self.down_Bps,
                "up_bps": self.up_Bps,
                "total_down": self.total_down,
                "total_up": self.total_up
            }
    
    def history(self, hours):
        """Get historical data"""
        return self.store.get_range(hours)
    
    def totals(self, hours):
        """Calculate totals and peaks"""
        records = self.history(hours)
        
        total_down = sum(r["down"] for r in records)
        total_up = sum(r["up"] for r in records)
        peak_down = max((r["down"] for r in records), default=0)
        peak_up = max((r["up"] for r in records), default=0)
        
        return {
            "total_down": total_down,
            "total_up": total_up,
            "peak_down": peak_down,
            "peak_up": peak_up
        }
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        self.store.persist()
        self._save_usage()


# =========================================================
# Dashboard Server
# =========================================================
class DashboardServer:
    """Serves modern dashboard with integrated design"""
    
    def __init__(self, monitor, port=8321):
        self.monitor = monitor
        self.port = port
        self.thread = None
        self.server = None
    
    def start(self):
        """Start server"""
        self._write_html()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        time.sleep(0.2)
    
    def stop(self):
        """Stop server"""
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
        except Exception:
            pass
    
    def _serve(self):
        """Server loop"""
        class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            allow_reuse_address = True
        
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=DATA_DIR, **kwargs)
            
            def log_message(self, *args, **kwargs):
                pass
            
            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                super().end_headers()
            
            def do_GET(self):
                if self.path == "/":
                    self.path = "/dashboard.html"
                    return super().do_GET()
                
                if self.path.startswith("/api/"):
                    return self._handle_api()
                
                return super().do_GET()
            
            def _handle_api(self):
                """Handle API requests"""
                try:
                    if self.path.startswith("/api/network"):
                        network_name = get_network_name()
                        return self._json_response({
                            "ssid": network_name,
                            "status": "connected",
                            "dot_color": "#10b981"
                        })
                    
                    if self.path.startswith("/api/live"):
                        stats = self.server.monitor.get_live()
                        return self._json_response({
                            "down_bps": stats["down_bps"],
                            "up_bps": stats["up_bps"],
                            "down_h": human_Bps(stats["down_bps"]),
                            "up_h": human_Bps(stats["up_bps"]),
                            "total_down": human_bytes(stats["total_down"]),
                            "total_up": human_bytes(stats["total_up"]),
                            "ts": int(time.time())
                        })
                    
                    if self.path.startswith("/api/history"):
                        query = parse_qs(urlparse(self.path).query)
                        range_key = query.get("r", ["year"])[0].lower()
                        
                        valid_ranges = ["7days", "month", "year", "all"]
                        if range_key not in valid_ranges:
                            range_key = "year"
                        
                        range_map = {
                            "7days": 168,
                            "month": 720,
                            "year": 8760,
                            "all": 876000
                        }
                        hours = range_map.get(range_key, 8760)
                        
                        records = self.server.monitor.history(hours)
                        aggregated = self._aggregate_data(records, range_key)
                        
                        return self._json_response({
                            "range": range_key, 
                            "data": aggregated,
                            "count": len(aggregated)
                        })
                    
                    if self.path.startswith("/api/summary"):
                        query = parse_qs(urlparse(self.path).query)
                        range_key = query.get("r", ["year"])[0].lower()
                        
                        valid_ranges = ["7days", "month", "year", "all"]
                        if range_key not in valid_ranges:
                            range_key = "year"
                        
                        range_map = {
                            "7days": 168,
                            "month": 720,
                            "year": 8760,
                            "all": 876000
                        }
                        hours = range_map.get(range_key, 8760)
                        
                        totals = self.server.monitor.totals(hours)
                        stats = self.server.monitor.get_live()
                        
                        return self._json_response({
                            "totals": {
                                "down": totals["total_down"],
                                "up": totals["total_up"],
                                "down_h": human_bytes(totals["total_down"]),
                                "up_h": human_bytes(totals["total_up"])
                            },
                            "current": {
                                "down_bps": stats["down_bps"],
                                "up_bps": stats["up_bps"],
                                "down_h": human_Bps(stats["down_bps"]),
                                "up_h": human_Bps(stats["up_bps"])
                            },
                            "peak": {
                                "down": human_Bps(totals["peak_down"]),
                                "up": human_Bps(totals["peak_up"])
                            }
                        })
                    
                    self.send_error(404)
                except Exception as e:
                    print(f"API error: {e}")
                    self.send_error(500, f"Error: {e}")
            
            def _aggregate_data(self, records, range_key):
                """Aggregate data for chart display"""
                if not records:
                    return [{"ts": time.time(), "down": 0, "up": 0}]
                
                if range_key == "7days":
                    return self._aggregate_by_hour(records)
                elif range_key == "month":
                    return self._aggregate_by_day(records)
                elif range_key == "year":
                    return self._aggregate_by_month(records)
                elif range_key == "all":
                    return self._aggregate_by_year(records)
                
                return self._aggregate_by_hour(records)
            
            def _aggregate_by_hour(self, records):
                """Aggregate by hour"""
                buckets = {}
                for rec in records:
                    try:
                        ts = datetime.fromisoformat(rec["timestamp"])
                        key = ts.replace(minute=0, second=0, microsecond=0)
                        if key not in buckets:
                            buckets[key] = {"down": 0, "up": 0, "count": 0}
                        buckets[key]["down"] += rec["down"]
                        buckets[key]["up"] += rec["up"]
                        buckets[key]["count"] += 1
                    except Exception:
                        continue
                
                result = []
                for key, val in sorted(buckets.items()):
                    result.append({
                        "ts": key.timestamp(),
                        "down": val["down"],
                        "up": val["up"]
                    })
                
                return result if result else [{"ts": time.time(), "down": 0, "up": 0}]
            
            def _aggregate_by_day(self, records):
                """Aggregate by day"""
                buckets = {}
                for rec in records:
                    try:
                        ts = datetime.fromisoformat(rec["timestamp"])
                        key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
                        if key not in buckets:
                            buckets[key] = {"down": 0, "up": 0, "count": 0}
                        buckets[key]["down"] += rec["down"]
                        buckets[key]["up"] += rec["up"]
                        buckets[key]["count"] += 1
                    except Exception:
                        continue
                
                result = []
                for key, val in sorted(buckets.items()):
                    result.append({
                        "ts": key.timestamp(),
                        "down": val["down"],
                        "up": val["up"]
                    })
                
                return result if result else [{"ts": time.time(), "down": 0, "up": 0}]
            
            def _aggregate_by_month(self, records):
                """Aggregate by month"""
                buckets = {}
                for rec in records:
                    try:
                        ts = datetime.fromisoformat(rec["timestamp"])
                        key = ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if key not in buckets:
                            buckets[key] = {"down": 0, "up": 0, "count": 0}
                        buckets[key]["down"] += rec["down"]
                        buckets[key]["up"] += rec["up"]
                        buckets[key]["count"] += 1
                    except Exception:
                        continue
                
                result = []
                for key, val in sorted(buckets.items()):
                    result.append({
                        "ts": key.timestamp(),
                        "down": val["down"],
                        "up": val["up"]
                    })
                
                return result if result else [{"ts": time.time(), "down": 0, "up": 0}]
            
            def _aggregate_by_year(self, records):
                """Aggregate by year"""
                buckets = {}
                for rec in records:
                    try:
                        ts = datetime.fromisoformat(rec["timestamp"])
                        key = ts.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                        if key not in buckets:
                            buckets[key] = {"down": 0, "up": 0, "count": 0}
                        buckets[key]["down"] += rec["down"]
                        buckets[key]["up"] += rec["up"]
                        buckets[key]["count"] += 1
                    except Exception:
                        continue
                
                result = []
                for key, val in sorted(buckets.items()):
                    result.append({
                        "ts": key.timestamp(),
                        "down": val["down"],
                        "up": val["up"]
                    })
                
                return result if result else [{"ts": time.time(), "down": 0, "up": 0}]
            
            def _json_response(self, obj):
                """Send JSON response"""
                body = json.dumps(obj).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        
        with ThreadingHTTPServer(("", self.port), Handler) as httpd:
            httpd.monitor = self.monitor
            self.server = httpd
            httpd.serve_forever()
    
    def _write_html(self):
        """Generate modern dashboard HTML"""
        html = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Internet Kit</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f0f0f;
      --surface: #1a1a1a;
      --surface-light: #252525;
      --primary: #6366f1;
      --primary-light: #818cf8;
      --text: #f8fafc;
      --text-secondary: #94a3b8;
      --border: #374151;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font: "Outfit", system-ui, sans-serif;
      --status-planned: #6b7280;
      --status-soon: var(--primary);
    }

    *, *::before, *::after { box-sizing: border-box; }

    body {
      margin: 0;
      background: linear-gradient(135deg, var(--bg) 0%, #1e1b4b 100%);
      font-family: var(--font);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: 0;
      color: var(--text);
      overflow: hidden;
    }

    .app-frame {
      background: var(--surface);
      width: 100%;
      height: 100vh;
      max-width: 100%;
      max-height: 100vh;
      border-radius: 0;
      overflow: hidden;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
      display: flex;
      flex-direction: column;
      border: none;
    }

    .topbar {
      background: var(--surface-light);
      padding: 12px 16px;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 12px;
      border-bottom: 1px solid var(--border);
      position: relative;
    }
    
    .back-btn {
      position: absolute;
      left: 16px;
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-secondary);
      border-radius: 8px;
      padding: 6px 12px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.85rem;
      font-weight: 500;
      display: none;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }
    
    .back-btn:hover {
      background: rgba(99, 102, 241, 0.1);
      color: var(--primary);
      border-color: var(--primary);
    }
    
    .back-btn.show {
      display: inline-flex;
    }
    
    .logo-center { height: 28px; width: auto; }

    .page { display: none; padding: 16px; flex: 1; overflow-y: auto; }
    .page.active { display: block; }

    .speed-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 16px 12px;
      gap: 20px;
    }
    .speed-col { flex: 1; min-width: 120px; }
    .speed-col.right { text-align: right; }
    .speed-label {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 0.9rem;
      color: var(--text-secondary);
    }
    .arrow { font-size: 1rem; }
    .arrow.down { color: var(--success); }
    .arrow.up { color: var(--primary-light); }

    .meter-col {
      text-align: center;
      flex: 1.5;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .isp {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 8px;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .network-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 6px var(--success);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.6; }
      100% { opacity: 1; }
    }
    .arc-wrapper {
      position: relative;
      width: 180px;
      height: 90px;
    }
    .arc-text {
      position: absolute;
      top: 100%;
      left: 50%;
      transform: translate(-50%, -70%);
      display: flex;
      flex-direction: column;
      gap: 4px;
      z-index: 2;
    }
    .big-num {
      font-weight: 700;
      font-size: 1.8rem;
      background: linear-gradient(90deg, var(--primary), var(--primary-light));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .small-text {
      font-size: 0.7rem;
      color: var(--text-secondary);
    }
    .semi-arc { width: 100%; height: 100%; position: absolute; left: 0; top: 0; }

    .usage-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 16px 12px;
    }
    .usage-title { margin: 0; font-weight: 700; font-size: 1.1rem; }
    .filter-container { position: relative; display: inline-block; }
    .filter {
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 12px;
      font-size: 0.8rem;
      cursor: pointer;
      background: var(--surface-light);
      transition: all 0.2s ease;
      user-select: none;
    }
    .filter:hover { border-color: var(--primary); }
    .caret { font-size: 0.8rem; color: var(--text-secondary); }
    .dropdown {
      position: absolute;
      top: 100%;
      right: 0;
      background: var(--surface-light);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      z-index: 10;
      min-width: 120px;
      display: none;
      flex-direction: column;
    }
    .dropdown.show { display: flex; }
    .dropdown-item {
      padding: 8px 12px;
      cursor: pointer;
      transition: background 0.2s;
      font-size: 0.8rem;
    }
    .dropdown-item:hover {
      background: rgba(99, 102, 241, 0.1);
      color: var(--primary);
    }

    .stat-cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      padding: 0 16px 16px;
    }
    .stat-card {
      background: var(--surface-light);
      border: 1px solid var(--border);
      border-radius: 12px;
      display: flex;
      gap: 10px;
      align-items: center;
      padding: 12px;
      transition: all 0.2s ease;
    }
    .stat-card:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2);
      border-color: var(--primary);
    }
    .icon-box {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      font-size: 0.9rem;
      background: rgba(99, 102, 241, 0.15);
      color: var(--primary);
    }
    .stat-info { display: flex; flex-direction: column; gap: 2px; }
    .stat-label {
      font-size: 0.7rem;
      font-weight: 600;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .stat-value { font-size: 1rem; font-weight: 700; }

    .chart-box {
      margin: 0 16px 16px;
      border-radius: 12px;
      background: var(--surface-light);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      border: 1px solid var(--border);
      height: 240px;
    }
    .chart-top {
      display: flex;
      align-items: center;
      gap: 16px;
      font-size: 0.8rem;
    }
    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      display: inline-block;
    }
    .dot.blue { background: var(--primary); }
    .dot.green { background: var(--success); }
    .legend { color: var(--text-secondary); }
    #usageChart { flex: 1; min-height: 0; }

    .bottom-nav {
      display: flex;
      justify-content: center;
      gap: 16px;
      padding: 16px;
      background: var(--surface-light);
      border-top: 1px solid var(--border);
    }
    .nav-btn {
      background: transparent;
      color: var(--text-secondary);
      border: 1px solid var(--border);
      border-radius: 8px;
      font-family: inherit;
      font-size: 0.85rem;
      font-weight: 500;
      padding: 8px 16px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .nav-btn:hover {
      background: rgba(99, 102, 241, 0.1);
      color: var(--primary);
      border-color: var(--primary);
    }
    .nav-btn:active { transform: translateY(1px); }

    .about-header { text-align: center; margin-bottom: 24px; }
    .about-header h2 {
      font-weight: 700;
      font-size: 1.8rem;
      margin: 0 0 12px;
      background: linear-gradient(90deg, var(--primary), var(--primary-light));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .about-header p {
      font-size: 1rem;
      color: var(--text-secondary);
      max-width: 600px;
      margin: 0 auto;
    }
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }
    .feature-card {
      background: var(--surface-light);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      text-align: center;
      transition: all 0.2s ease;
    }
    .feature-card:hover {
      transform: translateY(-3px);
      border-color: var(--primary);
      box-shadow: 0 8px 16px rgba(99, 102, 241, 0.1);
    }
    .feature-icon { color: var(--primary); margin-bottom: 12px; }
    .feature-card h3 {
      font-weight: 600;
      font-size: 1rem;
      margin: 0 0 6px;
      color: var(--text);
    }
    .feature-card p {
      font-size: 0.85rem;
      color: var(--text-secondary);
      line-height: 1.4;
    }
    .about-footer {
      text-align: center;
      margin-top: 32px;
      font-size: 0.9rem;
      color: var(--text-secondary);
    }
    .about-footer strong { color: var(--text); }

    .roadmap-header { text-align: center; margin-bottom: 24px; }
    .roadmap-header h2 { font-weight: 700; font-size: 1.8rem; margin: 0 0 12px; }
    .roadmap-header p {
      font-size: 1rem;
      color: var(--text-secondary);
      max-width: 700px;
      margin: 0 auto;
    }
    .roadmap-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .roadmap-item {
      background: var(--surface-light);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      display: flex;
      align-items: center;
      gap: 16px;
      transition: all 0.2s ease;
    }
    .roadmap-item:hover {
      border-color: var(--primary);
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .roadmap-item-icon {
      background: rgba(99, 102, 241, 0.1);
      color: var(--primary);
      border-radius: 8px;
      padding: 10px;
      flex-shrink: 0;
    }
    .roadmap-item-content { flex-grow: 1; }
    .roadmap-item-content h3 {
      font-weight: 600;
      font-size: 1rem;
      margin: 0 0 4px;
      color: var(--text);
    }
    .roadmap-item-content p {
      font-size: 0.85rem;
      color: var(--text-secondary);
      margin: 0;
    }
    .status {
      font-size: 0.7rem;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 16px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }
    .status.planned {
      background: rgba(107, 114, 128, 0.2);
      color: var(--status-planned);
    }
    .status.soon {
      background: rgba(99, 102, 241, 0.2);
      color: var(--status-soon);
    }
    .roadmap-cta { text-align: center; margin-top: 32px; }
    .roadmap-cta a {
      background: var(--primary);
      color: var(--text);
      text-decoration: none;
      font-weight: 600;
      padding: 10px 20px;
      border-radius: 8px;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .roadmap-cta a:hover {
      background: var(--primary-light);
      transform: translateY(-2px);
    }

    h2.page-title {
      font-weight: 700;
      font-size: 1.4rem;
      margin: 0 0 20px;
      color: var(--text);
    }
    p {
      line-height: 1.5;
      margin: 0 0 14px;
      color: var(--text-secondary);
    }
    .donate-links {
      display: flex;
      gap: 12px;
      margin-top: 20px;
      flex-wrap: wrap;
    }
    .donate-link {
      background: var(--surface-light);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 16px;
      text-decoration: none;
      color: var(--text);
      font-weight: 600;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .donate-link:hover {
      border-color: var(--primary);
      background: rgba(99, 102, 241, 0.1);
      color: var(--primary);
    }
    .coming-soon {
      text-align: center;
      font-size: 1.1rem;
      color: var(--text-secondary);
      margin-top: 40px;
    }

    @media (max-width: 768px) {
      .speed-row { flex-direction: column; gap: 16px; text-align: center; }
      .speed-col, .speed-col.right { width: 100%; text-align: center; }
      .meter-col { order: -1; margin-bottom: 12px; }
      .stat-cards { grid-template-columns: 1fr; }
      .bottom-nav { flex-wrap: wrap; }
      .roadmap-item { flex-direction: column; text-align: center; }
    }
  </style>
</head>
<body>
  <div class="app-frame">
    <header class="topbar">
      <button class="back-btn" id="backBtn">
        <i data-lucide="arrow-left" style="width: 16px; height: 16px;"></i>
        Back
      </button>
      <img src="assets/logo_light.svg" alt="Internet Kit Logo" class="logo-center">
    </header>

    <div id="dashboard" class="page active">
      <section class="speed-row">
        <div class="speed-col">
          <div class="speed-label">
            <span class="arrow down">⬇</span>
            <span id="leftSpeed">0 MB/s</span>
          </div>
        </div>

        <div class="meter-col">
          <div class="isp">
            <span class="network-dot" id="networkDot"></span>
            <span id="networkName">Loading Network...</span>
          </div>
          <div class="arc-wrapper">
            <div class="arc-text">
              <span class="big-num" id="used7d">0 GB</span>
              <span class="small-text" id="arcLabel">Used in selected period</span>
            </div>
            <svg viewBox="0 0 180 90" class="semi-arc">
              <defs>
                <linearGradient id="arcGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stop-color="#6366f1" />
                  <stop offset="100%" stop-color="#818cf8" />
                </linearGradient>
              </defs>
              <path d="M10 90 A80 80 0 0 1 170 90" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="12" stroke-linecap="round" />
              <path id="progressArc" d="M10 90 A80 80 0 0 1 170 90" fill="none" stroke="url(#arcGradient)" stroke-width="12" stroke-linecap="round" stroke-dasharray="251.2" stroke-dashoffset="125.6" />
            </svg>
          </div>
        </div>

        <div class="speed-col right">
          <div class="speed-label">
            <span id="rightSpeed">0 MB/s</span>
            <span class="arrow up">⬆</span>
          </div>
        </div>
      </section>

      <section class="usage-head">
        <h2 class="usage-title">Usage Statistics</h2>
        <div class="filter-container">
          <div class="filter" id="timeFilter">
            <span id="selectedPeriod">Last Year</span>
            <span class="caret">▾</span>
          </div>
          <div class="dropdown" id="timeDropdown">
            <div class="dropdown-item" data-value="7days">Last 7 Days</div>
            <div class="dropdown-item" data-value="month">Last Month</div>
            <div class="dropdown-item" data-value="year">Last Year</div>
            <div class="dropdown-item" data-value="all">All Time</div>
          </div>
        </div>
      </section>

      <section class="stat-cards">
        <div class="stat-card">
          <div class="icon-box">⬇</div>
          <div class="stat-info">
            <div class="stat-label">Download</div>
            <div class="stat-value" id="downloadVal">0 GB</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="icon-box">⬆</div>
          <div class="stat-info">
            <div class="stat-label">Upload</div>
            <div class="stat-value" id="uploadVal">0 GB</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="icon-box">⌀</div>
          <div class="stat-info">
            <div class="stat-label">Monthly Avg</div>
            <div class="stat-value" id="monthlyVal">0 GB</div>
          </div>
        </div>
      </section>

      <section class="chart-box">
        <div class="chart-top">
          <span class="dot blue"></span> <span class="legend">Download</span>
          <span class="dot green"></span> <span class="legend">Upload</span>
        </div>
        <canvas id="usageChart"></canvas>
      </section>

      <footer class="bottom-nav">
        <button class="nav-btn" data-page="about">About</button>
        <button class="nav-btn" data-page="roadmap">Roadmap</button>
        <button class="nav-btn" data-page="support">Support</button>
        <button class="nav-btn" data-page="settings">Settings</button>
      </footer>
    </div>

    <div id="about" class="page">
      <div class="about-header">
        <h2>About Internet Kit</h2>
        <p>A modern, free, and open-source network monitoring tool designed for clarity, privacy, and control.</p>
      </div>

      <div class="feature-grid">
        <div class="feature-card">
          <i data-lucide="activity" class="feature-icon" style="width: 40px; height: 40px;"></i>
          <h3>Real-time Monitoring</h3>
          <p>Track your download and upload speeds live with a beautiful, responsive interface.</p>
        </div>
        <div class="feature-card">
          <i data-lucide="bar-chart-3" class="feature-icon" style="width: 40px; height: 40px;"></i>
          <h3>Deep Insights</h3>
          <p>Analyze your data consumption over different periods to understand your usage patterns.</p>
        </div>
        <div class="feature-card">
          <i data-lucide="lock" class="feature-icon" style="width: 40px; height: 40px;"></i>
          <h3>Privacy First</h3>
          <p>Your data stays on your device. We believe in transparency and user privacy above all else.</p>
        </div>
        <div class="feature-card">
          <i data-lucide="code-2" class="feature-icon" style="width: 40px; height: 40px;"></i>
          <h3>Open Source</h3>
          <p>Our code is publicly available. Inspect, contribute, and help us build the best tool possible.</p>
        </div>
      </div>

      <div class="about-footer">
        <p>Designed with <i data-lucide="heart" style="display: inline; width: 16px; height: 16px; vertical-align: text-bottom; color: var(--danger);"></i> for users who care about their internet experience.</p>
        <p><strong>Version 1.0</strong> — The journey has just begun.</p>
      </div>
    </div>

    <div id="roadmap" class="page">
      <div class="roadmap-header">
        <h2>Our Roadmap</h2>
        <p>We're constantly working to make Internet Kit more powerful and intuitive. Here's a glimpse of what's coming next.</p>
      </div>

      <ul class="roadmap-list">
        <li class="roadmap-item">
          <div class="roadmap-item-icon">
            <i data-lucide="moon" style="width: 20px; height: 20px;"></i>
          </div>
          <div class="roadmap-item-content">
            <h3>Theme Customization</h3>
            <p>Switch seamlessly between a sleek dark mode and a clean light mode to match your environment and preference.</p>
          </div>
          <span class="status soon">In Development</span>
        </li>
        <li class="roadmap-item">
          <div class="roadmap-item-icon">
            <i data-lucide="smartphone" style="width: 20px; height: 20px;"></i>
          </div>
          <div class="roadmap-item-content">
            <h3>Data Usage by App</h3>
            <p>Get granular insights by seeing which applications are consuming the most data on your system.</p>
          </div>
          <span class="status soon">In Development</span>
        </li>
        <li class="roadmap-item">
          <div class="roadmap-item-icon">
            <i data-lucide="wifi" style="width: 20px; height: 20px;"></i>
          </div>
          <div class="roadmap-item-content">
            <h3>Network-Aware Statistics</h3>
            <p>Automatically detect and track usage for different networks (Wi-Fi, Ethernet, VPN) separately.</p>
          </div>
          <span class="status planned">Planned</span>
        </li>
        <li class="roadmap-item">
          <div class="roadmap-item-icon">
            <i data-lucide="download-cloud" style="width: 20px; height: 20px;"></i>
          </div>
          <div class="roadmap-item-content">
            <h3>Data Export & Reports</h3>
            <p>Export your usage data as CSV or PDF for personal records or further analysis.</p>
          </div>
          <span class="status planned">Planned</span>
        </li>
        <li class="roadmap-item">
          <div class="roadmap-item-icon">
            <i data-lucide="bell" style="width: 20px; height: 20px;"></i>
          </div>
          <div class="roadmap-item-content">
            <h3>Real-time Alerts</h3>
            <p>Set custom data usage limits and receive notifications when you're about to exceed them.</p>
          </div>
          <span class="status planned">Planned</span>
        </li>
      </ul>

      <div class="roadmap-cta">
        <a href="https://github.com/sh44ni/netkit-speed-meter" target="_blank">
          <i data-lucide="github" style="width: 18px; height: 18px;"></i>
          Follow our Progress on GitHub
        </a>
      </div>
    </div>

    <div id="support" class="page">
      <h2 class="page-title">Support This Project</h2>
      <p>Internet Kit is free and open-source — but development takes time and resources.</p>
      <p>If you find this tool useful, consider supporting its future development with a small donation. Every contribution helps keep the project alive and growing!</p>
      
      <div class="donate-links">
        <a href="#" class="donate-link"><i data-lucide="coffee" style="width:16px; height:16px;"></i> Buy Me a Coffee</a>
        <a href="#" class="donate-link"><i data-lucide="credit-card" style="width:16px; height:16px;"></i> PayPal</a>
        <a href="#" class="donate-link"><i data-lucide="coins" style="width:16px; height:16px;"></i> Crypto</a>
      </div>
      
      <p style="margin-top: 24px;"><em>Thank you for believing in open-source software!</em></p>
    </div>

    <div id="settings" class="page">
      <h2 class="page-title">Settings</h2>
      <div class="coming-soon">🛠️ Settings panel coming soon!</div>
      <p style="text-align: center; margin-top: 16px; color: var(--text-secondary);">
        Dark mode, notifications, data retention, and more — in development.
      </p>
    </div>
  </div>

  <script>
    document.addEventListener("DOMContentLoaded", () => {
      lucide.createIcons();

      const pages = ['dashboard', 'about', 'roadmap', 'support', 'settings'];
      const navButtons = document.querySelectorAll('.nav-btn');
      const backBtn = document.getElementById('backBtn');
      let pageHistory = ['dashboard'];

      function showPage(pageId, addToHistory = true) {
        pages.forEach(id => {
          document.getElementById(id).classList.remove('active');
        });
        document.getElementById(pageId).classList.add('active');
        
        if (addToHistory && pageHistory[pageHistory.length - 1] !== pageId) {
          pageHistory.push(pageId);
        }
        
        if (pageId === 'dashboard') {
          backBtn.classList.remove('show');
        } else {
          backBtn.classList.add('show');
        }
        
        lucide.createIcons();
      }

      navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
          showPage(btn.dataset.page, true);
        });
      });

      backBtn.addEventListener('click', () => {
        if (pageHistory.length > 1) {
          pageHistory.pop();
          const previousPage = pageHistory[pageHistory.length - 1];
          showPage(previousPage, false);
        } else {
          showPage('dashboard', false);
          pageHistory = ['dashboard'];
        }
      });

      const leftSpeed = document.getElementById("leftSpeed");
      const rightSpeed = document.getElementById("rightSpeed");
      const used7d = document.getElementById("used7d");
      const arcLabel = document.getElementById("arcLabel");
      const downloadVal = document.getElementById("downloadVal");
      const uploadVal = document.getElementById("uploadVal");
      const monthlyVal = document.getElementById("monthlyVal");
      const progressArc = document.getElementById("progressArc");
      const timeFilter = document.getElementById("timeFilter");
      const timeDropdown = document.getElementById("timeDropdown");
      const selectedPeriod = document.getElementById("selectedPeriod");
      const networkName = document.getElementById("networkName");
      const networkDot = document.getElementById("networkDot");

      const ctx = document.getElementById('usageChart').getContext('2d');
      let currentPeriod = 'year';
      let chartUpdateInterval;

      const usageChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: [],
          datasets: [
            {
              label: 'Download',
              data: [],
              borderColor: '#6366f1',
              backgroundColor: 'rgba(99, 102, 241, 0.1)',
              borderWidth: 2,
              tension: 0.4,
              fill: true
            },
            {
              label: 'Upload',
              data: [],
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2,
              tension: 0.4,
              fill: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(26, 26, 26, 0.9)',
              titleColor: '#f8fafc',
              bodyColor: '#94a3b8',
              borderColor: '#374151',
              borderWidth: 1,
              padding: 10,
              displayColors: true,
              callbacks: {
                label: function(context) {
                  let label = context.dataset.label || '';
                  if (label) {
                    label += ': ';
                  }
                  if (context.parsed.y !== null) {
                    label += formatBytes(context.parsed.y);
                  }
                  return label;
                }
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { 
                color: 'rgba(255, 255, 255, 0.6)', 
                font: { size: 10 },
                maxRotation: 0,
                autoSkip: true,
                maxTicksLimit: 8
              }
            },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { 
                color: 'rgba(255, 255, 255, 0.6)',
                font: { size: 10 },
                callback: (v) => formatBytes(v)
              }
            }
          }
        }
      });

      function formatBytes(bytes) {
        if (bytes === 0 || bytes === undefined || bytes === null) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
      }

      function formatTimeLabel(ts, range) {
        const d = new Date(ts * 1000);
        if (range === '7days') {
          return d.toLocaleDateString([], {weekday: 'short'});
        } else if (range === 'month') {
          return d.toLocaleDateString([], {month: 'short', day: 'numeric'});
        } else if (range === 'year') {
          return d.toLocaleDateString([], {month: 'short'});
        } else if (range === 'all') {
          return d.getFullYear().toString();
        }
        return d.toLocaleString();
      }

      function updateArcLabel(period) {
        const labels = {
          '7days': 'Used in last 7 days',
          'month': 'Used in last month',
          'year': 'Used in last year',
          'all': 'Used all time'
        };
        arcLabel.textContent = labels[period] || 'Used in selected period';
      }

      async function loadHistory(period) {
        try {
          const response = await fetch(`/api/history?r=${encodeURIComponent(period)}`);
          if (!response.ok) throw new Error('Network response was not ok');
          const historyData = await response.json();
          
          if (!historyData || !historyData.data || !Array.isArray(historyData.data)) {
            console.error('Invalid history data format:', historyData);
            return;
          }
          
          const dataPoints = historyData.data.length > 0 ? historyData.data : [{ts: Date.now()/1000, down: 0, up: 0}];
          
          const labels = dataPoints.map(p => formatTimeLabel(p.ts, period));
          const downloadData = dataPoints.map(p => p.down || 0);
          const uploadData = dataPoints.map(p => p.up || 0);

          usageChart.data.labels = labels;
          usageChart.data.datasets[0].data = downloadData;
          usageChart.data.datasets[1].data = uploadData;
          usageChart.update('none');

          updateArcLabel(period);
          await loadSummary(period);
        } catch (e) {
          console.error('Error loading history:', e);
          usageChart.data.labels = ['No Data'];
          usageChart.data.datasets[0].data = [0];
          usageChart.data.datasets[1].data = [0];
          usageChart.update('none');
        }
      }

      async function loadSummary(period) {
        try {
          const summaryResponse = await fetch(`/api/summary?r=${encodeURIComponent(period)}`);
          if (!summaryResponse.ok) throw new Error('Summary response was not ok');
          const summary = await summaryResponse.json();
          
          if (summary && summary.totals) {
            downloadVal.textContent = summary.totals.down_h || '0 GB';
            uploadVal.textContent = summary.totals.up_h || '0 GB';
            
            const totalGB = (summary.totals.down + summary.totals.up) / (1024 * 1024 * 1024);
            let months = 1;
            if (period === 'year') months = 12;
            else if (period === 'all') months = Math.max(1, Math.floor(totalGB / 10));
            else if (period === 'month') months = 1;
            else if (period === '7days') months = 0.25;
            
            const avgGB = totalGB / months;
            monthlyVal.textContent = avgGB.toFixed(1) + ' GB';

            const usageGB = (summary.totals.down + summary.totals.up) / (1024 * 1024 * 1024);
            
            let maxGB = 100;
            if (period === '7days') maxGB = 50;
            else if (period === 'month') maxGB = 200;
            else if (period === 'year') maxGB = 2000;
            else if (period === 'all') maxGB = Math.max(usageGB * 1.2, 100);
            
            const percentage = Math.min((usageGB / maxGB) * 100, 100);
            const dashOffset = 251.2 - (251.2 * percentage / 100);
            progressArc.style.strokeDashoffset = dashOffset;
            used7d.textContent = usageGB.toFixed(1) + " GB";
          }

          const periodLabels = {
            '7days': 'Last 7 Days',
            'month': 'Last Month',
            'year': 'Last Year',
            'all': 'All Time'
          };
          selectedPeriod.textContent = periodLabels[period] || 'Custom';
        } catch (e) {
          console.error('Error loading summary:', e);
        }
      }

      async function updateLive() {
        try {
          const response = await fetch('/api/live');
          if (!response.ok) throw new Error('Live response was not ok');
          const data = await response.json();
          
          if (data) {
            leftSpeed.textContent = data.down_h || '0 MB/s';
            rightSpeed.textContent = data.up_h || '0 MB/s';
          }
        } catch (e) {
          console.error('Error updating live:', e);
        }
      }

      async function loadNetworkName() {
        try {
          const response = await fetch('/api/network');
          if (!response.ok) throw new Error('Network response was not ok');
          const data = await response.json();
          
          if (data && data.ssid) {
            networkName.textContent = data.ssid.toUpperCase();
            if (data.dot_color) {
              networkDot.style.background = data.dot_color;
              networkDot.style.boxShadow = `0 0 6px ${data.dot_color}`;
            }
          }
        } catch (e) {
          console.error('Error loading network:', e);
          networkName.textContent = 'UNKNOWN';
        }
      }

      timeFilter.addEventListener('click', (e) => {
        e.stopPropagation();
        timeDropdown.classList.toggle('show');
      });

      document.addEventListener('click', (e) => {
        if (!timeFilter.contains(e.target)) {
          timeDropdown.classList.remove('show');
        }
      });

      document.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', (e) => {
          currentPeriod = e.target.dataset.value;
          loadHistory(currentPeriod);
          timeDropdown.classList.remove('show');
        });
      });

      (async function init() {
        await loadNetworkName();
        await loadHistory('year');
        updateLive();
        
        setInterval(updateLive, 1000);
        
        chartUpdateInterval = setInterval(() => {
          loadHistory(currentPeriod);
        }, 30000);
      })();
    });
  </script>
</body>
</html>
"""
        
        with open(DASHBOARD_HTML, "w", encoding="utf-8") as f:
            f.write(html)


# =========================================================
# Webview Launcher
# =========================================================
def run_webview(port):
    """Launch dashboard in webview"""
    try:
        import webview
        webview.create_window(
            "Internet Kit - NetKit Dashboard",
            f"http://localhost:{port}",
            width=1200,
            height=900,
            min_size=(900, 700),
            resizable=True,
            background_color="#0f0f0f"
        )
        webview.start(gui='edgechromium' if os.name == 'nt' else None)
    except ImportError:
        webbrowser.open(f"http://localhost:{port}")


# =========================================================
# Overlay Window
# =========================================================
class MinimalOverlay(tk.Tk):
    """Minimal overlay widget"""
    
    def __init__(self):
        super().__init__()
        
        self.transparent_key = "#000001"
        self.overrideredirect(True)
        self.configure(bg=self.transparent_key)
        self.wm_attributes("-transparentcolor", self.transparent_key)
        self.wm_attributes("-alpha", 0.85)
        
        if os.path.exists(ICON_BLACK_ICO):
            try:
                self.iconbitmap(ICON_BLACK_ICO)
            except Exception:
                pass
        
        self._set_topmost(True)
        self._build_ui()
        
        self.monitor = NetMonitor()
        self.server = DashboardServer(self.monitor, port=8321)
        self.server.start()
        
        self.webview_proc = None
        
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{sh - h - 50}")
        
        self._enforce_topmost()
        self.bind("<FocusOut>", lambda e: self._set_topmost(True))
        
        self._tick()
        self.after(500, self.open_dashboard)
    
    def _set_topmost(self, val=True):
        """Set always on top"""
        try:
            self.wm_attributes("-topmost", 1 if val else 0)
        except Exception:
            pass
    
    def _enforce_topmost(self):
        """Enforce topmost periodically"""
        self._set_topmost(True)
        self.after(3000, self._enforce_topmost)
    
    def _build_ui(self):
        """Build minimal UI"""
        frame = tk.Frame(self, bg=self.transparent_key)
        frame.pack(padx=10, pady=6)
        
        self.up_var = tk.StringVar(value="↑ 0 MB/s")
        self.dn_var = tk.StringVar(value="↓ 0 MB/s")
        
        tk.Label(
            frame,
            textvariable=self.up_var,
            bg=self.transparent_key,
            fg="#10b981",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")
        
        tk.Label(
            frame,
            textvariable=self.dn_var,
            bg=self.transparent_key,
            fg="#3b82f6",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")
        
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._on_move)
        
        menu = Menu(self, tearoff=0, bg="#0a0a0a", fg="#e5e7eb", font=("Segoe UI", 9))
        menu.add_command(label="📊 Dashboard", command=self.open_dashboard)
        menu.add_separator()
        menu.add_command(label="Exit", command=self.quit_app)
        self.menu = menu
        self.bind("<Button-3>", self._popup)
    
    def _start_move(self, event):
        """Start drag"""
        self._drag_x = event.x
        self._drag_y = event.y
    
    def _on_move(self, event):
        """Handle drag"""
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")
    
    def _popup(self, event):
        """Show menu"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
    
    def open_dashboard(self):
        """Open dashboard with smooth transition"""
        if self.webview_proc and self.webview_proc.is_alive():
            try:
                webbrowser.open(f"http://localhost:{self.server.port}")
            except Exception:
                pass
            return
        
        self.webview_proc = Process(
            target=run_webview,
            args=(self.server.port,),
            daemon=True
        )
        self.webview_proc.start()
    
    def _tick(self):
        """Update display"""
        try:
            stats = self.monitor.get_live()
            self.up_var.set(f"↑ {human_Bps(stats['up_bps'])}")
            self.dn_var.set(f"↓ {human_Bps(stats['down_bps'])}")
        except Exception as e:
            print(f"UI error: {e}")
        
        self.after(1000, self._tick)
    
    def quit_app(self):
        """Cleanup and exit"""
        try:
            self.monitor.stop()
        except Exception:
            pass
        
        try:
            self.server.stop()
        except Exception:
            pass
        
        try:
            if self.webview_proc and self.webview_proc.is_alive():
                self.webview_proc.terminate()
        except Exception:
            pass
        
        self.destroy()


# =========================================================
# Main Entry Point
# =========================================================
if __name__ == "__main__":
    import multiprocessing
    import signal
    
    multiprocessing.freeze_support()
    
    def signal_handler(sig, frame):
        print("\nShutting down gracefully...")
        try:
            app.quit_app()
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app = MinimalOverlay()
    try:
        app.mainloop()
    finally:
        try:
            app.quit_app()
        except Exception:
            pass