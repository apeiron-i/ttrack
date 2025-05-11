# pyinstaller ttrack.spec


import sys
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLabel,
    QVBoxLayout,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon

DATA_FILE = Path("timetracker_data.json")


def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2))


class TimeTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TT")

        self.setWindowIcon(QIcon("icon.png"))  # Sets the main app window icon

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))  # Replaces the default tray icon
        self.tray_icon.setVisible(True)

        self.resize(300, 300)
        self.setFixedSize(300, 240)  # width, height

        self.setStyleSheet("""
            QWidget {
                background-color: #2c2f33;
                color: #f5f6fa;
                font-family: Segoe UI, sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #444;
                border: 0px solid #666;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:pressed {
                background-color: #333;
            }
            QLineEdit, QComboBox {
                background-color: #1e2124;
                color: #fff;
                padding: 4px;
                border: 0px solid #666;
                border-radius: 4px;
            }
        """)

        self.data = load_data()
        self.current_client = None
        self.start_time = None

        # Layout setup
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignTop)

        # Client selection
        hlayout = QHBoxLayout()
        self.client_dropdown = QComboBox()
        self.client_dropdown.addItems(self.data.keys())
        self.client_dropdown.currentTextChanged.connect(self.select_client)
        self.add_client_input = QLineEdit()
        self.add_client_input.setPlaceholderText("New client name")
        self.add_client_input.returnPressed.connect(self.add_client)
        hlayout.addWidget(self.client_dropdown)
        hlayout.addWidget(self.add_client_input)
        layout.addLayout(hlayout)

        # Start/Stop button
        self.timer_button = QPushButton("Start")
        self.timer_button.clicked.connect(self.toggle_timer)
        self.timer_button.setStyleSheet("background-color: #28a745; color: white;")
        layout.addWidget(self.timer_button)

        # Session timer
        self.session_label = QLabel("Session: 0h 0m 0s")
        layout.addWidget(self.session_label)

        # Spacer between session and totals
        layout.addSpacing(8)

        # Totals
        self.time_label = QLabel()
        layout.addWidget(self.time_label)

        # Export button (subtle, right-aligned)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self.export_csv)
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #aaa;
                font-size: 12px;
                padding: 2px;
                border: none;
                text-align: right;
            }
            QPushButton:hover {
                color: #fff;
            }
        """)
        layout.addWidget(self.export_button, alignment=Qt.AlignRight)

        self.setLayout(layout)

        # Start timer
        self.timer = QTimer()
        self.timer.setInterval(1000)  # Update every second
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        if self.client_dropdown.count():
            default = self.client_dropdown.currentText()
            self.select_client(default)
            QTimer.singleShot(0, self.update_ui)  # Ensure totals show immediately

    def add_client(self):
        name = self.add_client_input.text().strip()
        if name and name not in self.data:
            self.data[name] = []
            self.client_dropdown.addItem(name)
            self.add_client_input.clear()
            save_data(self.data)

    def select_client(self, name):
        # Stop timer for previous client, if running
        if self.start_time:
            end_time = datetime.now()
            self.data[self.current_client].append(
                {"start": self.start_time.isoformat(), "end": end_time.isoformat()}
            )
            self.start_time = None
            self.timer_button.setText("Start")
            self.timer_button.setStyleSheet("background-color: #28a745; color: white;")
            save_data(self.data)

        self.current_client = name
        self.update_ui()

    def toggle_timer(self):
        if not self.current_client:
            return

        if self.start_time:
            end_time = datetime.now()
            self.data[self.current_client].append(
                {"start": self.start_time.isoformat(), "end": end_time.isoformat()}
            )
            self.start_time = None
            self.timer_button.setText("Start")
            self.timer_button.setStyleSheet("background-color: #28a745; color: white;")
            save_data(self.data)
        else:
            self.start_time = datetime.now()
            self.timer_button.setText("Stop")
            self.timer_button.setStyleSheet("background-color: #dc3545; color: white;")

        self.update_ui()

    def update_ui(self):
        if not self.current_client:
            self.time_label.setText("No client selected.")
            self.session_label.setText("Session: 0h 0m 0s")
            return

        total_today = timedelta()
        total_week = timedelta()
        total_month = timedelta()
        now = datetime.now()

        # Calendar-aligned week start (Monday 00:00)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        for session in self.data.get(self.current_client, []):
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"])
            duration = end - start

            if start.date() == now.date():
                total_today += duration
            if start >= start_of_week:
                total_week += duration
            if start.year == now.year and start.month == now.month:
                total_month += duration

        session_duration = timedelta()
        if self.start_time:
            session_duration = now - self.start_time
            total_today += session_duration
            total_week += session_duration
            total_month += session_duration

        def fmt(td):
            return f"{td.total_seconds() / 3600:.1f}h"

        self.time_label.setText(
            f"<span style='font-size:11px;'>"
            f"Today: {fmt(total_today)}<br>"
            f"Week: {fmt(total_week)}<br>"
            f"Month: {fmt(total_month)}"
            f"</span>"
        )

        if self.start_time:
            hours, remainder = divmod(int(session_duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.session_label.setText(f"Session: {hours}h {minutes}m {seconds}s")
        else:
            self.session_label.setText("Session: 0h 0m 0s")

    def export_csv(self):
        if not self.data:
            return

        filename = "all_clients_sessions.csv"
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Client", "Start", "End", "Duration (hours)"])

            for client, sessions in self.data.items():
                for session in sessions:
                    start = datetime.fromisoformat(session["start"])
                    end = datetime.fromisoformat(session["end"])
                    duration = (end - start).total_seconds() / 3600
                    writer.writerow(
                        [client, start.isoformat(), end.isoformat(), f"{duration:.2f}"]
                    )

        print(f"Exported all clients to {filename}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimeTracker()
    win.show()
    sys.exit(app.exec())
