# Strapman Lite

**Background Gremlin Group · Creating Unique Tools for Unique Individuals**

The original Strapman staged GitHub upload and restore experience, in the classic retro-bubble dark theme. It retains all currently shared core features: GitHub login, repository/branch selection, resumable byte-perfect chunk uploads, parallel workers, remote verification, restoration, README editing, and offline manuals.

## Launch

Windows: double-click `lite/Strapman-Lite.cmd` from a complete checkout.

Linux: run `./lite/Strapman-Lite.sh` from the repository root. The installer checks available space before installing required Python dependencies, then launches Lite.

Lite uses built-in desktop notification sounds through `QApplication.beep()` for the same event categories as Bootlegger. **It does not load or bundle Bootlegger's MP3 files.** Notification sounds and completion flashes are enabled by default and adjustable in Settings.

The existing root `Strapman.cmd` and `strapman.sh` still launch Lite. Settings and local checkpoints retain their prior Lite location. No existing uploads are migrated or erased.

See [shared USERMAN](../docs/USERMAN.md) and [the editions guide](../docs/EDITIONS.md).


### Shared development update: v0.5.0

The Lite UI keeps its original look and built-in sound effects, and now shares the collapsible navigation, Repo Desk code workbench, Jobs & Rebuild original-file recovery and optional sound-free headless interface. There are no Bootlegger MP3 dependencies.
