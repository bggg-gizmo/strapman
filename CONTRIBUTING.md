# Contributing to Strapman

Thank you for helping make Strapman Lite, Bootlegger Pro, and Headless Strapman better. Bug reports, ideas, testing evidence, documentation and code improvements are welcome.

**Using Codex, ChatGPT or another coding agent?** Read the root [AGENTS.md](AGENTS.md) for the repository architecture, testing workflow, safety invariants, and agent-specific permission boundaries.

- [Open an issue](https://github.com/bggg-gizmo/strapman/issues) for reproducible defects.
- [Start a discussion](https://github.com/bggg-gizmo/strapman/discussions) to propose features or new provider integrations.
- [Open a pull request](https://github.com/bggg-gizmo/strapman/pulls) with reviewed, tested changes.
- [Use the public testing checklist](docs/PUBLIC_TESTING_CHECKLIST.md) for end-to-end test scenarios and expected evidence.

## Licensing and the attribution chain

This project uses the **GNU General Public License version 3 or later** and its [NOTICE](NOTICE) attribution provisions. Please review [LICENSE](LICENSE), [NOTICE](NOTICE), and [ATTRIBUTION.md](ATTRIBUTION.md) before creating or distributing a modified version.

When contributing or distributing a fork:

1. **Preserve the existing chain of credits** and the original project attribution to Background Gremlin Group. Do not erase genuine prior entries.
2. **Add your name or handle** and the date and summary of your modifications to [ATTRIBUTION.md](ATTRIBUTION.md), or maintain an equivalent prominent, accessible attribution/change record alongside your fork.
3. Mark modified project files or describe modified areas clearly, so users can distinguish upstream material from your changes.
4. Ensure you have the authority to license your contribution under the project's terms. Do not submit third-party material without the rights needed for redistribution.
5. If AI tools assisted your contribution, you may credit the tool transparently, but **do not misstate AI assistance as independent human copyright ownership**.
6. Do not paste personal credentials, secrets, private repository information or unredacted machine logs into public pull requests.

## Engineering expectations

- Preserve working features across all three editions. Do not silently break upload, reconstruction, source preservation, authentication, or resume behavior.
- Use disposable repositories and generated fixtures for GitHub transfer tests. Never use another person's live backup or private data.
- Run applicable local tests: `python -m pytest -q`, `python tools/public_audit.py`, and `python tools/verify_audio_assets.py` from a complete checkout with the needed dependencies.
- Report what you actually verified, including failures, rather than asserting that untested Windows/Linux, audio hardware, network interruption, or third-party provider operations succeeded.
- Avoid GitHub Actions or paid runners; Strapman's workflows are designed for local execution.
- Do not enable unimplemented Gitea, Forgejo, or other providers without meeting the provider contract and end-to-end verification required by the roadmap.

A pull request should describe the change, reasons, relevant tests, expected compatibility impact, and any additions to the attribution chain. Maintainers may request updates before merging.

**Background Gremlin Group — Creating Unique Tools for Unique Individuals.**
