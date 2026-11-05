# HELPMAN — Troubleshooting and Safety

## Strapman won't start

Ensure Python 3.10 or later is installed. Run `python install.py --check-space` to check the disk-space gate. Linux needs its OS's `python3-venv`/`ensurepip` and Qt graphical display libraries. A headless server cannot display the desktop GUI. If package installation fails, read the installer output; it makes no administrative changes.

## Authentication failed

The native device-code login requires a public OAuth App **client ID** that belongs to a registered app with **Device Flow enabled**. It does not require a client secret. If the publisher client ID has not yet been configured, enter the public client ID in Settings or select **Use Existing GitHub Login** if another application already authenticated to GitHub. GitHub CLI remains optional. This alternative can install the verified official CLI locally (after a free-space check), then ask for a one-time code and browser approval.

If device code approval is pending, ensure you completed authorization at `https://github.com/login/device`. Restart the flow if the code expires. A rejected code never connects a user. GitHub CLI may fail to display its code if the local terminal or OS credential manager is unavailable; in that case use native OAuth with an App ID or a personal access token in Settings.

If your account is not listed among GitHub CLI accounts, select **Refresh Accounts** in Settings. **Use Existing GitHub Login** also tries Git Credential Manager non-interactively and does not need GitHub CLI. Use **Switch Account** to choose a different GitHub CLI identity. Strapman verifies the account before listing repositories. A user can disconnect without deleting the GitHub CLI account or sign out of the selected CLI account with confirmation.

Git credential helpers have their own storage policies; `git-credential-store` can store passwords in plaintext, while Git Credential Manager normally uses OS-provided secure storage. GitHub CLI may also fall back to plaintext local credential storage when an OS keyring is unavailable. Verify credential-storage behavior with `gh auth status` and avoid saving secrets on shared computers. Strapman never puts access tokens in its logs, Git commits, or upload manifests.

## Repository/branch missing

Refresh the repository selection and branch dropdowns. Ensure you have permission to read the repository. An entirely empty repository must be initialized with a README or another initial commit before GitHub's Git Data API can create trees and commits. Newly created repositories have an initial README.

## Upload interrupted or rate-limited

Open **Job History** and resume the incomplete job. Strapman keeps JSON checkpoints and checks previously created chunks. Network failures receive bounded retries; permanent authentication/permission errors are surfaced instead of silently ignored. Retry with fewer workers if GitHub throttles requests. Partial staged objects are not interpreted as a complete upload.

## SHA mismatch

Do not delete or modify your original file. A mismatch means the local or remote bytes no longer match the recorded SHA-256. Recreate a fresh upload after examining the source and local cache. Strapman refuses to mark a job completed on verification failure.

## No space

Strapman needs temporary space roughly equal to the input file plus a reserve to split it, and space for another copy during reconstruction. Free disk space outside the app or use a smaller file/different storage location. The installer independently checks for at least 1.5 GiB before installing Python dependencies.

## Remote file already exists

By design, uploads do not overwrite different remote content. Choose another path, a different repository or branch, or use the separate, confirmed README editor for intentional changes. Never force-push your way around a mismatch.

## Progress reaches 100% but job isn't complete

Transfer progress counts uploaded chunks; publication and remote integrity verification are separate phases. The job is complete only after the final commit/manifest stage finishes successfully. If the UI stops responding, inspect local JSON-lines logs; re-launch and resume from Job History.

## A private file might be published

Stop before uploading to a public repository. Scan both filenames and file contents for names, locations, access tokens, credentials, environment dumps, and embedded image metadata. Changing a repository to private does **not** erase sensitive content from a previously public Git history.

## GitHub file size constraints

Ordinary Git rejects individual files above 100 MiB. GitHub recommends smaller repositories; many chunks still increase repository size. Use dedicated artifact storage for truly large backups. GitHub Releases supports individual assets below 2 GiB, but Strapman's initial GUI uses the Git-object chunk transport and local reconstruction.

## Backups and deletion

Strapman does not delete originals after upload. It never clears a failed job automatically. Restoring an existing local filename is refused to prevent accidental replacement. Keep at least one separate backup of valuable data.

## Another Strapman window is already uploading

Strapman 0.3.0 refuses a second upload if a different local process owns the upload lock. The message `An upload is already running in another Strapman window or process` means to inspect the other window and let that job finish. The OS releases the lock after a process crashes or exits, even though the lock file remains on disk. Do not delete the lock file, clear jobs, or restart a working upload to make this warning disappear. The **Job History** screen is the safe place to resume interrupted work when no other upload is active.

