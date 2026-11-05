# Strapman Architecture

The desktop interface uses Qt/PySide6 with a dark, glossy Windows-era theme. `ui.py` coordinates non-blocking background tasks; `core.py` implements SHA-256 hashing, local chunking, validation, atomic JSON checkpoints, and local restore; `auth.py` implements OAuth device-code polling, noninteractive Git credential helper reuse, public publisher OAuth configuration, account selection and optional verified GitHub CLI installation; `auth_ui.py` supplies first-run/device-code dialogs; `github.py` handles HTTPS GitHub REST, selected credentials, retries, and Git database mutations; `engine.py` ties those components together with configurable worker pools.

Every upload has a content-addressed local cache and a destination-specific checkpoint, bound to repository, branch, mode, and target path. The remote layout mirrors the destination-specific identifier. Worker threads upload immutable blobs in parallel, but one coordinator constructs commits and fast-forwards the selected branch. Existing paths are rejected if they contain different data, except the explicitly designated cumulative staging path in source mode.

The manifest records the safe file name, total bytes, original SHA-256, number and order of chunks, per-chunk SHA-256, byte length, and Git blob SHA. It deliberately excludes OS username, home directory, host name, IP address, source path, system characteristics, and credentials. Only local checkpoints store the source path to allow resume. `restore()` verifies chunks before reconstruction and checks the complete reconstructed SHA-256 before atomic publication to a new destination.

GitHub's Git Data API requires a repository with an initial commit. New repositories created through Strapman are initialized with README. There is no GitHub Actions integration. For large archives, a future transport can use Releases assets rather than densely packing repository history. The reference migration scripts submitted during initial development are **not included** in the public source tree.

## Concurrent desktop process protection

A single non-blocking OS-level lock under local application data (`jobs/locks/upload.lock`) protects the complete staged-upload pipeline, from source chunking through final branch publication. A second Strapman window or process reports `JobAlreadyRunning` and does not re-split, re-upload, commit, or overwrite anything. Thread-pool chunk workers remain parallel within the one active job. The lock file persists, but the kernel lock is released automatically when the owning process terminates; users must **not** delete the lock file to force progress. This is local single-machine coordination, not a distributed lock between separate computers or accounts.

## Verified remote inventory and recovery (v0.3.0)

Before resuming a staged upload, Strapman walks the selected branch's actual Git tree to enumerate `strapman-uploads/<checkpoint>/chunks/`. It uses non-recursive tree requests so listing many chunks does not require a separate Contents API request per file. Truncated Git tree listings are rejected; they are not interpreted as a completed upload. A chunk returned by `POST /git/blobs` is **not** counted as published until the named path is attached to the requested branch.

On resume, branch-attached parts are compared against the byte-exact local chunk contents and their Git object hashes. A valid remote part missing from a saved checkpoint can be recovered into that checkpoint. Any previously published part which disappeared, or whose bytes were replaced, is treated as a conflict requiring inspection; Strapman will not silently rewrite it. Cumulative source-stage paths must match the expected prefix of the published chunks. Optional full-file destinations are checked for conflicts **before** publication begins. A completed upload is verified again against the remote manifest, chunk pointers and, when applicable, full-file pointer.

After the final commit, Strapman rechecks the committed chunk pointers, manifest contents and optional full-file pointer **before** recording local `complete` status. The in-app **Verify on GitHub** audit uses a read-only inventory and independently downloads each branch-attached part, verifies the stored SHA-256, and reports whether the complete portable manifest is attached. A partial audit is not represented as a fully recovered backup. Audit calls do not mutate GitHub or local job checkpoints. This is a snapshot audit: changes after the snapshot require another verification pass.

Restore uses a separate local cross-process lock and reconstructs to an exclusive temporary file. Publication uses Windows's non-overwriting `os.rename`, or an exclusive hard link on POSIX; it rejects an existing output even if another process creates it mid-reconstruction. Filesystems without support for atomic non-replacing publication fail closed instead of overwriting user data.

