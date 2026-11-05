# Strapman editions — private development layout

The same vetted `strapman/` core implements GitHub authentication, upload, chunk verification, remote audit, and restore. Keeping one core instead of copying it prevents bugs and security fixes from diverging.

| Feature | Strapman Lite | Bootlegger Pro |
| --- | --- | --- |
| Launcher | `lite/Strapman-Lite.cmd`, `.sh` | `bootlegger/Bootlegger-Pro.cmd`, `.sh` |
| Normal UI theme | Classic retro dark | Purple Night (purple/black) |
| Optional light themes | Not included | Pink Pearl (pink/white), Blue Frost (blue/white) |
| Application icon | Original Strapman bubble | Leg-lamp GitHub-shade original |
| Windows ICO asset | `lite/assets/strapman-lite-icon.ico` | `bootlegger/assets/bootlegger-icon.ico` (seven image sizes) |
| Audio notifications | OS-native beep; **no MP3 files** | Bundled MP3 cues; Windows-native player with Qt fallback and visible errors |
| Alert categories | Ready, setup, completion, error, exit, power changes | Same categories |
| Sound/flash toggles | Yes | Yes |
| Workload settings | Upload workers and chunk size | Same shared engine |
| App data | Existing Strapman location | Separate `bootlegger/` subdirectory |
| Github data formats | Current verified chunk manifest | Same compatible format |

## Private repository organization

- `lite/`: Lite launchers, branding and edition manual.
- `bootlegger/`: Pro launchers, themes, branding, bundled MP3 assets and edition manual.
- `strapman/`: shared Python application, Github transport, state and verification engine.
- `assets/`: original shared vector artwork and unmodified source recordings; already-present assets are not deleted.
- `docs/`: shared USERMAN, HELPMAN, SECURITY, and edition behavior documentation.
- `tests/`: tests for shared safety and edition-specific policy.

No paid GitHub Actions workflows are used, and the program never reclaims users' local source files. MP3 bytes are retained and linked under Bootlegger's folder in Git history without changing their contents. Never put credentials or machine-specific paths into the source repository.

## Release packaging

When creating the separate public Lite repository, **exclude** `bootlegger/` and any `assets/sounds/` MP3s. When packaging Pro, include `bootlegger/assets/sounds/` from the full private GitHub checkout. Shared source tree packages can contain both edition launchers, but the two public distributions should be built independently after real Windows/Linux and test-repository upload/restore tests.

The current milestone is a private development split. It is not a declaration that the applications are publicly certified or that premium licensing or entitlement enforcement is implemented.


## Reusing the Python runtime across updates

`install.py` shares one compatible user-local Python runtime between Lite and Bootlegger, independent of the source ZIP extraction path. Healthy older `.venv` environments can be reused in place. Both editions retain their own app state. No MP3s are installed as Python packages; the complete repository checkout includes all 16 Bootlegger MP3s under `bootlegger/assets/sounds/`.

## v0.4.3 voice and workflow policy

Bootlegger now has separate **Voice MP3 notifications** (default on) and **Play notification sounds** (default on). With voice off and general sound still on, it emits a standard system tone for events; Lite never imports the Pro recordings. The Bootlegger audio library covers **14 event categories** including pause, resume, remote verification, repository changes and both security setting successes. Two security recordings may be delivered as verified `.parts` and materialized locally without overwriting existing files. Owner-supplied bytes are never transcoded. MP3 cues are queued to avoid truncating spoken messages.

Both editions expose **Pause Safely** and **Resume Selected Job** for uploads/restores. Durably paused checkpoints survive a reboot; remote Git commits and local restore caches are preserved. See [functional coverage](FUNCTIONAL_COVERAGE.md) for individual event triggers, reconstructed multipart behavior and the release verification matrix.


## Shared v0.5.0 workflow controls

Both Lite and Bootlegger retain their edition-specific icons, palettes, sounds and user settings. Both now provide a compactable left sidebar and top workflow navigation, Repository Desk GitHub/local code editing with explicit confirmation, the separate Jobs & Rebuild verified recovery workflow, and the optional sound-free `headless-strapman` agent CLI. Existing transfer modes and remote Git blob publication are unchanged.


## v0.5.0 shared recovery, rebuild and editor capabilities

Both editions include **Job History → Build / Rebuild**, Repository Desk's remote GitHub text editor and local code-validation workbench, a compact responsive sidebar, and top workflow navigation. All use the same underlying Git blob chunk/manifest integrity engine; the edition-specific palettes, voices, and data directories remain separate. Both detect hard-exit checkpoints at startup without restarting uploads automatically. The separate sound-free `headless/` edition uses either edition's state when explicitly selected. See [Crash Recovery](CRASH_RECOVERY.md) and [Headless](HEADLESS.md).

## New GitHub write announcements

Two new owner-supplied clips extend Bootlegger from 14 to **16** named MP3 notifications: `readme_updated.mp3` after a successful GitHub README commit, and `codebase_updated.mp3` after a successfully committed non-README source file in Repository Code Workbench. Each clip exists, byte-exact, in both `assets/sounds/` and `bootlegger/assets/sounds/`. Lite uses its original OS tone instead; Headless remains silent. Neither a failed GitHub write nor a local-only edit should announce that GitHub was updated.
