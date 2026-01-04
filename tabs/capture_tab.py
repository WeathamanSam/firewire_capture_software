# capture_tab.py
import os
import signal
import subprocess
import datetime
import glob
import shutil  # <--- NEW: For checking disk space
import time    # <--- NEW: For file size checks
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QHBoxLayout, QGridLayout, QFrame, QMessageBox,
                             QMessageBox, QInputDialog, QLineEdit,
                             QApplication, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# Import the Dialog
from components.session_dialog import SessionDialog

# --- WATCHDOG THREAD ---
class RecordingWatchdog(QThread):
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

# --- MAIN CAPTURE DECK ---
class CaptureDeck(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config 
        
        self.preview_process = None
        self.watchdog = None 
        self.current_recording_path = None # <--- NEW: Track current file

        # Default Session Data
        self.client_fname = "Jane"
        self.client_lname = "Doe"
        self.tape_num = "01"
        self.tape_format = "mini_dv"
        self.manual_folder = "" 

        # Main Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # 1. VIDEO SCREEN
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black; border: 2px solid #333;")
        layout.addWidget(self.video_frame, stretch=1) 

        # 2. INFO LABEL
        self.info_label = QLabel("Current Session: Waiting for Setup...")
        self.info_label.setStyleSheet("color: #888; font-size: 10pt; padding: 5px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # 3. CONTROLS
        controls_layout = QHBoxLayout()
        tape_controls = QWidget()
        tape_grid = QGridLayout()
        tape_controls.setLayout(tape_grid)
        
        self.btn_rewind = QPushButton("<< REW")
        self.btn_play = QPushButton("PLAY >")
        self.btn_stop = QPushButton("STOP")
        self.btn_ff = QPushButton("FF >>")
        self.btn_record = QPushButton("🔴 REC")
        
        self.btn_record.setStyleSheet("background-color: darkred; color: white; font-weight: bold;")
        self.btn_record.setCheckable(True) 

        tape_grid.addWidget(self.btn_rewind, 0, 0)
        tape_grid.addWidget(self.btn_play, 0, 1)
        tape_grid.addWidget(self.btn_ff, 0, 2)
        tape_grid.addWidget(self.btn_stop, 1, 1)
        
        controls_layout.addWidget(tape_controls)
        controls_layout.addWidget(self.btn_record)
        
        layout.addLayout(controls_layout)

        # Connect Buttons
        self.btn_play.clicked.connect(self.play_tape)
        self.btn_stop.clicked.connect(self.stop_tape)
        self.btn_rewind.clicked.connect(self.rewind_tape)
        self.btn_ff.clicked.connect(self.ff_tape)
        self.btn_record.clicked.connect(self.toggle_record)

    def update_session_info(self, fname, lname, tape, fmt, manual_label):
        self.client_fname = fname
        self.client_lname = lname
        self.tape_num = tape
        self.tape_format = fmt
        self.manual_folder = manual_label
        
        display_text = f"Recording: {fname} {lname} | Tape {tape} | {fmt}"
        if fmt != "mini_dv":
            display_text += f" ({manual_label})"
        self.info_label.setText(display_text)

    # --- NEW: SAFETY CHECK FOR DISK SPACE ---
    def check_disk_space(self, path):
        try:
            total, used, free = shutil.disk_usage(path)
            # DV is ~13GB per hour. Warn if less than 15GB free.
            free_gb = free // (2**30)
            if free_gb < 15:
                QMessageBox.warning(self, "Low Disk Space", 
                                    f"⚠️ WARNING: Only {free_gb}GB free on drive!\n"
                                    "One MiniDV tape requires ~13GB.\n"
                                    "Recording may stop abruptly.")
                return False
            return True
        except FileNotFoundError:
            return True # Path doesn't exist yet, assume root is fine for now

    def run_command(self, cmd):
        FULL_PATH = "/usr/bin/dvcont"
        if cmd[0] == "dvcont":
            cmd[0] = FULL_PATH
        try:
            subprocess.Popen(cmd) 
        except FileNotFoundError:
            print(f"Error: Could not find {cmd[0]}")

    def play_tape(self):
        self.run_command(["dvcont", "play"]) 
        if self.preview_process is None:
            # Only start preview if not already running (prevents stacking windows)
            wid = str(int(self.video_frame.winId()))
            cmd = f"dvgrab -format raw - | mpv --wid={wid} --profile=low-latency -"
            self.preview_process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)

    def stop_tape(self):
        self.run_command(["dvcont", "stop"])
        # Only kill process if we are NOT recording. 
        # If recording, let the user stop the record button first.
        if not self.btn_record.isChecked():
            self.kill_process()

    def rewind_tape(self):
        self.run_command(["dvcont", "rewind"])

    def ff_tape(self):
        self.run_command(["dvcont", "ff"])

    def kill_process(self):
        if self.watchdog:
            self.watchdog.stop_monitoring()
            self.watchdog.wait() # Ensure thread finishes
            self.watchdog = None

        if self.preview_process:
            # Kill the whole process group (shell + dvgrab + tee + mpv)
            try:
                os.killpg(os.getpgid(self.preview_process.pid), signal.SIGTERM)
            except:
                pass
            self.preview_process = None
            self.video_frame.setStyleSheet("background-color: black; border: 2px solid #333;")

    def on_crash_detected(self):
        # Called if the pipeline dies unexpectedly (e.g., cable pulled)
        self.kill_process()
        self.btn_record.setChecked(False)
        self.btn_record.setText("🔴 REC")
        self.video_frame.setStyleSheet("border: 2px solid #333;")
        self.info_label.setText("Current Session: Waiting for Setup...")
        
        QMessageBox.critical(self, "Capture Error", 
                             "Signal Lost! The camera stopped communicating.\n"
                             "Recording has been stopped safely.")

    def get_meteorological_season(self):
        today = datetime.date.today()
        month = today.month
        year = today.year
        
        if month in [12, 1, 2]:
            start_month = 12
            start_year = year - 1 if month in [1, 2] else year
        elif month in [3, 4, 5]:
            start_month = 3
            start_year = year
        elif month in [6, 7, 8]:
            start_month = 6
            start_year = year
        else: 
            start_month = 9
            start_year = year

        end_month = (start_month + 2)
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
            
        start_str = f"{str(start_year)[2:]}{start_month:02d}"
        end_str = f"{str(end_year)[2:]}{end_month:02d}"
        return f"{start_str}_{end_str}"

    def toggle_record(self):
        # 1. STOPPING RECORDING
        if not self.btn_record.isChecked():
            self.btn_record.setText("🔴 REC")
            self.video_frame.setStyleSheet("border: 2px solid #333;")
            self.info_label.setText("Current Session: Waiting for Setup...")
            self.kill_process()

            if hasattr(self, 'tape_format') and self.tape_format == "mini_dv":
                if self.current_recording_path and os.path.exists(self.current_recording_path):
                    if os.path.getsize(self.current_recording_path) > 0:
                        self.process_autosplit()
                    else:
                        print("Warning: Master file is empty.")
                else:
                    print("Master file not found (or capture failed).")

            self.info_label.setText("Current Session: Waiting for Setup...")
            return

        # 2. STARTING RECORDING
        root_path = self.config.get("root_archive_path")
        
        # --- NEW: CHECK DISK SPACE BEFORE STARTING ---
        if not self.check_disk_space(root_path):
            self.btn_record.setChecked(False)
            return

        dialog = SessionDialog(root_path)
        if dialog.exec():
            fname, lname, tape, fmt, manual_lbl = dialog.get_data()
            self.update_session_info(fname, lname, tape, fmt, manual_lbl)
        else:
            self.btn_record.setChecked(False)
            return
        
        password, ok = QInputDialog.getText(self, "Sudo Access", "Enter Password for FireWire Access:", QLineEdit.EchoMode.Password)
        if ok and password:
            os.system(f"echo {password} | sudo -S chmod 666 /dev/fw*")
        else:
            self.btn_record.setChecked(False)
            return

        devices = glob.glob('/dev/fw*')
        if len(devices) < 2:
            self.btn_record.setChecked(False)
            self.info_label.setText("Current Session: Waiting for Setup...")
            QMessageBox.critical(self, "Connection Error", 
                                 "Camera not detected!\n\n"
                                 "My System sees the FireWire CARD, but not the CAMERA.")
            return

        season_folder = self.get_meteorological_season()
        client_folder = f"{self.client_lname.lower()}_{self.client_fname.lower()}"
        format_folder = self.tape_format

        now = datetime.datetime.now()
        yymm = now.strftime("%y%m")
        timestamp_str = now.strftime("%Y.%m.%d_%H-%M-%S")

        if self.tape_format == "mini_dv":
            final_folder = f"tape_{self.tape_num}_dv-{yymm}_{yymm}"
            filename_base = f"{self.client_lname.lower()}_{self.client_fname.lower()}_mdv_t{self.tape_num}_MASTER.dv"
        else:
            clean_label = self.manual_folder.replace(" ", "_").lower()
            final_folder = clean_label if clean_label else "manual_capture"
            filename_base = f"{self.client_lname.lower()}_{self.client_fname.lower()}_d8_t{self.tape_num}-{timestamp_str}"

        full_dir_path = os.path.join(
            root_path,
            format_folder,
            season_folder,
            client_folder,
            "dv_format",
            final_folder
        )
        
        os.makedirs(full_dir_path, exist_ok=True)
        print(f"Saving to: {full_dir_path}")

        self.current_recording_path = os.path.join(full_dir_path, filename_base) # Store for cleanup check

        self.btn_record.setText("⏹ STOP REC")
        self.video_frame.setStyleSheet("border: 2px solid red;")

        self.kill_process() 

        wid = str(int(self.video_frame.winId()))
        
        cmd = f"dvgrab --format raw - | tee {self.current_recording_path} | mpv --wid={wid} --profile=low-latency -"
        
        self.info_label.setText(f"Recording: {filename_base}")

        self.preview_process =subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)

        self.watchdog = RecordingWatchdog(self.preview_process)
        self.watchdog.crash_detected.connect(self.on_crash_detected)
        self.watchdog.start()

    def process_autosplit(self):
        master_file = self.current_recording_path

        if not self.current_recording_path or not os.path.exists(master_file):
            print("Error: Master file not found for autosplit.")
            return
        
        folder_path = os.path.dirname(master_file)
        # Base name for the split files (e.g. "lastname_firstname_mdv_t01-")
        base_name = os.path.basename(master_file).replace("_MASTER.dv", "-")

        # 1. Run dvgrab autosplit
        cmd = f'cd "{folder_path}" && dvgrab --autosplit --timestamp --size 0 --format raw -I "{master_file}" "{base_name}"'

        progress = QProgressDialog("Scanning tape for scenes...", "Abort", 0, 0, self)
        progress.setWindowTitle("Processing Scenes")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        process = subprocess.Popen(cmd, shell=True, stderr=subprocess.PIPE, text=True)

        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            if line:
                progress.setLabelText(f"Status: {line.strip()}")
                QApplication.processEvents()
            if progress.wasCanceled():
                process.terminate()
                self.info_label.setText("Autosplit Cancelled.")
                return
            
        progress.setValue(100)

        # 2. Check the output file to see if dvgrab found a date
        # dvgrab usually names the first file "...-001.dv" if it can't find a date, 
        # or "...2004.05.21_14-30-00.dv" if it can.
        
        # We look for the first split file generated
        split_files = glob.glob(os.path.join(folder_path, f"{base_name}*.dv"))
        # Exclude the master file from this list if it's still there
        split_files = [f for f in split_files if "_MASTER.dv" not in f]

        if not split_files:
            QMessageBox.warning(self, "Error", "Autosplit failed to generate any scene files.")
            return

        # Grab the first file to check its timestamp
        first_scene = split_files[0]
        
        # Helper function to check if a file has a valid digital timestamp
        def has_valid_timestamp(file_path):
            try:
                # We check for the date format YYYY.MM.DD in the filename 
                # (dvgrab puts it there automatically if it finds data)
                filename = os.path.basename(file_path)
                # Simple check: does it contain a 4 digit year starting with 19 or 20?
                if "19" in filename or "20" in filename:
                     # You could add stricter regex here if needed
                     return True
            except:
                pass
            return False

        # 3. Decision Time: Did we get a date?
        if has_valid_timestamp(first_scene):
            print("Success: Date detected automatically.")
            final_status = "Session Complete. Scenes split successfully."
        else:
            # --- THE NEW LOGIC: ASK THE USER ---
            print("Metadata missing. Prompting user...")
            
            # Play a sound or bring window to front here if you like
            
            date_str, ok = QInputDialog.getText(self, "Metadata Missing", 
                                                "The camera clock was not set for this tape.\n\n"
                                                "Please enter the date for these clips (YYYY.MM.DD):",
                                                QLineEdit.EchoMode.Normal, 
                                                "1990.01.01")
            
            if ok and date_str:
                # Rename all the split files with this manual date
                # Example: base-001.dv -> base-MANUALDATE_001.dv
                for f in split_files:
                    path, name = os.path.split(f)
                    # preserve the scene number (usually at the end like 001.dv)
                    # This logic depends slightly on how dvgrab named the undated file.
                    # Usually it is "basename001.dv"
                    
                    # We inject the date before the extension
                    new_name = name.replace(".dv", f"_{date_str}.dv")
                    new_full_path = os.path.join(path, new_name)
                    
                    try:
                        os.rename(f, new_full_path)
                    except OSError as e:
                        print(f"Rename error: {e}")
                
                final_status = f"Session Complete. Manually dated to {date_str}."
            else:
                final_status = "Session Complete. Files left undated (User Cancelled)."

        # 4. Clean up Master File
        reply = QMessageBox.question(self, 'Save Space?',
                                        f"{final_status}\n\nDo you want to DELETE the original Master file?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(master_file)
                self.info_label.setText("Master Deleted. " + final_status)
            except OSError:
                pass
        else:
            self.info_label.setText("Master Saved. " + final_status)