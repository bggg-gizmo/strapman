"""Sound-free Strapman agent CLI, local dashboard, and verified reconstruction.

All commands use the SAME Engine/Store/GitHub transport as Lite and Bootlegger.
No hosted agent, GitHub Action, remote listener, or delete/reclaim operation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .core import Journal, Store, atomic_json, read_json, assemble_local, validate_manifest
from .editions import BOOTLEGGER, LITE, EDITION_ENV
from .engine import Engine, JobPaused
from .github import GitHub
from .workbench import TextWorkbench, check_syntax


@dataclass
class RunContext:
    run_id: str
    command: str
    engine: Engine
    finished: threading.Event


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_session(session: dict) -> dict:
    """Explicit allowlist: never expose OS home paths or credentials to browser."""
    keys = ("checkpoint_id", "job_kind", "status", "repo", "branch", "mode", "name",
            "size", "sha256", "updated", "manifest_path", "reconstruction_status",
            "reconstruction_error", "verify_remote", "reconstruct", "publish_full")
    output = {key: session[key] for key in keys if key in session}
    if "source" in session:
        output["source_name"] = Path(session["source"]).name
    if "destination" in session:
        output["destination_name"] = Path(session["destination"]).name
    output["committed_parts"] = len(session.get("published") or ())
    return output


class HeadlessController:
    """Edition-scoped durable run status; only one agent task at a time."""
    def __init__(self, store: Store | None = None, journal: Journal | None = None):
        self.store = store or Store()
        self.journal = journal or Journal()
        self.root = self.store.root.parent / "headless"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "run.json"
        self.request_path = self.root / "command.json"
        self.audit_path = self.root / "last-audit.json"
        self._mutex = threading.RLock()
        self._run: RunContext | None = None

    def _status(self) -> dict:
        return read_json(self.state_path)

    def view(self) -> dict:
        state = self._status()
        if state.get("state") in {"running", "pausing"}:
            if not self.store.job_is_running("headless"):
                state = {**state, "state": "interrupted",
                         "detail": "Worker exited; resume from its durable checkpoint"}
            elif time.time() - float(state.get("heartbeat", 0)) > 15:
                state = {**state, "detail": "Worker lock is active; progress heartbeat is delayed"}
        sessions = self.store.list_sessions()
        summaries = [safe_session(s) for s in sessions if s.get("status") != "superseded"]
        # Local-only audit is clearly a historical snapshot, not a live guarantee.
        last_audit = read_json(self.audit_path)
        return {"application": "headless-strapman", "edition": os.environ.get(EDITION_ENV, LITE),
                "captured_at": _utc_now(), "run": {k: v for k, v in state.items() if k not in {"heartbeat", "run_id"}},
                "sessions": summaries, "last_audit": last_audit,
                "source_deletion_enabled": False,
                "notes": "Committed parts are not equivalent to verified whole files. Audit is read-only."}

    def _save_run(self, state: dict) -> None:
        with self._mutex:
            atomic_json(self.state_path, {**state, "heartbeat": time.time(), "updated_at": _utc_now()})

    def pause(self) -> dict:
        """Send an exact-run cooperative pause request; never signal an unrelated PID."""
        state = self._status()
        if state.get("state") not in {"running", "pausing"} or not self.store.job_is_running("headless"):
            raise RuntimeError("No running headless job; use resume for an interrupted checkpoint")
        run_id = state.get("run_id")
        if not isinstance(run_id, str) or len(run_id) != 32:
            raise ValueError("Active run has no valid identity")
        atomic_json(self.request_path, {"run_id": run_id, "command": "pause", "time": _utc_now()})
        if self._run and self._run.run_id == run_id:
            self._run.engine.request_pause()
        return {"pause_requested": True, "run_id": run_id,
                "message": "Pause requested; in-flight operations may finish before checkpointing"}

    def _new_run(self, action: str, engine: Engine, caption: str) -> RunContext:
        with self._mutex:
            # _execute acquired the OS lock. Do not trust a persisted run
            # heartbeat, which survives a killed process or sudden reboot.
            run = RunContext(secrets.token_hex(16), action, engine, threading.Event())
            self._run = run
            self._save_run({"run_id": run.run_id, "pid": os.getpid(), "command": action,
                            "state": "running", "phase": "starting", "done": 0, "total": 0,
                            "caption": caption, "detail": "Starting verified Strapman engine"})
            return run

    def _execute(self, action: str, caption: str, runner, *, needs_github: bool = True) -> dict:
        # Never allow two agent invocations to replace one another's progress
        # record. The operating-system lock releases even on hard termination.
        with self.store.job_lock("headless"):
            return self._execute_locked(action, caption, runner, needs_github=needs_github)

    def _execute_locked(self, action: str, caption: str, runner, *, needs_github: bool = True) -> dict:
        # Offline recovery must work without either GitHub credentials or network.
        engine = Engine(GitHub() if needs_github else None, self.store, self.journal)
        run = self._new_run(action, engine, caption)
        seen = {"at": 0., "phase": ""}
        def progress(phase: str, done: int, total: int, detail: str) -> None:
            now = time.monotonic()
            if now - seen["at"] < 0.25 and phase == seen["phase"] and done < total:
                return
            seen.update(at=now, phase=phase)
            state = self._status()
            if state.get("run_id") == run.run_id:
                self._save_run({**state, "phase": phase, "done": int(done),
                                "total": int(total), "detail": detail})

        def monitor() -> None:
            while not run.finished.wait(0.30):
                state = self._status()
                if state.get("run_id") != run.run_id:
                    return
                self._save_run(state)
                request = read_json(self.request_path)
                if request.get("run_id") == run.run_id and request.get("command") == "pause":
                    engine.request_pause()
                    self._save_run({**state, "state": "pausing",
                                    "detail": "Finishing in-flight work before pausing"})
                    continue
        watcher = threading.Thread(target=monitor, daemon=True, name="strapman-headless-control")
        watcher.start()
        try:
            result = runner(engine, progress)
            state = self._status()
            if state.get("run_id") == run.run_id:
                self._save_run({**state, "state": "complete", "phase": "complete", "detail": "Completed and verified"})
            return {"state": "complete", "result": _serializable_result(result)}
        except JobPaused as exc:
            state = self._status()
            if state.get("run_id") == run.run_id:
                self._save_run({**state, "state": "paused", "detail": str(exc)})
            return {"state": "paused", "message": str(exc)}
        except Exception as exc:
            state = self._status()
            if state.get("run_id") == run.run_id:
                self._save_run({**state, "state": "failed", "detail": f"{type(exc).__name__}: {exc}"})
            raise
        finally:
            run.finished.set()
            watcher.join(timeout=1)
            with self._mutex:
                if self._run is run:
                    self._run = None

    def upload(self, source: str, repo: str, branch: str, *, chunk_mib=4, workers=4,
               mode="chunks", remote_path="", verify_remote=True,
               reconstruct=False, publish_full=False) -> dict:
        # Never infer user authorization for an upload: only explicit invocation starts it.
        return self._execute("upload", Path(source).name, lambda e, progress:
            e.upload(Path(source), repo, branch, chunk_mib=chunk_mib, workers=workers,
                     mode=mode, remote_path=remote_path, verify_remote=verify_remote,
                     reconstruct=reconstruct, publish_full=publish_full, callback=progress))

    def restore(self, repo: str, branch: str, manifest: str, destination: str, *, workers=4) -> dict:
        return self._execute("restore", Path(destination).name,
                             lambda e, progress: e.restore(repo, branch, manifest, Path(destination),
                                                          workers=workers, callback=progress))

    def rebuild_from_github(self, repo: str, branch: str, manifest: str,
                            destination: str, *, workers: int = 4) -> dict:
        """Explicit build command for verified remote parts and manifests."""
        return self._execute("rebuild-github", Path(destination).name,
                             lambda e, progress: e.rebuild_from_github(
                                 repo, branch, manifest, Path(destination),
                                 workers=workers, callback=progress))

    def resume(self, checkpoint_id: str) -> dict:
        session = self.store.session(checkpoint_id)
        if not session:
            raise FileNotFoundError(f"No local checkpoint with ID {checkpoint_id}")
        if session.get("status") == "complete":
            raise ValueError("Job is already complete; use audit or reconstruct instead")
        if session.get("job_kind") == "restore":
            return self.restore(session["repo"], session["branch"], session["manifest_path"],
                                session["destination"], workers=int(session.get("workers", 4)))
        if session.get("job_kind") == "restore-local":
            return self.rebuild_local(session["manifest_file"], session["cache_dir"], session["destination"])
        source = session.get("source")
        if not source or not Path(source).is_file():
            raise FileNotFoundError("Saved original source file is unavailable; no data was deleted")
        return self.upload(source, session["repo"], session["branch"],
                           chunk_mib=int(session.get("chunk_mib", 4)),
                           workers=int(session.get("workers", 4)),
                           mode=session.get("mode", "chunks"),
                           remote_path=session.get("remote_path", ""),
                           verify_remote=bool(session.get("verify_remote", True)),
                           reconstruct=bool(session.get("reconstruct", False)),
                           publish_full=bool(session.get("publish_full", False)))

    def verify(self, checkpoint_id: str, *, workers=4) -> dict:
        session = self.store.session(checkpoint_id)
        if not session or session.get("job_kind", "upload") != "upload" or session.get("preparing"):
            raise ValueError("Select an existing upload checkpoint containing a prepared manifest")
        report = Engine(GitHub(), self.store, self.journal).audit_session(session, workers=workers)
        audit = {**report, "checked_at": _utc_now(), "checkpoint_id": checkpoint_id}
        atomic_json(self.audit_path, audit)
        return audit

    def rebuild_local(self, manifest_path: str, cache_dir: str, destination: str) -> dict:
        """Offline verified reconstruction with the same durable Engine checkpoint."""
        return self._execute("rebuild-local", Path(destination).name,
                             lambda e, progress: e.rebuild_local(
                                 Path(manifest_path), Path(cache_dir), Path(destination),
                                 callback=progress), needs_github=False)


def _serializable_result(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        # Session return may hold local paths, but this appears only in the user's
        # own terminal. Never include secret authentication data in saved reports.
        return {key: _serializable_result(v) for key, v in value.items() if key not in {"token", "password"}}
    if isinstance(value, list):
        return [_serializable_result(v) for v in value]
    return value


def _progress_html(report: dict, *, token: str = "") -> str:
    """Static, human-readable dashboard; all dynamic values are HTML escaped."""
    run = report.get("run", {})
    percent = (100 * run.get("done", 0) / run.get("total", 1)
               if isinstance(run.get("total"), (float, int)) and run.get("total", 0) > 0 else 0)
    percent = min(100, max(0, percent))
    esc = lambda v: html.escape(str(v), quote=True)
    rows = []
    for session in report.get("sessions", []):
        ident = esc(session.get("checkpoint_id", ""))
        name = esc(session.get("name", session.get("source_name", "unnamed")))
        desc = esc(f"{session.get('repo', 'local')}:{session.get('branch', '')}")
        status = esc(session.get("status", "unknown"))
        parts = esc(session.get("committed_parts", 0))
        rows.append(f"<tr><td>{name}</td><td>{desc}</td><td>{status}</td><td>{parts}</td><td><code>{ident}</code></td></tr>")
    items = "\n".join(rows) or '<tr><td colspan="5">No checkpoints yet</td></tr>'
    dashboard = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>headless-strapman · Background Gremlin Group</title>
<style>
:root {{color-scheme:dark}} body {{background:#0a0c14;color:#e7edf8;font:15px system-ui,Segoe UI,sans-serif;margin:0}}
header {{padding:26px 36px;background:linear-gradient(125deg,#221238,#11192e);border-bottom:2px solid #8b5bcd}}
main {{max-width:1120px;padding:28px;margin:auto}} h1 {{font-size:28px;margin:0 0 5px}} h2 {{color:#d8b8ff}}
small {{color:#abb8cc}}.card {{background:#191627;border:1px solid #6c4d88;border-radius:15px;padding:20px;margin:17px 0}}
.kpis {{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.kpi {{background:#241734;padding:16px;border-radius:12px}}.kpi strong {{display:block;font-size:23px;color:#efcaff}}
.progress {{height:22px;border:1px solid #8f72b3;border-radius:11px;background:#100e1b;overflow:hidden}}
.fill {{height:100%;width:{percent:.3f}%;background:linear-gradient(90deg,#a65ce8,#64d8de)}}
table {{width:100%;border-collapse:collapse}} td,th {{text-align:left;padding:9px;border-bottom:1px solid #554267;word-break:break-word}}
code {{font-size:12px;color:#d1b9ea}} a {{color:#86d9f7}} button {{background:#572e81;border:1px solid #ac79d5;color:white;padding:11px 17px;border-radius:9px;cursor:pointer}}
input {{padding:10px;background:#120f1a;color:white;border:1px solid #76518c;border-radius:8px;max-width:100%}}
label {{display:block;margin:9px 0}}.err {{color:#ffc0c0}}
</style></head><body>
<header><h1>◈ headless-strapman</h1><small>Background Gremlin Group · sound-free local execution · {esc(report.get('edition', 'lite'))} checkpoint space</small></header>
<main><section class="card"><h2>Live job state</h2><div class="kpis">
<div class="kpi">State<strong>{esc(run.get('state','idle')).upper()}</strong></div>
<div class="kpi">Phase<strong>{esc(run.get('phase','none'))}</strong></div>
<div class="kpi">Progress<strong>{percent:.1f}%</strong></div>
<div class="kpi">Operations<strong>{esc(run.get('command','none'))}</strong></div></div>
<p>{esc(run.get('caption','No active headless job'))}</p><div class="progress" role="progressbar" aria-valuenow="{percent:.1f}" aria-valuemin="0" aria-valuemax="100"><div class="fill"></div></div>
<p>{esc(run.get('detail',''))}</p><small>{int(run.get('done',0) or 0):,} / {int(run.get('total',0) or 0):,} phase units · Last update {esc(run.get('updated_at','none'))}</small></section>
<section class="card"><h2>Job history and restart checkpoints</h2><table><thead><tr><th>Source</th><th>Repository</th><th>State</th><th>Committed parts</th><th>Checkpoint ID</th></tr></thead><tbody>{items}</tbody></table></section>
<section class="card"><h2>Reconstruction and verification</h2><p>Existing source data is never reclaimed or deleted. Remote commits and verified SHA-256 parts are tracked separately; a completed manifest is required before declaring a full remote recovery.</p>
<p>Last read-only audit: {esc(report.get('last_audit',{}).get('checked_at','not yet run'))}.
Verified bytes: {esc(report.get('last_audit',{}).get('verified_bytes',0))}. Recoverable remote upload: {esc(report.get('last_audit',{}).get('complete',False))}.</p>
<p>Use CLI <code>upload --reconstruct</code>, <code>restore</code>, or <code>rebuild-local</code> to reconstruct files only after verifying all chunks.</p></section>
<section class="card"><h2>Task controls</h2><p>All actions operate on local checkpoints and use the same engine as the desktop editions. Start and restore actions always require explicit filenames and destinations.</p>
<button id="pause">Pause active headless job</button><form id="resume"><label>Resume checkpoint ID <input name="checkpoint_id" required></label><button type="submit">Resume selected</button></form>
<p id="feedback" aria-live="polite"></p><small>The local dashboard does not reveal credentials and cannot launch paid jobs. Full upload/restore options are available in the agent CLI or the desktop GUI.</small></section>
<small>Snapshot captured {esc(report.get('captured_at'))}. Local-only dashboard. No external networking or sounds.</small></main>
<script>
const TOKEN={json.dumps(token)};
async function action(body){{const response=await fetch('/api/action?token='+encodeURIComponent(TOKEN),{{method:'POST',headers:{{'Content-Type':'application/json','X-Strapman-Token':TOKEN}},body:JSON.stringify(body)}});let result=await response.json();document.getElementById('feedback').textContent=JSON.stringify(result);}}
document.getElementById('pause').onclick=()=>action({{action:'pause'}});
document.getElementById('resume').onsubmit=e=>{{e.preventDefault();action({{action:'resume',checkpoint_id:new FormData(e.target).get('checkpoint_id')}});}};
if(TOKEN) setTimeout(()=>location.reload(),2500);
</script></body></html>'''
    return dashboard


def _render_png(report: dict, filename: Path) -> Path:
    """Native Qt off-screen painter, reusing the existing PySide6 installation."""
    import os as _os
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
    from PySide6.QtCore import QRect, Qt
    app = QGuiApplication.instance() or QGuiApplication([])
    canvas = QImage(1280, 720, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#0d0a17"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(0, 0, 1280, 94, QColor("#301347"))
    painter.setPen(QColor("#f6d4ff"))
    painter.setFont(QFont("Segoe UI", 27, QFont.Weight.Bold))
    painter.drawText(34, 63, "headless-strapman · live progress snapshot")
    painter.setFont(QFont("Segoe UI", 14))
    run = report.get("run", {})
    items = [("State", run.get("state", "idle")), ("Phase", run.get("phase", "none")),
             ("Operation", run.get("command", "none")), ("Edition", report.get("edition", "lite"))]
    for i, (name, value) in enumerate(items):
        x = 34 + (i % 2) * 615
        y = 140 + (i // 2) * 85
        painter.fillRect(x, y, 592, 69, QColor("#21152f"))
        painter.setPen(QColor("#b9a8ce"))
        painter.drawText(x + 15, y + 27, name)
        painter.setPen(QColor("#efd4ff"))
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(x + 150, y + 29, str(value)[:42])
        painter.setFont(QFont("Segoe UI", 14))
    done, total = int(run.get("done") or 0), int(run.get("total") or 0)
    ratio = min(1, max(0, done / total if total else 0))
    painter.setPen(QColor("#faf2ff"))
    painter.drawText(34, 355, f"Progress: {ratio * 100:.1f}% ({done:,} of {total:,} phase units)")
    painter.fillRect(34, 378, 1210, 28, QColor("#36284a"))
    painter.fillRect(34, 378, int(1210 * ratio), 28, QColor("#aa60e3"))
    painter.setPen(QColor("#eadbf4"))
    painter.drawText(QRect(34, 433, 1210, 52), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                     str(run.get("detail", "No active job"))[:250])
    painter.drawText(34, 526, "Recent local job checkpoints")
    for i, session in enumerate(report.get("sessions", [])[:4]):
        line = f"{session.get('status','unknown'):12} {session.get('name', session.get('source_name','unnamed'))[:38]:38}  {session.get('committed_parts',0)} committed parts"
        painter.drawText(48, 563 + i * 27, line)
    painter.setPen(QColor("#a9b0c4"))
    painter.drawText(34, 692, f"Local-only · no source deletion · {report.get('captured_at','')}")
    painter.end()
    filename.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(filename), "PNG"):
        raise OSError(f"Could not write PNG snapshot to {filename}")
    return filename


class Dashboard:
    """Authenticated, loopback-only human view and cooperative control endpoint."""
    def __init__(self, controller: HeadlessController, address: str = "127.0.0.1", port: int = 8766):
        if address not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Dashboard listens only on localhost")
        self.controller = controller
        self.secret = secrets.token_urlsafe(32)
        self.address = address
        self.port = port
        self.server: ThreadingHTTPServer | None = None
        self._background: threading.Thread | None = None

    def handler(self):
        dashboard = self
        class Handler(BaseHTTPRequestHandler):
            def _authorized(self) -> bool:
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                return secrets.compare_digest(query.get("token", [""])[0], dashboard.secret)

            def _headers(self, status: int, content_type: str, content: bytes):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'")
                self.end_headers()
                self.wfile.write(content)

            def _json(self, status, result):
                self._headers(status, "application/json; charset=utf-8", json.dumps(result, ensure_ascii=False).encode())

            def do_GET(self):
                if not self._authorized():
                    return self._json(403, {"error": "Local dashboard token required"})
                path = urlsplit(self.path).path
                if path == "/":
                    return self._headers(200, "text/html; charset=utf-8",
                                         _progress_html(dashboard.controller.view(), token=dashboard.secret).encode("utf-8"))
                if path == "/api/status":
                    return self._json(200, dashboard.controller.view())
                return self._json(404, {"error": "No such read-only route"})

            def do_POST(self):
                if not self._authorized() or not secrets.compare_digest(
                        self.headers.get("X-Strapman-Token", ""), dashboard.secret):
                    return self._json(403, {"error": "Dashboard token required"})
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self._json(400, {"error": "Invalid request size or content type"})
                try:
                    request = json.loads(self.rfile.read(length))
                    operation = request.get("action")
                    if operation == "pause":
                        return self._json(202, dashboard.controller.pause())
                    if operation == "resume":
                        checkpoint = str(request.get("checkpoint_id", ""))
                        if not checkpoint or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-" for c in checkpoint):
                            return self._json(400, {"error": "Invalid checkpoint ID"})
                        if dashboard._background and dashboard._background.is_alive():
                            return self._json(409, {"error": "Headless operation already active"})
                        def work():
                            try:
                                dashboard.controller.resume(checkpoint)
                            except Exception as exc:
                                dashboard.controller.journal.write("headless", "error", f"Resume failed: {type(exc).__name__}: {exc}")
                        dashboard._background = threading.Thread(target=work, daemon=True)
                        dashboard._background.start()
                        return self._json(202, {"started": "resume", "checkpoint_id": checkpoint})
                    return self._json(400, {"error": "Unsupported action"})
                except (ValueError, KeyError, OSError, RuntimeError) as exc:
                    return self._json(400, {"error": str(exc)})

            def log_message(self, fmt, *args):
                # Don't echo URL query tokens into console or local logs.
                pass
        return Handler

    def serve(self) -> str:
        self.server = ThreadingHTTPServer((self.address, self.port), self.handler())
        actual = self.server.server_address[1]
        url = f"http://127.0.0.1:{actual}/?token={self.secret}"
        print(json.dumps({"dashboard_url": url, "note": "Local-only, stop with Ctrl+C"}), flush=True)
        try:
            self.server.serve_forever(poll_interval=0.25)
        finally:
            self.server.server_close()
        return url


def _cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="headless-strapman", description=__doc__)
    parser.add_argument("--edition", choices=(LITE, BOOTLEGGER), default=LITE,
                        help="Choose which existing Lite/Pro checkpoints and credentials to use")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("status", help="Output a current JSON report without requiring GitHub credentials")
    p = sub.add_parser("upload", help="Upload, verify, publish and optionally reconstruct")
    p.add_argument("--source", required=True)
    p.add_argument("--repo", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--chunk-mib", type=int, default=4)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--mode", choices=("chunks", "source"), default="chunks")
    p.add_argument("--remote-path", default="")
    p.add_argument("--skip-remote-verify", action="store_true")
    p.add_argument("--reconstruct", action="store_true", help="Verified local build from GitHub after publication")
    p.add_argument("--publish-full", action="store_true")
    p = sub.add_parser("restore", help="Download all parts and verify/reassemble a complete original")
    for name in ("repo", "branch", "manifest", "destination"):
        p.add_argument("--" + name, required=name != "branch", default="main" if name == "branch" else None)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("rebuild-github", help="Build/rebuild an original from committed GitHub parts")
    for name in ("repo", "branch", "manifest", "destination"):
        p.add_argument("--" + name, required=name != "branch", default="main" if name == "branch" else None)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("rebuild-local", help="Offline byte-exact reconstruction from previously verified local chunks")
    for name in ("manifest", "cache-dir", "destination"):
        p.add_argument("--" + name, required=True)
    p = sub.add_parser("resume", help="Resume an interrupted upload or restore from its saved ID")
    p.add_argument("--checkpoint", required=True)
    sub.add_parser("pause", help="Gracefully pause the active headless upload/restore")
    p = sub.add_parser("verify", help="Read-only full SHA-256 audit of a published upload")
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("dashboard", help="Start local authenticated human-readable monitoring")
    p.add_argument("--port", type=int, default=8766)
    p = sub.add_parser("snapshot", help="Save actual job state as a browser-readable HTML or PNG capture")
    p.add_argument("--output", required=True)
    p = sub.add_parser("code-check", help="Statically validate Python, JSON or TOML; never execute it")
    p.add_argument("--file", required=True)
    p = sub.add_parser("code-diff", help="Show a unified diff between two local UTF-8 text files")
    p.add_argument("--original", required=True)
    p.add_argument("--edited", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _cli_parser()
    args = parser.parse_args(argv)
    os.environ[EDITION_ENV] = args.edition
    controller = HeadlessController()
    try:
        if args.operation == "status":
            result = controller.view()
        elif args.operation == "upload":
            result = controller.upload(args.source, args.repo, args.branch,
                                       chunk_mib=args.chunk_mib, workers=args.workers,
                                       mode=args.mode, remote_path=args.remote_path,
                                       verify_remote=not args.skip_remote_verify,
                                       reconstruct=args.reconstruct, publish_full=args.publish_full)
        elif args.operation == "restore":
            result = controller.restore(args.repo, args.branch, args.manifest, args.destination, workers=args.workers)
        elif args.operation == "rebuild-github":
            result = controller.rebuild_from_github(args.repo, args.branch, args.manifest,
                                                    args.destination, workers=args.workers)
        elif args.operation == "rebuild-local":
            result = controller.rebuild_local(args.manifest, args.cache_dir, args.destination)
        elif args.operation == "resume":
            result = controller.resume(args.checkpoint)
        elif args.operation == "pause":
            result = controller.pause()
        elif args.operation == "verify":
            result = controller.verify(args.checkpoint, workers=args.workers)
        elif args.operation == "dashboard":
            Dashboard(controller, port=args.port).serve()
            return 0
        elif args.operation == "snapshot":
            target = Path(args.output).expanduser().resolve()
            if target.exists():
                raise FileExistsError(f"Snapshot already exists: {target}")
            report = controller.view()
            if target.suffix.lower() == ".html":
                with target.open("x", encoding="utf-8") as stream:
                    stream.write(_progress_html(report))
            elif target.suffix.lower() == ".png":
                _render_png(report, target)
            else:
                raise ValueError("Snapshot output must end in .html or .png")
            result = {"saved": str(target), "captured_at": report["captured_at"]}
        elif args.operation == "code-check":
            path = Path(args.file)
            text = TextWorkbench().open(path)
            result = {"path": str(path), **check_syntax(text, str(path))}
        elif args.operation == "code-diff":
            work = TextWorkbench()
            work.open(Path(args.original))
            other = TextWorkbench().open(Path(args.edited))
            result = {"diff": work.diff(other)}
        else:
            parser.error("Unknown command")
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if isinstance(result, dict) and result.get("state") == "paused":
            return 3
        if isinstance(result, dict) and result.get("valid") is False:
            return 4
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"error": "Interrupted locally; durable checkpoints remain"}), file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