## Prove which segments are actually on GitHub

Open **Job History**, select your job, then choose **Verify on GitHub**. This is a read-only check. It lists published chunks from the chosen branch, downloads their Git blobs, verifies each SHA-256 and compares the final `manifest.json` to the verified parts. The dialog reports exact committed part counts, verified bytes, and whether the upload is genuinely complete. A blob uploaded to the Git database but not committed to a branch is **not** counted. You can run this audit even if the local job is still marked incomplete, as long as its local manifest/checkpoint remains available.

If a previously published chunk has disappeared from the branch or now contains different bytes, Resume stops rather than silently replacing or re-publishing it. Inspect the repository branch/history and preserve all local checkpoints before attempting manual recovery. If the final manifest is not present, a fully transferred chunk set remains an **incomplete** upload.

If the audit fails with `truncated`, the GitHub tree inventory could not prove a complete result; it is **not** evidence that the files are missing. If the destination filesystem does not support atomic, non-replacing restore publication, select another filesystem rather than forcing overwrite.


## Upload verified, but optional reconstruction failed

GitHub publication can succeed even if the optional *local* reconstruction
runs out of disk space or encounters an existing destination. Strapman preserves
the completed GitHub checkpoint and shows a separate restoration warning. Free
storage or select an unused restore destination, then retry from Job History
or use **Restore from GitHub**. Do not delete source originals or GitHub parts.

## README save is blocked after switching repo/branch

The editor is bound to the account, repository and branch whose README was last
loaded. Press **Load README** for the newly selected destination. The application
preserves the old editor text until you intentionally replace it by loading.

## Main window refuses to close during a transfer

A job is still active. Use **Stop Job** and wait for the operation to finish or
report cancellation. This protects the Qt worker and the on-disk checkpoint.

## Public release privacy scan

Run `python tools/public_audit.py` in the source tree and the stronger
`python tools/public_audit.py --history` in a full Git checkout. Resolve every
finding before publishing. See `docs/RELEASE_READINESS.md` for the complete
pre-publication gates and the tests not yet performed on actual desktop systems.

## Edition and audio troubleshooting

Bootlegger has **Purple Night**, **Pink Pearl**, and **Blue Frost** modes, selected in Settings & Help. The preference applies immediately and persists. Lite intentionally has its original dark theme only.

If Bootlegger plays the OS beep instead of a Pro recording, check that `bootlegger/assets/sounds/` contains the original MP3 files and that your OS provides a working Qt Multimedia MP3 decoder. Choose a sound in Settings and click **Play selected cue** to test the decoder; disabling sounds suppresses automatic notifications. Lite always uses the OS beep by design and does not load the Pro recordings.

The `application_ready` cue is played only after GitHub authentication is confirmed and the user's available repositories are loaded, not merely when the app window appears. The `first_run_github_setup` cue is played when the first-run wizard opens; `task_complete` is for a finished job. Changes to AC power are reported only where a supported system power sensor is available.

If a launcher fails, run `python install.py --check-space` first and read the console error. The Linux GTK/Qt platform plugin and audio decoder are system dependencies; Python `pip` alone may not install them.


## Bootlegger MP3 is silent / only Windows beeps play

Open Settings & Help, choose a notification event and press **Play selected cue**. Bootlegger reports the exact MP3 filename and whether Windows-native or Qt playback started; if both fail, the audio status and local event log contain the backend's error. Windows-native playback does not require Git or GitHub CLI or any additional MP3 player installation. Check the Windows Volume Mixer output device and make sure this application's sound is not muted. If `bootlegger/assets/sounds/<cue>.mp3` is absent, obtain the complete GitHub repository ZIP rather than a source-only patch ZIP. Lite deliberately uses operating-system notification tones.

## Updating caused a new multi-gigabyte Python install

Use v0.4.2 or later `install.py`, which reuses a healthy previous `.venv` from the current or nearby extracted release folder, and otherwise installs to a reusable per-user Python runtime independent of ZIP extraction. Preserve old extraction folders until the new launcher reports that it reused dependencies. An explicit `STRAPMAN_VENV` environment variable can point to an existing compatible `.venv`. When requirements remain satisfied, no `pip install` occurs; no administrator account or deletion of previous environments is needed.

## Pausing a transfer and resuming after a restart

