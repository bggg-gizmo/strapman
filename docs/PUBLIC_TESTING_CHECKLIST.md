# Public Testing Checklist — The Road to Strapman v1.0

**Current build:** v0.5.2-dev · Public testing  
**Goal:** Collect reproducible evidence for a safe v1.0 release across Strapman Lite, Bootlegger Pro and Headless Strapman.  
**Currently supported host:** GitHub.

Thanks for helping test Strapman. We need real-world results, **including failures**. Tests should use **disposable GitHub repositories and copied, non-sensitive files**. Never risk your original files, production repositories, live backups or credentials.

**Platform integrations are in progress per the [roadmap](../ROADMAP.md).** Development is working toward a provider-independent architecture, with **Gitea and Forgejo** adapters planned and being developed/researched, and additional services such as GitLab under later evaluation. They are **not yet supported in this public testing build**. Please suggest desired hosts, versions and workflows in [Discussions](https://github.com/bggg-gizmo/strapman/discussions).

## Before testing

- [ ] Download a complete [source ZIP](https://github.com/bggg-gizmo/strapman/archive/refs/heads/main.zip) or clone the repository; keep all assets and edition launchers together.
- [ ] Record the exact tested **commit SHA**, application edition, Windows/Linux version, CPU architecture, Python version, and whether you launched from a ZIP or Git checkout.
- [ ] Create a **disposable** GitHub repository you control and choose synthetic or copied test files. Never use the development or release repositories as testing targets.
- [ ] Record the original test file's size and SHA-256. For every scenario report **Pass**, **Fail**, **Blocked**, or **Not tested**.
- [ ] Remove tokens, device codes, passwords, local home paths, private repository data, cookies and identifying screenshots from any logs or bug reports.

## 1. Installation, first run and authentication

- [ ] Start **Lite** and **Bootlegger Pro** using the supplied Windows/Linux launcher; confirm the correct edition, icon, theme and responsive UI.
- [ ] On a fresh profile, note dependency download size, free-space checks, startup errors and installation time.
- [ ] Extract an updated build to a different folder and relaunch: a compatible Python environment should be reused, rather than repeatedly downloading the full Qt stack.
- [ ] Reuse an existing GitHub sign-in method such as Git Credential Manager, **without requiring GitHub CLI**. Confirm that the displayed GitHub account is the one you authorized.
- [ ] Switch accounts if possible. Previous account repositories, branches and editor bindings should not silently persist.
- [ ] Try missing/expired credentials. Expect clear errors and **no unapproved writes**.

**Report:** edition, OS/Python versions, fresh/reused environment, how login was verified, and the redacted error plus attempted action for failures. The publisher's built-in GitHub OAuth device-code login is pending registration; mark that path **Not available** until announced, rather than counting it as a working feature.

## 2. Desktop UI, themes and Repository Desk

- [ ] Inspect all four pages: Upload Station, Repository Desk, Jobs & Rebuild, and Settings & Help; resize the window and try high-DPI scaling.
- [ ] Confirm the sidebar remains the page navigator, while the top workflow controls navigate **within the current page**, rather than duplicate sidebar buttons.
- [ ] Confirm Bootlegger's complete wordmark appears **beneath its icon** and no text or controls are cut off.
- [ ] Try Bootlegger's Purple Night, Pink Pearl and Blue Frost themes and verify selection persists after restart. Check that Lite retains its own identity.
- [ ] In your **disposable repository**, load an existing README and create one when absent; review and deliberately commit an edit. Confirm the correct file appears on GitHub.
- [ ] Browse branches/directories and edit a test source file in the Repository Code Workbench. Check syntax validation, diffs, and trusted local test execution.
- [ ] Switch repository or branch with unsaved edits. Confirm the app does not silently discard your draft or commit it to the wrong destination.
- [ ] Simulate a concurrently modified remote test file. Confirm optimistic SHA conflicts are detected; no forced overwrite or unwanted commit occurs.

**Report:** actual control behavior, window size/display scaling, redacted screenshots, repository/branch used for **test** commits, any errors and whether drafts remained intact.

## 3. Upload → verify → automatic local rebuild (critical)

- [ ] Upload a small generated binary to a disposable GitHub repository. Repeat with a file larger than the selected chunk size.
- [ ] Try **chunked binary/archive** and, where suitable for a small file, **cumulative source staging**.
- [ ] Confirm published chunk paths and the `manifest.json` appear under `strapman-uploads/` in the repository Code view. **Orphan blobs alone are not a complete upload.**
- [ ] Confirm remote chunks, Git blob IDs, part SHA-256 and the manifest are verified before reporting publication.
- [ ] Confirm the default job **automatically downloads and reconstructs the original locally**, with no separate mandatory Build/Rebuild click.
- [ ] Locate the rebuilt file via Upload Station and compare its **full SHA-256 and byte length** with the original. Both **must match exactly**.
- [ ] Use the separate manual **Jobs & Rebuild** path to rebuild from the GitHub manifest into a different unused output location. Hash the restored file again.
- [ ] Attempt a restore into an already occupied destination. Expect a safe refusal—not an overwrite. Confirm the original is unchanged.
- [ ] Where possible, repeat with another chunk size and worker count. No paid GitHub Actions or hosted runner should be needed.

**Report:** source size, source SHA-256, rebuilt SHA-256, chunk size/count, workers, manifest path, whether the Code view shows the commits, job status, error details, and observed transfer/rebuild times. **We need proven matching hashes**, not only a green progress bar.

**Optional advanced test:** If your disk space, bandwidth and GitHub quotas permit, use a **generated 1 GiB+ test file** in a disposable repository, including verification and reconstruction. This is especially valuable evidence for v1.0, but not expected of every volunteer.

## 4. Pause, crash/interruption and safe resume (critical)

- [ ] Pause an in-progress multipart upload; confirm it saves a checkpoint and resumes without needlessly republishing verified parts.
- [ ] Pause while rebuilding if that phase is reached. No incomplete output may be presented as a complete file.
- [ ] Restart the application after a cooperative pause and **explicitly** resume; confirm the final SHA-256 still matches the source.
- [ ] **Advanced testers, disposable data only:** Simulate an unexpected app process exit. On relaunch, verify the job is shown as interrupted and does **not** silently restart network writes.
- [ ] During a disposable test, safely interrupt network connectivity or reproduce low space. The application should preserve already verified GitHub data and report whether only publication or the entire rebuild is complete.
- [ ] Attempt to resume a previously published job: verify it can rebuild without duplicating final commits. Check that a second process cannot control the same job concurrently.
- [ ] Ensure **no original source files are deleted, modified, reclaimed or overwritten**, including during failure.

**Report:** phase at interruption, last checkpoint state, committed part count, resume steps, error status, commit count before/after, final SHA-256, and any source-file changes. **Do not turn off a production machine or interfere with someone else's backup to test this.**

## 5. Audio and accessibility

- [ ] On actual audio hardware, preview Bootlegger's **16 voice MP3 events**, including **README updated** and **Codebase updated** after successfully committed GitHub changes. The correct recording—not just a system beep—should play.
- [ ] Check that Sound and Voice can be toggled **independently**, default to on for a fresh Bootlegger profile and retain user preferences on restart.
- [ ] Verify Lite uses its normal non-MP3 system tones and that Headless is silent.
- [ ] If using a compatible laptop, check the unplugged power reminder repeats about **once per minute** while disconnected, and stops when power is restored.
- [ ] Record any failure to play, backend error or inaccurate "playing" status. Inspect clipped text, keyboard accessibility, resizing and themes.

**Report:** OS, speaker/output device, edition, specific cue or control, audible yes/no, expected vs actual sound, and sanitized backend error.

## 6. Headless Strapman and agent automation

- [ ] Run `headless/headless-strapman.cmd status` on Windows, or `./headless/headless-strapman.sh status` on Linux. Check JSON output and confirm basic CLI use does not download Qt or audio packages.
- [ ] In a disposable repository, run an explicitly authorized upload with default automatic reconstruction; verify reported final state and local file hash.
- [ ] Pause, inspect, restart and explicitly resume a saved checkpoint. Confirm progress and status remain accurate between processes.
- [ ] Open the token-protected **loopback-only** dashboard and generate an HTML snapshot; try PNG only where Qt is already installed.
- [ ] Validate/diff a trusted local test file. Run tests only if you understand and approve them.
- [ ] Trigger an unfinished rebuild in a disposable test: Headless should return a **nonzero exit code**, not success.
- [ ] Confirm Headless remains silent and never starts unapproved GitHub writes or hosted Actions.

**Report:** sanitized commands, JSON state, exit code, checkpoint ID only if harmless, dashboard behavior, final SHA-256, and discrepancies between the displayed progress and actual results.

## 7. Privacy and error handling

- [ ] Inspect generated public manifests: **no token, local home directory, device identifier or private log** should appear.
- [ ] Check wrong-account, permission-denied, changed remote file, occupied destination, and invalid manifest behavior; operations must fail safely, without force-push or silent file deletion.
- [ ] Report credential leakage/security issues **privately** rather than pasting sensitive material in public tickets.
- [ ] Submit a [bug report](https://github.com/bggg-gizmo/strapman/issues/new), discuss enhancements in [Discussions](https://github.com/bggg-gizmo/strapman/discussions), or propose a tested [pull request](https://github.com/bggg-gizmo/strapman/pulls).

## Required report format

| Field | Tester evidence |
|---|---|
| Build and edition | Commit SHA, Lite / Bootlegger / Headless |
| Environment | Windows/Linux version, Python version, hardware/display scaling where relevant |
| Checklist scenario | Section and checkbox, steps taken |
| Result | **Pass / Fail / Blocked / Not tested**; expected and actual behavior |
| Repeatability | One-time, intermittent, or consistent; number of attempts |
| Transfer details | Generated source size, chunk size/count, workers, GitHub manifest path |
| Integrity | Original and restored **SHA-256**, with equal file size |
| Recovery | Checkpoint/commit behavior, whether any source or destination changed |
| Evidence | Redacted screenshots, sanitized log excerpt, error and timing |

Use [Issues](https://github.com/bggg-gizmo/strapman/issues/new) for reproducible bugs, [Discussions](https://github.com/bggg-gizmo/strapman/discussions) for suggestions and integration requests, and [Pull Requests](https://github.com/bggg-gizmo/strapman/pulls) for reviewed changes. **Never submit real API tokens, passwords, one-time codes, private file contents or identifiable full logs.**

## v1.0 acceptance checklist (maintainer review)

These boxes describe the **results still needed**, not work already certified:

- [ ] **Integrity:** reproducible multipart GitHub upload, committed manifest, automatic + manual local rebuild, matching whole-file SHA-256, no modified originals.
- [ ] **Recovery:** real-world pause, restart/interruption, explicit resume, no duplicate worker or unintended commit, and no false `complete` status.
- [ ] **Desktop:** native Windows and Linux UI and first-run/upgrade testing, high-DPI readability, real Bootlegger sound output and available AC-reminder checks.
- [ ] **Headless:** JSON/exit-code accuracy, dashboard, pause/resume and automatic reconstruction without requiring GUI/audio dependencies.
- [ ] **Scale:** credible **1 GiB+** disposable upload/verify/rebuild evidence with equal final checksum.
- [ ] **Privacy/security:** source and reachable-history scans, credential handling, permissions, dependency/media review and no known source-deleting or unsafe overwrite path.
- [ ] **Licensing/distribution:** choose an explicit open-source license and verify redistribution rights for artwork and MP3s; publish accurate installation and release documentation.
- [ ] **Authentication:** verify available login paths; publisher OAuth registration and true device-flow acceptance stay pending until the publisher configures and tests them. Do not advertise an untested flow as operational.
- [ ] **Defects:** resolve and retest all confirmed critical data-integrity/security defects and decide the remaining high-severity findings before v1.0 sign-off.
- [ ] **Supported host claims:** GitHub remains verified; Gitea/Forgejo or further provider integrations must pass their own disposable-instance end-to-end checks before being labeled supported.

The [roadmap](../ROADMAP.md) tracks provider-independent work, Gitea, Forgejo, and longer-term platform research. We welcome feedback on the required host versions, authentication and workflows **while integrations are being completed**; their presence on the roadmap does not imply they work in this build.

**Background Gremlin Group — Creating Unique Tools for Unique Individuals.**
