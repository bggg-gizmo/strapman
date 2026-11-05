# USERMAN — Strapman User Manual

## What Strapman does

Strapman operates locally on Windows and Linux. It partitions source files into independently verified chunks, uses GitHub REST to upload and publish them, and can retrieve and reassemble them. It provides a repository/branch selector, repository creation, README editing, security controls, resumable job history, progress displays, optional completion sounds and flashing notifications.

## Installation and updates

Install Python 3.10+, including `venv` support. On Windows double-click `Strapman.cmd`; on Linux run `./strapman.sh`. The launcher first checks for at least 1.5 GiB of free disk space if it needs to install dependencies. It reuses any compatible environment in your current or nearby earlier Strapman extraction, or the reusable per-user environment at `%LOCALAPPDATA%\Strapman\python-runtime` (Windows) or `~/.cache/Strapman/python-runtime` (Linux). Only when no compatible environment exists does it check the destination filesystem, create a per-user environment, and install missing packages from `requirements.txt`. The environment is shared by Lite and Bootlegger; application settings and jobs remain separate. For a specific pre-existing virtual environment, set `STRAPMAN_VENV` to the environment directory. New ZIP versions do not normally require redownloading Qt; if you have an older installed release, retain its `.venv` until the new launcher confirms reuse. It does not attempt to install system Python or Linux desktop libraries.

## First-run GitHub sign-in

On the first launch, **Welcome to Strapman** offers reuse of an existing Git Credential Manager/GitHub CLI/Strapman login, native GitHub device-code sign-in, optional GitHub CLI sign-in, and advanced token settings. **Skip for Now — Work Offline** allows people to start without authorizing GitHub. Users can open the wizard again from **Settings & Help**. A Git sign-in discovered on first use is verified via GitHub `/user` and requires confirmation before its repositories are loaded.

### Native GitHub device-code login

The publisher of Strapman registers a GitHub OAuth App, enables **Device Flow**, and distributes the public client ID via `strapman/oauth_app.json`. There is no private OAuth client secret. This native device-code flow is independent of Git and GitHub CLI. During development, users may also supply the client ID in Settings or through the `STRAPMAN_OAUTH_CLIENT_ID` environment variable. If the publisher has not configured it yet, the app explains what is missing rather than forcing GitHub CLI installation.

1. Choose **Sign In with a GitHub Code** and **Generate Code**.
2. Strapman shows the one-time eight-character code inside the window and opens `https://github.com/login/device`.
3. Sign in to the intended GitHub account in the browser, enter the code, review GitHub's permission consent, and approve.
4. Strapman waits for approval, verifies `/user`, displays the confirmed username, and lists the repositories visible to that user. A rejected or expired code is reported without storing a token.

### Use existing GitHub authentication (no relinking required)

Select **Use Existing GitHub Login** on first run or in Settings. If Git is installed and its credential helper already holds an HTTPS GitHub token, Strapman asks it non-interactively using `git credential fill`. It does **not** store that token in the project, print it in logs, modify Git configuration, or trigger an approval flow. Strapman validates the credential with GitHub before loading repositories. A first-time or changed Git identity requires confirmation. If this method is unavailable, Strapman can also reuse an existing GitHub CLI token, the explicitly supplied environment token, or its own saved credentials. Other GitHub accounts are not automatically selected.

Git Credential Manager authentication does not require `gh`. Conversely, standalone native device-code authentication does not require either Git or `gh`.

### GitHub CLI device-code fallback

Click **Sign In with GitHub CLI Code**. Strapman checks for `gh` first. If it is not present, choose to download a copy from GitHub's official release after a storage check and SHA-256 verification. The CLI stores authentication locally using GitHub CLI's normal credential handling. Its device-code prompt is displayed by Strapman when available; `gh` may also open a browser for verification. Users with an already authorized GitHub CLI can choose **Use Existing GitHub Login**.

GitHub CLI supports multiple accounts. In **Settings & Help**, refresh its account list, select an account, and click **Switch Account**. Strapman verifies the newly active GitHub identity and refreshes the repository and branch pickers; the previous account's selected destination is not carried over.

### Token and offline fallback

A personal access token can be entered in **Settings & Help**. On approval, credentials are stored only if the OS keyring is available and secure storage was requested. Otherwise login remains session-only. **Disconnect Strapman** clears the app's active session without logging other applications out. **Log Out** removes the selected GitHub CLI login or current account's stored Strapman credential only after confirmation; for a Git credential helper connection, it disconnects Strapman without removing credentials owned by Git. CLI logout does not revoke existing GitHub authorizations on other devices.

