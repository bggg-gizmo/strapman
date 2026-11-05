# Future research only — bandwidth and compute controls

**Status:** Not implemented. Owner requested a later, researched update analogous to user-assigned resource budgets in peer-to-peer clients. Do not implement until reviewed and specifically authorized.

Research before design:

1. Measure real upload throughput separately from GitHub rate limits, local disk reads/writes, SHA-256 hashing, network transport and sequential Git commit latency. Establish reproducible metrics on a disposable repo with varied source sizes and connection conditions.
2. Identify current GitHub REST primary and secondary rate limits, acceptable concurrency, commit contention and abuse protections from current official documentation; do not assume more workers always improves throughput.
3. Design configurable caps on worker threads, bandwidth (bytes/second), CPU effort, memory use and optional time windows, preserving minimum safe resources for independent applications. Consider portable platform APIs and explicit defaults.
4. Determine whether shaping can be applied to upload and download streams separately, including retries, pauses, and backoff without corrupting checkpoints or weakening SHA-256 checks.
5. Create a rigorous security and integrity review. Limits must not bypass remote verification, cause stale commits or introduce deletions, force pushes or paid Actions.
6. Prototype behind a disabled experimental option on disposable fixtures; measure effects before a release choice. Document performance and battery impact on Windows and Linux.

This document is a research plan, not a claim that rate-limit or resource-control analysis is complete.
