# session_dialog.py
import os
import glob
import re
from PyQt6.QtWidgets import (QDialog, QFormLayout, QComboBox, QLineEdit, 
                             QLabel, QDialogButtonBox)
from PyQt6.QtCore import Qt

class SessionDialog(QDialog):
    # CHANGED: Added root_path argument to __init__
    def __init__(self, root_path):
        super().__init__()
        self.setWindowTitle("New Session Setup")
        self.resize(450, 250)
        
        self.root_path = root_path # Store the dynamic path
        
        layout = QFormLayout()
        self.setLayout(layout)
        
        # --- THE MAPPING ---
        self.format_map = {
            "MiniDV":   "mini_dv",
            "Digital8": "digital_8",
            "Hi8":      "hi_8",
            "Video8":   "video_8"
        }
        
        # 1. FORMAT SELECTION
        self.format_combo = QComboBox()
        self.format_combo.addItems(self.format_map.keys())
        self.format_combo.currentTextChanged.connect(self.on_input_changed)
        
        # 2. STANDARD INPUTS
        self.fname = QLineEdit()
        self.fname.setPlaceholderText("First Name")
        self.lname = QLineEdit()
        self.lname.setPlaceholderText("Last Name")
        self.tape = QLineEdit("01")
        
        # 3. MANUAL FOLDER INPUT 
        self.manual_label_input = QLineEdit()
        self.manual_label_input.setPlaceholderText("e.g. 1998_Summer (Optional)")
        self.manual_label_label = QLabel("Tape Label/Date:")
        
        # 4. STATUS LABEL
        self.status_label = QLabel("Enter client name to scan for existing tapes.")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 9pt;")
        self.status_label.setWordWrap(True)

        # Add Rows
        layout.addRow("Tape Format:", self.format_combo)
        layout.addRow("First Name:", self.fname)
        layout.addRow("Last Name:", self.lname)
        layout.addRow("Tape Number:", self.tape)
        layout.addRow(self.manual_label_label, self.manual_label_input)
        layout.addRow("", self.status_label) 
        
        # LOGIC CONNECTIONS
        self.fname.textChanged.connect(self.suggest_next_tape)
        self.lname.textChanged.connect(self.suggest_next_tape)
        self.tape.textChanged.connect(self.check_collision)
        self.format_combo.currentTextChanged.connect(self.toggle_manual_input)

        # OK / Cancel
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
        self.toggle_manual_input("MiniDV")

    def toggle_manual_input(self, text):
        if text == "MiniDV":
            self.manual_label_input.setVisible(False)
            self.manual_label_label.setVisible(False)
        else:
            self.manual_label_input.setVisible(True)
            self.manual_label_label.setVisible(True)
        self.suggest_next_tape()

    def get_base_path(self):
        # CHANGED: Uses self.root_path instead of hardcoded ~/Desktop
        fmt_folder = self.format_map[self.format_combo.currentText()]
        return os.path.join(self.root_path, fmt_folder)

    def suggest_next_tape(self):
        f_text = self.fname.text().strip().lower()
        l_text = self.lname.text().strip().lower()

        if not f_text or not l_text:
            self.status_label.setText("Enter full name to check history.")
            self.status_label.setStyleSheet("color: #666;")
            return

        client_folder_name = f"{l_text}_{f_text}"
        base = self.get_base_path()
        
        # Pattern to find client folder in any season: .../mini_dv/*/quivey_lara
        search_pattern = os.path.join(base, "*", client_folder_name)
        found_client_dirs = glob.glob(search_pattern)

        if not found_client_dirs:
            self.tape.setText("01")
            self.status_label.setText("New Client. Starting at Tape 01.")
            self.status_label.setStyleSheet("color: green;")
            return

        max_tape = 0
        tape_pattern = re.compile(r"tape_(\d+)", re.IGNORECASE)

        for client_dir in found_client_dirs:
            for root, dirs, files in os.walk(client_dir):
                for d in dirs:
                    match = tape_pattern.search(d)
                    if match:
                        num = int(match.group(1))
                        if num > max_tape: max_tape = num
                for f in files:
                    match = tape_pattern.search(f)
                    if match:
                        num = int(match.group(1))
                        if num > max_tape: max_tape = num

        next_tape = max_tape + 1
        self.tape.setText(f"{next_tape:02d}")
        self.status_label.setText(f"Found existing records. Next Tape: {next_tape:02d}")
        self.status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        
        self.check_collision()

    def check_collision(self):
        f_text = self.fname.text().strip().lower()
        l_text = self.lname.text().strip().lower()
        tape_num = self.tape.text().strip()
        
        if not f_text or not l_text or not tape_num:
            return

        base = self.get_base_path()
        client_folder_name = f"{l_text}_{f_text}"
        search_pattern = os.path.join(base, "*", client_folder_name)
        found_client_dirs = glob.glob(search_pattern)
        
        collision_found = False
        check_pattern = re.compile(rf"(?:tape_|t|_t)({tape_num})\b", re.IGNORECASE)

        for client_dir in found_client_dirs:
            for root, dirs, files in os.walk(client_dir):
                for d in dirs:
                    if check_pattern.search(d):
                        collision_found = True
                for f in files:
                    if check_pattern.search(f):
                        collision_found = True

        if collision_found:
            self.status_label.setText(f"⚠️ WARNING: Tape {tape_num} already exists!")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            if "WARNING" in self.status_label.text():
                 self.status_label.setText("Tape number valid.")
                 self.status_label.setStyleSheet("color: green;")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def on_input_changed(self):
        self.suggest_next_tape()

    def get_data(self):
        user_choice = self.format_combo.currentText()
        system_format = self.format_map[user_choice]
        return (self.fname.text(), self.lname.text(), self.tape.text(), 
                system_format, self.manual_label_input.text())