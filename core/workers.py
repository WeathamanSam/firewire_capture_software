# core/workers.py
import shutil
import subprocess
import os
import re 
import datetime
import glob
import time
import hashlib
from PyQt6.QtCore import QThread, pyqtSignal

# --- DIAGNOSTICS WORKER (UNCHANGED) ---
class DiagnosticWorker(QThread):
    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    finished = pyqtSignal(bool, list)

    CATEGORIES = {
        'capture': ['dvgrab', 'firewire_ohci (Driver)', 'video_group_permission', 'FireWire Hardware'],
        'converter': ['ffmpeg', 'mpv', 'ffprobe']
    }

    def __init__(self, mode='all'):
        super().__init__()
        self.mode = mode

    def run(self):
        missing_items = []
        to_check = self.CATEGORIES['capture'] + self.CATEGORIES['converter'] if self.mode == 'all' else self.CATEGORIES.get(self.mode, [])
        
        for i, item in enumerate(to_check):
            self.status_update.emit(f"Checking: {item}...")
            found = False
            if item == 'firewire_ohci (Driver)':
                res = subprocess.run(['lsmod'], capture_output=True, text=True)
                found = 'firewire_ohci' in res.stdout
            elif item == 'video_group_permission':
                res = subprocess.run(['groups'], capture_output=True, text=True)
                found = 'video' in res.stdout
            elif item == 'FireWire Hardware':
                found = len(glob.glob('/dev/fw*')) > 0
            else:
                found = shutil.which(item) is not None
            
            if not found: missing_items.append(item)
            self.progress_update.emit(int(((i + 1) / len(to_check)) * 100))
        
        self.finished.emit(len(missing_items) == 0, missing_items)

# --- CONVERTER WORKER (UNCHANGED) ---
class ConverterWorker(QThread):
    log_message = pyqtSignal(str)
    progress_update = pyqtSignal(int)
    finished = pyqtSignal(bool)

    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = root_dir.rstrip(os.sep) 
        self.is_running = True
        self.start_time = None

    def generate_checksum(self, filename):
        hash_md5 = hashlib.md5()
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def extract_file_info(self, filename):
        # Extract customer info and date-group from filename
        pattern = r"(.+)-(\d{4}\.\d{2}\.\d{2}_\d{2}-\d{2}-\d{2})\.dv"
        match = re.search(pattern, filename)
        if match:
            group_base = match.group(1) # e.g., quivey_lara_mdv_t01
            raw_ts = match.group(2)
            dt_object = datetime.datetime.strptime(raw_ts, "%Y.%m.%d_%H-%M-%S")
            iso_ts = raw_ts.replace(".", "-").replace("_", "T").replace("-", ":", 2)
            return group_base, dt_object, iso_ts
        return os.path.splitext(filename)[0], None, None

    def run(self):
        self.start_time = time.time()
        
        # --- PATH MAPPING ---
        tape_dv_folder = os.path.basename(self.root_dir)
        dv_format_dir = os.path.dirname(self.root_dir)
        client_dir = os.path.dirname(dv_format_dir)
        
        # Customer Name and Format for Report
        customer_name = os.path.basename(client_dir)
        media_format = os.path.basename(os.path.dirname(os.path.dirname(client_dir)))

        # Pivot to mp4_format
        mp4_tape_name = tape_dv_folder.replace("_dv-", "_mp4-") if "_dv-" in tape_dv_folder else f"{tape_dv_folder}_mp4"
        dest_base = os.path.join(client_dir, "mp4_format", mp4_tape_name)

        dv_files = sorted([os.path.join(self.root_dir, f) for f in os.listdir(self.root_dir) if f.lower().endswith(".dv")])
        if not dv_files:
            self.log_message.emit("ERROR: No .dv files found.")
            return

        files_by_group = {}
        stats = {"converted": 0, "skipped": 0}

        MAX_GAP = datetime.timedelta(hours=2)
        current_group_name = None
        last_dt = None

        # 1. CONVERSION
        for i, input_path in enumerate(dv_files):
            if not self.is_running: break
            
            filename_raw = os.path.basename(input_path)
            tape_prefix, dt_object, iso_metadata = self.extract_file_info(filename_raw)

            if dt_object:
                if last_dt is None or (dt_object - last_dt) > MAX_GAP:
                    date_str = dt_object.strftime("%Y-%m-%d")
                    current_group_name = f"{tape_prefix}-{date_str}"

                last_dt = dt_object
            else:
                current_group_name = tape_prefix
            
            output_dir = os.path.join(dest_base, current_group_name)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, os.path.splitext(filename_raw)[0] + ".mp4")

            if current_group_name not in files_by_group: files_by_group[current_group_name] = []
            files_by_group[current_group_name].append({'path': output_path, 'meta': iso_metadata, 'orig': filename_raw})

            if os.path.exists(output_path):
                self.log_message.emit(f"Skipping: {filename_raw}")
                stats["skipped"] += 1
            else:
                self.log_message.emit(f"Converting ({i+1}/{len(dv_files)}): {filename_raw}")
                cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", input_path, 
                       "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-vf", "yadif,format=yuv420p",
                       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]
                if iso_metadata: cmd += ["-metadata", f"creation_time={iso_metadata}"]
                cmd.append(output_path)
                subprocess.run(cmd, check=True)
                stats["converted"] += 1
            
            self.progress_update.emit(int(((i + 1) / len(dv_files)) * 80))

        # 2. STITCHING & DETAILED REPORT
        if self.is_running:
            # Report name format: quivey_lara_mdv_t01_transfer_report.txt
            report_filename = f"{tape_dv_folder}_transfer_report.txt"
            report_path = os.path.join(dest_base, report_filename)
            
            total_duration = str(datetime.timedelta(seconds=int(time.time() - self.start_time)))

            with open(report_path, "w") as report:
                report.write("==========================================\n")
                report.write("      RETROREEL DIGITIZATION REPORT       \n")
                report.write("==========================================\n\n")
                report.write(f"CUSTOMER: {customer_name.replace('_', ' ').title()}\n")
                report.write(f"FORMAT:   {media_format.upper()}\n")
                report.write(f"TAPE ID:  {tape_dv_folder}\n")
                report.write(f"DATE:     {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                report.write(f"DURATION: {total_duration} (H:M:S)\n\n")
                report.write(f"STATS: {stats['converted']} Converted, {stats['skipped']} Skipped\n")
                report.write("-" * 42 + "\n\n")
                
                for current_group_name in sorted(files_by_group.keys()):
                    merged_path = os.path.join(dest_base, f"{current_group_name}.mp4")
                    
                    if not os.path.exists(merged_path):
                        entries = files_by_group[current_group_name]
                        if len(entries) > 1:
                            list_txt = os.path.join(dest_base, "list.txt")
                            with open(list_txt, "w") as f:
                                for e in entries: f.write(f"file '{e['path']}'\n")
                            subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_txt, "-c", "copy", "-y", merged_path], check=True)
                            os.remove(list_txt)
                        else:
                            shutil.copy2(entries[0]['path'], merged_path)

                    report.write(f"OUTPUT FILE: {current_group_name}.mp4\n")
                    report.write(f"  - MD5 Hash: {self.generate_checksum(merged_path)}\n")
                    report.write(f"  - Clips Combined: {len(files_by_group[current_group_name])}\n")
                    report.write("-" * 20 + "\n")

            self.log_message.emit(f"SUCCESS: Report saved as {report_filename}")
        
        self.progress_update.emit(100)
        self.finished.emit(True)

