import os
import sys
import time
import threading
import tomllib
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

# Try to import Azure Storage SDK
try:
    from azure.storage.fileshare import ShareServiceClient
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False

CONFIG_FILE = "config.toml"

class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Azure Files Syncer")
        self.root.geometry("600x480")
        
        self.config = self.load_config()
        self.is_running = False
        self.sync_thread = None
        
        self.setup_ui()
        
        if not AZURE_SDK_AVAILABLE:
            messagebox.showerror("Error", "azure-storage-file-share is not installed. Please install it to use this tool.")
            self.start_btn.config(state=tk.DISABLED)
        
    def load_config(self):
        try:
            if getattr(sys, 'frozen', False):
                base_path = Path(sys.executable).parent
            else:
                base_path = Path(__file__).parent
                
            config_path = base_path / CONFIG_FILE
            
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load {CONFIG_FILE}, proceeding with defaults:\n{e}")
            return {}

    def setup_ui(self):
        azure_config = self.config.get("azure", {})
        sync_config = self.config.get("sync", {})
        
        # Settings frame
        settings_frame = ttk.LabelFrame(self.root, text="Settings")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(settings_frame, text="Azure Share:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(settings_frame, text=azure_config.get("share_name", "Not set")).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(settings_frame, text="Source Dir:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        source_display = sync_config.get("source_dir", "")
        ttk.Label(settings_frame, text=source_display if source_display else "(Root)").grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(settings_frame, text="Target Dir:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Label(settings_frame, text=sync_config.get("target_dir", "Not set")).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Controls
        controls_frame = ttk.Frame(self.root)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_btn = ttk.Button(controls_frame, text="Start Sync", command=self.start_sync)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(controls_frame, text="Stop Sync", command=self.stop_sync, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Idle")
        self.progress_label.pack(side=tk.TOP, anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=2)
        
        # Log
        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log("Application started. Ready to sync.")
        
    def log(self, message):
        def append():
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        if self.root:
            self.root.after(0, append)
            
    def update_progress(self, filename, percent, speed_mbps=None, done=False):
        def ui_update():
            if done:
                self.progress_label.config(text="Idle")
                self.progress_bar['value'] = 0
            else:
                speed_text = f" ({speed_mbps:.1f} Mbps)" if speed_mbps is not None else ""
                self.progress_label.config(text=f"Syncing {filename}: {percent:.1f}%{speed_text}")
                self.progress_bar['value'] = percent
        if self.root:
            self.root.after(0, ui_update)
            
    def start_sync(self):
        azure_config = self.config.get("azure", {})
        sync_config = self.config.get("sync", {})
        
        if not azure_config.get("connection_string") or not azure_config.get("share_name"):
            messagebox.showerror("Error", "Azure Connection String and Share Name must be set in config.toml")
            return
            
        if not sync_config.get("target_dir"):
            messagebox.showerror("Error", "Target directory must be set in config.toml")
            return
            
        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        self.sync_thread = threading.Thread(target=self.sync_worker, daemon=True)
        self.sync_thread.start()
        
    def stop_sync(self):
        self.is_running = False
        self.log("Stopping sync... please wait for the current file to finish or abort.")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
    def _scan_azure_directory(self, share_client, current_dir=""):
        """Recursively scans the Azure File Share directory and yields (relative_path, size)."""
        try:
            dir_client = share_client.get_directory_client(current_dir)
            if current_dir and not dir_client.exists():
                return
                
            for item in dir_client.list_directories_and_files():
                if not self.is_running:
                    break
                    
                item_path = f"{current_dir}/{item['name']}" if current_dir else item['name']
                
                if item["is_directory"]:
                    yield from self._scan_azure_directory(share_client, item_path)
                else:
                    yield (item_path, item["size"])
        except Exception as e:
            self.log(f"Error scanning Azure directory {current_dir}: {e}")

    def copy_file(self, share_client, file_path_str: str, target_path: Path, total_size: int):
        filename = Path(file_path_str).name
        self.log(f"Starting sync: {filename} ({(total_size / 1024 / 1024):.2f} MB)")
        
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"Failed to create directory {target_path.parent}: {e}")
            return False

        temp_dst = target_path.with_suffix(target_path.suffix + ".syncing")
        file_client = share_client.get_file_client(file_path_str)
        
        try:
            copied = 0
            
            # Using chunked streaming for large files
            stream = file_client.download_file()
            
            start_time = time.time()
            
            with open(temp_dst, "wb") as fdst:
                for chunk in stream.chunks():
                    if not self.is_running:
                        break
                    fdst.write(chunk)
                    copied += len(chunk)
                    
                    elapsed = time.time() - start_time
                    # Calculate Mbps: (bytes * 8) / 1,000,000 / seconds
                    speed_mbps = ((copied * 8) / 1000000) / elapsed if elapsed > 0 else 0
                    
                    progress = (copied / total_size) * 100 if total_size else 100
                    self.update_progress(filename, progress, speed_mbps=speed_mbps)
                    
            if self.is_running:
                if target_path.exists():
                    try:
                        target_path.unlink()
                    except Exception as e:
                        self.log(f"Warning: Could not remove old file {target_path.name}: {e}")
                temp_dst.replace(target_path)
                self.log(f"Successfully synced: {filename}")
                self.update_progress(filename, 100, done=True)
                return True
            else:
                self.log(f"Sync interrupted: {filename}")
                return False
                
        except Exception as e:
            self.log(f"Failed to copy {filename}: {e}")
            if temp_dst.exists():
                try:
                    temp_dst.unlink()
                except:
                    pass
            return False

    def sync_worker(self):
        azure_config = self.config.get("azure", {})
        sync_config = self.config.get("sync", {})
        
        conn_str = azure_config["connection_string"]
        share_name = azure_config["share_name"]
        source_dir = sync_config.get("source_dir", "").replace('\\', '/')
        target = Path(sync_config["target_dir"])
        interval = sync_config.get("scan_interval", 10)
        settle_time = sync_config.get("settle_time", 5)
        
        try:
            service_client = ShareServiceClient.from_connection_string(conn_str)
            share_client = service_client.get_share_client(share_name)
        except Exception as e:
            self.log(f"Failed to connect to Azure Storage: {e}")
            self.stop_sync()
            return
            
        file_stable_track = {}
        self.log(f"Sync worker started. Connected to share: {share_name}")
        self.log(f"Scanning every {interval}s.")
        
        while self.is_running:
            try:
                current_time = time.time()
                current_files = {}
                
                # Scan directory
                for file_path_str, current_size in self._scan_azure_directory(share_client, source_dir):
                    if not self.is_running:
                        break
                        
                    # Calculate target path relative to source_dir
                    rel_path_str = file_path_str
                    if source_dir and file_path_str.startswith(source_dir + "/"):
                        rel_path_str = file_path_str[len(source_dir) + 1:]
                        
                    target_path = target / Path(rel_path_str)
                    
                    # Check if already fully synced
                    is_synced = False
                    if target_path.exists():
                        try:
                            if target_path.stat().st_size == current_size:
                                is_synced = True
                        except Exception:
                            pass
                            
                    if is_synced:
                        continue
                    
                    # Track stability for new/modified files
                    current_files[file_path_str] = current_size
                    
                    if file_path_str not in file_stable_track:
                        file_stable_track[file_path_str] = {"size": current_size, "since": current_time}
                    else:
                        if file_stable_track[file_path_str]["size"] != current_size:
                            # File is still growing
                            file_stable_track[file_path_str] = {"size": current_size, "since": current_time}
                        else:
                            # Size is stable, ready to copy
                            if current_time - file_stable_track[file_path_str]["since"] >= settle_time:
                                success = self.copy_file(share_client, file_path_str, target_path, current_size)
                                if success and file_path_str in file_stable_track:
                                    del file_stable_track[file_path_str]
                                    
                # Clean up disappeared files from tracking state
                keys_to_remove = [k for k in file_stable_track if k not in current_files]
                for k in keys_to_remove:
                    del file_stable_track[k]
                    
            except Exception as e:
                self.log(f"Error in sync loop: {e}")
                
            self.sleep_for(interval)
            
        self.log("Sync worker stopped.")
        
    def sleep_for(self, seconds):
        """Sleep in small intervals to allow quick interruption."""
        steps = int(seconds * 10)
        for _ in range(steps):
            if not self.is_running:
                break
            time.sleep(0.1)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        # On Windows, try to scale DPI awareness for sharper UI
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    app = SyncApp(root)
    root.mainloop()
