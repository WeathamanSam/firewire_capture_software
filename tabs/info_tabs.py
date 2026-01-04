# info_tabs.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QFormLayout, QLineEdit, QHBoxLayout, QFrame)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont

class WelcomeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("Welcome to RetroReel")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        sub = QLabel("The Professional FireWire Archival Suite")
        sub.setStyleSheet("color: #888; font-size: 14pt;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        
        # Instruction Text
        info = QLabel(
            "\n\nRetroReel simplifies the transfer of legacy MiniDV and Hi8 tapes.\n"
            "This tool handles the entire pipeline: from hardware checks to digital stitching.\n\n"
            "To get started, please run the **Diagnostics** tab to ensure your hardware is ready."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size: 12pt; padding: 20px; line-height: 1.5;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        layout.addStretch()

class HelpTab(QWidget):
    def __init__(self, main_app_ref):
        super().__init__()
        self.main_app = main_app_ref
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # --- HEADER ---
        header_layout = QHBoxLayout()
        title = QLabel("📚 RetroReel Help Center")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        
        # Button to re-launch the Active Tour
        btn_replay = QPushButton("🏃 Start Interactive Tour")
        btn_replay.setFixedWidth(200)
        btn_replay.clicked.connect(self.main_app.launch_active_tour)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(btn_replay)
        layout.addLayout(header_layout)
        
        # --- HELP CONTENT ---
        content = QTextEdit()
        content.setReadOnly(True)
        content.setMaximumHeight(250) # Limit height so we have room for the store link
        content.setStyleSheet("font-size: 11pt;")
        content.setHtml("""
        <h3 style="color: #4CAF50;">Step 1: System Check</h3>
        <p>Go to the <b>Diagnostics</b> tab. You need all GREEN checks to proceed.</p>
        
        <h3 style="color: #2196F3;">Step 2: Capture Video</h3>
        <p>Use the <b>Capture Deck</b> tab. Ensure camera is in VCR mode.</p>
           
        <h3 style="color: #FF9800;">Step 3: Convert & Stitch</h3>
        <p>Use the <b>Post-Process</b> tab to convert huge .dv files into MP4.</p>
        """)
        layout.addWidget(content)

        # --- DIVIDER LINE ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # --- MERGED: ORDERS SECTION ---
        order_title = QLabel("📦 Ready to Archive?")
        order_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        order_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(order_title)
        
        desc = QLabel(
            "Visit our online portal to create new orders, print shipping labels, "
            "and track your digitization progress."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 11pt; padding: 10px; color: #666;")
        layout.addWidget(desc)
        
        btn_store = QPushButton("🌐 Visit RetroReel Online Store")
        btn_store.setMinimumHeight(50)
        btn_store.setStyleSheet("font-size: 12pt; background-color: #2196F3; color: white; font-weight: bold;")
        btn_store.clicked.connect(self.open_site)
        layout.addWidget(btn_store)
        
        layout.addStretch()

    def open_site(self):
        # NOTE: Replace with your actual URL
        QDesktopServices.openUrl(QUrl("https://www.your-website.com"))

class FeedbackTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        layout.addWidget(QLabel("<h2>🐛 Send Feedback / Report Bugs</h2>"))
        layout.addWidget(QLabel("Found a glitch? Have a feature idea? Let us know."))
        
        form_layout = QFormLayout()
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Brief summary...")
        
        self.body_input = QTextEdit()
        self.body_input.setPlaceholderText("Describe the issue or idea here...")
        
        form_layout.addRow("Subject:", self.subject_input)
        form_layout.addRow("Message:", self.body_input)
        layout.addLayout(form_layout)
        
        send_btn = QPushButton("📧 Create Email Draft")
        send_btn.setMinimumHeight(50)
        send_btn.clicked.connect(self.send_email)
        layout.addWidget(send_btn)
        
    def send_email(self):
        subject = self.subject_input.text()
        body = self.body_input.toPlainText()
        mailto_url = QUrl(f"mailto:support@retroreel.com?subject=RetroReel: {subject}&body={body}")
        QDesktopServices.openUrl(mailto_url)