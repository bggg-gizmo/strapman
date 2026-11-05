# Headless Strapman — CLI, local progress and safe agent operation

`headless-strapman` is a sound-free, separate command surface over the **same verified Strapman engine** used by Lite and Bootlegger. It does not require an external IDE, does not alter the Git transport, and does not automatically perform uploads when launched. Commands return JSON; progress remains available from local durable checkpoints.

## Install and launch

From the **complete private development repository** (containing `headless/`, `strapman/`, and `install.py`):

- Windows: `headless\headless-strapman.cmd status`
- Linux: `./headless/headless-strapman.sh status`
- Existing Python environment: `python -m strapman.headless --edition lite status`

Headless upload and remote restore commands use existing Strapman credentials or explicitly configured credentials for the selected edition. Offline Build/Rebuild, local status, syntax inspection and diffs do not require GitHub credentials or a live network. The headless wrappers avoid forcing Qt/audio installation for nonvisual commands.

## Command reference

```text
python -m strapman.headless --edition lite status
python -m strapman.headless --edition bootlegger dashboard --port 8766
python -m strapman.headless --edition lite upload --source demo.bin --repo example/disposable --branch main --chunk-mib 4 --workers 4
python -m strapman.headless --edition lite verify --checkpoint saved-checkpoint-id
python -m strapman.headless --edition lite pause
python -m strapman.headless --edition lite resume --checkpoint saved-checkpoint-id
python -m strapman.headless --edition lite rebuild-github --repo example/disposable --branch main --manifest strapman-uploads/saved-id/manifest.json --destination rebuilt.bin
python -m strapman.headless --edition lite rebuild-local --manifest cache/manifest.json --cache-dir cache --destination restored.bin
python -m strapman.headless --edition lite snapshot --output job-status.html
python -m strapman.headless --edition lite snapshot --output job-status.png
python -m strapman.headless --edition lite code-check --file source.py
python -m strapman.headless --edition lite code-diff --original before.py --edited after.py
```

The `example/disposable` and `saved-checkpoint-id` entries are documentation examples; use your actual selected disposable repository and returned local checkpoint IDs when testing. `rebuild-github` requires a committed Strapman manifest, verifies GitHub branch attachment and every part, then reconstructs into an output that **must not already exist**. `rebuild-local` verifies portable local chunks and never contacts GitHub.

## Human progress without a GUI dependency

`dashboard` starts a loopback-only, token-protected local status page. It can display actual checkpoint state and locally recorded progress. Its pause/resume actions are explicitly requested, never automatic. `snapshot --output ...html` saves a static report; `snapshot --output ...png` requires the optional installed Qt desktop stack and is not a promise of headless graphics without those dependencies. Terminal use needs no audio, Qt multimedia or packaged images. A dashboard or snapshot displays **observed** values; it is not evidence that an incomplete remote manifest is recoverable until the remote audit verifies it.

## Agent safety

- An agent must receive explicit authorization for each upload/destination change or remote edit. Neither a model nor the status endpoint can assume ownership of the user's repositories.
- The headless run lock prevents two agents from simultaneously controlling the same local runtime. A process crash releases that lock; a stale heartbeat cannot create phantom active jobs.
- `pause` waits cooperatively for the engine's next safe stop. An actual shutdown may interrupt a network request; the next explicit `resume` rechecks GitHub, rather than trusting a log line.
- No source-file deletion, force-push, GitHub Actions, hidden background schedules or automatic post-reboot publication is performed.
- Remote GitHub credentials and local checkpoint data stay inside the chosen user's edition state. Browser dashboard tokens are for the local interface only; do not paste them into reports or public logs.

For exceptional termination/reboot behavior, see [Crash recovery](CRASH_RECOVERY.md). For verified part reconstruction and the workflow contract, see [Functional coverage](FUNCTIONAL_COVERAGE.md).

### No-repeat bootstrap launcher

The Windows and Linux headless wrappers use the standard-library `headless/launch.py` selector. It prefers a healthy reusable Strapman Python runtime or compatible older extracted environment before the system interpreter. It checks only for the minimal `requests` dependency and never invokes pip or installs Qt/MP3 packages. If none exists, it shows a direct error rather than silently downloading a desktop runtime.


## v0.5.2 — Automatic reconstruction is the default

Headless `upload` now carries out the complete remote publication → committed-part verification → local Build/Rebuild → SHA-256 check unless the user **explicitly** supplies `--no-reconstruct`. Existing `--reconstruct` remains accepted. On a published-but-not-reconstructed run the command returns JSON `state: needs_rebuild` and exits with code **5**, rather than claiming success (`0`). The remote publication and checkpoints remain intact; explicit `resume` can complete the reconstruction without new GitHub commits. Pause still has exit code **3**. The headless CLI remains sound-free and does not require Qt for basic commands.
