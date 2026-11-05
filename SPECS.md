# Strapman — Complete Product and Engineering Specification

**Document status:** Development contract for v0.5.1-dev and later.
**Product family:** Strapman Lite, Bootlegger Pro, Headless Strapman.
**Developer:** Background Gremlin Group — Creating Unique Tools for Unique Individuals.
**Current shipped provider:** GitHub. Gitea, Forgejo, and additional providers are planned but NOT implemented in the current transport.
**Release stage:** Private development and controlled public-repository testing. Not production-certified.

## 1. Purpose and non-goals

Strapman exists to make large-file Git repository operations approachable to people who cannot or do not want to consume GitHub Actions minutes, paid runners, hosted build systems or a persistent CI machine. It performs staging, splitting, uploading, verification, recovery and reconstruction on the operator's own machine or an explicitly launched headless process. It must provide transparent progress and byte-level integrity without silently discarding original files.

Headless Strapman exposes these operations to local scripts and AI-assisted coding agents, reducing manual bootstrap/reassembly steps while preserving explicit approval for writes and account selection.

It is NOT a GitHub Actions runner, general-purpose hosted CI service, torrent swarm, universal Git provider, arbitrary code sandbox, encrypted backup vault, or automatic deletion/reclamation tool. Git hosting quotas, network connectivity, permissions and API limits still apply. A successful Git object upload is NOT proof that the named file is committed to a branch.

## 2. Editions and scope

### 2.1 Strapman Lite
- Windows/Linux desktop, dark glossy retro interface and existing native notification tones.
- All shared GitHub repository management, verified upload, restore, Build/Rebuild, Job History, local/remote editing, testing, recovery and safe pause functionality.
- Does not require or play Bootlegger's proprietary MP3 voice assets.
- Edition-specific launcher and settings directory; preserves the original Lite settings location.

### 2.2 Bootlegger Pro
- Full shared engine and all Lite features; not a reduced or incompatible storage format.
- Purple Night (purple/black), Pink Pearl (pink/white) and Blue Frost (blue/white) themes; user choice persists.
- Original leg-lamp-inspired GitHub-shade identity, PNG/ICO files, and 14 event-specific MP3 voice announcements.
- Master sound and independent voice toggles default on; fallback/error reporting must never pretend a failed MP3 actually played.
- Battery/AC state voice reminders where supported by the operating system; no device power telemetry is uploaded.
- No paid-license verification, payment processing, entitlement service or enforced Pro paywall exists as of v0.5.1.

### 2.3 Headless Strapman
- Sound-free CLI around the same core, store, authentication and integrity engine.
- Commands: status, upload, restore, rebuild-github, rebuild-local, resume, pause, verify, dashboard, snapshot, code-check and code-diff.
- Readable JSON statuses plus optional loopback token-protected HTML dashboard and on-demand HTML/PNG status snapshots.
- Does not assume a chat agent owns the user's repository. Remote uploads and edits need an explicitly selected account, repository, branch and action.
- Does not require full Qt/audio installation for basic headless commands; PNG rendering may require an existing Qt runtime.

## 3. Supported platforms and installation

- Windows 10/11 and Linux desktop (native desktop acceptance testing still outstanding).
- Python 3.10 or later; GUI dependencies in requirements.txt; no executable is currently distributed.
- Windows and Linux launchers select the desired edition.
- Installer checks free space before dependency bootstrap and prefers a healthy reusable per-user virtual environment, including compatibility with older extracted ZIP installations. It should not download hundreds of megabytes on every extracted update.
- No administrator privileges should be required for the app-local Python environment.
- Never silently install GitHub CLI; it is optional. Existing Git Credential Manager, GitHub CLI and secure saved-token login should be discoverable, followed by account identity validation.

## 4. Authentication and authorization

