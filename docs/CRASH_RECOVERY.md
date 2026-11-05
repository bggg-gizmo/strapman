# Strapman — unexpected exit, power loss and crash recovery

**Supported workflow:** A suddenly terminated Strapman job is **not** declared successful and is **not automatically restarted**. The user or an explicitly authorized headless caller can inspect Job History / status, verify their intended destination, and resume. The original source is never removed.

## Recovery contract

1. **Before hashing begins**, the upload engine records a local preparation checkpoint with source path, size, nanosecond modification time, edition, selected repository, branch, and options. Only local application state contains the source path; it is **not written to GitHub**. If a process dies while hashing or splitting, the original remains intact, and hashing/splitting can be repeated after restart. Changes in source size or modification time relative to the interrupted preparation checkpoint cause a fail-closed refusal rather than silently uploading a different source.
2. Checkpoints are written as temporary JSON files with a flushed, synced file and an atomic replacement. POSIX also syncs the parent directory. A hard shutdown can still defeat the storage hardware's durability guarantees; no software can guarantee recovery from physical disk failure, damaged storage, or lost source data.
3. Chunk staging flushes and syncs each completed part before replacing its old cache entry. A process killed during a part may leave an `.incomplete` temporary file. The next attempt reconstructs and validates the complete local parts and never treats partial scratch data as verified input. Incomplete scratch files can remain on disk; they are **not** silently removed by automatic housekeeping.
4. Upload and restore workers hold separate operating-system process locks. At startup, Strapman probes these locks and marks a checkpoint **Interrupted** only if the corresponding job lock is not owned. This prevents misidentifying a live worker in another window as a crashed one, even when its last log or heartbeat is stale. The lock itself is automatically released by the OS when the process dies.
5. Every completed GitHub chunk publication is confirmed against the selected branch; valid committed data is reconciled back into a local checkpoint after failure, including the case where GitHub accepted a commit immediately before the application died. An HTTP request interrupted mid-flight must **not** be assumed uploaded. Missing or conflicting GitHub paths block resume rather than overwrite another contributor's work.
6. Restore and offline Build/Rebuild use verified cached parts, durable restore checkpoints and a unique local scratch output. A reconstructed output is made visible only after checking every chunk and the complete file SHA-256, and the final publish **refuses overwrites**. A crash before publication leaves the destination absent; any scratch file is not a successful output.
7. Headless jobs have a separate exclusive OS-owned run lock, alongside their observable checkpoint/heartbeat. The OS lock, **not a recent heartbeat or PID number**, determines whether a headless worker is actually active. A stale run record cannot block a legitimate restart, and a delayed heartbeat during sleep does not justify spawning a duplicate process.
8. Running operations are not resumed automatically after a reboot. This is intentional: they might change a remote repository or overwrite user expectations. **Job History → Resume Selected Job**, or an explicit `headless-strapman resume --checkpoint ...`, is the recovery action. Resuming can repeat hashing or downloads but must not duplicate verified published chunks or replace original data.

## Which states are meaningful?

| Local state | Meaning |
| --- | --- |
| Preparing / Uploading / Downloading / Assembling | Saved job phase while a worker is active. If the worker disappears, the next desktop startup marks it Interrupted. |
| Interrupted | No owning worker lock; the last saved work was preserved. Review destination and resume explicitly. |
| Paused | A cooperative pause completed at a checkpoint. Resume when ready. |
| Failed / Cancelled | The last attempt failed or was stopped. Existing data stays intact; inspect before retrying. |
| Complete | Final publication / reconstruction was verified; a separate optional local reconstruction may have its own result. |

## How to test on your system

Use a **disposable GitHub repository and copied test data**, never production originals. Launch a multi-chunk upload, terminate only its dedicated test process using the operating system, then relaunch the app. Check that Job History offers an **Interrupted** checkpoint, the original bytes are unchanged, and the resume process reconciles committed parts. Repeat with Build/Rebuild and verify that no incomplete output is presented as complete. Verify separately that a second app window does **not** mark a live job interrupted or create a duplicate uploader. When emulating an actual hard power-off, do not risk production disks or files.

## Automated evidence and limitations

`tests/test_crash_recovery.py` uses **child Python processes that call `os._exit`** during first-source hashing and local reconstruction. Tests verify surviving checkpoints, non-published partial output, valid explicit resume, unchanged originals, live-process lock checks and headless heartbeat recovery. Existing tests cover remote commit reconciliation, cooperative pause, no-overwrite restore, and cross-process upload locks. These are local/mocked network tests, **not** a guarantee against drive failure, network race conditions, or a live Windows shutdown. Windows/Linux GUI and full GitHub integration tests remain release gates.
