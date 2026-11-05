"""Edition profiles, color schemes and notification asset policy.

No local accounts, credentials or system identities are embedded here.
The upload/verification engine is shared across both editions.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys

EDITION_ENV = "STRAPMAN_EDITION"
LITE = "lite"
BOOTLEGGER = "bootlegger"
PRO_THEMES = ("Purple Night", "Pink Pearl", "Blue Frost")
SOUND_EVENTS = {
    "ready": "application_ready.mp3",
    "first_run": "first_run_github_setup.mp3",
    "complete": "task_complete.mp3",
    "error": "application_error.mp3",
    "exit": "application_exit.mp3",
    "power_restored": "power_restored.mp3",
    "power_unplugged": "power_unplugged.mp3",
    "upload_resuming": "upload_resuming.mp3",
    "work_paused": "work_paused.mp3",
    "repository_refreshed": "repository_refreshed.mp3",
    "repository_private": "repository_private.mp3",
    "verification_started": "verification_started.mp3",
    "vulnerability_alerts_enabled": "vulnerability_alerts_enabled.mp3",
    "automated_security_fixes_enabled": "automated_security_fixes_enabled.mp3",
}


def active_edition(environment: dict[str, str] | None = None) -> str:
    values = environment if environment is not None else os.environ
    value = values.get(EDITION_ENV, LITE).strip().lower()
    return BOOTLEGGER if value == BOOTLEGGER else LITE


def display_name(edition: str | None = None) -> str:
    return "Bootlegger Pro" if (edition or active_edition()) == BOOTLEGGER else "Strapman Lite"


def normalize_theme(theme: str, edition: str | None = None) -> str:
    if (edition or active_edition()) != BOOTLEGGER:
        return "Retro Dark"
    return theme if theme in PRO_THEMES else PRO_THEMES[0]


def icon_path(project_root: Path, edition: str | None = None) -> Path:
    project_root = Path(project_root)
    if (edition or active_edition()) == BOOTLEGGER:
        return project_root / "bootlegger" / "assets" / "bootlegger-icon.png"
    return project_root / "assets" / "strapman-icon.png"


def audio_path(project_root: Path, event: str, edition: str | None = None) -> Path | None:
    """Only Pro reads bundled MP3 assets. Lite uses Qt's system sound."""
    if event not in SOUND_EVENTS:
        raise ValueError("Unknown notification event")
    if (edition or active_edition()) != BOOTLEGGER:
        return None
    return Path(project_root) / "bootlegger" / "assets" / "sounds" / SOUND_EVENTS[event]


PRO_DARK_CSS = """
QWidget { color: #f6eaff; }
QMainWindow, QWidget#shell { background: #0a0510; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #251035,stop:1 #100719); border-right: 1px solid #7f389d; }
QFrame#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3a174a,stop:0.1 #291334,stop:1 #160c21); border: 1px solid #8852ae; }
QLabel#brand { color: #f3caff; font-size: 21px; }
QLabel#brandSubtitle { color: #cb9cdb; }
QLabel#hero, QLabel#section { color: #ffebff; }
QLabel#caption { color: #c3acd3; }
QLabel#tag { background: #47205c; border: 1px solid #a968e6; color: #f4c6ff; }
QLabel#number { color: #e394ff; }
QPushButton { color: #ffedff; border: 1px solid #a472ce; border-bottom: 2px solid #190923; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #70448c,stop:0.45 #543071,stop:1 #391d52); }
QPushButton:hover { background: #8850b7; border-color: #f3baff; }
QPushButton:pressed { background: #361448; }
QPushButton:disabled { background: #23152c; color: #9988a9; border-color: #423253; }
QPushButton#primary { color: #14051e; border: 1px solid #f0bfff; background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f2c9ff,stop:0.35 #ce78fc,stop:1 #993bd7); }
QPushButton#primary:hover { background: #f6cbff; }
QPushButton#danger { background: #572447; border-color: #a9659c; }
QPushButton#nav { background: transparent; border: 1px solid transparent; color: #dec1f0; }
QPushButton#nav:checked { background: #451956; border: 1px solid #a35dcb; border-left: 4px solid #eaa5ff; color: #fff7ff; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox, QListWidget { background: #180e24; border: 1px solid #8655a5; color: #faefff; selection-background-color: #7e39a8; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #f0baff; }
QComboBox QAbstractItemView { background: #251432; color: #fff3ff; selection-background-color: #843eae; }
QCheckBox { color: #e7cef3; }
QCheckBox::indicator { background: #1c0e2d; border: 1px solid #905cba; }
QCheckBox::indicator:checked { background: #d974fc; border-color: #f1b5ff; }
QProgressBar { background: #170920; color: #fff7ff; border: 1px solid #9d54ca; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f3b8ff,stop:0.5 #ce60ff,stop:1 #8d2ec6); }
QMessageBox, QDialog { background: #21112f; }
QScrollBar:vertical { background: #190e26; }
QScrollBar::handle:vertical { background: #694085; }
"""