- GitHub-only v0.5.1: user-directed authentication by existing Git credential helper, GitHub CLI credentials, personal access token, or native GitHub OAuth device code.
- A publisher-registered GitHub OAuth App public client ID is required for the standalone native device flow; the ID has not yet been registered and bundled. NEVER bundle a client secret or fake client ID.
- Verify the chosen account through GitHub before exposing private repositories; confirm newly discovered identities.
- Switching identity invalidates previous repository, branch and README/editor bindings.
- Store secrets only in appropriate user-local secure facilities or session memory, never in source or Git commits.
- Use least privilege. Do not revoke or delete external Git credentials when disconnecting Strapman.

## 5. Repository management and in-app code tools

- Repository Desk: select, refresh, add URL, create repository/branch, choose branch, inspect repository metadata, edit README, and access implemented GitHub security controls.
- README refresh must fetch the actual branch README, not only repository metadata. A missing README must be identifiable with an explicit create workflow.
- GitHub source browser: list directories, open UTF-8 files, create text files, review diff and syntax checks, commit with user confirmation.
- Remote edit state is tied to account + repository + branch + path + remote file SHA. A stale load or concurrent edit must require reload; no silent force overwrite.
- Local workbench: open, create/save-as, diff, validate Python/JSON/TOML (TOML requires supported interpreter), backup and non-overwriting file saves.
- Running tests is explicit and executes local project code unsandboxed. Support unittest and already-installed pytest; never install a test runner automatically just because a user clicked Run.
- Present read-only status separately from actions that mutate GitHub. Preserve unsaved edits when refreshing or navigating.

## 6. Transfer strategies — existing v0.5.1 behavior

### 6.1 Chunked binary / archive
- Accept a local file; derive exact size, SHA-256, safe name and destination-bound checkpoint.
- Split into Git-host-compatible chunks (supported configured range 1–16 MiB) with per-part size, SHA-256 and Git object ID.
- Upload immutable Git blobs using a bounded worker pool. Publish chunk paths in the selected Git branch through serialized, non-force commits.
- Verify actual committed Git tree entries; orphan blobs do NOT count as published. Publish a final restorable manifest and upload guidance; verify final pointers before marking complete.

### 6.2 Cumulative source staging
- For suitable small source material (current eligible direct-source size up to 16 MiB), stage progressively with the existing remote prefix, checkpoint and manifest guarantees.
- Preserve original source content and avoid silently replacing an existing conflicting destination.
- The direct full-file publication option is separate and limited by the implementation's source-size rules.

### 6.3 Remote format
- Current transport uses ordinary Git database blobs and repository commits, NOT GitHub Releases assets or GitHub Actions. Uploaded large sources are reconstructed locally; GitHub must not contain an oversized single ordinary-Git file.
- Portable manifest identifies original filename, total size, full SHA-256, ordered chunk sizes/checksums/object references and publication state necessary for reassembly.
- Remote manifests must not contain OS home directories, secret tokens, device identifiers, personal local paths, or machine-specific telemetry.
- Maintain readable manifests and backward compatibility; any schema change requires versioning, tests and a reviewed migration.

## 7. Build / Rebuild — first-class operation

- Rebuild from GitHub: choose a committed remote manifest under the selected repo/branch; enumerate actual committed chunks, fetch them, validate Git blob object IDs and per-chunk SHA-256, and reconstruct the complete file to a new local destination.
- Offline rebuild: choose a valid local manifest and verified local chunk cache; no GitHub session is required.
- Validate chunk order, count, byte lengths, file name safety, and the final reconstructed SHA-256.
- Build only to a unique temporary file, then publish non-overwriting atomically; never replace an existing output. Reject conflicting output even if it appears during reconstruction.
- Expose exact reconstructable bytes, committed versus uncommitted parts, validation failure and output path to the operator.
- Optional automatic post-upload local reconstruction remains separate from remote-upload completion: reconstruction failure must NOT retroactively mark an already verified remote publication as missing.
- Current Build/Rebuild produces source files from parts; compiling executables or arbitrary build systems is not presently a supported feature.

## 8. Pause, resume, unexpected exit and recovery

