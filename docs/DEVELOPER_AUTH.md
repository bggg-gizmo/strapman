# Developer / Codex — public GitHub OAuth configuration

Strapman Lite and Bootlegger Pro share one verified REST/authentication engine. These steps are the **publisher setup gate** for public one-time-code sign-in. Users of a completed build need **neither Git nor GitHub CLI**. Git Credential Manager reuse is a separate optional convenience.

## Publisher registration (performed once, no user-machine details)

1. In the publisher's GitHub account, open **Settings → Developer settings → OAuth Apps → New OAuth App**. Register **Strapman** (the public consent name shown to all users), with the public project homepage and a valid callback URL. The device code flow does not use the callback. GitHub requires a configured OAuth App for this approach.
2. Enable **Device Flow**. A native app using this method sends `client_id` to `https://github.com/login/device/code`, presents `user_code` to the user at `https://github.com/login/device`, and polls until approval. Strapman already implements those calls with timeout, cancellation and interval handling.
3. **Disable expiring user access tokens for the first public build** unless access-token refresh support is implemented and tested before publication. Otherwise a working installation may lose authorization hours after login. GitHub currently exposes an expiration toggle during OAuth App registration; document the decision. Prefer limited permissions when possible; the current OAuth App asks for `repo read:org` for private-repo upload support.
4. Copy the App's **public client ID**, *not the client secret*. Create `strapman/oauth_app.json` containing a JSON object with exactly one key, `client_id`, and the real ID value. This is a public configuration file distributed in both editions. Never commit app client secrets, access tokens, local username, Git credentials, or machine-specific data. Strapman refuses any additional keys in this file.
5. Alternatively for development, supply `STRAPMAN_OAUTH_CLIENT_ID` as an environment variable or enter the public ID in **Settings → GitHub Accounts**. The installed publisher ID is used automatically when Settings has no override.
6. Test the device-code UI against two separate ordinary GitHub accounts using an isolated disposable test repository. Verify that `/user` returns the approved identity, repo dropdowns are limited to the approved account, and switching clears prior selections. Test the **same** flow on Windows and Linux with both `git` and `gh` absent from PATH. Do not put credentials or authorization codes in logs or screenshots used in the public repo.
7. Test **Use Existing GitHub Login** on a system with Git Credential Manager already authorized and **no GitHub CLI**, then test first-run confirmation, wrong-account switching, no cached credential, helper timeout, and invalid credential. Running `git credential fill` is noninteractive, does not alter Git settings, and is validated via `/user` before loading repositories. It cannot reuse the separate ChatGPT GitHub connector; those credentials are not exported into Strapman.
8. Keep the remaining public release gates in `docs/RELEASE_READINESS.md` open until verified: native GUI, audio, upload/restore, account switching, privacy scan including **Git history**, and executable packaging. Do not run paid GitHub Actions or publish private user data.

## How the public client ID is selected

1. Local Settings `oauth_client_id` override, when nonempty.
2. The publisher's `STRAPMAN_OAUTH_CLIENT_ID` environment variable (mainly development).
3. Distributed `strapman/oauth_app.json`, containing only `client_id`.

The ID is public. **No client secret is required by GitHub's device authorization flow.** If no public client ID is available yet, Strapman explains the configuration gate rather than silently requiring GitHub CLI. CLI installation is an **opt-in** alternative.

## Credential behavior

- GitHub OAuth device-code token: stored only in an OS keyring when available and requested; otherwise session-only. No plaintext Strapman token file is created.
- Git Credential Manager: `git credential fill` is queried with interactive prompts disabled (`GCM_INTERACTIVE=Never` and terminal/askpass disabled). Tokens stay in process memory, are never logged, and only get used after `/user` validation. **Disconnect Strapman** does not revoke Git credentials used by other apps.
- GitHub CLI: optional, and only installed if a user chooses it. Its storage and login lifecycle remain owned by the CLI.
- Account identity may not be inferred from a local Git username or remote URL; the verified GitHub `/user` response is authoritative.

GitHub documentation: [Register an OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app), [OAuth device flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [Git credential protocol](https://git-scm.com/docs/git-credential).