LIGHT_CSS = """
QWidget { color: #283047; }
QMainWindow, QWidget#shell { background: {background}; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {sidebar_top},stop:1 {sidebar_bottom}); border-right: 1px solid {border}; }
QFrame#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.15 {card_top},stop:1 {card_bottom}); border: 1px solid {border}; }
QLabel#brand { color: {title}; font-size: 21px; }
QLabel#brandSubtitle { color: {subtle}; }
QLabel#hero, QLabel#section { color: {title}; }
QLabel#caption { color: #57617b; }
QLabel#tag { background: {badge}; color: {title}; border: 1px solid {border}; }
QLabel#number { color: {accent}; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:0.5 {card_top},stop:1 {card_bottom}); border: 1px solid {border}; border-bottom: 2px solid {accent}; color: {title}; }
QPushButton:hover { background: {badge}; border-color: {accent}; }
QPushButton:pressed { background: {card_bottom}; }
QPushButton:disabled { background: #f0f0f2; border-color: #c7c9d4; color: #868b95; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {button_top},stop:1 {accent}); color: #ffffff; border: 1px solid {accent}; }
QPushButton#primary:hover { background: {button_top}; }
QPushButton#danger { background: #ffe4e9; color: #9c2e4b; border-color: #d38c9f; }
QPushButton#nav { background: transparent; border: 1px solid transparent; color: {title}; }
QPushButton#nav:checked { background: {badge}; border: 1px solid {border}; border-left: 4px solid {accent}; color: {title}; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox, QListWidget { background: #ffffff; color: #283047; border: 1px solid {border}; selection-background-color: {badge}; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid {accent}; }
QComboBox QAbstractItemView { background: #ffffff; color: #283047; border: 1px solid {border}; selection-background-color: {badge}; }
QCheckBox { color: #30384e; }
QCheckBox::indicator { background: #ffffff; border: 1px solid {border}; }
QCheckBox::indicator:checked { background: {accent}; border-color: {title}; }
QProgressBar { background: #ffffff; color: {title}; border: 1px solid {border}; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {button_top},stop:1 {accent}); }
QMessageBox, QDialog { background: {card_top}; }
QScrollBar:vertical { background: {card_top}; }
QScrollBar::handle:vertical { background: {border}; }
"""

PINK_COLORS = {
    "background": "#fff5fb", "sidebar_top": "#ffdcf0", "sidebar_bottom": "#fceafa",
    "border": "#dfa0c8", "card_top": "#fff8fd", "card_bottom": "#ffecf7",
    "title": "#84245c", "subtle": "#a55681", "badge": "#ffe0f2",
    "accent": "#d43285", "button_top": "#f384b9",
}
BLUE_COLORS = {
    "background": "#f2f9ff", "sidebar_top": "#d6edff", "sidebar_bottom": "#eaf6ff",
    "border": "#90c5ea", "card_top": "#f9fdff", "card_bottom": "#e5f4ff",
    "title": "#155187", "subtle": "#5d8db2", "badge": "#dbf1ff",
    "accent": "#1682d7", "button_top": "#77bbf4",
}


def edition_stylesheet(lite_css: str, *, edition: str | None = None, theme: str = "Purple Night") -> str:
    if (edition or active_edition()) != BOOTLEGGER:
        return lite_css
    theme = normalize_theme(theme, BOOTLEGGER)
    if theme == "Purple Night":
        return lite_css + "\n" + PRO_DARK_CSS
    palette = PINK_COLORS if theme == "Pink Pearl" else BLUE_COLORS
    light = LIGHT_CSS
    for name, color in palette.items():
        light = light.replace("{" + name + "}", color)
    return lite_css + "\n" + light


def on_ac_power() -> bool | None:
    """Poll optional power-status events without installing an additional dependency."""
    if sys.platform == "win32":
        class Status(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        status = Status()
        try:
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                return None
        except (AttributeError, OSError):
            return None
        return bool(status.ACLineStatus) if status.ACLineStatus in (0, 1) else None
    if sys.platform.startswith("linux"):
        root = Path("/sys/class/power_supply")
        try:
            for entry in sorted(root.iterdir()):
                if (entry / "type").read_text().strip().lower() in ("mains", "usb", "usb_pd"):
                    online = (entry / "online").read_text().strip()
                    if online in ("0", "1"):
                        return online == "1"
        except (FileNotFoundError, PermissionError, OSError):
            pass
    return None


class PowerReminder:
    """One notification per transition, and once per minute while unplugged.

    Polling uses monotonic time; unknown power readings never count as a
    connection change, and a restored connection clears the reminder timer.
    """

    def __init__(self, initial: bool | None = None, interval_seconds: float = 60.0):
        if interval_seconds <= 0:
            raise ValueError("Power reminder interval must be positive")
        self.state = initial
        self.interval_seconds = interval_seconds
        self.last_unplugged_notice: float | None = None

    def poll(self, current: bool | None, now: float) -> str | None:
        if current is None:
            return None
        if current:
            was_unplugged = self.state is False
            self.state = True
            self.last_unplugged_notice = None
            return "power_restored" if was_unplugged else None
        if self.state is not False or self.last_unplugged_notice is None:
            self.state = False
            self.last_unplugged_notice = now
            return "power_unplugged"
        if now - self.last_unplugged_notice >= self.interval_seconds:
            self.last_unplugged_notice = now
            return "power_unplugged"
        return None
