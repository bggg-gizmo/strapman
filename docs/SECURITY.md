# Security and privacy expectations

Strapman's source repository is intended to be publishable. It must not contain private backup archives, local inventory dumps, API tokens, system usernames, home directories, addresses, network interface details, device identifiers, credentials, or user-specific logs. Environment-specific state is written to OS app-data directories. `.gitignore` excludes local virtual environments, build outputs, secrets, logs, and uncommitted caches.

Authentication supports native GitHub OAuth device code with a public publisher client ID (no Git/gh required), transient personal access tokens, existing non-interactive Git credential helpers, the operating-system credential manager, or optional local GitHub CLI. The application does not create paid GitHub Actions jobs. Permission checks are enforced by GitHub; a token should have only the access needed for its target repositories.

All private-to-public transitions should be intentional, with a separate audit of **all existing commits and Git refs**. Filenames, source strings, `.env` files, images and image metadata can contain sensitive data. Strapman does not claim to automatically sanitize arbitrary source trees or prior Git history.

Untrusted remote manifests are validated for format, chunk order, lengths, and digests. Restore uses a controlled chunk cache, verifies full-file integrity, and refuses to overwrite existing output. Original input files are not removed. Remote writes use no force push. README changes explicitly require user confirmation and a current GitHub content SHA.

When reporting a vulnerability, avoid disclosing access tokens or private repository contents. Use a private channel to the maintainers instead of filing a public issue containing secrets.

## Account authorization and isolation

Native GitHub device-code OAuth uses a public OAuth App client ID and never requires Git, GitHub CLI, or a client secret. The optional publisher configuration `strapman/oauth_app.json` must contain **only** the public `client_id`. The app owner must enable Device Flow in GitHub settings. The one-time code is displayed locally and submitted only at GitHub's official verification page. When an account changes, Strapman discards the previous repository, branch and README editing selection before loading the new account's repository list. Uploads require an active, verified client.

Git credential reuse invokes `git credential fill` with interactive prompting disabled and never logs or stores returned credentials; GitHub `/user` validation is required before repository access, and first-use account identity is confirmed. Disconnecting does not erase credential-helper state. The installed helper itself determines whether credentials are securely stored; Git's plaintext `store` helper is not equivalent to an OS keyring.

CLI authentication is managed by the official GitHub CLI, with optional user-local installation from a SHA-256-verified release asset. The app checks available storage before downloading. CLI's own credential-storage policy applies; an unavailable OS keyring may result in local plaintext CLI token storage, unlike Strapman's direct keyring-backed login. No OAuth client secret or access token is committed.

## Branch-attached verification and restore safety

Strapman v0.3.0 audits branch-attached chunk Git objects rather than counting orphan uploads as remotely published. An independent read-only audit downloads committed parts and verifies each SHA-256. Missing or changed published paths fail closed during resume. The completed manifest is checked against the verified parts before reporting success. The job-history audit is a snapshot, not an immutable remote guarantee against later collaborator changes.

Local restore publication does not overwrite an existing file, even if it appears while another process is reconstructing. The platform must support the chosen atomic non-overwriting publication primitive; an unsupported filesystem causes a safe failure.


## Public-release source gate (v0.3.1)

`python tools/public_audit.py` checks the current source snapshot for token patterns,
private-key headers, device-specific home paths, suspicious files and accidental
GitHub Actions workflows. `python tools/public_audit.py --history` additionally
checks every reachable Git object and author/committer emails in a complete Git
checkout. The scan is read-only and intentionally errs on the side of flagging
suspicious matches for review. It cannot prove the absence of all personal data.

Strapman includes application icon assets created from its existing public vector
identity and does not embed local device paths in those images. Uploaded file
contents remain the sender's responsibility: Strapman does not sanitize source
material or media metadata before transmission.

Remote Git blob publication now validates GitHub's returned Git SHA-1 object ID
against the bytes submitted before attaching that object to a branch. The
read-only verification action can audit a published full source file after the
local staging cache has been removed.

An optional post-upload local reconstruction failure is recorded separately and
shown as a warning; it no longer changes a completed, verified GitHub upload
into an inaccurately failed upload. Originals are never deleted.
