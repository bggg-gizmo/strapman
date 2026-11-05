"""Strapman desktop interface: glossy dark retro Windows-era visual design."""
from __future__ import annotations

import os
import sys
import time
import textwrap
import threading
import re
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QThread, Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap, QSyntaxHighlighter, QTextCharFormat, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTabWidget,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTextBrowser,
    QVBoxLayout, QWidget
)

from .core import Journal, Settings, Store, VERSION, app_directory, parse_repository
from .engine import Engine
from .workbench import TextWorkbench, RemoteTextWorkbench, check_syntax, run_local_tests
from .audio import AudioPlaybackError, WindowsMp3Player
from .sound_assets import AudioAssetError, ensure_audio_asset
from .github import GitHub, GitHubError, cli_token, delete_token, saved_token, store_token, validate_repository_file_path
from .auth import (
    AuthError, bundled_oauth_client_id, git_credential_token, github_cli_accounts,
    github_cli_logout, github_cli_path, github_cli_switch, install_github_cli
)
from .auth_ui import DeviceLoginDialog, CliLoginDialog
from .editions import (
    BOOTLEGGER, PRO_THEMES, SOUND_EVENTS, active_edition, audio_path,
    PowerReminder, display_name, edition_stylesheet, icon_path, normalize_theme, on_ac_power,
    repository_write_sound_event
)
try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
except ImportError:  # A platform may lack QtMultimedia even if QtWidgets is available.
    QMediaPlayer = None
    QAudioOutput = None

def strapman_icon() -> QIcon:
    """Load the project-owned icon without requiring OS-specific assets."""
    source = icon_path(Path(__file__).resolve().parent.parent)
    return QIcon(str(source)) if source.is_file() else QIcon()


STYLES = """
QWidget { color: #e3edf8; font-family: 'Segoe UI', 'Noto Sans', sans-serif;
          font-size: 12px; background: transparent; }
QMainWindow, QWidget#shell { background: #101522; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1a2340,stop:1 #101729);
                 border-right: 1px solid #39496a; }
QFrame#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #283653,stop:0.06 #1c2944,stop:1 #172038);
              border: 1px solid #425678; border-radius: 17px; }
QLabel#brand { font-size: 16px; font-weight: 900; color: #e6efff; letter-spacing: 1px; }
QLabel#brandSubtitle { color: #8da4c8; font-size: 10px; }
QLabel#hero { font-size: 27px; color: #f3f7ff; font-weight: 800; }
QLabel#section { color: #f0f5ff; font-size: 16px; font-weight: 700; }
QLabel#caption { color: #a6b9d8; font-size: 11px; }
QLabel#tag { border-radius: 9px; background: #233c49; color: #86e8de;
             border: 1px solid #397269; padding: 6px 11px; font-weight: 700; }
QLabel#number { font-size: 27px; font-weight: 800; color: #a4f5e5; }
QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #586b95,stop:0.13 #415475,stop:0.51 #2d3d5f,stop:1 #253452);
              border: 1px solid #6b82af; border-bottom: 2px solid #101b33;
              border-radius: 13px; min-height: 28px; padding: 7px 14px;
              color: #f0f5ff; font-weight: 700; }
QPushButton:hover { background: #506b94; border-color: #a2dcd7; }
QPushButton:pressed { background: #1a2b4b; padding-top: 9px; padding-bottom: 5px; }
QPushButton:disabled { background: #253049; color: #8390ac; border-color: #394560; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #8cf5dd,stop:0.18 #48c6ba,stop:0.55 #268d9e,stop:1 #24677d);
                       border: 1px solid #92fff1; color: #061e2a; font-weight: 900; }
QPushButton#primary:hover { background: #9bfbed; }
QPushButton#danger { background: #633856; border-color: #b76e99; }
QPushButton#nav { background: transparent; border: 1px solid transparent; border-radius: 12px;
                  text-align: left; padding: 11px 15px; color: #b7c7e1; }
QPushButton#nav:hover { background: #344562; color: #f5fcff; }
QPushButton#nav[compact="true"] { text-align: center; padding: 8px 2px; }
QPushButton#nav:checked { background: #29415c; border-color: #4c7f98;
                          border-left: 4px solid #71e5d7; color: #f5fcff; }
QPushButton#workflow { background: #1b2840; border: 1px solid #3c5279; border-radius: 9px;
                         padding: 5px 8px; font-size: 11px; min-height: 24px; color: #cad9ec; }
QPushButton#workflow:checked { background: #2f4c66; color: #ffffff; border-color: #72b5d5; }
QLabel#brand { letter-spacing: 0px; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox, QListWidget {
  background: #101b31; border: 1px solid #4b6287; border-radius: 10px;
  selection-background-color: #317e92; color: #e5f0ff; padding: 8px;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
  border: 1px solid #76e1d2; }
QComboBox::drop-down { border-left: 1px solid #354a6a; width: 24px; }
QComboBox QAbstractItemView { background: #1b2940; color: #e7effc;
                              border: 1px solid #587093; selection-background-color: #2c6681; }
QCheckBox { color: #c7d7ee; spacing: 8px; }
QCheckBox::indicator { width: 17px; height: 17px; border-radius: 6px;
                       border: 1px solid #6b8eb9; background: #12213a; }
QCheckBox::indicator:checked { background: #3ed4c7; border-color: #b5fff7; }
QProgressBar { border: 1px solid #57749b; border-radius: 9px; background: #0e1829;
               min-height: 16px; text-align: center; font-weight: 700; color: white; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #8efce4,stop:0.4 #45c0c0,stop:1 #367cbb); border-radius: 8px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #15203a; width: 10px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #425878; border-radius: 5px; min-height: 30px; }
QMessageBox, QDialog { background: #17243d; }
"""


def label(text: str, object_name: str = "") -> QLabel:
    item = QLabel(text)
    if object_name:
        item.setObjectName(object_name)
    item.setWordWrap(True)
    return item


def card(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    container = QFrame()
    container.setObjectName("card")
    body = QVBoxLayout(container)
    body.setContentsMargins(21, 20, 21, 20)
    body.setSpacing(12)
    if title:
        body.addWidget(label(title, "section"))
    return container, body


def line(items: list[QWidget], spacing: int = 9) -> QWidget:
    parent = QWidget()
    row = QHBoxLayout(parent)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(spacing)
    for item in items:
        row.addWidget(item)
    return parent


def scroll_page() -> tuple[QScrollArea, QVBoxLayout]:
    area = QScrollArea()
    area.setWidgetResizable(True)
    body = QWidget()
    content = QVBoxLayout(body)
    content.setContentsMargins(14, 6, 14, 20)
    content.setSpacing(17)
    area.setWidget(body)
    return area, content


def ask(parent: QWidget, title: str, prompt: str, default: str = "") -> tuple[str, bool]:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(475)
    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)
    layout.addWidget(label(prompt))
    entry = QLineEdit(default)
    layout.addWidget(entry)
    ok = QPushButton("Continue")
    ok.setObjectName("primary")
    cancel = QPushButton("Cancel")
    controls = line([ok, cancel])
    layout.addWidget(controls)
    ok.clicked.connect(dialog.accept)
    cancel.clicked.connect(dialog.reject)
    entry.returnPressed.connect(dialog.accept)
    result = dialog.exec() == QDialog.DialogCode.Accepted
    return entry.text().strip(), result


class _CodeHighlighter(QSyntaxHighlighter):
    """Lightweight, dependency-free syntax accents for Python and JSON."""
    def __init__(self, document):
        super().__init__(document)
        self._suffix = ""
        self._keyword = QTextCharFormat()
        self._keyword.setForeground(QColor("#bb95fa"))
        self._keyword.setFontWeight(QFont.Weight.Bold)
        self._string = QTextCharFormat()
        self._string.setForeground(QColor("#86dcbd"))
        self._comment = QTextCharFormat()
        self._comment.setForeground(QColor("#99a3bd"))

    def set_filename(self, path: str) -> None:
        self._suffix = Path(path).suffix.lower()
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if self._suffix not in (".py", ".json", ".toml"):
            return
        for match in re.finditer(r"\b(def|class|return|import|from|if|else|elif|try|except|finally|with|as|for|while|yield|async|await|True|False|None)\b", text):
            self.setFormat(match.start(), len(match.group()), self._keyword)
        for match in re.finditer(r"\"[^\"\n]*\"|'[^'\n]*'", text):
            self.setFormat(match.start(), len(match.group()), self._string)
        if self._suffix in (".py", ".toml"):
            match = re.search(r"#.*$", text)
            if match:
                self.setFormat(match.start(), len(match.group()), self._comment)


