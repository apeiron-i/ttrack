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
from generate_report import generate_report
import hashlib
from datetime import date
import shutil
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QDateTimeEdit
import os
from PySide6.QtWidgets import QSpacerItem, QSizePolicy

BACKUP_FOLDER = Path(".backups")
BACKUP_FOLDER.mkdir(exist_ok=True)

DATA_FILE = Path("sessions.csv")
RUNNING_FILE = Path("running_session.csv")
HEARTBEAT_FILE = Path("last_seen.txt")
ICON_PATH = Path(__file__).parent / "icon_tt.ico"
ICON_ON_PATH = Path(__file__).parent / "icon_on.ico"


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def backup_sessions_csv(tag=""):
    if not DATA_FILE.exists():
        return

    today_str = date.today().isoformat()
    suffix = f"_{tag}" if tag else ""
    backup_file = BACKUP_FOLDER / f"sessions_{today_str}{suffix}.csv"

    # Avoid overwriting an existing backup of the same type
    if not backup_file.exists():
        shutil.copy2(DATA_FILE, backup_file)


def cleanup_old_backups(days=30):
    cutoff = datetime.now() - timedelta(days=days)
    for f in BACKUP_FOLDER.glob("sessions_*.csv"):
        try:
            timestamp = f.name.split("_")[1].split(".")[0]
            file_date = datetime.strptime(timestamp, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
        except Exception:
            pass  # Skip bad filenames


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


def get_csv_hash():
    if not DATA_FILE.exists():
        return None
    return hashlib.md5(DATA_FILE.read_bytes()).hexdigest()


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


def validate_sessions(sessions):
    errors = []
    for i, s in enumerate(sessions):
        try:
            start = datetime.fromisoformat(s["start"])
            end = datetime.fromisoformat(s["end"])
            if end <= start:
                errors.append(f"Row {i + 1}: End before Start ({start} → {end})")
        except Exception as e:
            errors.append(f"Row {i + 1}: Invalid timestamp — {e}")
    return errors


class EditLastEntryDialog(QDialog):
    def __init__(self, parent, last_entry):
        super().__init__(parent)
        self.setWindowTitle("Edit Last Entry")
        self.setMinimumWidth(300)
        self.last_entry = last_entry

        layout = QFormLayout()

        self.client_label = QLabel(last_entry["client"])
        self.start_edit = QDateTimeEdit(datetime.fromisoformat(last_entry["start"]))
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        self.end_edit = QDateTimeEdit(datetime.fromisoformat(last_entry["end"]))
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        layout.addRow("Client:", self.client_label)
        layout.addRow("Start:", self.start_edit)
        layout.addRow("End:", self.end_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_edited_values(self):
        return {
            "client": self.client_label.text(),
            "start": self.start_edit.dateTime().toPython(),
            "end": self.end_edit.dateTime().toPython(),
        }


class TimeTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TT")
        backup_sessions_csv()
        cleanup_old_backups()

        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(str(ICON_PATH)))

        # self.setWindowIcon(QIcon("icon_tt.ico"))
        self.heartbeat_counter = 0
        # self.tray_icon.setIcon(QIcon("icon_tt.ico"))
        self.tray_icon.setVisible(True)

        # self.setFixedSize(300, 270)

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
        errors = validate_sessions(self.sessions)
        if errors:
            QMessageBox.critical(
                self,
                "CSV Error",
                "⚠️ Invalid session data found:\n\n" + "\n".join(errors),
            )
            self.sessions = []  # or keep the valid ones only

        self.csv_hash = get_csv_hash()
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

        self.edit_button = QPushButton()
        self.stats_button = QPushButton()
        self.reload_button = QPushButton()
        self.edit_last_button = QPushButton()

        self.edit_button.setIcon(QIcon(resource_path("src/assets/i_table.png")))
        self.stats_button.setIcon(QIcon(resource_path("src/assets/i_stats.png")))
        self.reload_button.setIcon(QIcon(resource_path("src/assets/i_reload.png")))
        self.edit_last_button.setIcon(QIcon(resource_path("src/assets/i_edit.png")))

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

        self.reload_button.setStyleSheet(
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
        self.reload_button.clicked.connect(self.reload_csv)

        self.edit_last_button.setStyleSheet(
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
        self.edit_last_button.clicked.connect(self.edit_last_entry)

        self.edit_button.setToolTip(
            "Open sessions.csv in Excel or your default editor."
        )
        self.stats_button.setToolTip("Generate and open the interactive stats report.")
        self.reload_button.setToolTip(
            "Reload sessions from CSV (use after manual edits)."
        )
        self.edit_last_button.setToolTip("Quickly edit the last recorded session.")
        self.timer_button.setToolTip(
            "Start or stop tracking time for the selected client."
        )

        button_hlayout.addWidget(self.edit_last_button)
        button_hlayout.addWidget(self.stats_button)
        button_hlayout.addWidget(self.edit_button)
        button_hlayout.addWidget(self.reload_button)

        # Add vertical spacer before the button row
        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addLayout(button_hlayout)

        if self.client_dropdown.count():
            self.select_client(self.client_dropdown.currentText())
            QTimer.singleShot(0, self.update_ui)

    def refresh_client_dropdown(self):
        clients = [s["client"] for s in self.sessions]
        unique_clients = sorted(set(clients))

        self.client_dropdown.blockSignals(True)
        self.client_dropdown.clear()
        self.client_dropdown.addItems(unique_clients)
        self.client_dropdown.blockSignals(False)

        if clients:
            self.client_dropdown.setCurrentText(clients[-1])
            self.select_client(clients[-1])
        else:
            self.current_client = None

    def reload_csv(self):
        if self.start_time:
            QMessageBox.warning(
                self,
                "Active Session",
                "Cannot reload while a session is running.",
            )
            return

        new_hash = get_csv_hash()
        if new_hash != self.csv_hash:
            self.sessions = load_sessions()
            self.csv_hash = new_hash
            self.refresh_client_dropdown()
            self.update_ui()
            QMessageBox.information(self, "Reloaded", "Sessions reloaded from CSV.")
        else:
            QMessageBox.information(
                self, "No Change", "CSV has not changed since last load."
            )

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
            end_time = datetime.now()
            try:
                append_session(self.current_client, self.start_time, end_time)
            except PermissionError:
                QMessageBox.warning(
                    self,
                    "File Locked",
                    "sessions.csv is open (e.g., in Excel).\nPlease close it and stop the timer again.",
                )
                return  # Don't end session
            else:
                self.setWindowIcon(QIcon(str(ICON_PATH)))
                self.tray_icon.setIcon(QIcon(str(ICON_PATH)))
                self.tray_icon.setToolTip("Timer stopped")
                self.tray_icon.show()
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
                self.timer_button.setStyleSheet(
                    "background-color: #28a745; color: white;"
                )

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

    def edit_last_entry(self):
        if not self.sessions:
            QMessageBox.information(self, "No Data", "No session found to edit.")
            return

        last_entry = self.sessions[-1]
        dialog = EditLastEntryDialog(self, last_entry)
        if dialog.exec() == QDialog.Accepted:
            edited = dialog.get_edited_values()
            if edited["end"] <= edited["start"]:
                QMessageBox.warning(
                    self, "Invalid Entry", "End time must be after start time."
                )
                return

            # Update CSV in-place
            all_rows = []
            with open(DATA_FILE, newline="") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)

            if not all_rows:
                QMessageBox.warning(self, "Error", "CSV appears empty.")
                return

            all_rows[-1] = {
                "Client": edited["client"],
                "Start": edited["start"].isoformat(),
                "End": edited["end"].isoformat(),
            }

            with open(DATA_FILE, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Client", "Start", "End"])
                writer.writeheader()
                writer.writerows(all_rows)

            self.sessions = load_sessions()
            self.csv_hash = get_csv_hash()
            self.refresh_client_dropdown()
            self.update_ui()
            QMessageBox.information(self, "Saved", "Last entry updated.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    win = TimeTracker()
    win.show()
    sys.exit(app.exec())
