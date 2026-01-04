# converter_tab.py
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QProgressBar, QTextEdit, QFileDialog)
from PyQt6.QtCore import Qt
from core.workers import ConverterWorker

class ConverterTab(QWidget):
    # CHANGED: Added config argument to __init__
    def __init__(self, config):
        super().__init__()
        self.config = config # Store config
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Header
        self.lbl_title = QLabel("DV Batch Post-Processor")
        self.lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #888;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Instruction
        self.lbl_instruct = QLabel("Select a specific 'Tape Folder' (containing .dv files) to begin.")
        self.lbl_instruct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_instruct)

        # Select Button
        self.btn_select = QPushButton("📂 Select Folder & Start Conversion")
        self.btn_select.setMinimumHeight(50)
        self.btn_select.setStyleSheet("font-size: 12pt;")
        self.btn_select.clicked.connect(self.select_folder)
        layout.addWidget(self.btn_select)

        # Progress Bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Log Window
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("background-color: #111; color: #0f0; font-family: Monospace;")
        layout.addWidget(self.log_window)

        # Worker placeholder
        self.worker = None

    def log(self, message):
        self.log_window.append(message)

    def select_folder(self):
        # CHANGED: Uses config path as start location
        start_path = self.config.get("root_archive_path")
        folder = QFileDialog.getExistingDirectory(self, "Select DV Tape Folder", start_path)
        
        if folder:
            self.start_conversion(folder)

    def start_conversion(self, folder):
        self.btn_select.setEnabled(False)
        self.log_window.clear()
        self.log(f"Process started for: {folder}")
        
        self.worker = ConverterWorker(folder)
        self.worker.log_message.connect(self.log)
        self.worker.progress_update.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self):
        self.btn_select.setEnabled(True)
        self.log("--- JOB COMPLETE ---")