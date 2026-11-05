# Bootlegger Pro

**Background Gremlin Group · Creating Unique Tools for Unique Individuals**

Bootlegger is Strapman's Pro edition. It retains the shared lossless upload/restore engine and adds edition-specific presentation, sounds and settings.

## Launch

Windows: double-click `bootlegger/Bootlegger-Pro.cmd` from a complete checkout.

Linux: run `./bootlegger/Bootlegger-Pro.sh` from the repository root.

The shared installer checks free space and bootstraps dependencies when necessary. Pro maintains separate local settings, sessions, journals and checkpoints under the OS app-data directory's `bootlegger/` subfolder; credentials are still managed through the user's chosen GitHub authentication provider. Lite checkpoints and settings remain intact.

## Appearance

Choose one of three settings in **Settings & Help → Bootlegger color scheme**:

- **Purple Night** (default): dark purple and black, glossy retro-bubble controls.
- **Pink Pearl**: pink and white light mode.
- **Blue Frost**: blue and white light mode.

The selection applies immediately and persists across restarts. Bootlegger includes its custom GitHub-shade leg-lamp [PNG icon](assets/bootlegger-icon.png) for Qt and a seven-resolution [Windows ICO icon](assets/bootlegger-icon.ico) for future Windows packaging. The source launcher uses the PNG; no prebuilt executable is distributed.

## Audio cues

Pro uses the seven existing `.mp3` sound cues under `bootlegger/assets/sounds/` for launch, first-run GitHub setup, completed tasks, errors, exit, power restoration and power disconnection. Settings include a sound toggle and preview selector. Events on systems without an available power sensor do not fire power cues.

MP3 playback depends on the platform's Qt Multimedia codec support; the program falls back to a system beep if an MP3 cannot be played. Sounds are on by default and can be disabled at any time. The shared GitHub transfer engine is unchanged and never uploads these assets on its own.

See [shared USERMAN](../docs/USERMAN.md) and [the editions guide](../docs/EDITIONS.md).


### Shared development update: v0.5.0

Bootlegger retains its original MP3 recordings and three selectable themes. The sidebar now fits the full Bootlegger label and can collapse to tooltipped icons. The top workflow strip, Repository Desk code workbench and Jobs & Rebuild reconstruction are shared with Lite. The sound-free headless CLI remains independent of Bootlegger's voice settings.
