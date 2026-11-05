# Strapman Development Roadmap

**Owner direction:** Maintain complete GitHub functionality in Strapman Lite, Bootlegger Pro and Headless Strapman; support other Git hosts without removing current workflows. The separate owner-designated release/testing repository is bggg-gizmo/strapman and must remain private until explicitly approved for public visibility.

**Specification:** SPECS.md is the product/technical acceptance contract.
**Baseline:** v0.5.1-dev; GitHub-only storage transport; 110 local Python tests passing at the last recorded review. Real device and network acceptance remain open.

## Current — Stabilization and controlled public-source testing

- [x] Shared verified Git-blob upload engine, resumable checkpoints, SHA-256 audit and no-overwrite Build/Rebuild.
- [x] Desktop Lite and Bootlegger with theme selection, unique branding, and 16 voice MP3 events (Lite: standard OS audio).
- [x] Sound-free headless CLI with status, dashboard, snapshot, explicit pause/resume, upload, remote/local rebuild and code checks.
- [x] Repository Desk GitHub README editing and remote/local text workbench with explicit code validation and local testing.
- [x] Atomic checkpoints, hard-exit interruption detection and explicit user-authorized resume.
- [x] Dev-source privacy and audio-inventory tooling; 110-test regression baseline.
- [ ] Native Windows and Linux GUI acceptance for all screens, exact MP3 voice output and power reminders.
- [ ] Test 1+ GiB disposable GitHub upload including interrupt, restart, verification and byte-exact reconstruction.
- [ ] Register actual publisher GitHub OAuth App; ship its PUBLIC client ID only; exercise device-code flow without Git/gh.
- [ ] Audit entire Git history and source/media metadata, dependencies and public licensing policy.
- [ ] Publish a clean source snapshot and controlled testing instructions to private bggg-gizmo/strapman; do NOT transfer private development history or toggle visibility.
- [ ] Resolve all critical findings from actual public-testing reports before any public visibility change.

## Next — Provider-independent foundation (P1, development only)

**Goal:** Let users choose GitHub, Gitea, Forgejo or future Git services without weakening byte-level reconstruction or repository safety. Gitea/Forgejo are NOT currently supported merely because they are listed here.

- [ ] Introduce a provider interface for identity, selected host, repositories, branches, directory listing, content retrieval, upload staging, commit publication, manifest inventory, file edit and optional settings.
- [ ] Keep one shared engine and one provider-neutral file manifest; use explicit provider/host identity in checkpoint keys so a target on one server cannot be silently resumed on another.
- [ ] Add provider capability discovery: blob creation, readback, tree enumeration, branch update, bulk commit, contents create/update, version/size limits, auth modes and security endpoints.
- [ ] Specify portable transport fallback when Git Data API writes are unavailable: safe provider Contents API commits or explicit local Git transport without force pushing. Do not assume identical API operations on all hosts.
- [ ] Add mutually exclusive account/host selector, tested self-hosted URL validation, secure token storage and clear error reporting.
- [ ] Create deterministic provider contract tests and common mocked failure fixtures for competing writers, replay, malformed responses, permission denial, retry/rate-limit and data corruption.
- [ ] Keep GitHub adapter parity and full existing tests before enabling any new provider.

### Gitea (P1: first third-party integration)

Research confirms Gitea supports repository Contents API and Git object read APIs under /api/v1, but this does not by itself prove the GitHub Git Data *write* pipeline is interchangeable. Gitea's published OAuth provider describes authorization-code grant with PKCE, not GitHub's device-code grant; avoid assuming device codes exist on arbitrary Gitea instances.

- [ ] Choose a supported self-hosted disposable Gitea server/version and an optional public Gitea service for tests.
- [ ] Authenticate using a per-instance token first, then investigate OAuth authorization code + PKCE. Never send a token to a different hostname.
- [ ] Implement repo/branch discovery, README and text-file edits with SHA conflict protection.
- [ ] Implement portable chunk publication using tested Gitea write operations; verify all committed parts and full SHA-256 before marking complete.
- [ ] Verify pause/reboot resume, offline and remote Build/Rebuild, occupied branch/file conflict, 1+ GiB chunks, self-hosted rate limits and server outages.
- [ ] Document exact supported Gitea versions and optional/unsupported GitHub-only security settings.

