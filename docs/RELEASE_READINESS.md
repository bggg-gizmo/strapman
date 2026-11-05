# Strapman public-release readiness — v0.5.1 development

This is a factual technical gate record, **not** a guarantee of zero bugs or a
claim that a public release has been certified. It covers only Strapman.

**Current status:** Public testing for v1.0 is underway. See the [Public Testing Checklist](PUBLIC_TESTING_CHECKLIST.md) for test cases, the evidence to submit, and the criteria for moving to v1.0. Historical sections below reflect their original dates, including when the testing repository was private. The provider-independent foundation and Gitea/Forgejo integrations are in progress per the [roadmap](../ROADMAP.md), but GitHub remains the only currently supported host.

## Completed in the development environment

- v0.3.1 source review and automated regression suite: **46 passed** on Linux
  with Python 3.13.5; GitHub operations in this suite use simulated endpoints.
- Byte-exact binary splitting, per-chunk SHA-256 checks, branch-reconciliation
  resume, optional source publication, and local verified reconstruction exercised
  by the test suite.
- GitHub blob responses are checked against locally computed Git object IDs.
- Separate remote-upload / optional-local-restoration states, preventing false
  reports that published GitHub files were lost after a local restore failure.
- Remote full-source verification no longer depends on a local staging cache.
- GitHub README editing is restricted to the account/repo/branch loaded in the
  editor, preventing silent retargeting after a selection change.
- UI alert text distinguishes **JOB COMPLETE** from **JOB FAILED**; transfer
  metrics report bytes, throughput and estimates; active Qt worker is protected
  against accidental window destruction.
- Application PNG/ICO assets generated from the existing SVG brand icon; the
  GUI loads its PNG asset as the Qt application and window icon.
- `python tools/public_audit.py` passes for the source snapshot. The scanner
  is deliberately read-only and flags credential-looking strings, home paths,
  private key headers, undesirable archives and suspicious workflows.
- No GitHub Actions workflows, paid CI workflow jobs, automatic source-file
  deletion or GitHub Release-asset transport were added to Strapman.

## Gates still open before a general public release

1. **Full Git history privacy inspection:** From a genuine Git checkout run
   `python tools/public_audit.py --history`; review all refs, commits, author
   and committer metadata, images, archived payloads and text. This source-only
   development environment does not contain the original `.git` object history.
2. **Live GitHub integration:** In a disposable repository under the test
   account, exercise personal-access-token sign-in, native device-code login,
   Git credential-helper discovery without gh, GitHub CLI device-code fallback, account switching, repository creation,
   branch selection, README edit conflict, multi-worker chunks, interrupted
   transfer/resume, source-staging and full restore with remote SHA-256. Verify
   that all uploads are visible under the repository's Code tab.
3. **Windows GUI smoke test:** Validate first-run setup, background threads,
   window controls, completion/failure sounds and flashing, account switching,
   long transfers, restore and file-picker behavior on a real Windows desktop.
4. **Linux GUI smoke test:** Validate the same with a supported display server,
   desktop dependencies, permissions, dialogs and file packaging on Linux.
5. **Install bootstrap:** Test the disk-space gate when storage is insufficient,
   pip dependency resolution from scratch, verified GitHub CLI fallback install,
   and offline/partial-install error reporting on both operating systems.
6. **Native OAuth:** Register the public Strapman OAuth App with GitHub, enable
   Device Flow, distribute its public client ID, and confirm the first-run
   one-time-code flow with Git **and** GitHub CLI absent. Bundle the public client ID in `strapman/oauth_app.json`, keep the secret out of source, and test both fresh users and reused Git Credential Manager sessions. Test short-lived token expiry or disable expiration until refresh support exists; a GitHub CLI fallback is optional.
7. **Desktop distribution:** Decide executable/installer format with owner,
   select the final Windows executable icon, compile using a `.cmd` entrypoint,
   validate signed/unsigned installer behavior, and create a Linux desktop file
   if distributing a system-installed application. No EXE or signed installer
   is included in this source build.
8. **Independent release security review:** Audit dependencies, GitHub API
   permissions, secret-handling edge cases, symlink paths, large-file limits,
   rate limits and race conditions in a real network and filesystem test.

The application remains **development-stage** until these tests are performed.
Do not automatically make the current private repository public; use a fresh
reviewed public repository or a history-audited publication procedure as the
owner decides. A source snapshot scan never substitutes for reviewing Git
history or uploaded media metadata.

## Edition milestone: 0.4.0 development split

Lite and Bootlegger are separate entry folders sharing the existing Python engine. Bootlegger adds purple/black dark mode, two selectable light palettes, a distinct lamp-themed app icon, event MP3 playback with OS-beep fallback, and edition-separated app data. Lite retains its original dark UI and OS sounds.