Never share the GitHub one-time code with another person or enter it anywhere except GitHub's official verification page. GitHub scopes and repository access are enforced by GitHub, independently of Strapman's dropdowns. Your ChatGPT connection is separate from this local desktop application's sign-in.

## Choosing your destination

On **Upload Station**, choose a repository from the dropdown. To work with another repository, click **Add URL** and paste its `https://github.com/owner/repo` address. Click **New Repo** to create a private repository with an initial README. Choose an existing branch from **Branches**, or create one with **Branch**. Strapman commits only to the selected branch. Protected branches and server rules still apply.

## Uploading a file

Use **Browse Files** to select the original. Choose **Chunked binary / archive** or **Cumulative source staging**. Specify 1–16 MiB chunks and 1–12 workers. The default is four workers; increasing that number can improve throughput but uses more RAM/network bandwidth and may trigger GitHub's rate limits. Optionally enter a final repository path. Enable remote verification to compare downloaded remote blobs against the chunk SHA-256 values. Click **START STAGED UPLOAD**.

The progress console reports fingerprinting, splitting, transfer, publishing, remote verification, optional restore download, and reconstruction. A durable local session JSON file tracks what has already been published. In **Job History**, select an incomplete job and click **Resume Selected Upload** to continue. Before resuming, Strapman inspects the selected GitHub branch's committed chunk inventory, reconciles valid parts with the saved checkpoint, and stops if previously published bytes disappeared or changed. To see exactly what is remotely recoverable without altering anything, select **Verify on GitHub**. The resulting read-only audit checks each remotely committed part's SHA-256 and confirms whether the final manifest is present. **Stop Job** requests cancellation after in-flight operations reach a safe checkpoint.

## Completeness and reconstruction

A complete upload places a `manifest.json`, a short `README.md`, and numbered chunk files under `strapman-uploads/<upload-id>/` in the selected GitHub repository. A manifest means the complete file's checksums and chunk references were recorded and all parts published. It is not an ordinary extracted file. To restore, click **Restore from GitHub**, paste the manifest's path, and select an unused local destination filename. Strapman verifies the resulting file byte-for-byte against the manifest before publication on disk.

For files no larger than 16 MiB, you can also request publication of the original as a normal GitHub repository file. Cumulative source staging publishes the complete small source file after verification. For files larger than GitHub's standard Git file limit, reconstruction is local, not server-side.

## Repository tools

Open **Repository Desk** to fetch repository status, mark an existing repository private, request vulnerability alerts or automated security fixes, and load/save `README.md`. GitHub enforces your permissions; some settings may be unavailable. Saving the README uses GitHub's current blob SHA as an optimistic concurrency check.

## Feedback and logs

Sound and flashing notifications are enabled by default. Toggle either under **Settings & Help**. The UI keeps an event console and local durable JSON-lines logs. Logs live in OS application data, not on GitHub. Upload manifests and per-upload READMEs are the permanent remote audit trail.

## Good practice

Keep the originals until you have completed a test restore. Use small chunks and moderate workers on unstable networks. Check repository visibility before uploading private information. Do not upload device details or credentials to public repositories. Use GitHub Releases rather than huge Git histories for massive archives.

## Proving remote progress

The Job History **Verify on GitHub** action is separate from the Transfer Console's progress bars. It reports the number of chunks **attached to the selected branch**, their combined byte count after downloading and SHA-256 verification, and whether the `manifest.json` matches the complete set. An orphan Git blob that was uploaded but never committed does not count as published. If the manifest is absent, the upload is partial, even if all chunks are present. The audit does not push, delete, rename or modify any GitHub asset, local file or checkpoint. The result describes the Git branch snapshot that was read; run it again after new uploads if you need an updated status.

## Atomic restores

Reconstruction happens into a temporary file with full-file SHA-256 verification. Publication refuses to replace a destination that already exists, including a file created by another process while restoration was running. A second Strapman restore process must wait until the first has finished; the operating system releases the local restore lock after an interruption. The application never removes the original input file.


## Release-readiness safeguards (v0.3.1)

Strapman's transfer console shows exact byte counts, percentage, estimated
throughput, and an ETA once a transfer phase has progressed far enough. The
GitHub branch audit can confirm the published full source even if the local
chunk cache has been removed. A failure during optional **local** reconstruction
is reported separately from successful **remote** upload publication. You can
retry reconstruction without re-uploading the data.

