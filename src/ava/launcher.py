# src/ava/launcher.py
import json
import os
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from tkinter import Tk, Label, PhotoImage
from tkinter.ttk import Progressbar

# --- Configuration ---
VERSION_MANIFEST_URL = "https://raw.githubusercontent.com/carpsesdema/AvA_Kintsugi/main/version_manifest.json"
CURRENT_VERSION_FILE = "version.txt"
MAIN_EXECUTABLE = "Avakin.exe"


def get_current_dir():
    """Gets the directory of the running executable."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        # For running the launcher from source for testing
        return Path(__file__).parent.parent.parent / "dist_test"


class Launcher(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Avakin Launcher")
        self.geometry("400x200")
        self.resizable(False, False)
        self.configure(bg="#161b22")

        # Centering the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        self.status_label = Label(self, text="Checking for updates...", fg="#f0f6fc", bg="#161b22",
                                  font=("Segoe UI", 10))
        self.status_label.pack(pady=20)

        self.progress_bar = Progressbar(self, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.pack(pady=10)

        self.after(100, self.start_check)

    def set_status(self, text):
        self.status_label.config(text=text)
        self.update_idletasks()

    def start_check(self):
        # Run the update check in a separate thread to keep the GUI responsive
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        try:
            self.set_status("Checking for updates...")
            # 1. Get local version
            local_version = "0.0.0"
            version_file_path = get_current_dir() / CURRENT_VERSION_FILE
            if version_file_path.exists():
                local_version = version_file_path.read_text().strip()

            # 2. Get remote version
            with urllib.request.urlopen(VERSION_MANIFEST_URL) as response:
                manifest = json.loads(response.read().decode())
            remote_version = manifest["latest_version"]
            download_url = manifest["download_url"]

            self.set_status(f"Local: v{local_version} | Latest: v{remote_version}")

            # 3. Compare and update if needed
            if remote_version > local_version:
                self.set_status(f"Downloading update v{remote_version}...")
                self.update_application(download_url, remote_version)
            else:
                self.set_status("Application is up to date.")
                self.launch_application()

        except Exception as e:
            self.set_status(f"Error: {e}")
            # If there's an error, try to launch what we have
            self.after(2000, self.launch_application)

    def update_application(self, url, new_version):
        try:
            app_dir = get_current_dir()
            zip_path = app_dir / "update.zip"

            # Download the update
            with urllib.request.urlopen(url) as response, open(zip_path, 'wb') as out_file:
                total_length = int(response.info().get('Content-Length'))
                chunk_size = 8192
                downloaded = 0
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    self.progress_bar['value'] = (downloaded / total_length) * 100
                    self.update_idletasks()

            self.set_status("Download complete. Installing update...")

            # Kill main app if it's running
            try:
                subprocess.run(["taskkill", "/F", "/IM", MAIN_EXECUTABLE], check=False, capture_output=True)
            except Exception:
                pass  # Ignore if it fails (app might not be running)

            # Unzip the update
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # This will overwrite existing files
                zip_ref.extractall(app_dir)

            # Clean up
            os.remove(zip_path)

            # Update local version file
            version_file_path = app_dir / CURRENT_VERSION_FILE
            version_file_path.write_text(new_version)

            self.set_status("Update successful!")
            self.launch_application()

        except Exception as e:
            self.set_status(f"Update failed: {e}")
            self.after(2000, self.launch_application)

    def launch_application(self):
        try:
            main_app_path = get_current_dir() / MAIN_EXECUTABLE
            if main_app_path.exists():
                self.set_status("Launching Avakin...")
                # Use Popen to launch and forget
                subprocess.Popen([str(main_app_path)], cwd=get_current_dir())
                self.after(500, self.destroy)  # Close launcher after starting app
            else:
                self.set_status(f"Error: {MAIN_EXECUTABLE} not found!")
        except Exception as e:
            self.set_status(f"Failed to launch: {e}")


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()