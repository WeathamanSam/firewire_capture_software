# diagnostics_tab.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QProgressBar, 
                             QPushButton, QHBoxLayout, QTextEdit, QGridLayout, 
                             QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

# Import Workers
from core.workers import DiagnosticWorker, InstallerWorker, ConnectionMonitorWorker

class DiagnosticsTab(QWidget):
    # Signals to tell Main Window status
    checks_finished = pyqtSignal(list) 
    camera_online = pyqtSignal(bool) # <--- NEW SIGNAL

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        self.title = QLabel("System Diagnostics & Connection Monitor")
        self.title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- TERMINAL LOG WINDOW ---
        self.log_window = QTextEdit()
        self.log_window.setReadOnly(True)
        self.log_window.setStyleSheet("""
            background-color: #1e1e1e; 
            color: #00ff00; 
            font-family: Monospace; 
            font-size: 10pt;
            border: 1px solid #444;
        """)
        self.log_window.setPlaceholderText("Initializing diagnostics...")
        
        self.progress = QProgressBar()
        self.progress.setFixedWidth(600)
        self.progress.setValue(0)
        
        # --- BUTTON GRID ---
        btn_grid = QGridLayout()
        
        self.run_btn = QPushButton("🔄 Run Full System Check")
        self.run_btn.setStyleSheet("font-size: 11pt; padding: 8px; font-weight: bold;")
        self.run_btn.clicked.connect(lambda: self.run_diagnostics('all'))

        self.fix_btn = QPushButton("🛠 Fix Issues")
        self.fix_btn.setStyleSheet("background-color: #d9534f; color: white; font-size: 11pt; padding: 8px;")
        self.fix_btn.setVisible(False)
        self.fix_btn.clicked.connect(self.run_installer)
        
        btn_grid.addWidget(self.run_btn, 0, 0, 1, 2) 
        btn_grid.addWidget(self.fix_btn, 0, 2, 1, 2) 

        # Individual Tools
        self.btn_drivers = QPushButton("Drivers")
        self.btn_hardware = QPushButton("Hardware")
        self.btn_perms = QPushButton("Permissions")
        self.btn_soft = QPushButton("Software")
        
        for btn in [self.btn_drivers, self.btn_hardware, self.btn_perms, self.btn_soft]:
            btn.setStyleSheet("padding: 5px;")
        
        self.btn_drivers.clicked.connect(lambda: self.run_diagnostics('drivers'))
        self.btn_hardware.clicked.connect(lambda: self.run_diagnostics('hardware'))
        self.btn_perms.clicked.connect(lambda: self.run_diagnostics('permissions'))
        self.btn_soft.clicked.connect(lambda: self.run_diagnostics('software'))

        btn_grid.addWidget(self.btn_soft, 1, 0)
        btn_grid.addWidget(self.btn_hardware, 1, 1)
        btn_grid.addWidget(self.btn_drivers, 1, 2)
        btn_grid.addWidget(self.btn_perms, 1, 3)

        # Monitor Button
        self.btn_monitor = QPushButton("⏹ Stop Live Monitor")
        self.btn_monitor.setStyleSheet("font-size: 11pt; padding: 8px; color: #d9534f; border: 1px solid #d9534f;")
        self.btn_monitor.clicked.connect(self.toggle_monitor)
        btn_grid.addWidget(self.btn_monitor, 2, 0, 1, 4)

        layout.addWidget(self.title)
        layout.addSpacing(10)
        layout.addWidget(self.log_window, stretch=1)
        
        prog_layout = QHBoxLayout()
        prog_layout.addStretch()
        prog_layout.addWidget(self.progress)
        prog_layout.addStretch()
        layout.addLayout(prog_layout)

        layout.addSpacing(20)
        layout.addLayout(btn_grid)
        layout.addSpacing(10)
        
        self.setLayout(layout)
        self.missing_items = []
        self.monitor_worker = None
        
        # --- AUTO START MONITOR ---
        self.toggle_monitor()

    def log(self, message):
        self.log_window.append(message)
        sb = self.log_window.verticalScrollBar()
        sb.setValue(sb.maximum())

    def parse_monitor_status(self, message):
        """Intercepts log messages to detect camera status."""
        self.log(message) # Still log it to screen
        
        if "CONNECTED" in message:
            self.camera_online.emit(True)
        elif "NO CARD" in message or "STANDBY" in message:
            self.camera_online.emit(False)

    def run_diagnostics(self, mode):
        self.run_btn.setEnabled(False)
        self.fix_btn.setVisible(False)
        self.progress.setValue(0)
        
        # Remove self.root_dir reference
        self.worker = DiagnosticWorker(mode=mode)
        self.worker.progress_update.connect(self.progress.setValue)
        self.worker.status_update.connect(self.log)
        self.worker.finished.connect(self.on_diagnostics_finished)
        self.worker.start()

    def toggle_monitor(self):
        if self.monitor_worker is None:
            # START MONITOR
            self.monitor_worker = ConnectionMonitorWorker()
            # CHANGED: Connect to parser instead of direct log
            self.monitor_worker.status_update.connect(self.parse_monitor_status)
            self.monitor_worker.start()
            
            self.btn_monitor.setText("⏹ Stop Live Monitor")
            self.btn_monitor.setStyleSheet("font-size: 11pt; padding: 8px; color: #d9534f; border: 1px solid #d9534f;")
        else:
            # STOP MONITOR
            self.monitor_worker.stop()
            self.monitor_worker.wait()
            self.monitor_worker = None
            
            self.btn_monitor.setText("🔴 Start Live Camera Connection Monitor")
            self.btn_monitor.setStyleSheet("font-size: 11pt; padding: 8px; color: #4CAF50; border: 1px solid #4CAF50;")

    def on_diagnostics_finished(self, success, missing_items):
        self.run_btn.setEnabled(True)
        if self.worker.mode == 'all':
            self.checks_finished.emit(missing_items)
            self.missing_items = missing_items 

            if success:
                self.log("\n✅ [RESULT] SYSTEM READY! All checks passed.")
            else:
                self.log("\n⚠️ [RESULT] ISSUES DETECTED.")
                if any(x not in ["FireWire Hardware"] for x in missing_items):
                    self.fix_btn.setVisible(True)

    def run_installer(self):
        self.fix_btn.setEnabled(False)
        self.fix_btn.setText("Installing... (Check Popups)")
        self.log("\n>>> STARTING INSTALLER...")
        
        self.installer = InstallerWorker(self.missing_items)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()

    def on_install_finished(self, success, message):
        if success:
            QMessageBox.information(self, "Success", "Installation Complete. Re-running diagnostics...")
            self.fix_btn.setVisible(False)
            self.run_diagnostics('all') 
        else:
            self.log(f"[ERROR] Installation Failed: {message}")
            QMessageBox.critical(self, "Error", f"Installation Failed: {message}")
            self.fix_btn.setText("Retry Fix")
            self.fix_btn.setEnabled(True)