### Forgejo (P1: after Gitea adapter)

Forgejo publishes its own instance-specific Swagger API under /api/v1 and supports token-based authentication. Do NOT automatically equate Forgejo versions and quirks with Gitea, although much implementation may be reused.

- [ ] Exercise same provider contract against a disposable Forgejo server with its own compatibility matrix.
- [ ] Reuse provider-neutral chunk/manifest/rebuild logic where verified; add separate version and permission checks where needed.
- [ ] Test credentials, account switching, repository creation, audit, resume and remote file editing on Forgejo; verify all public claims with actual live testing.

**Research references (checked November 2026):**
- Gitea API blob read: https://docs.gitea.com/api/operations/get-blob/
- Gitea OAuth2 provider and PKCE: https://docs.gitea.com/development/oauth2-provider/
- Forgejo API usage: https://forgejo.codeberg.page/docs/v17.0/user/api/usage/
- GitHub Git tree publication: https://docs.github.com/en/rest/git/trees

## After provider parity — Additional hosts (P2)

- [ ] Evaluate GitLab support via a separate adapter (REST differences, project/group namespace and token scopes).
- [ ] Consider Codeberg, enterprise/self-hosted variants and generic Git remotes only with verified non-force publication and reliable content-addressed rebuild semantics.
- [ ] Add user-facing provider selection and import/export of *configuration* without copying stored credentials or altering host identity.
- [ ] Publish a capability table based on tests, not branding or API endpoint resemblance.

## Separate research-only future milestone — User-assigned bandwidth and compute

**NOT implemented and NOT authorized for implementation in this phase.** See docs/RESOURCE_CONTROLS_RESEARCH_ROADMAP.md.

Research before design:
- Chunk size and worker concurrency versus Git server API quotas, branch commit serialization, rate limits and memory pressure.
- Upload/download caps (bytes/s), fair scheduling, pause semantics and server backoff, including whether HTTP client stack permits truthful bandwidth throttling.
- CPU/core utilization during SHA-256 hashing, compression (if any), local verification and reconstruction; protect desktop responsiveness and battery.
- Per-provider limits and error handling; avoid mistaking faster uploads for completed committed/recoverable data.
- A user-adjustable resource budget similar to P2P clients must be opt-in, transparent, persistent, reversible and measured on actual hardware.
- Never start paid runners or hosted workflows to supply extra compute.

## Distribution and UX maturity (P2)

- [ ] Complete Windows/Linux screen-size and accessibility checks, audio preview testing and readable high-DPI GUI states.
- [ ] Versioned release candidates, release notes, platform-specific packaging, source SBOM/licensing, checksums and reproducible local build instructions.
- [ ] Owner must select the Windows EXE type and desired icon before compilation; compilation through a local .cmd, without paid Actions.
- [ ] Improve visible progress across upload, commit verification and file reconstruction; enable explicitly requested agent screenshots using actual local progress.
- [ ] Preserve all original files and existing features. No automatic source reclaim, force push, surprise network writes or silent security-setting changes.

## Acceptance rules for all roadmap items

1. Every implemented checkbox requires tests and a corresponding factual entry in the private AGENT_COORDINATION.md.
2. No new provider ships as 'supported' until an actual disposable-instance end-to-end upload → verify → pause/reboot/resume → reconstruct passes with byte-exact digests.
3. Public-source snapshots must be from reviewed current files, not a mirror of dev history. The public testing repository remains private until owner approval.
4. All editions use the same verified storage format where technically possible; preserve manifest backward compatibility and existing upload/restore semantics.
5. No paid GitHub Actions, paid hosted CI, repository deletion, source reclamation or WatchMan changes.
