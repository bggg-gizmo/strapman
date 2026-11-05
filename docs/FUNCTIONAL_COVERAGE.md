# Strapman Lite / Bootlegger Pro — functional contract and regression coverage

**Development build:** 0.5.1-dev. Both editions share one GitHub upload/restore engine. This document describes current behavior, what automated tests prove, and what still requires testing on Windows/Linux. It is not a certification of bug-free software.

## Account connection, repository selection and README editing

| Feature | Current contract | Automated test or remaining gate |
| --- | --- | --- |
| Existing Git sign-in | Noninteractive `git credential fill` uses the Git helper if available, without requiring `gh`. The returned identity is verified by GitHub's `/user`, and a newly detected account requires confirmation. External Git credentials remain under Git's control. | Mocked credential tests pass. Live Git Credential Manager tests on Windows/Linux pending. |
| Native device-code sign-in | No Git or `gh` required once the publisher bundles the public client ID in `strapman/oauth_app.json`. No client secret is distributed. | Mocked OAuth tests pass. Real GitHub App registration and live device flow pending. |
| Repository/branch selector | Fetches GitHub's accessible repositories, allows manual GitHub URLs and new private repositories/branches. Account switching resets previous destination scopes. | API unit tests/logic exercised. Live account scope and permission tests pending. |
| Repository Desk | Opening the desk or clicking **Refresh Repo Info** loads both repository metadata and the selected branch's `README.md`; a missing README is explicitly identified as ready to create. | Code-level implementation; live Qt/network test pending. |
| README editor | **Load README** fetches the selected account/repo/branch. **Save README** requires confirmation and the previously fetched content SHA; creation omits SHA. Changes to selection invalidate the save binding. A refresh never discards unsaved text, including drafts made before switching branches. | GitHub text API tests and code-level checks. Live conflicting-edit test pending. |
| Visibility/security controls | Making a repository private and enabling vulnerability alerts or automated fixes require explicit confirmation. Voice success events occur only after API success. GitHub plan/token permissions may reject either operation. | GitHub API unit coverage; real repository test pending. |

## End-to-end transfer pipeline

1. Validate local input, destination repo/branch, chunk size 1–16 MiB, worker count 1–12, and disk space; verify/compute the original SHA-256. Source staging/full-file publication is capped at 16 MiB.
2. Split into ordered local binary parts with per-part SHA-256 and a whole-file digest. Save a content-addressed local manifest under per-edition app data. Original source files are never reclaimed or deleted by Strapman.
3. Save a destination-scoped job checkpoint, protected by an operating-system cross-process upload lock. Blob uploads may run in parallel, but Git branch commits are serialized and never forced.
4. Reconcile each committed chunk from the selected branch against the local manifest; orphan Git blobs do not count as published. Recover valid committed parts after interruptions, and stop if committed remote contents have disappeared or changed.
5. For source staging, publish cumulative source bytes as an explicit staging path alongside immutable parts. For chunk mode, publish bounded batches. Do not overwrite remote conflicts.
6. Independently SHA-256 verify remote parts when requested, and check committed Git blob references. Commit `manifest.json` and per-upload `README.md` only once the parts have been published and verified. Optionally publish the full original for <=16 MiB.
7. Re-read the final manifest and committed chunk paths before reporting complete. Job History's **Verify on GitHub** reads actual branch-attached content without changing the checkpoint or GitHub.
8. Restore via the manifest: download/cache parts, validate part lengths and SHA-256, reconstruct into an exclusive temporary file, and publish only after validating the whole-file SHA-256. A preexisting destination or concurrent creation of one is never overwritten.

**What automated tests exercise:** real local splitting/reassembly, tampering/corruption rejection, safe non-overwrite, cross-process job locks, remote chunk reconciliation, missing final manifests, auditing, cumulative source mode, publication exceptions and fake GitHub API failures. **Not yet exercised:** actual GitHub rate limits, remote branch contention, large real networks, GitHub permissions and multi-gigabyte live transfers.

## Pause, resume and reboot

- **Pause Safely** is enabled during uploads and restores, separate from **Stop Job**. It signals the active worker cooperatively: an in-flight HTTP request may finish, but no source file is deleted. The worker records `paused` instead of `failed`/`cancelled`.
- A pause during initial source hashing/splitting creates a preparation checkpoint; restarting that job may repeat incomplete local preprocessing but does not upload duplicate data. Pauses after remote uploads begin retain published batches and all durable checkpoint records.
- A paused restore retains verified cached chunks and destination/manifest metadata. **Job History → Resume Selected Job** can reconstruct it after the application or computer restarts.
- On resume, Strapman rehashes/validates local caches and re-reads committed GitHub state. It refuses missing or altered remote paths, output-file overwrites and concurrent duplicate processes.
- **Stop Job** retains original data but is a distinct cancellation state. A pause requested after final remote publication may result in a completed upload; the verified publication is not undone. Optional local reconstruction has a separate restore checkpoint and can be resumed independently.
- Unexpected process termination releases the OS job lock. The last fully saved checkpoint and remote commits remain; the app does not claim that a partially transmitted HTTP request was published.

