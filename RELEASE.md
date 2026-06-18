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

### [0.4.0] - 2026-06-18
#### Added / Fixed
- **[BR-TL-3 MEDIUM]** Grupo UB per-line emission: `_imposto_seletivo_block` emits `<IS>`
  (UB01–UB11); `_ibs_cbs_block` emits `<IBSCBS>` (`<gIBSUF>`, `<gIBSMun>`, `<gCBS>`,
  UB12–UB67); partial-population guard raises `DocumentGenerationError("BR-TL-3: …")`.
  `_icms_tot_block` extended to emit `<vISTot>` (W33) and `<IBSCBSTot>` (W34–W56b).
- **[BR-SH-3 MEDIUM]** `tests/test_standards/test_nfe_generator_escape.py`:
  parametrised XML-escape parity tests for `xNome`, `xLgr`, `xMun`, `xProd`,
  `natOp`, `xPag`.
- **[BR-SC-3 LOW]** `BRInvoice.chave_acesso`: `min_length=44` and PL_010d
  `@field_validator`; regex `^[0-9]{6}[0-9A-Z]{14}[0-9]{24}$`.
- **[BR-LC-2 LOW]** Replaced `SEFAZ_ENV` with `BR_READ_ONLY` in `server.json`;
  `README.md` env-var table updated; drift-detection test added.
- **[BR-SC-4 LOW]** Dropped hardcoded `pFCP`/`vFCP` zeros from ICMS00 branch
  (`minOccurs="0"` in XSD; omission matches "FCP not modeled" docstring).
- Audit gate: PASS (0 blocking / 0 warnings); 181 tests pass.

### [0.3.2] - 2026-06-18
#### Fixed
- **[BR-SC-1 BLOCKING]** Aligned `__version__` (was `"0.2.0"`) with `pyproject.toml`
  and `server.json`; added `tests/test_metadata.py` version-slot and `server.json`
  consistency regression tests.
- **[BR-TL-1 HIGH]** Removed emitente-CNPJ fallback in `_pag_block`; added
  `_TPAG_REQUIRES_CNPJ` frozenset; raises `DocumentGenerationError("BR-TL-1: …")`
  when `cnpj_pag` absent for electronic payment methods; `<CNPJPag>` and `<UFPag>`
  emitted only when set.
- **[BR-LC-1 HIGH]** Completed `_CUF_AUTORIZADOR` (all 27 UFs) and
  `_SEFAZ_ENDPOINTS` (added SP, MG, PR, MS, MT, GO, BA, CE, PE, AM, SVAN).
- **[BR-SC-2 MEDIUM]** Rewrote `NFeGenerator` module docstring IBS/CBS block to
  reflect that Grupo UB/W03 fields are modeled but not yet emitted.
- Audit gate: PASS (0 blocking / 0 warnings); 155 tests pass.

### [0.3.1] - 2026-06-15
#### Added
- `mcp_nfe_br.standards.sefaz_client.SefazClient`: SOAP 1.2 envelope builders,
  namespace-agnostic response parser, and UF to endpoint routing table, posting via
  `BaseEInvoicingClient(auth_mode=AuthMode.MTLS)`.
- New tools: `br__consult_sefaz_status` (`NFeStatusServico4`, read-only),
  `br__submit_nfe` (`NFeAutorizacao4`, returns `protNFe`),
  `br__distribute_dfe` (`NFeDistribuicaoDFe`, per NT2014.002_v1.30). The latter two
  gated with `assert_not_read_only` and `ConfirmationGate`.
- UF to endpoint routing populated for Ambiente Nacional (distribuição) and SVRS/cUF=43;
  other UFs raise `ValueError` with `endpoint_override` escape hatch.
- Unit tests cover envelope shapes, endpoint routing, response parsing, and
  mocked-mTLS-transport round trips.
- Audit gate: PASS (0 blocking / 0 warnings).

### [0.3.0] - 2026-06-15
#### Added
- `br__sign_nfe` tool (`mcp_nfe_br.standards.nfe_signer`) wrapping
  `mcp_einvoicing_core.XMLDSigSigner` for enveloped XML-DSig over `infNFe`
  (RSA-SHA1/SHA-1, per MOC 7.0 Table 4-2). ICP-Brasil A1 (PKCS#12) only;
  A3/HSM not modeled.
- `NFeXSDValidator`/`br__validate_nfe_xml` now auto-selects between the unsigned
  derivative schema and the unmodified official `nfe_v4.00.xsd` based on presence
  of `ds:Signature`.
- CPF/CNPJ validators re-pointed at `mcp_einvoicing_core.models.TaxIdentifier`.
- Extended ICMS/PIS/COFINS/IPI generator tax-code coverage.
- IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) fields modeled in
  `BRInvoiceLine`.
- Core dependency pin raised to `>=1.5.1,<2.0.0`.
- Audit gate: PASS (0 blocking / 0 warnings).

### [0.2.0] - 2026-06-13
- NF-e/NFC-e (modelo 55/65, schema 4.00) **generation and XSD validation**
  (Phase 1 of the roadmap): unsigned `<NFe><infNFe>…</infNFe></NFe>` document
  generation (`br__generate_nfe`), validation against the bundled PL_010d XSD
  set (`br__validate_nfe_xml`), and 44-character `chNFe` access-key assembly
  with mod-11 check digit (`br__build_access_key`).
- Covers ICMS (CST `00` / CSOSN `102`), PIS/COFINS (CST `01`/`02`/`04`-`09`),
  and IPI (CST `00`/`49`/`50`/`99` or NT) tax groups; other codes raise a
  `DocumentGenerationError` with a Portuguese message — see
  `context-library/countries/br.md` for the full coverage table.
- ICP-Brasil XML-DSig signing and SEFAZ webservice submission are **not**
  implemented — generated documents are unsigned and must be signed and
  transmitted by a separate process. Both tools surface this in their
  responses.
- XSD validation uses a locally derived "unsigned" variant of the official
  `nfe_v4.00.xsd`/`leiauteNFe_v4.00.xsd` (PL_010d), with `<ds:Signature>`
  changed from mandatory to optional — `[Inference]`, see
  `src/mcp_nfe_br/validators/nfe_xsd.py` docstring. Signed documents (a later
  phase) should validate against the unmodified official schema.

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