The README editor is tied to the GitHub account, repository and branch selected
when you pressed **Load README**. If that destination changes, **Save README**
will refuse to commit until you load the current destination's README again.
Your unsaved text remains in the editor for manual copying. This prevents
accidentally saving one repository's text into another repository or branch.

Strapman's window uses the project's own icon. Closing the main window while
an upload/restore thread runs is refused; press **Stop Job** and wait for the
finished status before closing. This prevents terminating an active Qt worker
through an abrupt window destruction. Source originals are not deleted.

## Strapman Lite and Bootlegger Pro

This private development repository contains edition-specific launchers under `lite/` and `bootlegger/`. Both editions use the same Git transport, SHA-256 records, restoration and account-management code.

- **Strapman Lite**: classic dark bubble UI, default sound and flashing notifications, no bundled MP3 playback. Open `lite/Strapman-Lite.cmd` (Windows) or `lite/Strapman-Lite.sh` (Linux).
- **Bootlegger Pro**: purple-and-black dark mode, with **Pink Pearl** (pink and white) and **Blue Frost** (blue and white) selectable under Settings & Help → Bootlegger color scheme. Open `bootlegger/Bootlegger-Pro.cmd` or `bootlegger/Bootlegger-Pro.sh`. Bootlegger uses the bundled Pro MP3 notifications for GitHub setup, GitHub-ready status, completed tasks, errors, exit and detected AC power changes.

Sound cues and completion flashes are on by default and can be switched off in Settings for either edition. Use **Play selected cue** to preview the event sound. On Windows Pro first tries the built-in Windows MP3 driver, then Qt Multimedia if required; the audio status label and local event log disclose missing MP3s or backend errors. The app does not silently substitute the Windows beep in Pro. Lite continues using system feedback. Power cues require a power state readable on the local machine; no power data is uploaded.

Bootlegger stores its own settings, job histories and journals in a separate `bootlegger` app-data location so it cannot silently reassign existing Lite checkpoints. Existing Lite settings and sessions remain intact. See [EDITIONS](EDITIONS.md) for details.

## Graceful Pause, Resume and reboot recovery (v0.4.3-dev)

**Pause Safely** sits next to **Stop Job** in the Transfer Console. While an upload or restore runs, click **Pause Safely** and wait for the app to report **PAUSED**. Network calls already in progress may finish; source originals, published chunks, local manifests and restoration caches are retained. The status is distinct from an error or cancellation. After reboot or a later launch, open **Job History**, choose the paused **UPLOAD** or **RESTORE** entry, then choose **Resume Selected Job**. A paused transfer may need to re-hash the source, reconcile the branch, or finish a previously incomplete local split. It never assumes an orphan Git blob is safely committed. The app refuses to overwrite a conflicting restored output. If a process dies without processing the Pause request, resume from its last saved checkpoint after confirming no other job is running.

An upload that has already published and verified its final manifest remains complete. If optional local reconstruction is paused, a separate restore checkpoint is available in Job History. Use the saved restore entry to resume that part without reuploading the original source.

## Repository Desk README loading (v0.4.3-dev)

Choose a repository and branch in the Upload Station, then open **Repository Desk**. The app automatically loads **repository information and that branch's README.md**. **Refresh Repo Info** does the same thing, or use **Load README** to refresh the document alone. If no README exists, the editor explicitly says it can create one. Type your content and press **Save README to GitHub**; Strapman asks for confirmation and creates the file if necessary. It will not overwrite changed remote content without the correct SHA, and refreshes will not discard unsaved changes—even after you switch repositories or branches. Saving to a different destination requires loading that destination's README first.

## Bootlegger voice, notification library and AC-power reminders (v0.4.3-dev)

Under **Settings & Help**, enable **Play notification sounds** and **Bootlegger voice MP3 notifications** to hear the owner-supplied speech clips; both settings default to enabled. Turn **Voice MP3 notifications** off to use ordinary tones while keeping audible event alerts; turn off **Play notification sounds** for silence. **Play selected cue** previews individual files for diagnosis. Lite continues using its own operating-system tones without loading Pro voice files.

Bootlegger has distinct speech cues for first-run setup, account ready, completed tasks, error, exit, pause, resume, remote verification started, repository refresh, making a repository private, enabling vulnerability alerts, enabling automated security fixes, AC unplugged and AC restored. If unplugged status persists, the unplugged reminder plays **once per minute** until power is restored; polling and any already queued voice may add a short delay. Security announcements only play after GitHub confirms the corresponding setting was changed. The two larger security clips can be reconstructed from integrity-checked `.parts` the first time they play, without overwriting any existing file.


