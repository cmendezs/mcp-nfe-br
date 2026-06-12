# Release Process

This document describes how to release a new version of `mcp-nfe-br` to PyPI and the official MCP registry.

## One-Time Setup Requirements

### PyPI Trusted Publishing

PyPI publishing is fully automated via OIDC (no token stored). The Trusted Publisher must be configured on PyPI under `cmendezs/mcp-nfe-br`, workflow `publish.yml`, environment `pypi`, before the first tag push. No `.env` or secret needed.

### MCP Publisher CLI

Binary installed at `~/.local/bin/mcp-publisher` (already in `PATH`). To update to a newer version:

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_darwin_arm64.tar.gz" \
  | tar xzf - -C ~/.local/bin/
```

### MCP Registry Authentication

Authenticate once with GitHub (device flow):

```bash
mcp-publisher login github
```

---

## Release Steps

### 1. Bump the version

Edit **both** files — replace `X.X.X` with the new version (e.g. `0.1.0` → `0.1.1`):

- `pyproject.toml` → `version = "X.X.X"`
- `server.json` → `"version": "X.X.X"` and `"version": "X.X.X"` (in `packages[]`)

### 2. Commit, tag and push

GitHub Actions publishes to PyPI automatically on tag push.

```bash
git add pyproject.toml server.json
git commit -m "chore: bump version to X.X.X"
git push origin main
git tag vX.X.X
git push origin vX.X.X
```

### 3. Publish to the MCP registry

```bash
mcp-publisher publish
```

Expected output:
```
✓ Successfully published
✓ Server io.github.cmendezs/mcp-nfe-br version X.X.X
```

---

## Changelog

### [0.1.0] - 2026-06-12
- Initial scaffold: NF-e / NFC-e (modelo 55/65, schema 4.00) party-identifier
  validation tools (`br__validate_cpf`, `br__validate_cnpj`). Phase 1 of the
  Brazilian e-invoicing roadmap (NFS-e and CT-e are later phases — see
  `context-library/countries/br.md`).

---

## Notes

- The MCP registry does **not** sync automatically with PyPI or GitHub — step 3 is required for every release.
- The `server.json` description field must be **≤ 100 characters**.
- PyPI rejects re-uploads of the same version — always bump before tagging.
- GitHub Actions creates the GitHub Release automatically (with release notes) alongside the PyPI publish.
