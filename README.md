<div align="center">

# Strapman Lite · Bootlegger Pro · Headless Strapman

**Local-first GitHub uploads, integrity verification, file reconstruction and developer tools.**

**Background Gremlin Group — Creating Unique Tools for Unique Individuals**

</div>

> **PRIVATE TESTING SNAPSHOT — v0.5.1-dev.** This repository is intentionally private while the Windows/Linux GUI, voice playback, authentication, multipart transfer and restore workflows complete real-device acceptance testing. Do not treat this code as a certified public production release.

## Why Strapman exists

Not everyone can or wants to spend credits on hosted runners, CI jobs or GitHub Actions. Strapman performs its large-file staging, chunked transfers, integrity checks, recovery and reconstruction locally, through direct GitHub APIs. No paid GitHub Actions are required for its core workflow.

Headless Strapman provides a sound-free, command-line interface for local scripts and AI coding assistants to stage and rebuild large files without re-explaining the complete bootstrap procedure each time. Remote actions still require the user's explicit account, repository, branch and authorization.

## Editions

- **Strapman Lite:** Windows/Linux GUI, GitHub repository desk, chunked and staged uploads, remote verification, robust pause/resume, file restoration, local/remote code workbench and built-in system notification tones.
- **Bootlegger Pro:** Everything in Lite, plus purple/black, pink/white and blue/white themes, a distinct leg-lamp-inspired icon, and 14 optional event-specific voice MP3 cues.
- **Headless Strapman:** JSON status, upload, pause, resume, audit, rebuild, safe reconstruction, local code checks, dashboard and on-demand status snapshots. No voice or paid CI runner.

All editions share the same underlying source validation, checksum and GitHub upload/rebuild engine.

## Launch

Extract the entire source repository so its assets and dependencies remain in their expected folders. Python 3.10+ is required.

**Windows**
- Lite: double-click lite/Strapman-Lite.cmd
- Bootlegger: double-click bootlegger/Bootlegger-Pro.cmd
- Headless: run headless/headless-strapman.cmd status

**Linux**
- Lite: ./lite/Strapman-Lite.sh
- Bootlegger: ./bootlegger/Bootlegger-Pro.sh
- Headless: ./headless/headless-strapman.sh status

The installer checks disk space and reuses a compatible per-user Python environment instead of reinstalling a full Qt stack for each extracted update.

For native GitHub device-code login, a publisher-registered OAuth public client ID must still be bundled. Existing Git credentials, secure tokens, and GitHub CLI may be used according to supported authentication options.

## What is actually supported

**Current remote provider: GitHub.** The application uploads small verified Git blobs and commits chunk paths and a reconstruction manifest into the selected branch. A blob uploaded but not attached to the branch is not considered published. It can reconstruct from committed GitHub parts or from a verified offline local cache, refusing to overwrite existing output.

**Gitea and Forgejo support are planned for development** and are **not** currently supported by the upload engine. See ROADMAP.md in the development repository or the edition documentation when provider support is released.

GitHub-hosted Actions, hosted builders, arbitrary executable compilation, hosted databases, and automatic deletion/reclaim of original source files are **not** part of the current product.

## How to help test

Use a disposable repository and non-sensitive sample data, not production backups. Exercise:
1. First-run sign-in, repository/branch selection and README editing.
2. Multi-chunk upload and remote SHA-256 verification.
3. Safe Pause; exit the application; relaunch and explicitly Resume from Job History.
4. Build/Rebuild the downloaded parts; compare SHA-256 to the original.
5. Bootlegger voice previews, power notices, all three themes and window resizing.
6. Headless CLI status, commands and safe local progress dashboard.

Run the local checks from the extracted root when development dependencies are present:

    python -m pytest -q
    python tools/public_audit.py
    python tools/verify_audio_assets.py

The last development-source review recorded **110 passing Python automated tests** with mocked GitHub network responses and real local filesystem tests. That is not the same as real Windows, Linux or GitHub API certification.

## Documentation

- docs/USERMAN.md — User manual
- docs/HELPMAN.md — Troubleshooting
- docs/FINAL_SWEEP.md — Function and audio coverage
- docs/RELEASE_READINESS.md — Remaining acceptance gates
- docs/SECURITY.md — Source, token and data-handling expectations
- docs/HEADLESS.md — Agent/CLI commands
- docs/EDITIONS.md — Lite/Bootlegger feature differences

## Safety and publication

Do not publish private tokens, OS account paths, complete backups or user logs. Avoid unexpected remote writes and never force-push to repair a resumed upload. **This snapshot is private until the owner approves a public visibility change.** Do not infer an open-source license from the ability to view or test the code; licensing must be selected by the owner before broad distribution.

**Developed by Background Gremlin Group.**
