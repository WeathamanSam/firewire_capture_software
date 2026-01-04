# capture_tab.py
import os
import signal
import subprocess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QHBoxLayout, QGridLayout, QFrame, QMessageBox,
                             QInputDialog, QLineEdit, QProgressDialog)
from PyQt6.QtCore import Qt

# --- NEW IMPORTS ---
from components.session_dialog import SessionDialog
from core.capture_manager import CaptureManager
from core.workers import RecordingWatchdog, AutosplitWorker

class CaptureDeck(QWidget):
    def __init__(self, config):
        super().__init__()
        # Use the new Manager for logic
        self.manager = CaptureManager(config)
        
        self.preview_process = None
        self.watchdog = None 
        self.current_recording_path = None 

        # Default Session Data (fname, lname, tape, format, manual_label)
        self.session_data = ("Jane", "Doe", "01", "mini_dv", "") 

        self.setup_ui()

    def setup_ui(self):
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

        # Connect Buttons via Manager
        self.btn_play.clicked.connect(self.play_tape)
        self.btn_stop.clicked.connect(self.stop_tape)
        self.btn_rewind.clicked.connect(lambda: self.manager.run_tape_control("rewind"))
        self.btn_ff.clicked.connect(lambda: self.manager.run_tape_control("ff"))
        self.btn_record.clicked.connect(self.toggle_record)

    def update_session_display(self, fname, lname, tape, fmt, manual_label):
        self.session_data = (fname, lname, tape, fmt, manual_label)
        display_text = f"Recording: {fname} {lname} | Tape {tape} | {fmt}"
        if fmt != "mini_dv":
            display_text += f" ({manual_label})"
        self.info_label.setText(display_text)

    # --- TAPE CONTROL HANDLERS ---
    def play_tape(self):
        self.manager.run_tape_control("play")
        # Only start preview if not already running
        if self.preview_process is None:
            cmd = self.manager.get_preview_command(int(self.video_frame.winId()))
            self.start_process(cmd)

    def stop_tape(self):
        self.manager.run_tape_control("stop")
        # Only kill process if we are NOT recording
        if not self.btn_record.isChecked():
            self.kill_process()

    def start_process(self, cmd_str):
        # Starts a process and attaches setsid so we can kill the whole group later
        self.preview_process = subprocess.Popen(cmd_str, shell=True, preexec_fn=os.setsid)

    def kill_process(self):
        if self.watchdog:
            self.watchdog.stop_monitoring()
            self.watchdog.wait()
            self.watchdog = None

        if self.preview_process:
            try:
                os.killpg(os.getpgid(self.preview_process.pid), signal.SIGTERM)
            except:
                pass
            self.preview_process = None
            self.video_frame.setStyleSheet("background-color: black; border: 2px solid #333;")

    def on_crash_detected(self):
        self.kill_process()
        self.btn_record.setChecked(False)
        self.btn_record.setText("🔴 REC")
        self.video_frame.setStyleSheet("border: 2px solid #333;")
        self.info_label.setText("Current Session: Waiting for Setup...")
        QMessageBox.critical(self, "Capture Error", "Signal Lost! Recording stopped safely.")

    # --- RECORDING LOGIC ---
    def toggle_record(self):
        # 1. STOPPING RECORDING
        if not self.btn_record.isChecked():
            self.btn_record.setText("🔴 REC")
            self.video_frame.setStyleSheet("border: 2px solid #333;")
            self.info_label.setText("Current Session: Waiting for Setup...")
            self.kill_process()

            # Check if we should split (Only for MiniDV usually)
            if self.session_data[3] == "mini_dv":
                if self.current_recording_path and os.path.exists(self.current_recording_path):
                    if os.path.getsize(self.current_recording_path) > 0:
                        self.process_autosplit()
                    else:
                        print("Warning: Master file is empty.")
            return

        # 2. STARTING RECORDING
        is_safe, free_gb = self.manager.check_disk_space()
        if not is_safe:
            QMessageBox.warning(self, "Low Disk Space", f"⚠️ WARNING: Only {free_gb}GB free!\nRecording may stop abruptly.")
            # We allow them to continue if they want, or we could return here.

        dialog = SessionDialog(self.manager.config.get("root_archive_path"))
        if dialog.exec():
            # Get data tuple and update UI
            data = dialog.get_data() 
            self.update_session_display(*data)
        else:
            self.btn_record.setChecked(False)
            return
        
        # Sudo check for FireWire permissions
        password, ok = QInputDialog.getText(self, "Sudo Access", "Enter Password for FireWire Access:", QLineEdit.EchoMode.Password)
        if ok and password:
            os.system(f"echo {password} | sudo -S chmod 666 /dev/fw*")
        else:
            self.btn_record.setChecked(False)
            return

        # Setup Paths via Manager
        dir_path, full_path, filename = self.manager.generate_paths(self.session_data)
        os.makedirs(dir_path, exist_ok=True)
        self.current_recording_path = full_path

        # Update UI for Recording
        self.btn_record.setText("⏹ STOP REC")
        self.video_frame.setStyleSheet("border: 2px solid red;")
        self.kill_process() # Stop any existing preview

        # Start Recording Process
        cmd = self.manager.get_capture_command(full_path, int(self.video_frame.winId()))
        self.info_label.setText(f"Recording: {filename}")
        
        self.start_process(cmd)
        
        # Start Watchdog
        self.watchdog = RecordingWatchdog(self.preview_process)
        self.watchdog.crash_detected.connect(self.on_crash_detected)
        self.watchdog.start()

    # --- AUTOSPLIT LOGIC ---
    def process_autosplit(self):
        master_file = self.current_recording_path
        cmd = self.manager.get_autosplit_command(master_file)

        # UI: Progress Dialog
        self.progress = QProgressDialog("Scanning tape for scenes...", "Abort", 0, 0, self)
        self.progress.setWindowTitle("Processing Scenes")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)

        # Worker: Handles the blocking process
        self.splitter = AutosplitWorker(master_file, cmd)
        self.splitter.status_update.connect(lambda msg: self.progress.setLabelText(f"Status: {msg}"))
        self.splitter.finished.connect(self.on_autosplit_finished)
        self.progress.canceled.connect(self.splitter.cancel)
        
        self.splitter.start()

    def on_autosplit_finished(self):
        self.progress.setValue(100)
        master_file = self.current_recording_path
        split_files = self.manager.find_split_files(master_file)

        if not split_files:
            QMessageBox.warning(self, "Error", "Autosplit failed to generate any scene files.")
            return

        # Date Check
        if self.manager.has_valid_timestamp(split_files[0]):
            final_status = "Session Complete. Scenes split successfully."
        else:
            # Metadata missing logic
            date_str, ok = QInputDialog.getText(self, "Metadata Missing", 
                                                "Camera clock was missing.\nEnter date (YYYY.MM.DD):",
                                                QLineEdit.EchoMode.Normal, "1990.01.01")
            if ok and date_str:
                self.manager.batch_rename_files(split_files, date_str)
                final_status = f"Session Complete. Manually dated to {date_str}."
            else:
                final_status = "Session Complete. Files left undated."

        # Master Cleanup
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
