# main.py
import sys
import locale 
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QMessageBox)

# --- IMPORT MODULES ---
from core.config_manager import ConfigManager 
from core.workers import DiagnosticWorker 
from tabs.capture_tab import CaptureDeck
from tabs.converter_tab import ConverterTab
from tabs.diagnostics_tab import DiagnosticsTab
from tabs.info_tabs import WelcomeTab, HelpTab, FeedbackTab
from components.tour_config import setup_tour

# Locale fix for MPV
locale.setlocale(locale.LC_NUMERIC, 'C')

class RetroReelApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RetroReel: FireWire Capture Suite")
        self.resize(1000, 750)
        
        self.cfg = ConfigManager()
        self.tour = None 
        
        # --- SEPARATED STATE TRACKING ---
        self.drivers_ok = False       # FireWire Card/Driver status
        self.software_ok = False      # FFmpeg/Converter status
        self.camera_connected = False # Physical Plug status

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { height: 40px; padding: 10px; font-size: 10pt; }
            QTabBar::tab:selected { font-weight: bold; }
            QTabBar::tab:disabled { color: #888; background: #e0e0e0; }
        """)
        self.setCentralWidget(self.tabs)

        # Build Tabs
        self.welcome_tab = WelcomeTab()
        self.diag_tab = DiagnosticsTab()
        self.capture_tab = CaptureDeck(self.cfg) 
        self.converter_tab = ConverterTab(self.cfg) 
        self.help_tab = HelpTab(self) 
        self.feedback_tab = FeedbackTab()

        self.tabs.addTab(self.welcome_tab, "🏠 Welcome")
        self.tabs.addTab(self.diag_tab, "🔍 Diagnostics")
        self.tabs.addTab(self.capture_tab, "🔴 Capture Deck")
        self.tabs.addTab(self.converter_tab, "🎞️ Post-Process") 
        self.tabs.addTab(self.help_tab, "❓ Help")
        self.tabs.addTab(self.feedback_tab, "💬 Feedback")

        # --- CONNECTIONS ---
        self.diag_tab.checks_finished.connect(self.handle_diagnostic_results)
        self.diag_tab.camera_online.connect(self.handle_camera_status)
        
        # NEW: Connect Capture Tab finish signal to the Auto-Switcher
        self.capture_tab.session_finished.connect(self.on_capture_session_finished)

        self.update_tab_locks()
        self.diag_tab.run_diagnostics('all')

        if self.cfg.get("show_startup_tutorial"):
            QTimer.singleShot(2000, self.launch_active_tour)

    def launch_active_tour(self):
        self.tour = setup_tour(self)
        self.tour.tour_finished.connect(self.update_tab_locks)
        self.tour.start()
        self.cfg.set("show_startup_tutorial", False)

    def update_tab_locks(self):
        """Manages tab availability independently."""
        
        # --- 1. CAPTURE TAB LOGIC ---
        # Needs BOTH Hardware Drivers AND a Physical Connection
        capture_ready = self.drivers_ok and self.camera_connected
        self.tabs.setTabEnabled(2, capture_ready)
        
        if capture_ready:
            self.tabs.setTabIcon(2, self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))
            self.tabs.setTabToolTip(2, "Ready to Capture")
        elif not self.drivers_ok:
            self.tabs.setTabToolTip(2, "LOCKED: Driver/Hardware issues detected.")
        else:
            self.tabs.setTabToolTip(2, "LOCKED: Please plug in your camera.")

        # --- 2. CONVERTER TAB LOGIC ---
        # ONLY needs the software (FFmpeg) installed. Camera status is ignored here.
        self.tabs.setTabEnabled(3, self.software_ok)
        
        if self.software_ok:
            self.tabs.setTabIcon(3, self.style().standardIcon(self.style().StandardPixmap.SP_DialogApplyButton))
            self.tabs.setTabToolTip(3, "Ready to Convert (Camera not required)")
        else:
            self.tabs.setTabIcon(3, self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxCritical))
            self.tabs.setTabToolTip(3, "LOCKED: Missing FFmpeg. Run Diagnostics to fix.")

    def handle_diagnostic_results(self, missing_items):
        cat = DiagnosticWorker.CATEGORIES
        
        # If any item from 'capture' is missing, drivers_ok is False
        self.drivers_ok = not any(item in missing_items for item in cat['capture'])
        
        # If any item from 'converter' is missing, software_ok is False
        self.software_ok = not any(item in missing_items for item in cat['converter'])
        
        self.update_tab_locks()

    def handle_camera_status(self, is_connected):
        # Called by the Live Monitor in the Diagnostics tab
        self.camera_connected = is_connected
        self.update_tab_locks()

    def on_capture_session_finished(self, folder_path):
        """Called when a tape finishes recording/splitting."""
        # 1. Unlock converter tab just in case
        if not self.tabs.isTabEnabled(3):
             QMessageBox.warning(self, "Missing Software", "Capture finished, but FFmpeg is missing.\nCannot start conversion.")
             return

        # 2. Switch to Converter Tab
        self.tabs.setCurrentIndex(3)
        
        # 3. Automatically start the conversion process for the new folder
        self.converter_tab.start_conversion(folder_path)
        
        QMessageBox.information(self, "Session Complete", 
                                f"Capture successful!\n\nStarting automated conversion for:\n{folder_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = RetroReelApp()
    window.show()
    sys.exit(app.exec())