## v0.5.0 — Sidebar, Repository Code Workbench, Build/Rebuild and headless

**Sidebar:** Use `≪` to collapse the left navigation to icons; `≫` expands it again. All destinations remain available and each icon has an accessible name/tooltip. The top workflow controls jump to sections of the currently selected page; the persistent sidebar alone navigates between pages. They never upload or commit.

**Repository Desk → Repository Code Workbench:** Select your GitHub account, repo and branch on the Upload Station. Open Repository Desk. In **GitHub repository**, choose **Browse Folder**, double-click directories/files, or enter an exact path and click **Open GitHub File**. To create a file, enter a new path and click **New GitHub File**. Edit UTF-8 code, select **Validate Syntax** or **Review Diff**, then **Review & Commit to GitHub**. Inspect the full diff, enter a meaningful message, and confirm the exact destination. A missing or altered remote SHA, different account, branch or file will stop an unsafe write. No GitHub code is automatically executed.

The **Local files and tests** tab opens and saves UTF-8 files. Save makes a separate backup and fails rather than replacing a file changed by another program. Save As creates a new file and refuses overwrite. **Run Local Tests** asks permission to execute test code in a folder that you trust, uses your local Python interpreter and reports unittest or already-installed pytest results. Static Python/JSON/TOML validation does not run code.

**Jobs & Rebuild:** Choose **Discover GitHub Builds** to list committed Strapman manifests, select one, choose a new local destination, then **Build / Rebuild from GitHub**. This downloads and validates each segment and the full SHA-256 before publishing the restored original. **Rebuild from Local Manifest + Parts** uses a previously stored manifest and cache folder without GitHub. Neither path overwrites an existing output. Existing Upload Station options remain upload strategies, not reconstruction modes.

**Headless:** Use `headless/headless-strapman.cmd` on Windows or `headless/headless-strapman.sh` on Linux and pass `--help` for machine-readable CLI operation details. Headless includes the same chunk format, pause/resume, remote audit and verified Build/Rebuild with no sounds. `dashboard` starts a local authenticated browser progress panel. `snapshot` writes a non-overwriting HTML or PNG status image of real checkpoints; it never fabricates progress. PNG requires a locally installed Qt. The offline build can run without GitHub credentials.


## After an unexpected program exit or computer shutdown

On the next desktop launch, Strapman checks OS-owned upload and restore locks. A saved **Preparing**, **Uploading**, **Downloading** or **Assembling** record with no worker lock is marked **Interrupted**, not **Complete**. Use **Job History → Resume Selected Job** after verifying the repository, branch, and output file are correct. Remote commit state and local SHA-256 parts are reconciled again. **Do not erase the cache to make the button work.** Interrupted local Build/Rebuild can also resume without a GitHub login. The application never restarts uploads automatically after boot. Details: [Crash Recovery](CRASH_RECOVERY.md).

**Agent commands and progress:** `headless/headless-strapman.cmd` (Windows) and `.sh` (Linux) provide no-sound operations, a local status dashboard, and snapshots. See [Headless](HEADLESS.md).

## Verify Bootlegger audio before your first test

Run `python tools/verify_audio_assets.py` from a full checkout of the
private development repository. It checks all 14 original MP3s and all
14 Pro package copies against the expected original Git blobs. A code-only
patch does not contain the full recordings and therefore cannot pass this
test. Lite deliberately uses built-in system tones rather than MP3s.
In Bootlegger Settings & Help, preview each voice event with sound and
voice enabled; a successful file check alone does not prove speakers work.


## v0.5.2 — Automatic reconstruction and contextual workflow

Upload Station defaults to automatic remote verification and **local reconstruction from GitHub's committed chunks**. Once the returned original is SHA-256 verified, the job is marked complete and the reconstructed output path appears on Upload Station with an Open Rebuilt Output Folder control. Manual Build/Rebuild remains accessible from Jobs & Rebuild for later recovery without repeating an upload.

A remote upload which finished but whose automatic rebuild failed or paused has status `rebuild_failed` or `rebuild_paused`, not `complete`. It retains the committed GitHub manifest and can be resumed without duplicate commits. Original files are not deleted and existing destinations are never overwritten. An explicit per-upload opt-out is available for users who specifically want publish-only operation.

The Bootlegger branding icon now sits **above** the complete title. Existing sidebar entries are preserved. Top-row controls select stages **within the current page**; they do not replicate the sidebar's destinations or perform remote writes. See [WORKFLOW.md](WORKFLOW.md).