# --- MONITOR & INSTALLER (UNCHANGED) ---
class ConnectionMonitorWorker(QThread):
    status_update = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.is_running = True
    def stop(self): self.is_running = False
    def run(self):
        last_state = None
        while self.is_running:
            devices = glob.glob('/dev/fw*')
            state = "CONNECTED" if len(devices) > 1 else "STANDBY" if len(devices) == 1 else "NO_CARD"
            if state != last_state:
                self.status_update.emit(f"Status: {state}")
                last_state = state
            time.sleep(1)

class InstallerWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, missing_items):
        super().__init__()
        self.missing_items = missing_items
    def run(self):
        try:
            apt_tools = [t for t in self.missing_items if t not in ["firewire_ohci (Driver)", "video_group_permission", "FireWire Hardware"]]
            if apt_tools: subprocess.run(["pkexec", "apt-get", "install", "-y"] + apt_tools, check=True)
            self.finished.emit(True, "Success")
        except Exception as e: self.finished.emit(False, str(e))

# --- NEW ADDITIONS (MOVED FROM CAPTURE TAB) ---

class RecordingWatchdog(QThread):
    """Monitors the recording process. Emits crash_detected if it dies."""
    crash_detected = pyqtSignal()
    
    def __init__(self, process):
        super().__init__()
        self.process = process
        self.is_active = True
        
    def run(self):
        while self.is_active:
            # If the process stops running (returns a code), emit crash signal
            if self.process.poll() is not None:
                if self.is_active: 
                    self.crash_detected.emit()
                return
            self.msleep(500)
            
    def stop_monitoring(self):
        self.is_active = False

class AutosplitWorker(QThread):
    """Handles the blocking dvgrab autosplit process."""
    status_update = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, master_file, cmd):
        super().__init__()
        self.master_file = master_file
        self.cmd = cmd
        self.process = None
        self.is_running = True

    def run(self):
        # Run dvgrab command
        self.process = subprocess.Popen(self.cmd, shell=True, stderr=subprocess.PIPE, text=True)
        
        while self.is_running:
            line = self.process.stderr.readline()
            if not line and self.process.poll() is not None:
                break
            if line:
                self.status_update.emit(line.strip())
        
        self.finished.emit()

    def cancel(self):
        self.is_running = False
        if self.process:
            self.process.terminate()