class Task(QThread):
    progress = Signal(str, int, int, str)
    successful = Signal(object)
    failed = Signal(str)

    def __init__(self, action: Callable[[Callable], Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.action = action

    def run(self) -> None:
        try:
            value = self.action(lambda phase, done, total, detail:
                                self.progress.emit(phase, done, total, detail))
            self.successful.emit(value)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class StrapmanWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.edition = active_edition()
        self.brand_name = display_name(self.edition)
        self.settings = Settings()
        self.store = Store()
        self.journal = Journal()
        self._recovered_on_start = self.store.recover_interrupted_jobs()
        self.github: GitHub | None = None
        self.engine: Engine | None = None
        self.task: Task | None = None
        self._currently_running = False
        self._flash_count = 0
        self._flash_message = "JOB COMPLETE"
        self._phase_metrics: dict[str, tuple[float, int, int]] = {}
        self._repo_cache: list[dict] = []
        self._readme_sha = ""
        self._readme_scope: tuple[str, str, str] | None = None
        self._readme_original = ""
        self._active_task_kind = ""
        self._verify_cue_sent = False
        self._workbench = TextWorkbench()
        self._remote_workbench = RemoteTextWorkbench()
        self._remote_directory = ""
        self._manual_base = Path(__file__).resolve().parent.parent / "docs"
        self._media_player = None
        self._audio_output = None
        self._sound_event = ""
        self._pending_cues: list[str] = []
        self._native_audio = None
        self._last_audio_failure = ""
        if self.edition == BOOTLEGGER and sys.platform == "win32":
            try:
                self._native_audio = WindowsMp3Player()
            except AudioPlaybackError as exc:
                self._last_audio_failure = str(exc)
        self._closing_for_exit_audio = False
        self._power_reminder = PowerReminder(on_ac_power(), interval_seconds=60.0)
        self._theme = normalize_theme(self.settings.get("theme_mode"), self.edition)
        self._base_title = f"{self.brand_name} • Background Gremlin Group"
        if self.edition == BOOTLEGGER and QMediaPlayer is not None and QAudioOutput is not None:
            self._audio_output = QAudioOutput(self)
            self._audio_output.setVolume(1.0)
            self._media_player = QMediaPlayer(self)
            self._media_player.setAudioOutput(self._audio_output)
            self._media_player.errorOccurred.connect(self._audio_error)
        self.setWindowTitle(self._base_title)
        self.setWindowIcon(strapman_icon())
        self.resize(1320, 850)
        self.setMinimumSize(1010, 700)
        self.setStyleSheet(edition_stylesheet(STYLES, edition=self.edition, theme=self._theme))
        self._build()
        self._load_settings()
        self._refresh_history()
        self._event("SYSTEM", f"{self.brand_name} initialized; sign in to load repositories")
        if self._recovered_on_start:
            self._event("RECOVERY", f"Found {len(self._recovered_on_start)} interrupted job(s). "
                        "Their checkpoints were retained; open Job History and select Resume.")
        self._cue_timer = QTimer(self)
        self._cue_timer.setInterval(250)
        self._cue_timer.timeout.connect(self._drain_cues)
        self._cue_timer.start()
        self._power_timer = QTimer(self)
        self._power_timer.setInterval(10000)
        self._power_timer.timeout.connect(self._check_power_change)
        self._power_timer.start()
        QTimer.singleShot(1000, self._check_power_change)
        if not self.settings.get("onboarded"):
            QTimer.singleShot(350, self._show_first_run)
        elif self._startup_token_available():
            QTimer.singleShot(120, self._connect)

    def _build(self) -> None:
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        # Resizable, keyboard-accessible sidebar with an explicit compact mode.
        # Compact mode keeps every action, rather than clipping the last items.
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        sidebar = self.sidebar
        sidebar.setFixedWidth(260)
        menu = QVBoxLayout(sidebar)
        menu.setContentsMargins(15, 19, 13, 13)
        menu.setSpacing(10)
        # Brand header only: icon ABOVE full wordmark. Sidebar page entries
        # retain their original text/icon layout; this block must never clip.
        brand_header = QVBoxLayout()
        brand_header.setSpacing(4)
        brand_top = QHBoxLayout()
        self.brand_icon = QLabel()
        self.brand_icon.setPixmap(strapman_icon().pixmap(58, 58))
        self.brand_icon.setFixedSize(62, 62)
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_icon.setAccessibleName(f"{self.brand_name} application logo")
        brand_top.addWidget(self.brand_icon)
        brand_top.addStretch(1)
        self.sidebar_toggle = QPushButton("≪")
        self.sidebar_toggle.setToolTip("Collapse sidebar to icons")
        self.sidebar_toggle.setAccessibleName("Collapse or expand the navigation sidebar")
        self.sidebar_toggle.setFixedSize(30, 36)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        brand_top.addWidget(self.sidebar_toggle)
        brand_header.addLayout(brand_top)
        self.brand_title = label("BOOTLEGGER" if self.edition == BOOTLEGGER else "STRAPMAN", "brand")
        self.brand_title.setFont(QFont("Segoe UI", 17 if self.edition == BOOTLEGGER else 19, QFont.Weight.Black))
        self.brand_title.setWordWrap(False)
        self.brand_title.setMinimumWidth(0)
        self.brand_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        brand_header.addWidget(self.brand_title)
        menu.addLayout(brand_header)
        self.brand_subtitle = label("PRO / " + self._theme.upper()
                                    if self.edition == BOOTLEGGER else "LITE / RETRO BUBBLE", "brandSubtitle")
        menu.addWidget(self.brand_subtitle)
        menu.addSpacing(10)
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_inner = QWidget()
        nav_inner.setObjectName("navContent")
        nav = QVBoxLayout(nav_inner)
        nav.setContentsMargins(0, 0, 2, 0)
        nav.setSpacing(7)
        self.nav_pages = (
            ("◈", "Upload Station"),
            ("▣", "Repository Desk"),
            ("▤", "Jobs & Rebuild"),
            ("⚙", "Settings & Help"),
        )
        self.nav_buttons = []
        for index, (symbol, title) in enumerate(self.nav_pages):
            button = QPushButton(f"{symbol}  {title}")
            button.setObjectName("nav")
            button.setMinimumHeight(48)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.clicked.connect(lambda checked=False, page=index: self._navigate(page))
            nav.addWidget(button)
            self.nav_buttons.append(button)
        nav.addStretch(1)
        nav_scroll.setWidget(nav_inner)
        menu.addWidget(nav_scroll, 1)
        self.sidebar_footer, footer_layout = card()
        footer_layout.setContentsMargins(12, 12, 12, 12)
        footer_layout.addWidget(label("● LOCAL-FIRST", "tag"))
        footer_layout.addWidget(label("Direct GitHub uploads\nNo Actions · No hosted builds", "caption"))
        menu.addWidget(self.sidebar_footer)
        self.sidebar_copyright = label("Background Gremlin Group\nCreating Unique Tools for Unique Individuals", "caption")
        menu.addWidget(self.sidebar_copyright)
        self._sidebar_compact = False
        row.addWidget(sidebar)

        center = QWidget()
        center_body = QVBoxLayout(center)
        center_body.setContentsMargins(20, 16, 23, 15)
        center_body.setSpacing(12)
        top = QHBoxLayout()
        self.screen_title = label("Upload Station", "hero")
        top.addWidget(self.screen_title)
        top.addStretch()
        self.connection_status = label("● Not connected", "tag")
        self.connection_status.setMaximumWidth(235)
        top.addWidget(self.connection_status)
        center_body.addLayout(top)

        # Contextual workflow steps within the ACTIVE page, NOT a second
        # navigation menu. Steps scroll to actual controls; no actions run.
        workflow = QHBoxLayout()
        workflow.setSpacing(7)
        self.workflow_buttons = []
        self._workflow_sections: dict[int, list[tuple[str, QWidget]]] = {}
        for index in range(4):
            button = QPushButton()
            button.setObjectName("workflow")
            button.setVisible(False)
            button.setToolTip("Jump to this section of the current page; nothing is submitted")
            button.clicked.connect(lambda checked=False, n=index: self._jump_workflow(n))
            workflow.addWidget(button)
            self.workflow_buttons.append(button)
        center_body.addLayout(workflow)
        self.pages = QStackedWidget()
        center_body.addWidget(self.pages, 1)
        self.pages.addWidget(self._make_upload())
        self.pages.addWidget(self._make_repo())
        self.pages.addWidget(self._make_history())
        self.pages.addWidget(self._make_settings())
        row.addWidget(center, 1)
        self._update_workflow(0)

    def _update_workflow(self, page: int) -> None:
        sections = self._workflow_sections.get(page, [])
        for index, button in enumerate(self.workflow_buttons):
            if index < len(sections):
                button.setText(f"{index + 1:02d}  {sections[index][0]}")
                button.setAccessibleName(f"Jump to {sections[index][0]}")
                button.setVisible(True)
            else:
                button.setVisible(False)

    def _jump_workflow(self, index: int) -> None:
        page = self.pages.currentIndex()
        sections = self._workflow_sections.get(page, [])
        if not (0 <= index < len(sections)):
            return
        scroll = self.pages.currentWidget()
        if not isinstance(scroll, QScrollArea):
            return
        target = sections[index][1]
        if target is None:
            return
        # Target QWidget lives under the scroll area's content widget.
        y = target.mapTo(scroll.widget(), target.rect().topLeft()).y()
        scroll.verticalScrollBar().setValue(max(0, y - 4))

    def _toggle_sidebar(self) -> None:
        self._sidebar_compact = not self._sidebar_compact
        compact = self._sidebar_compact
        self.sidebar.setFixedWidth(82 if compact else 260)
        self.brand_title.setVisible(not compact)
        self.brand_subtitle.setVisible(not compact)
        self.sidebar_footer.setVisible(not compact)
        self.sidebar_copyright.setVisible(not compact)
        self.brand_icon.setVisible(not compact)
        self.sidebar_toggle.setText("≫" if compact else "≪")
        self.sidebar_toggle.setToolTip("Expand sidebar" if compact else "Collapse sidebar to icons")
        for button, (symbol, title) in zip(self.nav_buttons, self.nav_pages):
            button.setText(symbol if compact else f"{symbol}  {title}")
            button.setProperty("compact", compact)
            button.style().unpolish(button)
            button.style().polish(button)

    def _navigate(self, page: int) -> None:
        if not 0 <= page < self.pages.count():
            return
        self.pages.setCurrentIndex(page)
        for idx, button in enumerate(self.nav_buttons):
            button.setChecked(page == idx)
        self._update_workflow(page)
        self.screen_title.setText(self.nav_pages[page][1])
        if page == 2:
            self._refresh_history()
        elif page == 1 and self.github and not (self.task and self.task.isRunning()):
            QTimer.singleShot(0, self._fetch_repo_info)

    def _make_upload(self) -> QWidget:
        area, content = scroll_page()
        hero, hero_layout = card()
        hero_row = QHBoxLayout()
        hero_row.addWidget(label("✦  STAGE · VERIFY · PUBLISH", "tag"))
        hero_row.addStretch()
        hero_row.addWidget(label("PRECISE / RESUMABLE / PARALLEL", "caption"))
        hero_layout.addLayout(hero_row)
        hero_layout.addWidget(label("Drop the stress. Keep every byte.", "section"))
        hero_layout.addWidget(label("Split into verified segments, upload with parallel workers, and publish an auditable manifest. GitHub commits happen sequentially to protect your branch.", "caption"))
        content.addWidget(hero)

        dest, d = card("01   Destination")
        self.repo_combo = QComboBox()
        self.repo_combo.setEditable(True)
        self.repo_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.repo_combo.setPlaceholderText("owner/repository or paste github.com URL")
        self.repo_combo.currentTextChanged.connect(self._repo_changed)
        new_repo = QPushButton("＋ New Repo")
        new_repo.clicked.connect(self._create_repository)
        add_url = QPushButton("＋ Add URL")
        add_url.clicked.connect(self._add_repo_url)
        d.addWidget(line([self.repo_combo, add_url, new_repo]))
        self.branch_combo = QComboBox()
        self.branch_combo.setEditable(True)
        self.branch_combo.setPlaceholderText("Branch (main)")
        self.branch_combo.currentTextChanged.connect(self._branch_changed)
        refresh_branches = QPushButton("↻ Branches")
        refresh_branches.clicked.connect(self._load_branches)
        new_branch = QPushButton("＋ Branch")
        new_branch.clicked.connect(self._create_branch)
        d.addWidget(line([label("Branch:"), self.branch_combo, refresh_branches, new_branch]))
        content.addWidget(dest)

        source, s = card("02   Payload & Strategy")
        self.source_entry = QLineEdit()
        self.source_entry.setPlaceholderText("Choose a file from your computer")
        self.source_entry.textChanged.connect(self._source_changed)
        file_button = QPushButton("Browse Files…")
        file_button.clicked.connect(self._browse_source)
        s.addWidget(line([self.source_entry, file_button]))
        self.path_entry = QLineEdit()
        self.path_entry.setPlaceholderText("Optional final file path for staged source or small-file publication")
        s.addWidget(line([label("Final path:"), self.path_entry]))
        controls = QGridLayout()
        controls.setHorizontalSpacing(16)
        controls.setVerticalSpacing(9)
        self.mode = QComboBox()
        self.mode.addItems(["Chunked binary / archive", "Cumulative source staging"])
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(1, 16)
        self.chunk_spin.setSuffix(" MiB")
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 12)
        controls.addWidget(label("Upload strategy"), 0, 0)
        controls.addWidget(self.mode, 1, 0)
        controls.addWidget(label("Chunk size"), 0, 1)
        controls.addWidget(self.chunk_spin, 1, 1)
        controls.addWidget(label("Parallel workers"), 0, 2)
        controls.addWidget(self.workers_spin, 1, 2)
        s.addLayout(controls)
        self.verify_check = QCheckBox("Verify every GitHub blob after upload (SHA-256)")
        self.reconstruct_check = QCheckBox("Automatically rebuild and SHA-256 verify the original after upload (default: on)")
        self.publish_full_check = QCheckBox("Publish original file too (only files up to 16 MiB)")
        for check in (self.verify_check, self.reconstruct_check, self.publish_full_check):
            s.addWidget(check)
        self.auto_build_output = label("Workflow: stage → upload → remote verify → automatic rebuild → final SHA-256 check", "caption")
        s.addWidget(self.auto_build_output)
        self.source_detail = label("Source size and required local staging space will be checked.", "caption")
        s.addWidget(self.source_detail)
        content.addWidget(source)

        progress, p = card("03   Transfer Console")
        self.state_label = label("READY  •  Select a repository and a file", "tag")
        p.addWidget(self.state_label)
        self.transfer_metrics = label("Waiting for a job · 0 bytes transferred", "caption")
        p.addWidget(self.transfer_metrics)
        self.phase_bars = {}
        for key, title in (("hashing", "Fingerprint"), ("splitting", "Partition"),
                           ("uploading", "Transfer"), ("committing", "Publish"),
                           ("verify", "Remote integrity"), ("downloading", "Restore transfer"),
                           ("assembling", "Reconstruction")):
            roww = QWidget()
            rlayout = QHBoxLayout(roww)
            rlayout.setContentsMargins(0, 1, 0, 1)
            title_label = label(title, "caption")
            title_label.setFixedWidth(125)
            bar = QProgressBar()
            bar.setValue(0)
            bar.setFormat("%p%")
            rlayout.addWidget(title_label)
            rlayout.addWidget(bar, 1)
            p.addWidget(roww)
            self.phase_bars[key] = bar
        self.start_button = QPushButton("✦  START STAGED UPLOAD")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start_upload)
        self.pause_button = QPushButton("Ⅱ  Pause Safely")
        self.pause_button.setEnabled(False)
        self.pause_button.setToolTip("Finish in-flight operations, save checkpoints and stop. Resume from Job History after reboot.")
        self.pause_button.clicked.connect(self._pause_job)
        self.cancel_button = QPushButton("Stop Job")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_job)
        self.restore_button = QPushButton("Restore from GitHub…")
        self.restore_button.clicked.connect(self._restore_dialog)
        p.addWidget(line([self.start_button, self.pause_button, self.cancel_button, self.restore_button]))
        self.event_log = QPlainTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumBlockCount(700)
        self.event_log.setMinimumHeight(150)
        p.addWidget(self.event_log)
        self.rebuilt_output_label = label("Rebuilt output: none yet", "caption")
        self.rebuilt_output_label.setWordWrap(True)
        p.addWidget(self.rebuilt_output_label)
        open_output = QPushButton("Open Rebuilt Output Folder")
        open_output.clicked.connect(self._open_rebuild_output_folder)
        p.addWidget(open_output)
        content.addWidget(progress)
        self._workflow_sections[0] = [
            ("Destination", dest), ("File & strategy", source),
            ("Transfer & auto rebuild", progress),
        ]
        content.addStretch(1)
        return area

    def _make_repo(self) -> QWidget:
        area, content = scroll_page()
        a, body = card("Repository Manager")
        body.addWidget(label("Edit README.md, inspect repository visibility, and enable supported GitHub security controls. All changes require your action.", "caption"))
        self.repo_info = label("No repository selected", "tag")
        body.addWidget(self.repo_info)
        roww = line([QPushButton("Refresh Repo Info"), QPushButton("Make Private"),
                     QPushButton("Enable Vulnerability Alerts"), QPushButton("Enable Automated Security Fixes")])
        controls = roww.layout()
        controls.itemAt(0).widget().clicked.connect(self._fetch_repo_info)
        controls.itemAt(1).widget().clicked.connect(self._make_private)
        controls.itemAt(2).widget().clicked.connect(self._enable_alerts)
        controls.itemAt(3).widget().clicked.connect(self._enable_fixes)
        body.addWidget(roww)
        content.addWidget(a)
        b, readme_layout = card("README.md Editor")
        readme_layout.addWidget(label("Load an existing README from the selected repository and branch. Save uses GitHub's current file SHA to detect conflicts.", "caption"))
        self.readme_editor = QPlainTextEdit()
        self.readme_editor.setPlaceholderText("README.md will load here. You can create one if it doesn't exist.")
        self.readme_editor.setMinimumHeight(340)
        readme_layout.addWidget(self.readme_editor)
        self.readme_status = label("Load README to bind this editor to an account, repository and branch", "caption")
        readme_layout.addWidget(self.readme_status)
        load_readme = QPushButton("Load README")
        load_readme.clicked.connect(self._load_readme)
        save_readme = QPushButton("Save README to GitHub")
        save_readme.setObjectName("primary")
        save_readme.clicked.connect(self._save_readme)
        readme_layout.addWidget(line([load_readme, save_readme]))
        workspace, workspace_body = card("Repository Code Workbench")
        workspace_body.addWidget(label(
            "Browse and edit GitHub text files on the selected branch, review changes and commit deliberately. "
            "Or inspect local files, validate source and run trusted local tests without an external IDE.", "caption"))
        self.workbench_tabs = QTabWidget()
        self.workbench_tabs.addTab(self._make_remote_workbench(), "GitHub repository")
        self.workbench_tabs.addTab(self._make_workbench(), "Local files and tests")
        workspace_body.addWidget(self.workbench_tabs)
        content.addWidget(workspace)
        content.addWidget(b)
        self._workflow_sections[1] = [
            ("Repository settings", a), ("Browse & edit code", workspace),
            ("README editor", b),
        ]
        content.addStretch()
        return area

    def _make_history(self) -> QWidget:
        area, content = scroll_page()
        head, body = card("Resumable Job History")
        body.addWidget(label("Checkpoints live in your OS-specific application data directory, never in the source repository. A failed upload can resume without rehashing unaffected parts.", "caption"))
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(370)
        body.addWidget(self.history_list)
        refresh = QPushButton("↻ Refresh")
        refresh.clicked.connect(self._refresh_history)
        resume = QPushButton("Resume Selected Job")
        resume.setObjectName("primary")
        resume.clicked.connect(self._resume_selected)
        inspect = QPushButton("Show Job Details")
        inspect.clicked.connect(self._show_job_details)
        audit = QPushButton("✓ Verify on GitHub")
        audit.setToolTip("Read-only audit: verify committed chunk paths, SHA-256 data and the final manifest")
        audit.clicked.connect(self._audit_selected)
        body.addWidget(line([refresh, inspect, audit, resume]))
        build, operations = card("Build / Rebuild · Verified Original Files")
        operations.addWidget(label(
            "This is a reconstruction workflow, separate from both upload strategies. "
            "Discover fully committed Strapman manifests on the selected GitHub branch, "
            "download and SHA-256-verify every part, and rebuild a local original. "
            "Existing destination files are never overwritten.", "caption"))
        self.build_manifest_combo = QComboBox()
        self.build_manifest_combo.setEditable(True)
        self.build_manifest_combo.setPlaceholderText("strapman-uploads/<upload-id>/manifest.json")
        discover = QPushButton("Discover GitHub Builds")
        discover.clicked.connect(self._discover_builds)
        operations.addWidget(line([self.build_manifest_combo, discover]))
        self.build_dest_entry = QLineEdit()
        self.build_dest_entry.setPlaceholderText("Save rebuilt file to a new local path")
        browse = QPushButton("Choose Destination…")
        browse.clicked.connect(self._browse_build_destination)
        operations.addWidget(line([self.build_dest_entry, browse]))
        remote_build = QPushButton("Build / Rebuild from GitHub")
        remote_build.setObjectName("primary")
        remote_build.clicked.connect(self._build_from_github)
        local_build = QPushButton("Rebuild from Local Manifest + Parts…")
        local_build.clicked.connect(self._build_from_local)
        operations.addWidget(line([remote_build, local_build]))
        self.build_status = label("Ready to discover remote builds or select local verified chunks.", "caption")
        operations.addWidget(self.build_status)
        content.addWidget(head)
        content.addWidget(build)
        self._workflow_sections[2] = [
            ("Recovery & audit", head), ("Manual rebuild", build),
        ]
        content.addStretch()
        return area

    def _make_workbench(self) -> QWidget:
        """Built-in local editor embedded in the Repository Desk."""
        panel = QWidget()
        content = QVBoxLayout(panel)
        content.setContentsMargins(3, 12, 3, 12)
        header, body = card("Local Code Editor")
        body.addWidget(label("Open a local UTF-8 Python, JSON, TOML, Markdown, or other text file. Validate syntax without running code. Save requires your confirmation, creates a separate backup, and refuses external disk changes. Save As never overwrites.", "caption"))
        self.code_file = label("No file loaded", "tag")
        self.code_status = label("Editor is idle", "caption")
        body.addWidget(self.code_file)
        commands = []
        for caption, callback in (
            ("Open File", self._wb_open), ("Check Syntax", self._wb_check),
            ("Show Diff", self._wb_diff), ("Save File", self._wb_save),
            ("Save As", self._wb_save_as)):
            button = QPushButton(caption)
            button.clicked.connect(callback)
            commands.append(button)
        body.addWidget(line(commands))
        self.code_editor = QPlainTextEdit()
        self.code_editor.setMinimumHeight(480)
        self.code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_editor.setFont(QFont("Consolas", 11))
        self.code_editor.setTabStopDistance(32)
        self._code_highlighter = _CodeHighlighter(self.code_editor.document())
        body.addWidget(self.code_editor)
        body.addWidget(self.code_status)
        self.test_framework = QComboBox()
        self.test_framework.addItem("Auto (pytest if installed; otherwise unittest)", "auto")
        self.test_framework.addItem("Python unittest", "unittest")
        self.test_framework.addItem("pytest (if already installed)", "pytest")
        self.test_framework.setToolTip("Tests execute locally under your account only after confirmation; no dependencies are installed")
        test_button = QPushButton("Run Local Tests…")
        test_button.setToolTip("Runs trusted local tests only after explicit confirmation; GitHub source is never executed automatically")
        test_button.clicked.connect(self._wb_run_tests)
        body.addWidget(line([self.test_framework, test_button]))
        content.addWidget(header)
        return panel

    def _discover_builds(self) -> None:
        try:
            client = self._authenticated()
            repo, branch = self._selected_repo(), self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "Discover builds", str(exc))
            return
        engine = Engine(client, self.store, self.journal)
        def loaded(paths):
            try:
                if (self._selected_repo(), self._selected_branch()) != (repo, branch):
                    return True
            except ValueError:
                return True
            previous = self.build_manifest_combo.currentText()
            self.build_manifest_combo.clear()
            self.build_manifest_combo.addItems(paths)
            if previous and previous not in paths:
                self.build_manifest_combo.setEditText(previous)
            self.build_status.setText(f"Found {len(paths)} committed Strapman manifests on {repo}:{branch}. "
                                      "A discovered manifest is verified again during reconstruction.")
            return True
        self._launch(lambda notify: engine.discover_builds(repo, branch),
                     f"Discovering published builds on {repo}:{branch}", loaded)

    def _browse_build_destination(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Choose a new reconstructed file destination")
        if path:
            self.build_dest_entry.setText(path)

    def _build_from_github(self) -> None:
        try:
            client = self._authenticated()
            repo, branch = self._selected_repo(), self._selected_branch()
            manifest = self.build_manifest_combo.currentText().strip()
            destination = Path(self.build_dest_entry.text().strip()).expanduser()
            if not manifest.startswith("strapman-uploads/") or not manifest.endswith("/manifest.json"):
                raise ValueError("Choose a committed Strapman manifest first")
            if not self.build_dest_entry.text().strip():
                raise ValueError("Choose the rebuilt file's destination first")
            if destination.exists():
                raise FileExistsError(f"Rebuilt destination already exists: {destination}")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Build / Rebuild", str(exc))
            return
        if QMessageBox.question(self, "Build original file",
                                f"Download, verify and reconstruct {manifest} from {repo}:{branch}?\n"
                                f"Destination: {destination}\nNo remote source or existing local file is replaced.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        engine = Engine(client, self.store, self.journal)
        self.engine = engine
        def completed(result):
            self.build_status.setText(f"Verified reconstruction saved: {result}")
            return True
        self._launch(lambda notify: engine.rebuild_from_github(
            repo, branch, manifest, destination,
            workers=self.workers_spin.value(), callback=notify),
            f"Building verified original from {repo}:{branch}/{manifest}", completed,
            job_kind="restore")

    def _build_from_local(self) -> None:
        manifest, _ = QFileDialog.getOpenFileName(self, "Choose a local Strapman manifest", filter="JSON manifest (*.json)")
        if not manifest:
            return
        parts = QFileDialog.getExistingDirectory(self, "Select local chunk cache directory")
        if not parts:
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Choose new rebuilt output file")
        if not destination:
            return
        if Path(destination).exists():
            QMessageBox.warning(self, "Build / Rebuild", "Destination already exists; no file will be overwritten")
            return
        if QMessageBox.question(self, "Rebuild from local parts",
                                f"Verify the manifest and every local chunk, then reconstruct into {destination}?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        engine = Engine(self.github, self.store, self.journal)
        self.engine = engine
        def completed(result):
            self.build_status.setText(f"Verified local reconstruction saved: {result}")
            return True
        self._launch(lambda notify: engine.rebuild_local(
            Path(manifest), Path(parts), Path(destination), callback=notify),
            f"Rebuilding original from locally verified chunks", completed,
            job_kind="restore")

    def _make_remote_workbench(self) -> QWidget:
        panel = QWidget()
        body = QVBoxLayout(panel)
        body.setContentsMargins(3, 12, 3, 12)
        body.setSpacing(9)
        body.addWidget(label("Browse the selected GitHub branch. Opening files is read-only; editing and creating a file requires an explicit SHA-checked commit.", "caption"))
        self.remote_folder_label = label("Directory: /", "tag")
        body.addWidget(self.remote_folder_label)
        browse = QPushButton("↻ Browse Folder")
        browse.clicked.connect(self._remote_browse)
        up = QPushButton("↑ Parent")
        up.clicked.connect(self._remote_parent)
        body.addWidget(line([browse, up]))
        self.remote_files = QListWidget()
        self.remote_files.setMinimumHeight(135)
        self.remote_files.itemDoubleClicked.connect(self._remote_choose_item)
        body.addWidget(self.remote_files)
        self.remote_code_path = QLineEdit()
        self.remote_code_path.setPlaceholderText("Path in repository: example src/module.py")
        body.addWidget(self.remote_code_path)
        open_file = QPushButton("Open GitHub File")
        open_file.clicked.connect(self._remote_open)
        new_file = QPushButton("New GitHub File")
        new_file.clicked.connect(self._remote_new)
        body.addWidget(line([open_file, new_file]))
        self.remote_code_editor = QPlainTextEdit()
        self.remote_code_editor.setMinimumHeight(330)
        self.remote_code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.remote_code_editor.setFont(QFont("Consolas", 10))
        self._remote_highlighter = _CodeHighlighter(self.remote_code_editor.document())
        body.addWidget(self.remote_code_editor)
        self.remote_code_status = label("Choose a file to inspect; nothing is automatically committed.", "caption")
        body.addWidget(self.remote_code_status)
        validate = QPushButton("Validate Syntax")
        validate.clicked.connect(self._remote_validate)
        compare = QPushButton("Review Diff")
        compare.clicked.connect(self._remote_diff)
        save = QPushButton("Review & Commit to GitHub…")
        save.setObjectName("primary")
        save.clicked.connect(self._remote_commit)
        body.addWidget(line([validate, compare, save]))
        return panel

    def _remote_scope(self) -> tuple[str, str, str]:
        self._authenticated()
        return self.settings.get("auth_login"), self._selected_repo(), self._selected_branch()

    def _remote_confirm_draft(self) -> bool:
        if not self._remote_workbench.dirty(self.remote_code_editor.toPlainText()):
            return True
        return QMessageBox.question(
            self, "Unsaved GitHub code", "Discard the unsaved GitHub code draft? No commit has been made.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _remote_browse(self) -> None:
        try:
            login, repo, branch = self._remote_scope()
            directory = validate_repository_file_path(self._remote_directory, allow_root=True)
        except (ValueError, GitHubError) as exc:
            QMessageBox.warning(self, "Browse repository", str(exc))
            return
        client = self.github
        def loaded(rows):
            try:
                if self._remote_scope() != (login, repo, branch):
                    return True
            except ValueError:
                return True
            self.remote_files.clear()
            for entry in rows:
                item = QListWidgetItem(("▣  " if entry["type"] == "dir" else "▤  ") + entry["name"])
                item.setData(Qt.ItemDataRole.UserRole, entry)
                item.setToolTip(entry["path"])
                self.remote_files.addItem(item)
            self.remote_folder_label.setText("Directory: /" + directory)
            self.remote_code_status.setText(f"Listed {len(rows)} entries from {repo}:{branch}. Double-click a file to inspect.")
            return True
        self._launch(lambda notify: client.list_directory(repo, branch, directory),
                     f"Browsing GitHub {repo}:{branch}/{directory}", loaded)

    def _remote_parent(self) -> None:
        self._remote_directory = self._remote_directory.rpartition("/")[0]
        self._remote_browse()

    def _remote_choose_item(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, dict):
            return
        if entry["type"] == "dir":
            self._remote_directory = entry["path"]
            self._remote_browse()
        else:
            self.remote_code_path.setText(entry["path"])
            self._remote_open()

    def _remote_open(self) -> None:
        if not self._remote_confirm_draft():
            return
        try:
            login, repo, branch = self._remote_scope()
            path = validate_repository_file_path(self.remote_code_path.text().strip())
        except (ValueError, GitHubError) as exc:
            QMessageBox.warning(self, "GitHub file", str(exc))
            return
        client = self.github
        def loaded(result):
            try:
                if self._remote_scope() != (login, repo, branch) or self.remote_code_path.text().strip() != path:
                    return True
                if result is None:
                    QMessageBox.information(self, "GitHub file missing", "No file exists at that path. Use New GitHub File to create one.")
                    return True
                self._remote_workbench.bind(login, repo, branch, path, result[0], result[1])
                self.remote_code_editor.setPlainText(result[0])
                self._remote_highlighter.set_filename(path)
                self.remote_code_status.setText(f"Loaded {path} from {repo}:{branch} · Git SHA {result[1][:12]}")
            except (ValueError, UnicodeDecodeError) as exc:
                QMessageBox.warning(self, "GitHub editor", str(exc))
            return True
        self._launch(lambda notify: client.read_text(repo, path, branch),
                     f"Reading GitHub file {repo}:{branch}/{path}", loaded)

    def _remote_new(self) -> None:
        if not self._remote_confirm_draft():
            return
        try:
            login, repo, branch = self._remote_scope()
            path = validate_repository_file_path(self.remote_code_path.text().strip())
        except (ValueError, GitHubError) as exc:
            QMessageBox.warning(self, "New GitHub file", str(exc))
            return
        client = self.github
        def checked(sha):
            if self._remote_scope() != (login, repo, branch):
                return True
            if sha is not None:
                QMessageBox.warning(self, "File exists", "A GitHub file already exists here. Open it rather than creating over it.")
                return True
            self._remote_workbench.bind(login, repo, branch, path, "", "")
            self.remote_code_editor.setPlainText("")
            self.remote_code_path.setText(path)
            self._remote_highlighter.set_filename(path)
            self.remote_code_status.setText(f"New file {path} · Not created on GitHub until you review and commit")
            return True
        self._launch(lambda notify: client.file_sha(repo, branch, path),
                     f"Checking GitHub path {path}", checked)

    def _remote_validate(self) -> None:
        try:
            path = validate_repository_file_path(self.remote_code_path.text().strip())
        except ValueError as exc:
            QMessageBox.warning(self, "Syntax validation", str(exc))
            return
        result = check_syntax(self.remote_code_editor.toPlainText(), path)
        self.remote_code_status.setText(result["message"])
        if result["valid"] is False:
            QMessageBox.warning(self, "Syntax validation failed", result["message"])

    def _show_diff(self, title: str, diff: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(950, 650)
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setFont(QFont("Consolas", 10))
        box.setPlainText(diff or "No changes")
        layout.addWidget(box)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _remote_diff(self) -> None:
        try:
            self._show_diff("Proposed GitHub code changes", self._remote_workbench.diff(self.remote_code_editor.toPlainText()))
        except ValueError as exc:
            QMessageBox.warning(self, "GitHub diff", str(exc))

    def _remote_commit(self) -> None:
        try:
            login, repo, branch = self._remote_scope()
            path = self.remote_code_path.text().strip()
            content = self.remote_code_editor.toPlainText()
            sha = self._remote_workbench.prepare_commit(login, repo, branch, path, content)
        except (ValueError, GitHubError) as exc:
            QMessageBox.warning(self, "GitHub commit refused", str(exc))
            return
        diff = self._remote_workbench.diff(content)
        self._show_diff("Review before GitHub commit", diff)
        message, ok = ask(self, "Commit message", f"Commit {path} to {repo}:{branch}. This changes the selected branch.",
                          f"edit: update {Path(path).name} in Strapman")
        if not ok or not message:
            return
        if QMessageBox.question(self, "Confirm GitHub write",
                                f"Commit reviewed changes to {repo}:{branch}/{path}?\n"
                                "No force push; GitHub rejects a stale file SHA.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        client = self.github
        scope = (login, repo, branch, path)
        def saved(result):
            if self._remote_workbench.scope == scope and self.remote_code_editor.toPlainText() == content:
                metadata = result.get("content") if isinstance(result, dict) else None
                new_sha = metadata.get("sha", "") if isinstance(metadata, dict) else ""
                if not re.fullmatch(r"[0-9a-f]{40}", new_sha or ""):
                    self._remote_workbench.scope = None
                    self.remote_code_status.setText(
                        "Commit succeeded without a verified file SHA; reload before committing again")
                    return True
                self._remote_workbench.bind(login, repo, branch, path, content, new_sha)
                self.remote_code_status.setText(f"Committed {path} to {repo}:{branch} · SHA {new_sha[:12]}")
            else:
                self.remote_code_status.setText("GitHub write completed, but your editor changed; inspect before next commit")
            # A confirmed remote SHA is required before announcing an update.
            metadata = result.get("content") if isinstance(result, dict) else None
            committed_sha = metadata.get("sha", "") if isinstance(metadata, dict) else ""
            if re.fullmatch(r"[0-9a-f]{40}", committed_sha):
                self._play_cue(repository_write_sound_event(path))
            return True
        self._launch(lambda notify: client.write_text(repo, branch, path, content, message, sha),
                     f"Committing GitHub code {path}", saved)

    def _wb_run_tests(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose a trusted local unittest project")
        if not path:
            return
        framework = self.test_framework.currentData()
        if QMessageBox.question(self, "Run local Python tests",
                                f"Run {framework} test discovery in this local folder? Tests execute Python code with your user permissions.\n"
                                "Only run code you trust. GitHub files are never run automatically.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        def finished(result):
            self._show_diff("Local Python test results", result["output"])
            self.code_status.setText(f"Local {result['framework']} finished: {result['tests']} tests · exit code {result['exit_code']}")
            return True
        self._launch(lambda notify: run_local_tests(Path(path), framework=framework),
                     f"Running trusted local {framework} tests in {Path(path).name}", finished)

    def _wb_confirm_discard(self) -> bool:
        if self._workbench.path is None:
            return True
        if self.code_editor.toPlainText() == self._workbench.original:
            return True
        return QMessageBox.question(
            self, "Unsaved work", "Discard unsaved changes in the Code Workbench?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _wb_open(self) -> None:
        if not self._wb_confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open local text/code file")
        if not path:
            return
        try:
            text = self._workbench.open(Path(path))
            self.code_editor.setPlainText(text)
            self.code_file.setText(str(self._workbench.path))
            self._code_highlighter.set_filename(path)
            self.code_status.setText(f"Opened {len(text):,} characters. No code was executed.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Workbench", str(exc))

    def _wb_check(self) -> None:
        if self._workbench.path is None:
            QMessageBox.information(self, "Workbench", "Open a code file first")
            return
        result = check_syntax(self.code_editor.toPlainText(), str(self._workbench.path))
        self.code_status.setText(result["message"])
        if result["valid"] is False:
            QMessageBox.warning(self, "Syntax check", result["message"])

    def _wb_diff(self) -> None:
        if self._workbench.path is None:
            return
        diff = self._workbench.diff(self.code_editor.toPlainText())
        dialog = QDialog(self)
        dialog.setWindowTitle("Unsaved code changes · Unified diff")
        dialog.resize(950, 650)
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setFont(QFont("Consolas", 10))
        box.setPlainText(diff if diff else "No unsaved changes")
        layout.addWidget(box)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _wb_save(self) -> None:
        if self._workbench.path is None:
            QMessageBox.information(self, "Workbench", "Open a code file before saving")
            return
        if QMessageBox.question(self, "Save local code", f"Save changes to {self._workbench.path.name}? A backup of the original will be retained.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            saved = self._workbench.save(self.code_editor.toPlainText())
            self.code_status.setText(f"Saved {saved.name}. Existing content was backed up if changed.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Workbench save refused", str(exc))

    def _wb_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save text as a NEW file")
        if not path:
            return
        try:
            saved = self._workbench.save_as(self.code_editor.toPlainText(), Path(path))
            self.code_file.setText(str(saved))
            self._code_highlighter.set_filename(str(saved))
            self.code_status.setText(f"Created {saved.name}. No previous file was overwritten.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Workbench Save As refused", str(exc))

    def _make_settings(self) -> QWidget:
        area, content = scroll_page()
        authentication, a = card("GitHub Accounts · Device-Code Login")
        a.addWidget(label("Use an existing Git Credential Manager, GitHub CLI or saved login without reauthorizing. Alternatively use GitHub's native one-time code (no Git or CLI required once the publisher configures the public OAuth App ID). Every account is verified with GitHub before repositories load.", "caption"))
        self.account_status = label("No active account", "tag")
        a.addWidget(self.account_status)
        self.oauth_id_entry = QLineEdit()
        self.oauth_id_entry.setPlaceholderText("Public Strapman OAuth App client ID (not a secret)")
        self.oauth_id_entry.setToolTip("The app publisher registers one OAuth App and enables Device Flow. The client ID can safely be public; no client secret is ever stored.")
        save_id = QPushButton("Save App ID")
        save_id.clicked.connect(self._save_client_id)
        a.addWidget(line([self.oauth_id_entry, save_id]))
        self.existing_button = QPushButton("✓  Use Existing GitHub Login")
        self.existing_button.setObjectName("primary")
        self.existing_button.clicked.connect(self._connect_existing)
        self.device_button = QPushButton("◉  Sign In with a GitHub Code")
        self.device_button.setObjectName("primary")
        self.device_button.clicked.connect(self._show_device_login)
        self.cli_button = QPushButton("◉  Sign In with GitHub CLI Code")
        self.cli_button.clicked.connect(self._show_cli_login)
        self.cli_install_button = QPushButton("Install GitHub CLI")
        self.cli_install_button.clicked.connect(self._install_cli)
        a.addWidget(self.existing_button)
        a.addWidget(line([self.device_button, self.cli_button, self.cli_install_button]))
        a.addWidget(label("GitHub CLI is OPTIONAL. Native device-code login needs only Strapman's public OAuth App client ID, configured by the publisher; it does not need Git or gh. Existing Git credentials remain owned by Git Credential Manager and other tools.", "caption"))
        self.cli_account_combo = QComboBox()
        self.cli_account_combo.setMinimumWidth(180)
        refresh_accounts = QPushButton("Refresh Accounts")
        refresh_accounts.clicked.connect(self._refresh_cli_accounts)
        use_account = QPushButton("Switch Account")
        use_account.clicked.connect(self._switch_cli_account)
        logout_account = QPushButton("Log Out")
        logout_account.clicked.connect(self._logout_active)
        a.addWidget(line([self.cli_account_combo, refresh_accounts, use_account, logout_account]))
        a.addWidget(label("Personal access token fallback. Tokens are kept in memory unless secure OS credential storage succeeds.", "caption"))
        self.token_entry = QLineEdit()
        self.token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_entry.setPlaceholderText("Your GitHub personal access token (optional fallback)")
        self.persist_token = QCheckBox("Store token in my OS credential manager")
        self.persist_token.setChecked(True)
        self.connect_button = QPushButton("Connect with Token")
        self.connect_button.clicked.connect(lambda: self._connect("pat"))
        disconnect = QPushButton("Disconnect Strapman")
        disconnect.clicked.connect(self._disconnect)
        clear = QPushButton("Forget Current Saved Token")
        clear.clicked.connect(self._forget_token)
        first_run = QPushButton("Reopen First-Run Setup")
        first_run.clicked.connect(self._show_first_run)
        a.addWidget(self.token_entry)
        a.addWidget(self.persist_token)
        a.addWidget(line([self.connect_button, disconnect, clear]))
        a.addWidget(first_run)
        content.addWidget(authentication)
        preferences, p = card("Appearance, Feedback & Workload")
        if self.edition == BOOTLEGGER:
            p.addWidget(label("Bootlegger color scheme", "section"))
            self.theme_combo = QComboBox()
            self.theme_combo.addItems(PRO_THEMES)
            self.theme_combo.setToolTip("Purple Night: purple and black. Pink Pearl: pink and white. Blue Frost: blue and white.")
            self.theme_combo.currentTextChanged.connect(self._select_theme)
            p.addWidget(self.theme_combo)
        else:
            self.theme_combo = None
            p.addWidget(label("Lite uses the classic Strapman dark bubble theme.", "caption"))
        self.sound_check = QCheckBox("Play notification sounds for completion, errors, sign-in, power and launch (default: on)")
        self.voice_check = QCheckBox("Bootlegger voice MP3 notifications (default: on; off uses a simple tone)")
        self.flash_check = QCheckBox("Flash the window title when a job finishes (default: on)")
        for widget in (self.sound_check, self.voice_check, self.flash_check):
            p.addWidget(widget)
        self.sound_check.toggled.connect(lambda val: self.settings.set("sound_enabled", val))
        self.voice_check.toggled.connect(lambda val: self.settings.set("voice_enabled", val))
        self.voice_check.setEnabled(self.edition == BOOTLEGGER)
        self.flash_check.toggled.connect(lambda val: self.settings.set("flash_enabled", val))
        p.addWidget(label("Bootlegger uses the bundled MP3 effects; Lite uses operating-system feedback without loading those files. Both can disable sounds here.", "caption"))
        sound_row = QHBoxLayout()
        self.sound_preview = QComboBox()
        for event in SOUND_EVENTS:
            self.sound_preview.addItem(event.replace("_", " ").title(), event)
        sound_button = QPushButton("Play selected cue")
        sound_button.clicked.connect(lambda: self._play_cue(self.sound_preview.currentData(), preview=True))
        sound_row.addWidget(self.sound_preview, 1)
        sound_row.addWidget(sound_button)
        p.addLayout(sound_row)
        self.audio_status = label("Use Play selected cue to test the current audio output.", "caption")
        p.addWidget(self.audio_status)
        p.addWidget(label("Workers and chunk size can also be changed directly on the Upload Station. Settings persist between launches.", "caption"))
        content.addWidget(preferences)
        manuals, m = card("USERMAN & HELPMAN")
        m.addWidget(label("Offline manuals are included with the application. Nothing here requires browser access.", "caption"))
        userman = QPushButton("▣  Open USERMAN")
        userman.clicked.connect(lambda: self._open_manual("USERMAN.md"))
        helpman = QPushButton("?  Open HELPMAN")
        helpman.clicked.connect(lambda: self._open_manual("HELPMAN.md"))
        logs = QPushButton("Open Local Logs")
        logs.clicked.connect(self._show_logs)
        m.addWidget(line([userman, helpman, logs]))
        content.addWidget(manuals)
        about, about_body = card("About")
        about_body.addWidget(label(f"{self.brand_name.upper()}  v{VERSION}", "section"))
        about_body.addWidget(label("Developed by the Background Gremlin Group\nCreating Unique Tools for Unique Individuals", "caption"))
        about_body.addWidget(label("Python / Qt · Windows and Linux · Direct GitHub REST · No GitHub Actions", "caption"))
        content.addWidget(about)
        self._workflow_sections[3] = [
            ("Account & OAuth", authentication), ("Audio & themes", preferences),
            ("Help & manuals", manuals), ("About", about),
        ]
        content.addStretch()
        return area

    def _load_settings(self) -> None:
        self.chunk_spin.setValue(int(self.settings.get("chunk_mib")))
        self.workers_spin.setValue(int(self.settings.get("workers")))
        self.sound_check.setChecked(bool(self.settings.get("sound_enabled")))
        self.voice_check.setChecked(bool(self.settings.get("voice_enabled")))
        if self.theme_combo is not None:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(normalize_theme(self.settings.get("theme_mode"), self.edition))
            self.theme_combo.blockSignals(False)
        self.flash_check.setChecked(bool(self.settings.get("flash_enabled")))
        self.verify_check.setChecked(bool(self.settings.get("verify_remote_after_upload")))
        self.reconstruct_check.setChecked(bool(self.settings.get("reconstruct_after_upload")))
        self.publish_full_check.setChecked(bool(self.settings.get("publish_full_if_possible")))
        self.repo_combo.setEditText(self.settings.get("last_repo"))
        self.branch_combo.setEditText(self.settings.get("last_branch"))
        self.oauth_id_entry.setText(self.settings.get("oauth_client_id") or bundled_oauth_client_id())
        self._refresh_cli_accounts()

    def _event(self, phase: str, message: str) -> None:
        self.event_log.appendPlainText(f"[{phase}]  {message}")
        self.state_label.setText(f"● {phase.upper()}  ·  {message[:130]}")

    def _busy(self, enabled: bool, *, job_kind: str = "") -> None:
        self._currently_running = enabled
        self._active_task_kind = job_kind if enabled else ""
        self.start_button.setEnabled(not enabled)
        self.pause_button.setEnabled(enabled and job_kind in ("upload", "restore"))
        self.cancel_button.setEnabled(enabled)
        self.restore_button.setEnabled(not enabled)

    def _launch(self, action: Callable, description: str, on_success: Callable | None = None,
                *, job_kind: str = "") -> None:
        if self.task and self.task.isRunning():
            QMessageBox.warning(self, "Job already active", "Finish or cancel the active job first.")
            return
        self._busy(True, job_kind=job_kind)
        self._verify_cue_sent = False
        self._phase_metrics.clear()
        self.transfer_metrics.setText("Preparing job…")
        self._event("RUNNING", description)
        task = Task(action, self)
        self.task = task
        outcome: dict[str, Any] = {}
        task.progress.connect(self._progress)
        task.successful.connect(lambda result: outcome.update(result=result))
        task.failed.connect(lambda error: outcome.update(error=error))
        def when_finished():
            finished_kind = self._active_task_kind
            self._busy(False)
            if "error" in outcome:
                if outcome["error"].startswith("JobPaused:"):
                    self._finish_paused(outcome["error"].partition(":")[2].strip())
                else:
                    self._finish_failure(outcome["error"])
            elif "result" in outcome:
                self._finish_success(description, outcome["result"], on_success,
                                     notify_transfer=finished_kind in ("upload", "restore"))
            else:
                self._finish_failure("Task ended without a result")
        task.finished.connect(when_finished)
        task.start()

    def _progress(self, phase: str, done: int, total: int, detail: str) -> None:
        if phase == "verify" and not self._verify_cue_sent:
            self._verify_cue_sent = True
            self._play_cue("verification_started")
        if phase in self.phase_bars:
            self.phase_bars[phase].setValue(min(100, max(0, round(done * 100 / max(1, total)))))
        if phase in {"hashing", "splitting", "uploading", "verify", "downloading", "assembling"}:
            now = time.monotonic()
            started, initial, previous = self._phase_metrics.get(phase, (now, done, done))
            if done < previous:
                started, initial = now, done
            self._phase_metrics[phase] = (started, initial, done)
            elapsed = max(0.001, now - started)
            speed = max(0.0, (done - initial) / elapsed)
            remaining = max(0, total - done)
            eta = f" · ETA {int(remaining / speed)}s" if speed > 0 and remaining else ""
            self.transfer_metrics.setText(
                f"{phase.title()}  ·  {done:,} / {total:,} bytes  ·  "
                f"{speed / (1024 * 1024):.2f} MiB/s{eta}")
        self._event(phase, detail)

    def _finish_success(self, description: str, result: Any, callback: Callable | None,
                        *, notify_transfer: bool = True) -> None:
        status = result.get("status") if isinstance(result, dict) else None
        rebuild_problem = status in ("rebuild_failed", "rebuild_paused")
        rebuilt = result.get("reconstruction_path") if isinstance(result, dict) else None
        if rebuilt and Path(rebuilt).is_file():
            self._last_rebuild_output = rebuilt
            self.rebuilt_output_label.setText(f"Rebuilt and SHA-256 verified: {rebuilt}")
        if rebuild_problem:
            self._event("REBUILD NEEDED", "Remote upload is verified; reconstruction remains incomplete")
            QMessageBox.warning(self, "GitHub upload verified · Rebuild incomplete",
                                "The GitHub upload is published and verified, but the automatic "
                                "post-upload reconstruction is not complete. It was not reported "
                                "as a fully finished job. Resume the checkpoint from Job History.\n\n" +
                                str(result.get("reconstruction_error") or "Rebuild needs attention."))
        else:
            self._event("COMPLETE", description)
            if notify_transfer:
                self._notify_done(success=True)
        handled = callback(result) is True if callback else False
        self._refresh_history()
        if not handled and not rebuild_problem:
            QMessageBox.information(self, "Strapman — Complete", f"Completed successfully:\n{description}")

    def _finish_paused(self, message: str) -> None:
        self._event("PAUSED", message)
        self._play_cue("work_paused")
        self._refresh_history()
        QMessageBox.information(self, "Strapman — Paused Safely",
                                message + "\n\nOpen Job History → Resume Selected Job "
                                "when you are ready, including after restarting the computer.")

    def _finish_failure(self, message: str) -> None:
        self._event("ERROR", message)
        self._notify_done(success=False)
        QMessageBox.critical(self, "Strapman — Job Failed", message)

    def _select_theme(self, theme: str) -> None:
        if self.edition != BOOTLEGGER:
            return
        self._theme = normalize_theme(theme, self.edition)
        self.settings.set("theme_mode", self._theme)
        self.setStyleSheet(edition_stylesheet(STYLES, edition=self.edition, theme=self._theme))
        self.brand_subtitle.setText("PRO / " + self._theme.upper())
        self._event("APPEARANCE", f"Changed Bootlegger theme to {self._theme}")

    def _audio_status(self, message: str, *, failure: bool = False) -> None:
        if hasattr(self, "audio_status"):
            self.audio_status.setText(message)
        self._event("AUDIO ERROR" if failure else "AUDIO", message)

    def _audio_error(self, *_args) -> None:
        if not self._sound_event:
            return
        name = SOUND_EVENTS[self._sound_event]
        detail = self._media_player.errorString() if self._media_player is not None else ""
        self._audio_status(
            f"Could not play {name} through Qt audio: {detail or 'backend error'}. "
            "Check Windows output device and mixer.", failure=True)
        self._sound_event = ""
        # Pro must never silently substitute an unrelated Windows beep.

    def _audio_playing(self) -> bool:
        try:
            if self._native_audio is not None and self._native_audio.playback_state() == "playing":
                return True
        except AudioPlaybackError:
            pass
        if self._media_player is not None and QMediaPlayer is not None:
            return self._media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        return False

    def _drain_cues(self) -> None:
        if self._pending_cues and not self._audio_playing():
            event = self._pending_cues.pop(0)
            self._play_cue(event, skip_queue=True)

    def _play_cue(self, event: str, *, preview: bool = False,
                  skip_queue: bool = False) -> None:
        if not self.settings.get("sound_enabled") and not preview:
            return
        if event not in SOUND_EVENTS:
            raise ValueError("Unknown notification event")
        asset = audio_path(Path(__file__).resolve().parent.parent, event, self.edition)
        if asset is not None and not self.settings.get("voice_enabled") and not preview:
            QApplication.beep()
            return
        if asset is None:
            QApplication.beep()  # Lite only: intentional built-in sound.
            if preview:
                self._audio_status("Strapman Lite: operating-system notification tone")
            return
        if not skip_queue and self._audio_playing():
            # Retain each voiced message instead of truncating the previous
            # clip (important for first-run and completed-job notifications).
            if len(self._pending_cues) < 24:
                self._pending_cues.append(event)
            else:
                self._audio_status("Voice notification queue is full; event " + event +
                                   " could not be queued", failure=True)
            return
        if not asset.is_file():
            try:
                ensure_audio_asset(asset)
            except (AudioAssetError, OSError) as exc:
                self._audio_status(f"Bootlegger voice asset cannot be prepared: {exc}", failure=True)
                return
        if not asset.is_file():
            self._audio_status(f"Bootlegger MP3 is missing: {asset.name}", failure=True)
            return

        # On Windows use the built-in MCI MP3 driver first. It works without
        # Qt Multimedia/FFmpeg's Windows audio-output pipeline.
        if self._native_audio is not None:
            try:
                self._native_audio.play(asset)
            except AudioPlaybackError as exc:
                self._last_audio_failure = str(exc)
                self._audio_status(f"Windows native MP3 failed for {asset.name}: {exc}. Trying Qt audio.",
                                   failure=True)
            else:
                self._sound_event = ""
                self._last_audio_failure = ""
                self._audio_status(f"Playing Bootlegger MP3 via Windows audio: {asset.name}")
                return

        if self._media_player is not None:
            self._sound_event = event
            self._media_player.stop()
            self._media_player.setSource(QUrl.fromLocalFile(str(asset)))
            self._media_player.play()
            self._audio_status(f"Starting Bootlegger MP3 via Qt audio: {asset.name}")
            return
        self._audio_status(f"No available audio player for {asset.name}. "
                           f"{self._last_audio_failure}", failure=True)

    def _check_power_change(self) -> None:
        event = self._power_reminder.poll(on_ac_power(), time.monotonic())
        if event:
            self._event("POWER", "AC power unplugged: reminder every minute" if event == "power_unplugged"
                        else "AC power restored")
            self._play_cue(event)

    def _notify_done(self, *, success: bool) -> None:
        self._play_cue("complete" if success else "error")
        if self.settings.get("flash_enabled"):
            self._flash_count = 0
            self._flash_message = "JOB COMPLETE" if success else "JOB FAILED"
            self._flash_window()

    def _flash_window(self) -> None:
        if self._flash_count >= 8:
            self.setWindowTitle(self._base_title)
            return
        self.setWindowTitle(f"✦ {self._flash_message} ✦" if self._flash_count % 2 == 0
                            else self._base_title)
        self._flash_count += 1
        QTimer.singleShot(450, self._flash_window)

    def _selected_repo(self) -> str:
        text = self.repo_combo.currentText().strip()
        if not text:
            raise ValueError("Choose or enter a GitHub repository")
        return parse_repository(text)

    def _selected_branch(self) -> str:
        return self.branch_combo.currentText().strip() or "main"

    def _authenticated(self) -> GitHub:
        if self.github is None:
            raise ValueError("Connect GitHub first in Settings & Help")
        return self.github

    def _startup_token_available(self) -> bool:
        method = self.settings.get("auth_method")
        login = self.settings.get("auth_login")
        if method == "git":
            return bool(git_credential_token(login))
        if method == "cli":
            return bool(cli_token(login))
        if method in ("oauth", "pat"):
            return bool(saved_token(login))
        if method == "env":
            return bool(os.environ.get("STRAPMAN_GITHUB_TOKEN"))
        return False

    def _show_first_run(self) -> None:
        if self._currently_running:
            return
        self._play_cue("first_run")
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Welcome to {self.brand_name} · First Run")
        dialog.setMinimumWidth(560)
        body = QVBoxLayout(dialog)
        body.setSpacing(15)
        body.addWidget(label(f"✦ WELCOME TO {self.brand_name.upper()}", "hero"))
        body.addWidget(label("Developed by the Background Gremlin Group\nCreating Unique Tools for Unique Individuals", "caption"))
        body.addWidget(label(f"Already connected to GitHub through Git Credential Manager or another supported login? Reuse it without linking again. Otherwise use the native one-time GitHub code (no Git or CLI required when the publisher OAuth client ID is configured). {self.brand_name} verifies your actual account before loading repositories."))
        actions = [
            ("✓  Use Existing GitHub Login", self._connect_existing),
            ("◉  Sign In with GitHub Code", self._show_device_login),
            ("◉  Sign In with GitHub CLI Code", self._show_cli_login),
            ("Token / Advanced Settings", lambda: self._navigate(3)),
        ]
        for title, callback in actions:
            button = QPushButton(title)
            if not body.count() == 0 and title.startswith("◉"):
                button.setObjectName("primary")
            button.clicked.connect(lambda checked=False, fn=callback: (dialog.accept(), QTimer.singleShot(0, fn)))
            body.addWidget(button)
        skip = QPushButton("Skip for Now — Work Offline")
        skip.clicked.connect(lambda: (self.settings.set("onboarded", True), dialog.accept(), self._navigate(0)))
        body.addWidget(skip)
        dialog.exec()

    def _save_client_id(self) -> None:
        value = self.oauth_id_entry.text().strip()
        if value and not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", value):
            QMessageBox.warning(self, "Invalid App ID", "Enter a valid public OAuth App client ID or leave it blank.")
            return
        self.settings.set("oauth_client_id", value)
        QMessageBox.information(self, "OAuth App", "The public client ID has been saved locally.")

    def _show_device_login(self) -> None:
        if not self._can_change_account():
            return
        client_id = self.oauth_id_entry.text().strip()
        if not client_id:
            QMessageBox.information(self, "GitHub Device Code",
                "Native sign-in requires a public OAuth App client ID, configured once by Strapman's publisher or in Settings. Git and GitHub CLI are not required for native device sign-in. You can also select Use Existing GitHub Login if already authorized.")
            self._navigate(3)
            return
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", client_id):
            QMessageBox.warning(self, "OAuth App", "Invalid public GitHub OAuth App client ID.")
            return
        self.settings.set("oauth_client_id", client_id)
        dialog = DeviceLoginDialog(client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.token:
            self._connect("oauth", dialog.token)

    def _connect_existing(self) -> None:
        """Reuse credentials without installing gh or initiating a fresh login."""
        if not self._can_change_account():
            return
        last = self.settings.get("auth_method")
        login = self.settings.get("auth_login")
        candidates = [last, "git", "cli", "env", "oauth", "pat"]
        for candidate in dict.fromkeys(candidates):
            if candidate == "git" and git_credential_token(login if last == "git" else ""):
                self._connect("git")
                return
            if candidate == "cli" and cli_token(login if last == "cli" else ""):
                self._connect("cli")
                return
            if candidate == "env" and os.environ.get("STRAPMAN_GITHUB_TOKEN"):
                self._connect("env")
                return
            if candidate in ("oauth", "pat") and login and saved_token(login):
                self._connect(candidate)
                return
        QMessageBox.information(self, "GitHub Login",
            "No usable saved GitHub credential was detected non-interactively. "
            "You can sign in using the native GitHub device code (after the public OAuth "
            "client ID is configured), GitHub CLI, or a personal access token.")
        self._navigate(3)

    def _show_cli_login(self) -> None:
        if not self._can_change_account():
            return
        if not github_cli_path():
            response = QMessageBox.question(self, "Install GitHub CLI", "GitHub CLI is not installed. Download a SHA-256-verified copy from the official GitHub release after checking disk space?")
            if response == QMessageBox.StandardButton.Yes:
                self._install_cli(open_login=True)
            return
        dialog = CliLoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.success:
            self._refresh_cli_accounts()
            self._connect("cli", cli_username="")

    def _install_cli(self, open_login: bool = False) -> None:
        if not self._can_change_account():
            return
        def install(progress):
            return install_github_cli(lambda done, total, status: progress("downloading", done, total, status))
        def completed(_):
            self._refresh_cli_accounts()
            if open_login:
                QTimer.singleShot(0, self._show_cli_login)
        self._launch(install, "Installing and verifying official GitHub CLI", completed)

    def _refresh_cli_accounts(self) -> None:
        accounts = github_cli_accounts()
        previous = self.cli_account_combo.currentData() if self.cli_account_combo.count() else ""
        self.cli_account_combo.clear()
        for row in accounts:
            self.cli_account_combo.addItem(row["login"] + ("  ● active" if row["active"] else ""), row["login"])
        for index in range(self.cli_account_combo.count()):
            if self.cli_account_combo.itemData(index) == previous:
                self.cli_account_combo.setCurrentIndex(index)
                break

    def _switch_cli_account(self) -> None:
        if not self._can_change_account():
            return
        login = self.cli_account_combo.currentData()
        if not login:
            QMessageBox.information(self, "GitHub Accounts", "No GitHub CLI account found. Sign in using GitHub CLI Code first.")
            return
        try:
            github_cli_switch(login)
        except AuthError as exc:
            QMessageBox.warning(self, "Account Switch", str(exc))
            return
        self._connect("cli", cli_username=login)

    def _can_change_account(self) -> bool:
        if self._currently_running or (self.task and self.task.isRunning()):
            QMessageBox.warning(self, "Job Active", "Account switching is unavailable while a job is running.")
            return False
        return True

    def _disconnect(self) -> None:
        if not self._can_change_account():
            return
        self.github = None
        self.engine = None
        self._repo_cache = []
        self.repo_combo.clear()
        self.branch_combo.clear()
        self.readme_editor.clear()
        self._readme_original = ""
        self._readme_sha = ""
        self._readme_scope = None
        self.readme_status.setText("Disconnected · Reload README after signing in")
        self.connection_status.setText("● Not connected")
        self.account_status.setText("No active account")
        self.settings.set("auth_method", "")
        self.settings.set("auth_login", "")
        self.settings.set("last_repo", "")
        self._event("ACCOUNT", "Strapman disconnected; no repositories are loaded")

    def _logout_active(self) -> None:
        if not self._can_change_account():
            return
        method = self.settings.get("auth_method")
        login = self.settings.get("auth_login")
        if not login:
            QMessageBox.information(self, "Sign Out", "No active account to sign out of.")
            return
        if QMessageBox.question(self, "Sign Out", f"Sign out of {login} on this device? GitHub CLI logout also affects other apps using its account. This does not revoke GitHub authorization on other devices.") != QMessageBox.StandardButton.Yes:
            return
        try:
            if method == "git":
                QMessageBox.information(self, "Existing Git Login",
                    "Strapman will disconnect only. Your Git Credential Manager login remains available to Git and other apps.")
            elif method == "cli":
                github_cli_logout(login)
            elif method in ("pat", "oauth"):
                delete_token(login)
            elif method == "env":
                QMessageBox.warning(self, "Environment Token", "Remove STRAPMAN_GITHUB_TOKEN from your environment to stop using this token.")
        except AuthError as exc:
            QMessageBox.warning(self, "Sign Out", str(exc))
            return
        self._disconnect()
        self._refresh_cli_accounts()

    def _connect(self, method: str = "", token_override: str = "", cli_username: str | None = None) -> None:
        if not self._can_change_account():
            return
        entered = token_override or self.token_entry.text().strip()
        source = method or self.settings.get("auth_method")
        expected_login = self.settings.get("auth_login")
        if not source:
            source = "pat" if entered else ("env" if os.environ.get("STRAPMAN_GITHUB_TOKEN") else "git")
        if source == "git":
            entered = git_credential_token(expected_login if method == "" and expected_login else "")
        elif source == "cli":
            entered = cli_token(expected_login if cli_username is None else cli_username)
        elif source in ("pat", "oauth"):
            entered = entered or saved_token(expected_login)
        elif source == "env":
            entered = os.environ.get("STRAPMAN_GITHUB_TOKEN", "")
        if not entered:
            self._navigate(3)
            QMessageBox.information(self, "GitHub Login", "No usable credentials for this sign-in method. Use an existing login, native device code, or a token in Settings.")
            return
        client = GitHub(entered)
        should_store = source in ("pat", "oauth") and bool(token_override or self.token_entry.text().strip()) and self.persist_token.isChecked()

        def fetch(progress):
            account = client.account()
            if source == "cli" and cli_username and account["login"].lower() != cli_username.lower():
                raise RuntimeError("GitHub CLI returned the wrong account; no repositories were loaded")
            repositories = client.repositories()
            return account, repositories

        def loaded(result):
            account, repos = result
            new_login = account["login"]
            if source == "git" and (not self.settings.get("onboarded")
                                   or (self.settings.get("auth_login") and
                                       self.settings.get("auth_login").lower() != new_login.lower())):
                if QMessageBox.question(self, "Confirm Existing GitHub Account",
                        f"Existing Git credentials belong to {new_login}. Use this account in {self.brand_name}? "
                        "Only this account's accessible repositories will be loaded.") != QMessageBox.StandardButton.Yes:
                    self._event("ACCOUNT", "Existing GitHub identity not selected")
                    return
            stored = False
            if should_store:
                try:
                    store_token(entered, new_login)
                    stored = True
                except Exception:
                    QMessageBox.warning(self, "Secure Credential Store", "Your OS keyring is unavailable. This login will remain in memory for this session only; no token was saved as plaintext.")
            old_login = self.settings.get("auth_login")
            if old_login and old_login.lower() != new_login.lower():
                self._readme_scope = None
                self._readme_sha = ""
                self.readme_editor.clear()
                self._readme_original = ""
                self.settings.set("last_repo", "")
                self.settings.set("last_branch", "main")
            self.github = client
            self.engine = Engine(client, self.store, self.journal)
            self._repo_cache = repos
            self.settings.set("auth_login", new_login)
            self.settings.set("auth_method", source if (source not in ("pat", "oauth") or stored or saved_token(new_login) == entered) else "session")
            self.settings.set("onboarded", True)
            self.connection_status.setText(f"● Connected as {new_login}")
            self.account_status.setText(f"● GitHub: {new_login} · {'Git Credential Manager' if source == 'git' else source.upper()}")
            selected = self.settings.get("last_repo")
            valid_repos = {repository["full_name"] for repository in repos}
            self.repo_combo.blockSignals(True)
            self.repo_combo.clear()
            for repository in repos:
                self.repo_combo.addItem(repository["full_name"])
            for additional in self.settings.get("repo_favorites"):
                if additional in valid_repos and self.repo_combo.findText(additional) < 0:
                    self.repo_combo.addItem(additional)
            if selected in valid_repos:
                self.repo_combo.setEditText(selected)
            elif repos:
                self.repo_combo.setCurrentIndex(0)
            self.repo_combo.blockSignals(False)
            self.branch_combo.clear()
            self._load_branches()
            self.token_entry.clear()
            self._refresh_cli_accounts()
            self._navigate(0)
            self._event("CONNECTED", f"Verified GitHub account {new_login}; loaded {len(repos)} accessible repositories")
            self._play_cue("ready")

        self._launch(fetch, "Verifying GitHub identity and loading your repositories", loaded)

    def _repo_changed(self, value: str) -> None:
        self._readme_scope = None
        self._readme_sha = ""
        if hasattr(self, "readme_status"):
            self.readme_status.setText("Destination changed · Reload README before committing")
        try:
            selected = parse_repository(value)
        except ValueError:
            return
        self.settings.set("last_repo", selected)

    def _branch_changed(self, value: str) -> None:
        if self._readme_scope and value != self._readme_scope[2]:
            self._readme_scope = None
            self._readme_sha = ""
            if hasattr(self, "readme_status"):
                self.readme_status.setText("Branch changed · Reload README before committing")

    def _load_branches(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
        except ValueError:
            return

        def fetch(progress):
            return client.branches(repo)

        def loaded(branches):
            previous = self.branch_combo.currentText().strip()
            self.branch_combo.clear()
            self.branch_combo.addItems(branches)
            selected = previous if previous in branches else ("main" if "main" in branches else (branches[0] if branches else "main"))
            self.branch_combo.setEditText(selected)
            self._event("BRANCHES", f"Loaded {len(branches)} branches for {repo}")

        self._launch(fetch, "Fetching branch dropdown", loaded)

    def _add_repo_url(self) -> None:
        text, ok = ask(self, "Add GitHub repository", "Enter an owner/repository or complete https://github.com URL")
        if not ok:
            return
        try:
            repo = parse_repository(text)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid repository", str(exc))
            return
        if self.repo_combo.findText(repo) == -1:
            self.repo_combo.addItem(repo)
        self.repo_combo.setEditText(repo)
        favorites = list(self.settings.get("repo_favorites"))
        if repo not in favorites:
            favorites.append(repo)
            self.settings.set("repo_favorites", favorites)
        self._load_branches()

    def _create_repository(self) -> None:
        try:
            client = self._authenticated()
        except ValueError as exc:
            QMessageBox.warning(self, "GitHub not connected", str(exc))
            return
        name, ok = ask(self, "New repository", "Repository name (new repositories default to PRIVATE)")
        if not ok or not name:
            return
        description, ok = ask(self, "Repository description", "Optional description shown on GitHub")
        if not ok:
            return

        def create(progress):
            return client.create_repo(name, description, private=True)

        def created(result):
            repo = result["full_name"]
            self.repo_combo.addItem(repo)
            self.repo_combo.setEditText(repo)
            self.branch_combo.setEditText(result["default_branch"])
            self._event("REPOSITORY", f"Created private repository {repo}")

        self._launch(create, f"Creating private repository {name}", created)

    def _create_branch(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
            base = self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "Branch", str(exc))
            return
        name, ok = ask(self, "Create branch", f"Create a branch in {repo} from {base}")
        if not ok or not name:
            return
        self._launch(lambda progress: client.create_branch(repo, name, base),
                     f"Creating branch {name}", lambda result: self._load_branches())

    def _browse_source(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "Choose upload source")
        if selected:
            self.source_entry.setText(selected)

    def _source_changed(self, text: str) -> None:
        path = Path(text).expanduser()
        if path.is_file():
            size = path.stat().st_size
            chunks = (size + self.chunk_spin.value() * 1024 * 1024 - 1) // (self.chunk_spin.value() * 1024 * 1024)
            self.source_detail.setText(f"File size: {size:,} bytes  ·  Approximately {chunks:,} segments  ·  Requires about {size / 1024**2:.1f} MiB temporary disk space plus reserve")
        else:
            self.source_detail.setText("Choose an existing file to calculate the staged-upload footprint.")

    def _start_upload(self) -> None:
        try:
            client = self._authenticated()
            engine = self.engine or Engine(client, self.store, self.journal)
            source = Path(self.source_entry.text()).expanduser().resolve(strict=True)
            if not source.is_file():
                raise ValueError("Choose a regular file")
            repo = self._selected_repo()
            branch = self._selected_branch()
            workers = self.workers_spin.value()
            chunk_mib = self.chunk_spin.value()
            mode = "source" if self.mode.currentIndex() == 1 else "chunks"
            path = self.path_entry.text().strip()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Upload preflight", str(exc))
            return
        self.settings.set("workers", workers)
        self.settings.set("chunk_mib", chunk_mib)
        self.settings.set("last_repo", repo)
        self.settings.set("last_branch", branch)
        self.settings.set("verify_remote_after_upload", self.verify_check.isChecked())
        self.settings.set("reconstruct_after_upload", self.reconstruct_check.isChecked())
        self.settings.set("publish_full_if_possible", self.publish_full_check.isChecked())
        verify_selected = self.verify_check.isChecked()
        reconstruct_selected = self.reconstruct_check.isChecked()
        publish_selected = self.publish_full_check.isChecked()
        for bar in self.phase_bars.values():
            bar.setValue(0)
        self.engine = engine
        self._launch(lambda notify: engine.upload(
            source, repo, branch, chunk_mib=chunk_mib, workers=workers, mode=mode,
            remote_path=path, verify_remote=verify_selected,
            reconstruct=reconstruct_selected,
            publish_full=publish_selected, callback=notify),
            f"Upload / verify / {'rebuild' if reconstruct_selected else 'publish only'} {source.name} to {repo}:{branch}",
            job_kind="upload")

    def _open_rebuild_output_folder(self) -> None:
        target = getattr(self, "_last_rebuild_output", None)
        if not target or not Path(target).is_file():
            QMessageBox.information(self, "Rebuilt original", "No completed reconstructed file is available yet.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(target).parent)))

    def _pause_job(self) -> None:
        if self._active_task_kind not in ("upload", "restore") or not self.engine:
            return
        self.pause_button.setEnabled(False)
        self.engine.request_pause()
        self._event("PAUSING", "Pause requested; completing in-flight work and retaining checkpoints")

    def _cancel_job(self) -> None:
        if self.engine:
            self.engine.abort()
            self._event("CANCEL", "Cancellation requested; waiting for in-flight network calls")

    def _restore_dialog(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
            branch = self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "Restore", str(exc))
            return
        path, ok = ask(self, "Restore from GitHub", "GitHub path to a Strapman manifest.json")
        if not ok or not path:
            return
        chosen, _ = QFileDialog.getSaveFileName(self, "Save reconstructed file")
        if not chosen:
            return
        engine = Engine(client, self.store, self.journal)
        self.engine = engine
        self._launch(lambda notify: engine.restore(repo, branch, path, Path(chosen),
                                                  workers=self.workers_spin.value(), callback=notify),
                     f"Restoring {path} into a verified local file", job_kind="restore")

    def _readme_dirty(self) -> bool:
        # A repository/branch switch invalidates the binding but must not
        # erase a draft typed for the previous selection.
        return self.readme_editor.toPlainText() != self._readme_original

    def _apply_readme(self, result, login: str, repo: str, branch: str,
                      *, auto: bool = False) -> bool:
        try:
            current = (self.settings.get("auth_login"), self._selected_repo(),
                       self._selected_branch())
        except ValueError:
            current = None
        scope = (login, repo, branch)
        if current != scope:
            self._event("README", "Account or destination changed during read; ignoring outdated response")
            return False
        if self._readme_dirty():
            if auto:
                self.readme_status.setText("Unsaved README edits preserved · Save or manually reload")
                return False
            if QMessageBox.question(self, "Unsaved README changes",
                                    "Reloading README will discard unsaved editor changes. Continue?") != QMessageBox.StandardButton.Yes:
                return False
        self._readme_scope = scope
        self._readme_sha = result[1] if result else ""
        body = result[0] if result else ""
        self._readme_original = body
        self.readme_editor.setPlainText(body)
        self.readme_status.setText(f"README loaded · {repo}:{branch}" if result else
                                   f"README absent · Create README.md for {repo}:{branch}")
        self._event("README", "Loaded repository README.md" if result else
                    "No README.md exists on this branch; editor ready to create it")
        return True

    def _fetch_repo_info(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
            branch = self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "Repository", str(exc))
            return
        login = self.settings.get("auth_login")
        def fetch(notify):
            info = client.repo_info(repo)
            readme = client.read_text(repo, "README.md", branch)
            return info, readme
        def loaded(result):
            info, readme = result
            if self.settings.get("auth_login") != login:
                return
            try:
                if (self._selected_repo(), self._selected_branch()) != (repo, branch):
                    return
            except ValueError:
                return
            self.repo_info.setText(f"{info['full_name']}   •   {'PRIVATE' if info['private'] else 'PUBLIC'}   •   Default branch: {info['default_branch']}")
            self._apply_readme(readme, login, repo, branch, auto=True)
            self._play_cue("repository_refreshed")
            return True
        self._launch(fetch, f"Refreshing repository details and README for {repo}:{branch}", loaded)

    def _make_private(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
        except ValueError as exc:
            QMessageBox.warning(self, "Repository", str(exc))
            return
        if QMessageBox.question(self, "Change repository visibility", f"Make {repo} PRIVATE on GitHub?\n\nThis changes visibility and may affect access to the repository.") != QMessageBox.StandardButton.Yes:
            return
        self._launch(lambda notify: client.set_private(repo, True), f"Setting {repo} PRIVATE", self._fetch_repo_info_after)

    def _fetch_repo_info_after(self, result: Any) -> bool:
        self._play_cue("repository_private")
        # Schedule the refreshed dashboard outside this completed Qt task.
        QTimer.singleShot(0, self._fetch_repo_info)
        return True

    def _enable_alerts(self) -> None:
        self._security_operation("vulnerability alerts", "enable_vulnerability_alerts")

    def _enable_fixes(self) -> None:
        self._security_operation("automated security fixes", "enable_automated_fixes")

    def _security_operation(self, title: str, method: str) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
        except ValueError as exc:
            QMessageBox.warning(self, "Repository", str(exc))
            return
        if QMessageBox.question(self, "GitHub security control", f"Enable {title} for {repo}?\nGitHub plan and token permissions may affect availability.") != QMessageBox.StandardButton.Yes:
            return
        def activated(_result):
            event = "vulnerability_alerts_enabled" if method == "enable_vulnerability_alerts" else "automated_security_fixes_enabled"
            self._play_cue(event)
        self._launch(lambda notify: getattr(client, method)(repo), f"Enabling {title} for {repo}", activated)

    def _load_readme(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
            branch = self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "README", str(exc))
            return
        login = self.settings.get("auth_login")
        def loaded(result):
            self._apply_readme(result, login, repo, branch)
            return True
        self._launch(lambda notify: client.read_text(repo, "README.md", branch),
                     f"Loading {repo}:{branch}/README.md", loaded)

    def _save_readme(self) -> None:
        try:
            client = self._authenticated()
            repo = self._selected_repo()
            branch = self._selected_branch()
        except ValueError as exc:
            QMessageBox.warning(self, "README", str(exc))
            return
        if self._readme_scope != (self.settings.get("auth_login"), repo, branch):
            QMessageBox.warning(self, "README destination changed",
                                "Load README for the current account, repository and branch "
                                "before committing. Your existing editor text is preserved.")
            return
        text = self.readme_editor.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Empty README", "Refusing to save an empty README.")
            return
        if QMessageBox.question(self, "Commit README", f"Save README.md to {repo}:{branch}?\nChanges are committed immediately.") != QMessageBox.StandardButton.Yes:
            return
        saved_scope = self._readme_scope
        expected_sha = self._readme_sha
        def saved(result):
            metadata = result.get("content") if isinstance(result, dict) else None
            new_sha = metadata.get("sha", "") if isinstance(metadata, dict) else ""
            try:
                current_scope = (self.settings.get("auth_login"), self._selected_repo(),
                                 self._selected_branch())
            except ValueError:
                current_scope = None
            if not re.fullmatch(r"[0-9a-f]{40}", new_sha or ""):
                self._readme_scope = None
                self._readme_sha = ""
                self.readme_status.setText("README commit reported success but no verified SHA; reload before editing")
                return True
            if (self._readme_scope == saved_scope == current_scope
                    and self.readme_editor.toPlainText() == text):
                self._readme_sha = new_sha
                self._readme_original = text
                self.readme_status.setText(f"README saved to {repo}:{branch} · SHA {new_sha[:12]}")
            else:
                # The GitHub write succeeded, but the user changed the editor
                # or destination in flight. Preserve the new draft and require
                # a refresh before another commit to avoid using a stale SHA.
                self._readme_scope = None
                self._readme_sha = ""
                self.readme_status.setText(
                    f"README committed on {repo}:{branch}; newer editor changes preserved. Reload to reconcile")
            self._play_cue("readme_updated")
            return True
        self._launch(lambda notify: client.write_text(repo, branch, "README.md", text,
                                      "docs: update README with Strapman", expected_sha),
                     f"Saving README.md on {branch}", saved)

    def _refresh_history(self) -> None:
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        for row in self.store.list_sessions():
            if row.get("status") == "superseded":
                continue
            name = row.get("name", "Unknown")
            status = row.get("status", "unknown").upper()
            repo = row.get("repo", "unknown")
            branch = row.get("branch", "main")
            count = len(row.get("published", []))
            kind = row.get("job_kind", "upload").upper()
            summary = (f"{count} published segments" if kind == "UPLOAD"
                       else f"Destination: {Path(row.get('destination', '')).name}")
            self.history_list.addItem(f"{status:10} · {kind} · {name}  ·  {repo}:{branch}  ·  {summary}")
            self.history_list.item(self.history_list.count() - 1).setData(Qt.ItemDataRole.UserRole, row)

    def _selected_history(self) -> dict | None:
        item = self.history_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _show_job_details(self) -> None:
        session = self._selected_history()
        if not session:
            return
        visible = {key: value for key, value in session.items() if key != "source"}
        import json
        QMessageBox.information(self, "Job Checkpoint", json.dumps(visible, indent=2)[:4000])

    def _audit_selected(self) -> None:
        session = self._selected_history()
        if not session:
            QMessageBox.information(self, "Job History", "Select an upload to verify")
            return
        if session.get("job_kind", "upload") != "upload" or session.get("preparing"):
            QMessageBox.information(self, "Job History", "Remote audit is available for published upload checkpoints, not preparation or restore jobs.")
            return
        try:
            client = self._authenticated()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "GitHub Sign In", str(exc))
            return
        app = Engine(client, self.store, self.journal)
        self.phase_bars["verify"].setValue(0)
        self.phase_bars["committing"].setValue(0)

        def present(report: dict) -> bool:
            status = "COMPLETE AND VERIFIED" if report["complete"] else "PARTIAL — RESUMABLE"
            body = (f"{status}\n\n"
                    f"Repository: {report['repo']}\nBranch: {report['branch']}\n"
                    f"Committed chunks verified: {report['verified_parts']} / {report['total_parts']}\n"
                    f"Verified bytes: {report['verified_bytes']:,} / {report['total_bytes']:,}\n"
                    f"Final manifest committed: {'Yes' if report['manifest_present'] else 'No'}\n\n"
                    "Only files attached to the selected branch count.\n"
                    "This check makes no changes to GitHub or local checkpoints.")
            self._event("AUDIT", body.replace("\n", " | "))
            QMessageBox.information(self, "Strapman — Remote Verification", body)
            return True  # The audit has its own detailed completion dialog.

        self._launch(lambda notify: app.audit_session(session, workers=self.workers_spin.value(),
                                                       callback=notify),
                     f"Auditing GitHub upload on {session['repo']}:{session['branch']}", present)

    def _resume_selected(self) -> None:
        session = self._selected_history()
        if not session:
            QMessageBox.information(self, "Job History", "Select a job to resume")
            return
        if session.get("status") == "complete":
            QMessageBox.information(self, "Already complete", "This job has already completed.")
            return
        if session.get("job_kind") == "restore-local":
            try:
                manifest_file = Path(session["manifest_file"])
                cache_dir = Path(session["cache_dir"])
                destination = Path(session["destination"])
            except KeyError as exc:
                QMessageBox.warning(self, "Local rebuild resume", str(exc))
                return
            if destination.exists():
                QMessageBox.warning(self, "Local rebuild resume", "Destination exists; no file will be overwritten.")
                return
            app = Engine(None, self.store, self.journal)
            self.engine = app
            self._navigate(0)
            self._launch(lambda notify: app.rebuild_local(manifest_file, cache_dir, destination,
                                                          callback=notify),
                         "Resuming local verified rebuild", job_kind="restore")
            return
        if session.get("job_kind") == "restore":
            try:
                client = self._authenticated()
                saved_repo = session["repo"]
                saved_branch = session["branch"]
                manifest = session["manifest_path"]
                destination = Path(session["destination"])
                workers = int(session.get("workers", 4))
            except (ValueError, KeyError) as exc:
                QMessageBox.warning(self, "Restore resume", str(exc))
                return
            if destination.exists():
                QMessageBox.warning(self, "Restore resume", "The destination already exists. Nothing will overwrite it.")
                return
            app = Engine(client, self.store, self.journal)
            self.engine = app
            self._navigate(0)
            self._play_cue("upload_resuming")
            self._launch(lambda notify: app.restore(saved_repo, saved_branch, manifest,
                                                      destination, workers=workers, callback=notify),
                         f"Resuming restore from {saved_repo}:{saved_branch}", job_kind="restore")
            return
        source = Path(session.get("source", ""))
        if not source.is_file():
            QMessageBox.warning(self, "Missing file", "The original local source file is no longer available at its saved path.")
            return
        self._navigate(0)
        self.repo_combo.setEditText(session["repo"])
        self.branch_combo.setEditText(session["branch"])
        self.source_entry.setText(str(source))
        self.mode.setCurrentIndex(1 if session.get("mode") == "source" else 0)
        self.path_entry.setText(session.get("remote_path", ""))
        self.chunk_spin.setValue(int(session.get("chunk_mib", 4)))
        self.workers_spin.setValue(int(session.get("workers", 4)))
        self.verify_check.setChecked(bool(session.get("verify_remote", True)))
        self.reconstruct_check.setChecked(bool(session.get("reconstruct", True)))
        self.publish_full_check.setChecked(bool(session.get("publish_full", False)))
        self._play_cue("upload_resuming")
        self._start_upload()

    def _open_manual(self, filename: str) -> None:
        path = self._manual_base / filename
        if not path.is_file():
            QMessageBox.warning(self, "Manual missing", f"Cannot find {filename} in the installation")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Strapman  •  {filename}")
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)
        view = QTextBrowser()
        view.setMarkdown(path.read_text(encoding="utf-8"))
        layout.addWidget(view)
        close = QPushButton("Close Manual")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _show_logs(self) -> None:
        path = self.journal.path
        dialog = QDialog(self)
        dialog.setWindowTitle("Strapman • Local event log")
        dialog.resize(800, 540)
        l = QVBoxLayout(dialog)
        l.addWidget(label("This file stays on your computer. It is not uploaded to GitHub.", "caption"))
        view = QPlainTextEdit()
        view.setReadOnly(True)
        if path.is_file():
            with path.open("r", encoding="utf-8") as stream:
                view.setPlainText("".join(stream.readlines()[-350:]))
        l.addWidget(view)
        dialog.exec()

    def _forget_token(self) -> None:
        if not self._can_change_account():
            return
        login = self.settings.get("auth_login")
        if not login:
            QMessageBox.information(self, "Saved Token", "No account is currently selected.")
            return
        if QMessageBox.question(self, "Forget Saved Token", f"Delete Strapman's stored token for {login}? GitHub CLI and other applications are unaffected.") == QMessageBox.StandardButton.Yes:
            delete_token(login)
            self.token_entry.clear()
            if self.settings.get("auth_method") in ("pat", "oauth"):
                self._disconnect()


    def closeEvent(self, event) -> None:
        """Never destroy an active Qt worker thread during a transfer."""
        if self.task and self.task.isRunning():
            QMessageBox.warning(self, "Transfer in progress",
                                "A job is still running. Use Stop Job and wait for its final "
                                "status before closing Strapman; no remote data will be deleted.")
            event.ignore()
            return
        if (self.edition == BOOTLEGGER and self.settings.get("sound_enabled")
                and self.settings.get("voice_enabled")
                and (self._native_audio is not None or self._media_player is not None)
                and not self._closing_for_exit_audio
                and (asset := audio_path(Path(__file__).resolve().parent.parent,
                                          "exit", self.edition)) is not None and asset.is_file()):
            self._closing_for_exit_audio = True
            self._pending_cues.clear()
            self._play_cue("exit", skip_queue=True)
            self.hide()
            event.ignore()
            # Keep the event loop alive for a brief exit cue without blocking the UI.
            # The bundled exit cue is about 3.4s long; do not truncate it.
            QTimer.singleShot(4200, self.close)
            return
        if not self._closing_for_exit_audio:
            self._play_cue("exit")
        if self._native_audio is not None:
            try:
                self._native_audio.close()
            except AudioPlaybackError:
                pass
        super().closeEvent(event)


def launch() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(display_name())
    app.setOrganizationName("Background Gremlin Group")
    app.setWindowIcon(strapman_icon())
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    window = StrapmanWindow()
    window.show()
    return app.exec()
