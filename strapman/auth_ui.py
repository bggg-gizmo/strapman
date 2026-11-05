"""First-run and account authorization dialogs for Strapman."""
from __future__ import annotations

import re
import threading

from PySide6.QtCore import QProcess, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout
)

from .auth import AuthCancelled, DeviceAuthorization, VERIFY_URI, github_cli_path


def _button(text: str, handler, primary: bool = False) -> QPushButton:
    item = QPushButton(text)
    if primary:
        item.setObjectName("primary")
    item.clicked.connect(handler)
    return item


def _label(text: str) -> QLabel:
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return item


class DeviceWorker(QThread):
    issued = Signal(str, int)
    status = Signal(str)
    authenticated = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, client_id: str, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.cancel_event = threading.Event()

    def run(self):
        try:
            oauth = DeviceAuthorization(self.client_id)
            ticket = oauth.begin()
            if self.cancel_event.is_set():
                raise AuthCancelled("Cancelled")
            self.issued.emit(ticket.code, int(ticket.expires_at))
            self.authenticated.emit(oauth.await_token(ticket, self.cancel_event, self.status.emit))
        except AuthCancelled:
            self.cancelled.emit()
        except Exception as exc:
            # The exception type and sanitized AuthError message cannot contain tokens.
            self.failed.emit(str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "GitHub authorization failed")


class DeviceLoginDialog(QDialog):
    """Native OAuth App device login, no copy/paste of private access tokens."""

    def __init__(self, client_id: str, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.token = ""
        self.worker: DeviceWorker | None = None
        self.setWindowTitle("Strapman • GitHub Device Sign-In")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setSpacing(17)
        layout.addWidget(_label("Authorize Strapman with your own GitHub account. The one-time code is entered on GitHub's secure website; never share your password with Strapman."))
        self.status = _label("Press Generate Code to begin.")
        layout.addWidget(self.status)
        self.code = QLabel("---- ----")
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setStyleSheet("font-size: 33px; font-weight: 900; letter-spacing: 5px; color: #a0f6e8;")
        self.code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.code)
        controls = QHBoxLayout()
        self.start_button = _button("Generate Code", self.start, True)
        self.copy_button = _button("Copy Code", self.copy_code)
        self.open_button = _button("Open GitHub", lambda: QDesktopServices.openUrl(QUrl(VERIFY_URI)))
        self.copy_button.setEnabled(False)
        for widget in (self.start_button, self.copy_button, self.open_button):
            controls.addWidget(widget)
        layout.addLayout(controls)
        layout.addWidget(_label("1. Generate the code.  2. Open github.com/login/device.  3. Enter the code and approve.  4. Strapman confirms your GitHub username automatically."))
        self.cancel_button = _button("Cancel Sign-In", self.reject)
        layout.addWidget(self.cancel_button)
        self.code_value = ""

    def start(self):
        self.start_button.setEnabled(False)
        self.status.setText("Asking GitHub for a device code…")
        self.worker = DeviceWorker(self.client_id, self)
        self.worker.issued.connect(self._issued)
        self.worker.status.connect(self.status.setText)
        self.worker.authenticated.connect(self._authenticated)
        self.worker.failed.connect(self._failed)
        self.worker.cancelled.connect(self._cancelled)
        self.worker.start()

    def _issued(self, code: str, expires: int):
        self.code_value = code
        self.code.setText(code)
        self.copy_button.setEnabled(True)
        self.status.setText("Code ready. Enter it on GitHub and approve access before it expires.")
        QDesktopServices.openUrl(QUrl(VERIFY_URI))

    def copy_code(self):
        if self.code_value:
            QGuiApplication.clipboard().setText(self.code_value)

    def _authenticated(self, token: str):
        self.token = token
        self.status.setText("Approved. Verifying your GitHub account…")
        if self.worker:
            self.worker.finished.connect(self.accept)
        else:
            self.accept()

    def _failed(self, reason: str):
        if self.worker:
            self.worker.finished.connect(lambda: self.start_button.setEnabled(True))
        self.code_value = ""
        self.code.setText("---- ----")
        self.copy_button.setEnabled(False)
        self.status.setText(reason)

    def _cancelled(self):
        if self.worker:
            self.worker.finished.connect(super().reject)
        else:
            super().reject()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.status.setText("Cancelling authorization…")
            self.cancel_button.setEnabled(False)
            self.worker.cancel_event.set()
            return
        super().reject()


class CliLoginDialog(QDialog):
    """GitHub CLI device login in a native dialog. No OAuth client ID required."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Strapman • GitHub CLI Device Sign-In")
        self.resize(530, 320)
        self.setMinimumWidth(500)
        self.success = False
        self.proc: QProcess | None = None
        self._buffer = ""
        self._code = ""
        self._returning = False
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(_label("GitHub CLI signs you in with your own account. It displays a one-time device code and opens GitHub for your approval. Credentials are managed by GitHub CLI, not saved in Strapman's project."))
        self.code = QLabel("---- ----")
        self.code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code.setStyleSheet("font-size: 33px; font-weight: 900; letter-spacing: 4px; color: #a0f6e8;")
        layout.addWidget(self.code)
        self.status = _label("Preparing GitHub CLI…")
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.copy_button = _button("Copy Code", self.copy_code)
        self.copy_button.setEnabled(False)
        controls.addWidget(self.copy_button)
        controls.addWidget(_button("Open GitHub", lambda: QDesktopServices.openUrl(QUrl(VERIFY_URI))))
        layout.addLayout(controls)
        layout.addWidget(_button("Cancel Sign-In", self.reject))
        QTimer.singleShot(50, self.start)

    def start(self):
        exe = github_cli_path()
        if not exe:
            self.status.setText("GitHub CLI is not installed. Install it in Settings and try again.")
            return
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._output)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(lambda _: self.status.setText("Could not run GitHub CLI; try the native device-code method."))
        self.proc.start(exe, ["auth", "login", "--hostname", "github.com", "--web", "--git-protocol", "https", "--skip-ssh-key"])
        self.status.setText("GitHub CLI started. Waiting for its verification code…")

    def _output(self):
        if self.proc is None:
            return
        self._buffer += bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        self._buffer = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", self._buffer)[-3000:]
        match = re.search(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b", self._buffer)
        if match and not self._code:
            self._code = match.group(0)
            self.code.setText(self._code)
            self.copy_button.setEnabled(True)
            self.status.setText("Enter the one-time code at github.com/login/device, then approve access.")
            QDesktopServices.openUrl(QUrl(VERIFY_URI))
        if self.proc and not self._returning and ("Press Enter" in self._buffer or "press enter" in self._buffer.lower()):
            self._returning = True
            self.proc.write(b"\n")
        # Some CLI versions request a newline before they report the device code.
        if self.proc and not self._returning and "first copy" in self._buffer.lower():
            self._returning = True
            self.proc.write(b"\n")

    def copy_code(self):
        if self._code:
            QGuiApplication.clipboard().setText(self._code)

    def _finished(self, code: int, status):
        if code == 0:
            self.success = True
            self.status.setText("GitHub CLI sign-in completed.")
            self.accept()
        else:
            self.status.setText("GitHub CLI sign-in did not complete. Try again, or use the native device-code option.")

    def reject(self):
        if self.proc and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(2000)
        super().reject()
