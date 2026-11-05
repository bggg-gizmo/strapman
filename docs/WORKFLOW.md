# Strapman v0.5.2 — Automated Transfer and Reconstruction Workflow

This document describes the updated behavior of Strapman Lite, Bootlegger Pro, and Headless Strapman. It is not a claim that a live Windows/Linux or GitHub end-to-end test has passed.

## Default workflow

1. Select the GitHub account, repository, branch, and original local file.
2. Select an upload transport: chunked binary/archive or cumulative staging for supported small source files. These are transport choices, not different reconstruction requirements.
3. Strapman hashes the original and splits it into verified chunks, keeping durable local checkpoints and all source bytes.
4. It uploads immutable Git blob objects with a bounded worker pool; branch commits are serialized without force-push.
5. It verifies the committed chunk paths, data and final manifest against the selected branch. An orphan blob alone is not publication.
6. **Automatically, by default:** It downloads the published parts, checks their Git object IDs and per-part SHA-256, rebuilds the original into a new local output, and validates its full SHA-256. The output is never used to overwrite the original or another existing file.
7. Only after the requested remote publication and local reconstruction are verified does the application report the complete end-to-end workflow.

The automatic rebuilt file is kept inside the local Strapman job cache and its location appears in the Upload Station, with an **Open Rebuilt Output Folder** control. To restore into a separate user-selected path later, the independent Build/Rebuild utility remains available under Jobs & Rebuild.

**Important GitHub limitation:** GitHub does not allow an oversized single ordinary-Git file (>100 MiB). Strapman reconstructs large uploaded files locally from committed repository chunks; it does not claim to assemble a >100-MiB original *inside the GitHub repository*, provide a hosted builder, or run paid GitHub Actions.

## Recovery and honest job status

- The published remote manifest and final commit are stored separately from local reconstruction state.
- If the remote data is verified but reconstruction fails, the parent job reports `rebuild_failed`, **not** `complete`; the remote publication remains intact. For a cooperative pause, it reports `rebuild_paused`.
- Resume verifies remote publication and local data again and reuses existing committed chunks; it does not create a duplicate commit merely to rerun reconstruction.
- A hard exit or power loss preserves the last atomic checkpoint; an interrupted job requires explicit Resume on restart. No automatic background write happens merely because the app opens.
- Users may explicitly opt out of automatic reconstruction for an upload. The UI defaults it on for both new and migrated installations; an explicit later opt-out persists. Headless uses automatic reconstruction by default, accepts `--no-reconstruct`, and returns a nonzero exit code when reconstruction is incomplete.
- Never delete an original, delete a lock file to force progress, force-push, or treat an unfinished scratch file as a reconstructed original.

## Navigation and layout

The **sidebar** remains the persistent page navigation (Upload Station, Repository Desk, Jobs & Rebuild, Settings & Help); its existing page entries have not been redesigned. The top **contextual workflow strip** contains actions to jump to sections **within the currently selected page**, not duplicate links to other pages. It never implicitly uploads or commits.

The Bootlegger brand header puts the icon **above** the complete BOOTLEGGER wordmark, with the lettering sized to fit in the sidebar. Lite follows the same structure. The compact/expand sidebar feature remains available.

## Testing contract

Automated tests check successful build, byte-for-byte reconstruction, failed build without false success, resuming a previously upload-only checkpoint without re-committing, and pausing after publication before rebuilding. Actual speaker output, full desktop layout and live GitHub uploads remain separate operator acceptance tests. Keep all previous transfer, authentication, editor, security, and manual restore features intact.
