# ttrack_csv_version.py with session recovery (no export button, fixed size)
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
    QMessageBox,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon
import subprocess
import platform
import webbrowser
import plotly.express as px
import pandas as pd

DATA_FILE = Path("sessions.csv")
RUNNING_FILE = Path("running_session.csv")
HEARTBEAT_FILE = Path("last_seen.txt")
ICON_PATH = Path(__file__).parent / "icon_tt.ico"
ICON_ON_PATH = Path(__file__).parent / "icon_on.ico"


def generate_report():
    df = pd.read_csv("sessions.csv", parse_dates=["Start", "End"])
    df["Duration"] = (df["End"] - df["Start"]).dt.total_seconds() / 3600
    df["Date"] = df["Start"].dt.date
    df["Week"] = df["Start"].dt.to_period("W").apply(lambda r: r.start_time)
    df["Month"] = df["Start"].dt.to_period("M").apply(lambda r: r.start_time)
    df["Weekday"] = df["Start"].dt.weekday

    chart_height = 500

    # ----- 1. Monthly totals per client -----
    monthly = df.groupby(["Client", "Month"])["Duration"].sum().reset_index()
    fig_monthly = px.bar(
        monthly,
        x="Month",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Month",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- 2. Weekly totals per client -----
    weekly = df.groupby(["Client", "Week"])["Duration"].sum().reset_index()
    fig_weekly = px.bar(
        weekly,
        x="Week",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Week",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- 3. Daily average including all days -----
    days_worked = df.groupby("Client")["Date"].nunique()
    total_hours = df.groupby("Client")["Duration"].sum()
    daily_avg = (total_hours / days_worked).reset_index()
    daily_avg.columns = ["Client", "AvgHoursPerDay"]
    fig_avg = px.bar(
        daily_avg,
        x="Client",
        y="AvgHoursPerDay",
        title="Average Hours per Day (All Days)",
        labels={"AvgHoursPerDay": "Avg Hours"},
        height=chart_height,
    )

    # ----- 4. Total hours per client per day -----
    per_day = df.groupby(["Client", "Date"])["Duration"].sum().reset_index()
    fig_day = px.bar(
        per_day,
        x="Date",
        y="Duration",
        color="Client",
        title="Total Hours per Client per Day",
        labels={"Duration": "Hours"},
        height=chart_height,
    )

    # ----- Combine all into one HTML file -----
    html_path = Path("report.html")
    with open(html_path, "w") as f:
        f.write("<html><head><title>Time Tracking Report</title></head><body>\n")
        f.write("<h4 style='font-family:sans-serif;'>Time Tracking Summary</h4>\n")
        f.write(fig_day.to_html(full_html=False, include_plotlyjs="cdn"))
        f.write(fig_weekly.to_html(full_html=False, include_plotlyjs=False))
        f.write(fig_monthly.to_html(full_html=False, include_plotlyjs=False))
        f.write(fig_avg.to_html(full_html=False, include_plotlyjs=False))
        f.write("</body></html>")

    print(f"✅ Report saved to {html_path.resolve()}")


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


def save_running_session(client, start):
    with open(RUNNING_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Client", "Start"])
        writer.writerow([client, start.isoformat()])


def load_running_session():
    if not RUNNING_FILE.exists():
        return None
    with open(RUNNING_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return row["Client"], datetime.fromisoformat(row["Start"])
    return None


def save_heartbeat():
    HEARTBEAT_FILE.write_text(datetime.now().isoformat())


def load_heartbeat():
    if HEARTBEAT_FILE.exists():
        return datetime.fromisoformat(HEARTBEAT_FILE.read_text())
    return None


def clear_session_state():
    if RUNNING_FILE.exists():
        RUNNING_FILE.unlink()
    if HEARTBEAT_FILE.exists():
        HEARTBEAT_FILE.unlink()


class TimeTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TT")

        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(str(ICON_PATH)))

        # self.setWindowIcon(QIcon("icon_tt.ico"))
        self.heartbeat_counter = 0
        # self.tray_icon.setIcon(QIcon("icon_tt.ico"))
        self.tray_icon.setVisible(True)

        self.setFixedSize(300, 260)

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

        hlayout = QHBoxLayout()

        # self.client_dropdown = QComboBox()
        # self.client_dropdown.addItems(sorted(set(s["client"] for s in self.sessions)))
        self.client_dropdown = QComboBox()
        clients = [s["client"] for s in self.sessions]
        unique_clients = sorted(set(clients))
        self.client_dropdown.addItems(unique_clients)

        # Preselect the most recent client if sessions exist
        if clients:
            self.client_dropdown.setCurrentText(clients[-1])

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

        self.recover_session()

        button_hlayout = QHBoxLayout()
        self.edit_button = QPushButton("Edit CSV")
        self.edit_button.setStyleSheet(
            """
            QPushButton {
                font-size: 12px; color: #ccc; background-color: #333;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #444;
                color: #fff;
            }
            QPushButton:pressed {
                background-color: #222;
                color: #fff;
            }
            """
        )
        self.edit_button.clicked.connect(self.open_csv_file)
        button_hlayout.addWidget(self.edit_button)

        self.stats_button = QPushButton("Stats")
        self.stats_button.setStyleSheet(
            """
            QPushButton {
                font-size: 12px; color: #ccc; background-color: #333;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #444;
                color: #fff;
            }
            QPushButton:pressed {
                background-color: #222;
                color: #fff;
            }
            """
        )
        self.stats_button.clicked.connect(self.open_stats_report)
        button_hlayout.addWidget(self.stats_button)

        layout.addLayout(button_hlayout)

        if self.client_dropdown.count():
            self.select_client(self.client_dropdown.currentText())
            QTimer.singleShot(0, self.update_ui)

    def recover_session(self):
        recovered = load_running_session()
        if recovered:
            client, start = recovered
            last_seen = load_heartbeat() or datetime.now()
            elapsed = last_seen - start
            minutes = int(elapsed.total_seconds() / 60)

            reply = QMessageBox.question(
                self,
                "Recover session?",
                f"A session for '{client}' started at {start.strftime('%H:%M')} and last seen at {last_seen.strftime('%H:%M')}\nLog {minutes} minutes?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                append_session(client, start, last_seen)
                self.sessions.append(
                    {
                        "client": client,
                        "start": start.isoformat(),
                        "end": last_seen.isoformat(),
                    }
                )

            clear_session_state()

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
            self.setWindowIcon(QIcon(str(ICON_PATH)))
            self.tray_icon.setIcon(QIcon(str(ICON_PATH)))
            self.tray_icon.setToolTip("Timer stopped")
            self.tray_icon.show()

            end_time = datetime.now()
            append_session(self.current_client, self.start_time, end_time)
            clear_session_state()
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
            self.setWindowIcon(QIcon(str(ICON_ON_PATH)))
            self.tray_icon.setIcon(QIcon(str(ICON_ON_PATH)))
            self.tray_icon.setToolTip("Timer running…")
            self.tray_icon.show()

            self.start_time = datetime.now()
            save_running_session(self.current_client, self.start_time)
            save_heartbeat()
            self.timer_button.setText("Stop")
            self.timer_button.setStyleSheet("background-color: #dc3545; color: white;")

        self.update_ui()

    def update_ui(self):
        if self.start_time:
            self.heartbeat_counter += 1
            if self.heartbeat_counter >= 60:  # once per minute
                save_heartbeat()
                self.heartbeat_counter = 0

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

    def open_csv_file(self):
        file_path = str(DATA_FILE.resolve())

        if platform.system() == "Windows":
            subprocess.run(["start", "", file_path], shell=True)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path])
        else:  # Linux
            subprocess.run(["xdg-open", file_path])

    def open_stats_report(self):
        generate_report()
        report_path = Path("report.html").resolve()
        if report_path.exists():
            webbrowser.open(str(report_path))
        else:
            QMessageBox.warning(
                self, "Stats Report", "Report file not found. Please generate it first."
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    win = TimeTracker()
    win.show()
    sys.exit(app.exec())
