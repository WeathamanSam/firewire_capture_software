# active_tutorial.py
from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QDialog, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont

class CoachMark(QDialog):
    next_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # CHANGED: ApplicationModal freezes the rest of the app while this is open
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal) 
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # --- Style ---
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: #333; 
                color: #fff;
                border-radius: 8px;
                border: 2px solid #555;
            }
            QLabel { font-size: 11pt; color: #fff; }
            QPushButton {
                background-color: #2196F3;
                color: #fff;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout()
        layout.addWidget(self.container)
        self.setLayout(layout)

        self.inner_layout = QVBoxLayout(self.container)
        
        self.lbl_title = QLabel("Title")
        self.lbl_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.inner_layout.addWidget(self.lbl_title)
        
        self.lbl_text = QLabel("Description goes here...")
        self.lbl_text.setWordWrap(True)
        self.inner_layout.addWidget(self.lbl_text)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_next = QPushButton("Next ➡")
        self.btn_next.clicked.connect(self.handle_click) 
        btn_layout.addWidget(self.btn_next)
        
        self.inner_layout.addLayout(btn_layout)

    def handle_click(self):
        self.next_clicked.emit()
        self.accept()

    def show_at(self, target_widget, title, text, is_last=False):
        self.lbl_title.setText(title)
        self.lbl_text.setText(text)
        self.btn_next.setText("Finish ✅" if is_last else "Next ➡")
        
        target_pos = target_widget.mapToGlobal(QPoint(0, 0))
        x = target_pos.x() + target_widget.width() + 20
        y = target_pos.y() 
        
        # Screen boundary check
        screen_width = self.screen().geometry().width()
        if x + self.width() > screen_width:
            x = target_pos.x() - self.width() - 20
            
        self.move(x, y)
        self.show()

class TourManager(QObject):
    # CHANGED: Added signal to notify main.py when done
    tour_finished = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.steps = []
        self.current_step = -1
        self.current_mark = None 

    def add_step(self, tab_index, widget_getter, title, text):
        self.steps.append({
            'tab': tab_index,
            'widget_getter': widget_getter,
            'title': title,
            'text': text
        })

    def start(self):
        self.current_step = 0
        self.run_step()

    def run_step(self):
        # 1. Check if we are done
        if self.current_step >= len(self.steps):
            self.tour_finished.emit() # <--- Tell Main Window to re-lock tabs!
            return 

        step = self.steps[self.current_step]
        
        # Force unlock tab so we can show it (The App is frozen, so user can't click anyway)
        if not self.main.tabs.isTabEnabled(step['tab']):
            self.main.tabs.setTabEnabled(step['tab'], True)

        # Switch Tab
        self.main.tabs.setCurrentIndex(step['tab'])
        
        # Wait for switch then show
        QTimer.singleShot(300, lambda: self._show_mark(step))

    def _show_mark(self, step):
        target = step['widget_getter']()
        
        if self.current_mark:
            self.current_mark.close()

        is_last = (self.current_step == len(self.steps) - 1)
        
        self.current_mark = CoachMark(self.main)
        self.current_mark.show_at(target, step['title'], step['text'], is_last)
        self.current_mark.next_clicked.connect(self.next_step)

    def next_step(self):
        self.current_step += 1
        self.run_step()