- Create a durable preparation checkpoint before initial hashing; write session updates atomically and sync verified local artifacts.
- User **Pause Safely** is cooperative: current requests may finish before a safe pause is recorded; mark paused distinctly from failed/cancelled.
- Process-owned locks prevent duplicate local uploads, restores and agent-controlled runs. A lock file's mere existence is not proof of a live worker.
- After process exit, reboot or forced termination, classify abandoned active checkpoints as interrupted. Never auto-resume GitHub writes without explicit user authorization.
- Resume validates source identity (including size/mtime and contents as applicable), local chunk SHA-256, GitHub's current branch-attached chunk IDs, final manifest and destination conflicts. Recover verified uploaded chunks instead of blindly retransmitting.
- Rebuild checkpoints must never expose partial scratch output as a complete recovered original.
- Backups and existing originals are NEVER deleted or reclaimed by Strapman. Branch force pushes are prohibited.
- Power-loss durability on every filesystem and live Windows OS lifecycle handling remain separate acceptance gates.

## 9. Integrity and concurrency

- Calculate Git blob object IDs from actual data and compare them with GitHub responses and subsequent downloaded blobs; also validate full-file and per-part SHA-256.
- Reject remote tree truncation, missing committed paths, changed blobs, malformed manifests, mismatched byte sizes and unsupported filesystem publication primitives.
- Keep bounded pending futures for large audits, downloads and reconstructions; worker settings should not allocate one task object per every chunk of a huge file.
- Use sequential, non-force branch updates to avoid competing Git publication writers. Multi-machine concurrent publishing remains a conflict case, not a distributed lock guarantee.
- Handle HTTP errors/rate limits with bounded retries, clear status and durable failure/retry checkpoints; never treat interrupted network upload as proven successful.

## 10. Interface, accessibility and notification behavior

- Preserve the sidebar navigation, plus compact responsive layout and top workflow navigation. Workflow navigation must NOT implicitly upload, commit, delete or skip verification.
- Upload Station, Repository Desk, Job History/Build-Rebuild and Settings/Help must remain accessible at common screen sizes.
- Show current stage, file count/bytes, verified bytes, speed/ETA when known, actual committed progress, checkpoint ID and error/paused state separately.
- Show clear user choices when a target file already exists or repository permissions are insufficient.
- Both editions notify on the same operational events; Lite uses standard system tones, Bootlegger Pro uses event-specific voice assets when enabled.
- Pro audio mapping (14 original files):
  - First-run GitHub setup: first_run_github_setup.mp3
  - Connected and ready: application_ready.mp3
  - Error/timeout: application_error.mp3
  - Application exit: application_exit.mp3
  - AC connected again: power_restored.mp3
  - AC disconnected (every 60 seconds while OS reports unplugged): power_unplugged.mp3
  - Verified task completed: task_complete.mp3
  - Upload paused: work_paused.mp3
  - Upload resumed: upload_resuming.mp3
  - Verification started: verification_started.mp3
  - Repository refreshed: repository_refreshed.mp3
  - Repository made private: repository_private.mp3
  - Vulnerability alerts enabled: vulnerability_alerts_enabled.mp3
  - Automated security fixes enabled: automated_security_fixes_enabled.mp3
- Voice queue overflow and backend failure must be visible and testable; do not silently substitute a beep while claiming MP3 playback succeeded. A manual preview must be available.
- The original MP3s and two multipart backup-source clips are preserved byte-for-byte in the private development repository; public test packages should carry required Bootlegger assets.

## 11. Logs, diagnostics, privacy and security

- Local journal and per-job checkpoints distinguish requested/started/completed/paused/failed actions. Remote reports exclude tokens and local device paths.
- Read-only remote audit does not commit changes, rewrite checkpoints or delete files.
- Headless dashboard must bind to loopback and require its local session token; status export must redact local secrets and sensitive paths.
- Reject path traversal and untrusted manifest paths. Preserve no-overwrite behavior for local edits and rebuild output.
- A public-source scan is required for each public testing snapshot. The **entire Git history** must be reviewed before publishing old history or switching an existing repository to public.
- Public testing repositories should start with a fresh clean snapshot, not a blind fork of private development history.
- Never add paid or automatically running GitHub Actions. No secrets, owner-specific backup archives or local logs may be included in the public snapshot.