**Still mandatory before declaring a public or Pro release ready:** native Windows and Linux Qt Multimedia codec playback, actual theme-switching GUI tests, power-state notification verification where supported, a GitHub upload/restore against an explicitly disposable test repo, and a full Git-history privacy check from an authenticated local checkout. A source snapshot or mocked tests do not certify these gates. No licensing, premium access enforcement, payment processing, or release automation is implied by the edition names.

## v0.4.1 — authentication reuse and native OAuth preparation

- 57 mocked Python regression tests passed locally, including noninteractive Git credential helper retrieval, missing `git` and `gh` fallback cases, invalid helper output, publisher public-ID validation and REST-client credential reuse.
- First-run/Settings can use an existing Git Credential Manager session, without forcing `gh` installation or a new OAuth login. Account identity is verified via GitHub `/user`; newly discovered Git identities must be confirmed. Logging out of Strapman does not revoke Git Credential Manager credentials.
- Native one-time-code flow uses a **publisher-supplied public OAuth client ID**, not Git or `gh`. Codex registration steps and the exact public configuration file are documented in `docs/DEVELOPER_AUTH.md`. No actual client ID or secret has been registered or bundled at this stage.
- Real Windows Git Credential Manager reuse, native device-code flow with the publisher's actual OAuth App, Linux GUI, and disposable GitHub upload/restore tests **remain open**. Qt GUI tests were not run in the local environment. No GitHub Actions are added.


## v0.4.2 — reported Windows MP3 silence and repeated dependency downloads

- Observed on Windows: Qt/FFmpeg loaded the seven Bootlegger MP3s but the owner heard system beeps instead of the voice cues. The prior UI swallowed Qt playback errors and silently used `QApplication.beep`. v0.4.2 uses built-in Windows MCI MP3 playback ahead of Qt with explicit backend errors, Settings playback status, and no deceptive beep fallback in Pro. The exit MP3 is no longer truncated to 1.5 seconds. Lite's system sounds are unchanged.
- The bootstrap reused `.venv` only when extraction root was unchanged, triggering repeated large PySide6 installs with new ZIP roots. v0.4.2 reuses a compatible per-user Python runtime across editions and releases, and can reuse existing nearby `.venv` folders from earlier downloaded copies. It runs pip only when the environment is missing/incompatible, after a destination disk-space check.
- Local mocked audio and bootstrap tests pass. **Native Windows MCI device playback has not been tested in this Linux development environment**; the owner's follow-up Windows audio smoke test remains required. The original MP3 Git blobs are unchanged.

## v0.4.3 — functional completeness and pause/voice regression pass

- 79 local Python automated regression tests pass, including pause during hashing, pause after an upload commit, restore pause/reboot recovery, late interruption before local output publication, distinction between cancellation and pause, multipart audio checksum and non-overwriting rebuild checks, minute-based AC reminders, default voice settings, existing upload/restore integrity, authentication and reusable install behavior.
- Repository Desk now loads both repo metadata and the selected branch README on navigation/refresh; it preserves unsaved editor content and indicates absent README instead of presenting an unexplained blank editor.
- Added per-edition user **Pause Safely** and persistent upload/restore checkpoint/restart semantics. A completed GitHub upload is not reclassified as failed merely because optional local reconstruction pauses.
- Bootlegger now routes all 14 owner-supplied voice event categories and queues them, separating a voice preference from the overall sound preference. AC unplugged is reannounced at 60-second intervals while the OS reports unplugged power. The two multipart security clips can be verified and assembled without replacing the originals.
- The installer reuses an existing healthy Python environment; no paid GitHub Actions, forced branch updates, file reclamation, Windows system changes or WatchMan edits were introduced.

**Still untested here:** native Qt GUI event sequencing, actual Windows MCI/Qt audio playback, live AC transitions on hardware, publisher native OAuth registration, complete original Git-history audit and real disposable-repository upload/restore with throttling and pause/resume. The automated suite uses mock GitHub responses and is not evidence of platform certification. See [functional coverage](FUNCTIONAL_COVERAGE.md).


## v0.5.0 — headless, workbench and sidebar preview gates

The headless CLI, GitHub-scoped editor model, local unittest runner, path guards and offline reconstruction have passed mock/local Python tests. **This is not a live desktop or public release certification.** PySide6 was unavailable locally and could not be installed because the package index was unreachable; therefore sidebar clipping, compact navigation, top workflow, theme styling, Windows audio and Qt PNG snapshots must still be tested on real systems. Live GitHub text-file commit, remote Build/Rebuild and account/branch conflict tests must use a disposable repository with explicit authorization. Public OAuth App client ID and full historical privacy review are still outstanding. No paid GitHub Actions were used.


## v0.5.0 — unexpected exit and boot-resume evidence