**Automated tests:** pause during hashing, pause after first Git commit, resume with a new Engine instance, paused restore resumed from durable metadata, failed/cancelled distinction and a late pause immediately before reconstruction output publication. These are simulated network tests; interactive Windows/Linux lifecycle tests remain mandatory.

## Sound, voice, and power

Bootlegger Pro uses the owner-supplied MP3s under `bootlegger/assets/sounds/`, with native Windows MP3 playback attempted first and Qt Multimedia as a fallback. Lite does not open Pro MP3s and uses native operating-system tones. Both editions have a master **Play notification sounds** switch. Bootlegger separately exposes **Voice MP3 notifications** (on by default); turning voice off preserves a simple audible tone while keeping the master switch on. Explicit **Play selected cue** previews are allowed even if automatic voice is off.

| Event | Bootlegger MP3 | Trigger |
| --- | --- | --- |
| Initial connection setup | `first_run_github_setup.mp3` | First-run linking wizard |
| Verified account ready | `application_ready.mp3` | Identity verified and repository list loaded |
| Upload/restore completed | `task_complete.mp3` | Verified successful transfer/restore, not simple repository refresh |
| Transfer or application error | `application_error.mp3` | Failed action; pause has a separate status |
| Application exit | `application_exit.mp3` | Graceful window close |
| AC power disconnected | `power_unplugged.mp3` | Transition to unplugged or initial unplugged state; repeats at least every 60 seconds while still unplugged (10s poll) |
| AC power restored | `power_restored.mp3` | Connection restored after known unplugged state |
| Pause completed | `work_paused.mp3` | Cooperative paused checkpoint completed |
| Resume requested | `upload_resuming.mp3` | Resume selected upload/restore job |
| Remote verification started | `verification_started.mp3` | First verify phase of a task |
| Repository refreshed | `repository_refreshed.mp3` | Repo metadata and README loaded |
| Made repository private | `repository_private.mp3` | GitHub confirmed visibility change |
| Vulnerability alerts enabled | `vulnerability_alerts_enabled.mp3` | GitHub security API succeeded |
| Automated fixes enabled | `automated_security_fixes_enabled.mp3` | GitHub security API succeeded |

The two longer security announcements may be stored as Git-tracked `.parts` alongside the original recordings. They are validated against recorded SHA-256 digests and assembled **only when needed**, without replacing an existing MP3, altering the parts or accessing the network. A missing/corrupt asset produces an audio error, not silent success. MP3 playback is queued rather than interrupted by another voice cue.

**Known limits:** Unsupported machines may not report AC status. Normal AC notification can be delayed by the 10-second poll and voice playback queue. UI/MP3 backend behavior and user audio devices must still be tested on Windows and Linux. Voice off does not mean total silence unless the master sound checkbox is also off.

## Installer, UI and release gates

- The Windows and Linux launchers call `install.py --edition`; the installer checks compatible packages and reuses a healthy per-user Python environment or an existing older extraction instead of reinstalling hundreds of megabytes on every update.
- Lite and Pro have separate application settings, caches, histories, icons, sounds and themes. Bootlegger offers Purple Night, Pink Pearl and Blue Frost. Both editions use one shared verified Git-blob format for interoperability.
- The code-level regression suite and source privacy scan run without paid GitHub Actions. No WatchMan repository is changed by Strapman work.
- The public release remains gated on real Windows/Linux Qt tests, publisher OAuth registration, Git-history privacy review, genuine disposable-GitHub upload/resume/restore tests, and desktop installer/executable validation.


## v0.5.0 — newly exposed actions and verification

| Capability | Contract | Automated coverage / open gate |
| --- | --- | --- |
| Responsive left sidebar | Full Bootlegger label, collapse to icon/tooltip navigation, scroll as needed; no pages removed. Top workflow changes tabs only. | GUI source/compilation checks. Native Windows/Linux Qt layout tests remain open because PySide6 was not available in the test environment. |
| Repository code browser/editor | Browse selected-branch GitHub paths, inspect UTF-8, create and edit text via explicit commits guarded by account/repo/branch/path and prior file SHA; static syntax validation and unified diff. | In-memory REST path/listing tests and stale-editor scope tests pass. Live remote commit/permissions remain open. |
| Local mini-IDE | Open/read, change diff, backup on explicit save, exclusive Save As and syntax checks. Run trusted local unittest or already-installed pytest with separate consent. | Filesystem and subprocess tests pass. Local code is not sandboxed; test execution is opt-in. |
| First-class Build / Rebuild | Discover committed GitHub manifests and restore through full chunk verification, or run local offline reconstruction with durable checkpoint and no overwrite. | Fake-GitHub engine tests and offline pause/reboot recovery checks pass. Network/system test remains open. |
| Headless agent CLI | `upload`, `restore`, `verify`, `pause`, `resume`, `rebuild-github`, `rebuild-local`, `status`, `dashboard`, `snapshot`, `code-check`, `code-diff`; no audio. | CLI parse, JSON status, escaped dashboard and offline rebuild tests pass; a real agent integration test remains open. |
| Progress snapshot | Local status HTML or Qt PNG with actual engine checkpoint values; loopback dashboard uses an access token. | HTML output checked; Qt PNG renderer requires installed PySide6 and has not been run here. |