Use **Pause Safely**, not the window close button. Wait until the job reports **PAUSED**; the app may finish its current network request first. From **Job History**, select the matching paused upload or restore and use **Resume Selected Job**. For initial hashing/splitting, an incomplete preparation step may repeat; after a remote batch has been committed the next attempt reuses and verifies it. Restore resumes from verified cached chunks and never replaces an existing destination. Check any earlier open Strapman windows if the cross-process lock reports another job running. **Stop Job** records cancellation, not graceful pause, but also retains source originals.

## README is blank after repository refresh

The current **Refresh Repo Info** loads both metadata and `README.md` from the chosen **branch**. The status under the editor explicitly says whether a README was loaded or no README exists and can be created. If you change accounts, branches, or repositories, load that selection's README again before saving. Unsaved local edits are preserved across automatic refresh; manually reloading asks before discarding drafts. GitHub write conflicts still require reloading the latest SHA and resolving edits.

## Voice missing, unplugged reminder or a delayed MP3

Open **Settings & Help** and verify the master sound setting and Bootlegger's separate **Voice MP3 notifications** checkbox are enabled. Both default to enabled. Select a cue and choose **Play selected cue** to test the exact MP3. The two security clips may be reconstructed from locally available, SHA-256-checked Git parts. A missing or corrupt part is reported rather than silently replaced. Windows-native MP3 playback is attempted before Qt fallback; audio-driver failures are displayed in the audio status. Incoming voice notifications queue instead of cutting off the previous recording. AC disconnect repeats at approximately one-minute intervals with a 10-second poll while unplugged; `power_restored` plays once upon reconnection. If the OS cannot report AC status, no transition is guessed. Lite only uses its built-in notification tones.


## v0.5.0 — Troubleshooting the built-in workbench and sidebar

If Bootlegger's title is clipped, verify you launched the updated v0.5.0 source. The sidebar now uses a smaller brand font and optional compact icon navigation. Click `≪` or `≫` to change width, hover icons for full labels, and scroll the nav if the display height is small. The top workflow is navigation-only.

If the GitHub code list is empty, connect a verified GitHub account, select a repository/branch, open Repository Desk and click **Browse Folder**. Double-click directories to navigate; use **↑ Parent** to go back. Files larger than the editor limit, non-UTF-8 files, binary files and truncated folder inventories are rejected rather than implicitly edited. Use the Upload/Restore workflows for binary data.

If a GitHub code save is refused, verify the account, branch and exact path have not changed since loading; GitHub rejects stale file SHA versions. Reload and review your changes; the editor does not force an overwrite. Local-file saves also refuse external modifications and make backups. Local unittest or already-installed pytest tests execute code and should only be run in trusted projects, after the explicit prompt.

If original files seem absent from the Code tab, use **Jobs & Rebuild → Discover GitHub Builds** and select a completed manifest to reconstruct. An uploaded orphan Git object is not a committed and recoverable file. The remote rebuild checks the committed chunks and full-file hash; offline rebuild uses the original manifest and chunk cache. Existing destinations are never replaced.

For automation, run `python -m strapman.headless --help`. `status` does not require a GitHub connection; `rebuild-local` likewise works offline. A `dashboard` URL is only for the local machine and is protected by a randomized token. Native GUI visual validation is outstanding; an IDE pane or sidebar rendering issue on Windows should be reported with the edition, window dimensions and app version.


## Unexpected shutdown, force close, or power cut

Open **Job History** after restarting. If no actual worker still owns the OS lock, a previously active job appears as **Interrupted**; select it and press **Resume Selected Job** when you are ready. Incomplete hashing may be repeated; existing verified GitHub commits and local chunk caches are rechecked, not trusted from a stale log. If a local input changed since interrupted preprocessing, Strapman refuses to continue as if it were the same source. A destination that already exists is never overwritten. Do not delete checkpoint folders or `.incomplete` files to force a restart. If another instance is actively uploading, it will not be marked interrupted. See [Crash Recovery](CRASH_RECOVERY.md) for the detailed behavior and limitations.

## Audio inventory or playback errors

Run `python tools/verify_audio_assets.py` from a **complete checkout**.
A missing/altered MP3 is reported by path and Git object ID without
modifying the recording. When all bytes verify but the voice is inaudible,
check both Sound and Voice toggles and use **Play selected cue** in
Settings & Help. The audio status and local diagnostic log identify the
backend and failures. Lite does not play Bootlegger's voice recordings.
The exact-asset checker cannot certify Windows audio hardware or drivers.
