# Bootlegger README and codebase audio bootstrap

The current software event map supports two owner-provided recordings: codebase_updated.mp3 (110,385 bytes) and readme_updated.mp3 (89,069 bytes). They are intended for the source sounds directory and the Bootlegger Pro sounds directory. The application and audit code will expect 16 events, 32 MP3 copies total.

**Code and catalog changes do not mean the audio bytes are already committed to GitHub.** The separate source package contains the original recordings, checksum-verified chunk files and a safe bootstrap publisher.

To publish, extract the file named Strapman-Bootlegger-Voice-2-clip-GitHub-Bootstrap.zip to a new folder on the authenticated machine. In that folder, use:

    py -3 publish_voice_assets.py
    py -3 publish_voice_assets.py --publish

On Linux, substitute python3. The first command verifies all originals and chunks locally and does not write to GitHub. The second checks that bggg-gizmo/strapman-dev and bggg-gizmo/strapman are PRIVATE and writable; creates the five Git chunk objects; attaches the parts in both directory trees with a non-force commit; downloads every committed part back from GitHub and checks its Git blob hash plus SHA-256; reconstructs the full two files locally; and creates the final full Git blob objects in GitHub, committing each to both sound folders. The script checks all four final branch file paths.

GitHub does not concatenate chunks by itself. The local bootstrapper uses the remotely verified chunks to reconstruct, then publishes the completed files inside GitHub without a hosted runner or GitHub Actions.

Original MP3 SHA-256:
- codebase_updated.mp3: 9bcc3101de57b113aa88e359ec8a748ace381de6a27463e9b22c103b32af6cf2
- readme_updated.mp3: 83ddaf10f1eb087bf433bd2b10dc3917423fb5d71360bba888aab16b5586e11e

No existing asset is overwritten if its hash differs. Source originals are not deleted. The uploader can be safely resumed and skips already matching committed parts. Local Git Credential Manager login, an existing GitHub CLI login or GH_TOKEN/GITHUB_TOKEN are accepted; no login, CLI installation or new Python dependencies are forced.

After publishing, download a complete updated repository checkout and run:

    python tools/verify_audio_assets.py

The required result is 32/32 MP3 copies verified for 16 mapped events. Windows speaker playback remains a separate acceptance check.

The new recording cues play only after successful SHA-confirmed GitHub commits: README commits use the README clip and other remote workbench file commits use the codebase clip. Lite continues to use OS sounds; Headless remains silent. Keep both repositories private until the user authorizes public release. No WatchMan changes.