No remote branch force updates, token exposure, hosted workflows, source deletion or compute/bandwidth throttling were introduced. Resource-control design is deferred until researched and reviewed.


## v0.5.0 — hard-exit and reboot reliability

- A preparation checkpoint exists **before** source hashing. Unexpected termination during hashing does not hide the job from the next desktop startup. Source size and nanosecond modification time are bound to the interrupted preparation: if the source differs, automatic reuse is refused.
- On startup, an OS-owned upload/restore lock probe distinguishes an abandoned job from a live worker, even if a prior heartbeat or log is stale. A found abandoned job becomes **Interrupted**, remains available for explicit Resume, and is not automatically restarted.
- Headless operations have a separate OS-owned run lock. Recent persisted run heartbeats cannot falsely block restart after process death; old heartbeats cannot falsely report that a live locked worker has terminated.
- Completed staged chunks and downloaded restore parts are flushed and synced before publication to cache. Stale scratch output is not treated as a verified reconstructed original. Real partial network requests are rechecked against the committed GitHub tree.
- Desktop Job History can also explicitly resume **offline local Build/Rebuild** checkpoints without requiring GitHub credentials.
- `tests/test_crash_recovery.py` terminates child processes with `os._exit` during hashing and reconstruction, then verifies checkpoint recovery, original preservation, source-change detection, no-overwrite reconstruction, nonduplicated process locking, and explicit resume. **102 Python tests pass** in the Linux/mock-GitHub environment; actual Windows shutdown, storage failure, and live GitHub transfers remain untested.

See [CRASH_RECOVERY.md](CRASH_RECOVERY.md) for the exact recovery contract. The release is still development-stage.

## v0.5.1 — verification sweep

| Function | Current implementation | Evidence and limitation |
|---|---|---|
| Pro event sounds | 14 configured MP3 events, default-on voice, Windows/Qt backends, 60-second unplugged reminder | Both remote directories contain every expected Git object. `tools/verify_audio_assets.py` checks exact installed bytes; live speakers still unverified. |
| Lite notifications | Built-in OS tones, no Pro MP3 dependency | Existing edition tests pass. |
| Embedded GitHub editor/README | Explicit SHA-bound writes, account/repo/branch scope and asynchronous draft protection | Regression tests plus source review; live GitHub edit still open. |
| Local mini-IDE | UTF-8 edit, diff, guarded saves, Python/JSON/TOML checks, optional consented unittest/installed pytest | Local tests pass; execution is not sandboxed. |
| Multipart upload | Chunked or cumulative strategy, remote SHA checks, durable restart checkpoints | Automated integrity/interrupt tests; live repository transfer open. |
| Build/Rebuild | First-class GitHub manifest discovery or offline cache, full SHA-256 and no overwrite | Engine tests pass; live multi-GiB rebuild open. |
| Headless | CLI, status, dashboard, snapshot, explicit pause/resume and rebuild | Local tests pass; host agent integration open. |
| Crash/shutdown recovery | OS-owned locks, surviving checkpoints, explicit Resume, no surprise upload | Hard-killed child-process tests; Windows forced power loss open. |

**Test evidence:** 110 local Python tests passed, privacy scan passed
on current source, and static compilation passed. Audio-byte verification
must run from a complete checkout; external platform certification is not
claimed. See [FINAL_SWEEP.md](FINAL_SWEEP.md).


## v0.5.2 — Corrected required workflow semantics

- **Desktop default**: stage, upload, verify committed GitHub parts/manifest, locally rebuild from GitHub chunks, verify complete SHA-256, then announce job completion. An explicit user opt-out can publish-only.
- **Headless default**: same phases, no sounds. `--no-reconstruct` is an explicit exception; incomplete auto rebuild produces `needs_rebuild` with nonzero exit code 5 instead of success.
- **Recovery**: remote commit identity is retained even when local build pauses or fails; retry/resume verifies and reuses it without a duplicate remote commit. No original/source deletion or output overwrite.
- **UI**: persistent sidebar pages unchanged, Bootlegger branding stacked icon-over-wordmark, top strip changes only which section is in view within the current page. Manual Build/Rebuild remains available for independent recovery.
- **Evidence**: 105 local regression tests passed on the available source snapshot, including new automatic reconstruction, failed rebuild and pause/restart scenarios. Previously recorded 110-test baseline included headless modules absent from this local code-only workspace; the combined published project still requires full-suite rerun. Native Qt/live GitHub acceptance is open.