## 12. Provider expansion — specification, not a current feature

- Current GitHub adapter couples GitHub REST Git Data API, branch commits, accounts and security toggles. Do not pretend that a generic URL field automatically supports Gitea/Forgejo.
- Add a provider capabilities interface exposing identity, repositories, branch/ref reads, blob read/write, atomic publication or safe serialized file commits, directory browse, README edit and optional security controls.
- Prefer provider-neutral manifest/checkpoint format with explicit provider + host identity in destination-binding keys, preventing cross-server reuse.
- Gitea and Forgejo will require self-hosted instance base-URL validation and instance-specific token/OAuth support. Gitea's published OAuth provider documents authorization-code with PKCE; do not reuse GitHub's device-code workflow unless independently demonstrated for a target instance.
- Investigate two safe publication paths: provider-specific contents API and a local Git transport adapter using non-force refs. Preserve per-part and whole-file verification whichever is selected.
- Require disposable Gitea/Forgejo instance integration for upload, branch conflict, cancellation, resume, rebuild, auth, self-signed/TLS rejection and API/version variability before declaring support.
- GitLab and other services follow later as separately tested adapters. Do not remove the working GitHub integration to add them.

## 13. Test and acceptance matrix

### Existing development evidence (2026-11-04 owner testing cycle)
- 110 local Python automated tests passed on Linux; they use mocked GitHub API plus real local filesystem and forced child-process terminations.
- Current-source privacy audit, syntax compilation and disk-space check passed.
- GitHub private development tree contains all 14 source MP3s and 14 corresponding Pro copies with matching object IDs; the full installed-file audio checker is available at tools/verify_audio_assets.py.
- These results do not certify actual Windows/Linux GUI layout, speaker output, native OAuth, real upload quotas or real unexpected Windows shutdown.

### Required acceptance before general public release
1. Full clean source/public-commit-history privacy audit, media metadata audit and licensing review.
2. Both editions launch on supported Windows and Linux desktops; buttons, sidebar, workflow strip and editor function at short and wide resolutions.
3. Reuse credentials, login by new native OAuth device code after publisher registration, logout, account change and permissions-failure handling.
4. Real disposable-repository README editing, file-create conflict, branch selection, repo creation and security toggle checks.
5. Small source staging and 1+ GiB multipart upload to a disposable GitHub repository; verify visible committed tree, restart, pause, resume, audit and reconstruct with exact SHA-256.
6. Confirm a failed optional local reconstruction never falsifies remote complete status; confirm atomic no-overwrite on Windows/Linux.
7. Real audio output for all 14 Pro cues, master/voice toggles, queuing, one-minute unplugged alert and reconnect behavior where hardware supports AC telemetry.
8. Headless CLI operations, token-protected dashboard, status and snapshot; no unapproved actions or background writes.
9. Versioned, reproducible source/installer bundles; explicit owner choice of Windows executable format and icon before compiling an EXE.
10. Gitea/Forgejo integration tests and capability gates before those providers appear in supported-provider lists.

## 14. Release packaging and coordination

- Private source-of-truth: bggg-gizmo/strapman-dev.
- Owner-designated future public source repository: bggg-gizmo/strapman; initially private.
- The public testing snapshot should carry operational source, documented dependencies, Lite/Pro/Headless launchers, required assets, user manuals, security/release caveats, tests and tools.
- Exclude private agent coordination logs and sensitive development history from public snapshots; preserve AGENT_COORDINATION.md in private development and use a clean initial public commit.
- Do not automatically switch visibility to public, publish a release binary or run paid Actions. Owner approves those separate steps.
- Canonical dev roadmap: ROADMAP.md. Research-only resource controls: docs/RESOURCE_CONTROLS_RESEARCH_ROADMAP.md.