**102 local automated tests passed** including five new hard-termination tests using separate child Python processes. They exercise death during initial hashing, death during local reconstruction, interrupted checkpoint identification without touching a live lock-owning worker, refusal of changed inputs, and headless lock ownership after a phantom heartbeat. The local source privacy scan passed; a full historical Git audit was **not** performed on this source-only workspace. Disk hardware failure, power loss during filesystem journal commit, Windows lifecycle controls, Qt layout, MP3 playback, and real GitHub API transfers remain open validation gates. Strapman does not automatically resume remote writes after reboot.

## v0.5.1 — final source and audio sweep

**Source evidence:** 110 local Python automated tests passed, static
compilation passed, current-source privacy scan passed, and the installer
space check passed. Updated GitHub blob reads verify content/object ID;
large audit/rebuild operations use bounded futures; README/editor callbacks
refuse stale optimistic SHA scope. README, manuals and
[FINAL_SWEEP.md](FINAL_SWEEP.md) record the current feature contract.

**Audio inventory:** 14 configured voice events correspond to 14 original
MP3 blobs, with an identical Pro copy for each on GitHub main. The new
`python tools/verify_audio_assets.py` checks all 28 local MP3 copies
without editing them. Complete audio-byte checks, actual Qt/Windows speaker
playback, and the AC unplug reminder still require a real complete checkout
and test devices.

**Still required before public certification:** Native Windows/Linux GUI
layout and event behavior; speaker playback of every Pro cue; genuine
disposable GitHub upload, SHA verification, resume and Build/Rebuild;
publisher OAuth App with a real public client ID; full original Git-history
privacy audit; native packaging and interruption tests. Mocked tests do not
substitute for these release gates. No WatchMan edits or paid Actions.


## v0.5.2 corrective acceptance gates

The prior default upload-only reconstruction path and duplicated top navigation were owner-reported UX defects. The development correction makes verified local reconstruction part of the automatic upload pipeline by default, separates remote publication from rebuild completion, keeps manual recovery, stacks the Bootlegger brand icon above the complete fitted name, and uses in-page top workflow controls instead of a second page menu. Headless returns a nonzero exit code for incomplete automatic rebuilds.

**Verification still outstanding:** Real Windows/Linux GUI layout at screenshot-equivalent dimensions, full headless CLI live tests, speaker/cue tests, a disposable >1-GiB GitHub transfer → pause → reboot → resume → rebuild → exact SHA-256, OAuth publisher setup, and full Git-history/privacy metadata inspection. Do not call this public-production certified from local mock tests.

## 2026-11-05 — Complete-checkout Windows and private GitHub check

- Windows Python 3.12: **122 passed, 0 failed**. Three earlier tests assumed POSIX paths, LF text writes, or UTF-8 as the Windows default; their fixtures now express the intended behavior on both platforms. Eleven tests were added after the earlier 110-test baseline and none were removed.
- `tools/verify_audio_assets.py`: **32/32 exact MP3 copies, 16 events**. The two new recordings retain their owner-supplied SHA-256 digests. Current-source and full Git-history privacy checks passed in a real checkout.
- A private disposable GitHub repo passed a real three-part upload, pause after a committed part, resume from a new engine instance, remote manifest readback, and SHA-256-equal local reconstruction. A separate live Headless CLI upload completed its default remote verification and reconstruction. The Headless run exposed a Windows progress-file read/write race, which was corrected and retested.
- A Windows Qt offscreen smoke test instantiated Lite and Bootlegger at their 1010×700 minimum, checked the full brand title fits and confirmed the top strip changes within each selected page. Offscreen font glyphs did not render legibly, so this is not a native-display visual certification. Native Windows MCI returned an initialization error for the new MP3s; audible playback was not verified.

**Still open:** Native Windows/Linux GUI and speaker acceptance, AC transition hardware, OAuth publisher registration, a 1+ GiB live transfer with real reboot and recovery, installer packaging, media/licensing review, and any future public visibility change. The testing repository remains private.

## 2026-11-05 — Community public testing → v1.0

The public testing repository is open for feedback. The [Public Testing Checklist](PUBLIC_TESTING_CHECKLIST.md) requests real Windows/Linux visual and audio evidence, installer/authentication checks, GitHub chunk publication and SHA-256-verified automatic/manual rebuild, safe pause/interruption/restart/resume, Headless parity, one 1 GiB+ disposable stress test, and privacy, dependency, license and media-rights reviews. The recorded 122 automated tests and earlier disposable multipart integration are useful baseline evidence, **not** proof every gate has closed. Publisher device-code OAuth setup remains pending; do not claim it is fully configured. Platform integrations for Gitea/Forgejo are being developed according to the roadmap, not currently supported. Critical correctness and data-integrity reports must be fixed and retested before v1.0.
