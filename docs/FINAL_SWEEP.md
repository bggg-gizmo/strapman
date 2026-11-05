# Strapman Lite / Bootlegger Pro — v0.5.1 final feature and audio sweep

This is a traceable implementation/verification record for the private
development repo. It is not a certification that native UI, speakers,
GitHub OAuth, or every network failure has been exercised on real hardware.

## Edition architecture and sound inventory

- **Strapman Lite:** existing GitHub staging, publication, verification,
  restoration and code-workbench functionality. Uses OS notification tones,
  not any Bootlegger voice recording.
- **Bootlegger Pro:** same shared recovery engine, purple/black, pink/white
  and blue/white interface settings; leg-lamp icon; independent application
  settings; 14 event-specific owner-provided voice MP3s. Master sound and
  voice options start enabled and can be disabled separately.
- **Headless Strapman:** explicit CLI commands, no sound, checkpoint/status
  reporting, local token-protected dashboard and optional Qt PNG snapshot.
- **Original files:** never automatically reclaimed or deleted.

The 14 MP3s below are present both at `assets/sounds/` and
`bootlegger/assets/sounds/`; source and Pro Git blob object IDs match:

| Event | MP3 |
|---|---|
| Initial GitHub connection/setup | `first_run_github_setup.mp3` |
| Connected and ready | `application_ready.mp3` |
| Application error/timeout | `application_error.mp3` |
| Closing the application | `application_exit.mp3` |
| Safe pause | `work_paused.mp3` |
| Resume a paused upload | `upload_resuming.mp3` |
| Verified task complete | `task_complete.mp3` |
| Verification started | `verification_started.mp3` |
| Repository metadata refreshed | `repository_refreshed.mp3` |
| Repository made private | `repository_private.mp3` |
| AC disconnected, repeated each minute | `power_unplugged.mp3` |
| AC reconnected | `power_restored.mp3` |
| Vulnerability alerts enabled | `vulnerability_alerts_enabled.mp3` |
| Automated security fixes enabled | `automated_security_fixes_enabled.mp3` |

Two original larger clips also retain their unchanged multipart sources in
`assets/sounds/.parts/` and `bootlegger/assets/sounds/.parts/`.

**Reproducible full-checkout validation:**

```sh
python tools/verify_audio_assets.py
python -m pytest -q
python tools/public_audit.py
```

The audio validator reads every complete MP3 and compares the actual byte
length and exact Git blob ID to the documented originals: 28 files total.
It reports missing or altered clips, does not play audio, does not download
packages, and never writes to the sound directories. A code-only patch without
the owner-supplied binaries correctly fails the installed-file audit.

## First-class operations

| Workflow | Existing function | Verification and safety |
|---|---|---|
| Repository selection | Account, repository, branch, URL and creation controls | Separate account/repo/branch scope; real OAuth/permission test still open |
| Repository Desk README | Load, edit and commit current README, or create it | SHA-bound GitHub write; protect edits made while a commit is in flight |
| Repository Desk remote IDE | Browse UTF-8 source, create/edit and commit | GitHub file SHA, branch and account scope; no force overwrite |
| Repository Desk local IDE | Open, syntax-check Python/JSON/TOML, diff, backup/save, run opt-in tests | Unittest or already-installed pytest; never automatically run remote code |
| Upload Station | Cumulative source or chunked binary/archive staging | Existing part/full SHA-256, checkpoints, no new transport |
| Pause Safely | Pause upload, restore or rebuild work | Checkpointed, with explicit user-triggered resume |
| Job History | Resume, verify committed GitHub chunks, see interrupted/paused | Distinguishes active worker locks from abandoned records |
| Build / Rebuild | Restore from committed GitHub manifest or offline local parts | Independent first-class action, per-part and full-file verification, no overwrite |
| Interrupted operation | Durable preparation and partial work state | Hard-killed subprocess tests; unexpected real Windows power loss not certified |
| Headless | Upload/restore/build/audit/status/dashboard/snapshot/pause/resume | Same engine; no default auto-upload or sound |
| Notification settings | Master sound, Pro voice toggle, cue previews and AC reminders | Remote asset inventory checked; live speaker and hardware tests outstanding |

## Reliability improvements made in v0.5.1

1. A downloaded remote Git blob is rejected unless its computed Git
   object ID equals the requested SHA. Existing individual chunk and
   complete-file SHA-256 checks are retained.
2. Remote verification, chunk auditing and Build/Rebuild downloads use a
   bounded work queue, keeping no more than twice the configured worker
   count of futures pending rather than allocating per-chunk futures for
   enormous manifests.
3. An in-flight README or remote-code commit cannot silently rebind the
   editor to a stale remote file after the user edits the draft or changes
   repository/account/branch. An absent/invalid returned SHA requires reload.
4. The built-in local runner supports an installed pytest in addition to
   unittest. Executing user code remains explicit and unsandboxed.
5. Pro voice-queue overflow is reported instead of silently dropping events.
   Disabled voice no longer keeps the application open for the Pro exit MP3.
6. The independent audio asset checker detects missing or byte-modified MP3s
   in either of the two packaged sound directories.

## Verification evidence and unresolved release gates

**Local development test result:** 110 Python tests passed on Linux with
mocked GitHub API and genuine local filesystem/subprocess operations.
Static Python compilation, source privacy scan, and disk-space preflight
passed. GitHub main's audio tree confirmed all 14 source and 14 Pro MP3
blob IDs and exact file sizes; source binaries were not available in the
code-only test environment for an actual installed-file run of the
sound auditor.

**Not yet certified:** Live Windows/Linux PySide6 GUI layout, native
Windows MCI/Qt speaker audio and every cue, real AC reminders, OAuth
publisher client ID/device sign-in, real disposable GitHub multipart
upload/pause/reboot/resume/Build/Rebuild under network contention, actual
Windows power-cut durability, full Git history privacy audit, and public
packaging. Tests and source inspection do not establish those external
properties.

**Security and ownership constraints:** Do not delete source data; do
not change the Git-blob transport or existing manifest formats without
owner authorization; do not touch private WatchMan repositories. Never
force-push or run paid GitHub Actions. Bandwidth/compute allocation
remains a separate research-only future feature.