Large UTF-8 manifests which GitHub's Contents API returns with `encoding: none` are fetched through the matching Git Blob API with the returned object SHA. Storage remains the existing Git blob/branch transport; no Releases, paid Actions or automatic source reclamation are introduced.

The local checkpoint `updated` timestamp is refreshed on each atomic session save, so Job History can sort by recent activity without recording the device clock zone, host name or private source path in remote metadata.


## v0.3.1 safety and operator feedback

The Git blob creation response is checked against a locally computed Git blob
object ID. The branch audit checks committed chunks and, for source/full-file
publishing, downloads and independently verifies the committed full-file content
without requiring the local chunk cache.

Remote publication and optional local reconstruction now have independent
completion states. An unavailable local reconstruction destination does not
rewrite a verified GitHub upload as failed. Repeat reconstruction validates an
existing matching file before attempting another download; conflicting files
are not overwritten.

The Qt transfer console reports bytes, per-phase throughput and an estimated
remaining duration when sufficient observations exist. GUI notifications use
an explicit success/failure message and reject window close while a Qt job
thread is still active. README editor writes are bound to the account, repo and
branch where the README was loaded, and changing a destination requires reload
before save.

## Edition composition

Entry folders `lite/` and `bootlegger/` select an edition through `install.py --edition` and the process-local `STRAPMAN_EDITION` environment variable. `strapman/editions.py` owns pure edition policy, theme CSS overrides, icon/sound asset resolution and optional AC power-state inspection. `strapman/ui.py` presents the selected edition but uses the same `strapman/engine.py` and `strapman/github.py` as before.

The original Lite state location is preserved for continuity. Bootlegger state occupies a separate `bootlegger/` subdirectory. The MP3s are existing Git blobs linked into the Bootlegger asset folder without rewriting the source recordings; only Bootlegger's playback function resolves those assets. No remote source deletion or changed Git transport is part of this tranche.


## v0.5.0 — Headless and editor architecture

`strapman/headless.py` provides the sound-free, explicit-action agent CLI, a token-protected loopback dashboard, JSON checkpoint/status reports and on-demand offline HTML/PNG captures. No hosted agent, remote listener, GitHub Actions, unapproved publication or file reclamation is involved. It uses the same `Engine`, `Store` and `GitHub` classes as the GUI. `rebuild-local` invokes `Engine.rebuild_local` without constructing a GitHub client, so recovery works without network credentials and retains the durable restore-local checkpoint; `rebuild-github` uses the shared verified restore engine.

`strapman/workbench.py` supplies dependency-free static validation for Python, JSON and TOML (TOML validation requires Python 3.11+), local file diff/backup/save protection, account/repository/branch/path/SHA-scoped GitHub editor state, and explicit local unittest execution. Syntax checking never evaluates project code; running tests does execute local files and requires a separate GUI confirmation. `GitHub.list_directory` uses GitHub's selected-branch Contents API with path traversal validation and an explicit 1,000-entry completeness gate. `GitHub.write_text` uses the SHA from the loaded file, never a force push.

Qt `Repository Desk` exposes GitHub and local editor tabs together with README and security features. The sidebar is collapsible, scrolling, accessible and theme-neutral, while the top workflow row changes pages only. `Jobs & Rebuild` is a first-class area for verified reconstruction from committed GitHub parts or offline local caches. This is source-reviewed and Python-tested; a real Qt visual layout smoke test remains mandatory before publication.

## v0.5.1 — transport, editor and test-scaling checks

Remote Git blob reads now validate the requested Git SHA-1 object ID,
not merely the response length. The engine still validates each segment's
SHA-256 and the original full-file digest before reconstruction publication.
Read-only audits, verification and restore downloads maintain at most
twice the selected number of pending network jobs. Active uploads and
sequential non-forced branch commits preserve their existing workflow.

Repository Desk's local test runner offers unittest and an optional already-
installed pytest backend, with explicit user approval before executing
local code. README and remote-code commit callbacks discard optimistic
SHA bindings if a newer draft or destination supersedes a completed write.
The original 14 Pro audio events can be byte-audited by the independent
read-only `tools/verify_audio_assets.py` against the published Git blobs.
