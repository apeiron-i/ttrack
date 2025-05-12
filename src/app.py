# ttrack_csv_version.py
import sys
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

DATA_FILE = Path("sessions.csv")


def load_sessions():
    sessions = []
    if DATA_FILE.exists():
        with open(DATA_FILE, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sessions.append(
                    {"client": row["Client"], "start": row["Start"], "end": row["End"]}
                )
    return sessions


def append_session(client, start, end):
    write_header = not DATA_FILE.exists()
    with open(DATA_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["Client", "Start", "End"])
        writer.writerow([client, start.isoformat(), end.isoformat()])


class TimeTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TT")
        self.setWindowIcon(QIcon("icon_tt.ico"))

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon_tt.ico"))
        self.tray_icon.setVisible(True)

        self.setFixedSize(300, 220)

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

        self.sessions = load_sessions()
        self.current_client = None
        self.start_time = None

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignTop)

        # Client selection
        hlayout = QHBoxLayout()
        self.client_dropdown = QComboBox()
        self.client_dropdown.addItems(sorted(set(s["client"] for s in self.sessions)))
        self.client_dropdown.currentTextChanged.connect(self.select_client)
        self.add_client_input = QLineEdit()
        self.add_client_input.setPlaceholderText("New client name")
        self.add_client_input.returnPressed.connect(self.add_client)
        hlayout.addWidget(self.client_dropdown)
        hlayout.addWidget(self.add_client_input)
        layout.addLayout(hlayout)

        self.timer_button = QPushButton("Start")
        self.timer_button.clicked.connect(self.toggle_timer)
        self.timer_button.setStyleSheet("background-color: #28a745; color: white;")
        layout.addWidget(self.timer_button)

        self.session_label = QLabel("Session: 0h 0m 0s")
        layout.addWidget(self.session_label)

        layout.addSpacing(8)

        self.time_label = QLabel()
        layout.addWidget(self.time_label)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        if self.client_dropdown.count():
            self.select_client(self.client_dropdown.currentText())
            QTimer.singleShot(0, self.update_ui)

    def add_client(self):
        name = self.add_client_input.text().strip()
        if name and name not in [
            self.client_dropdown.itemText(i)
            for i in range(self.client_dropdown.count())
        ]:
            self.client_dropdown.addItem(name)
            self.add_client_input.clear()

    def select_client(self, name):
        if self.start_time:
            end_time = datetime.now()
            append_session(self.current_client, self.start_time, end_time)
            self.sessions.append(
                {
                    "client": self.current_client,
                    "start": self.start_time.isoformat(),
                    "end": end_time.isoformat(),
                }
            )
            self.start_time = None
            self.timer_button.setText("Start")
            self.timer_button.setStyleSheet("background-color: #28a745; color: white;")

        self.current_client = name
        self.update_ui()

    def toggle_timer(self):
        if not self.current_client:
            return

        if self.start_time:
            end_time = datetime.now()
            append_session(self.current_client, self.start_time, end_time)
            self.sessions.append(
                {
                    "client": self.current_client,
                    "start": self.start_time.isoformat(),
                    "end": end_time.isoformat(),
                }
            )
            self.start_time = None
            self.timer_button.setText("Start")
            self.timer_button.setStyleSheet("background-color: #28a745; color: white;")
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
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        for s in self.sessions:
            if s["client"] != self.current_client:
                continue
            start = datetime.fromisoformat(s["start"])
            end = datetime.fromisoformat(s["end"])
            duration = end - start

            if start.date() == now.date():
                total_today += duration
            if start >= start_of_week:
                total_week += duration
            if start.year == now.year and start.month == now.month:
                total_month += duration

        if self.start_time:
            live = datetime.now() - self.start_time
            total_today += live
            total_week += live
            total_month += live

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
            hours, remainder = divmod(
                int((datetime.now() - self.start_time).total_seconds()), 3600
            )
            minutes, seconds = divmod(remainder, 60)
            self.session_label.setText(f"Session: {hours}h {minutes}m {seconds}s")
        else:
            self.session_label.setText("Session: 0h 0m 0s")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TimeTracker()
    win.show()
    sys.exit(app.exec())
