# mcp-nfe-br — Release Notes

## v0.6.1 (2026-07-03) — CT-e SEFAZ submission/consultation (BR-CTE-10..12)

- **[BR-CTE-10]** Extracted `mcp_nfe_br.standards._sefaz_soap` (private shared SOAP envelope/response-parsing helper: `soap_envelope`, `scrape_fields`, `parse_response_root`); refactored `sefaz_client.py` to use it. All 48 existing NF-e SEFAZ tests pass unchanged, confirming the extraction preserves behavior
- **[BR-CTE-11]** `mcp_nfe_br.standards.sefaz_cte_client.SefazCTeClient` — covers `CTeStatusServicoV4`/`CTeConsultaV4` (plain XML) and `CTeRecepcaoSincV4` (GZip+Base64 payload, a structurally different shape from NF-e, confirmed against MOC CT-e Visão Geral §3.4.1)
  - No CT-e endpoint URLs are bundled or independently verified (the MOC only points to the live dfe-portal.svrs.rs.gov.br listing) — `get_cte_endpoint` always raises; `endpoint_override` is mandatory on every call
- **[BR-CTE-12]** Three new tools (server now exposes 20 tools): `br__submit_cte` (gated), `br__consult_cte_sefaz_status` (read-only), `br__consult_cte` (read-only — queries one already-known chCTe, not a bulk pull, per the CT-e scoping plan's tool table). New `BR_CTE_READ_ONLY` env var, kept distinct from `BR_READ_ONLY`
- `br__distribute_cte_dfe` (CTeDistribuicaoDFe) is **not implemented** — the bundled spec confirms the `distDFeInt` payload shape but not the webservice's method/namespace/wrapper details; deferred as `BR-CTE-13` `[NEED: verify]`
- `br__build_cte_access_key` MCP tool wrapper also deferred (the underlying `build_cte_access_key` util has existed since BR-CTE-5)

## v0.6.0 (2026-07-03) — CT-e (modelo 57) Phase 3, v1 (BR-CTE-1..9)

CT-e (Conhecimento de Transporte Eletrônico) work begins, per explicit user request (previously deferred, see `context-library/roadmap-2026.md`). v1 scope: modal rodoviário only, ICMS CST 00 (tributação normal) only, event tools deferred.

- Spec bundle sourced from https://dfeportal.svrs.rs.gov.br/Cte/Documentos and bundled under `specs/cte/` (MOC CT-e 4.00, `PL_CTe_400.zip`, `PL_CTeDistDFe_100.zip`, 14 Notas Técnicas); XSDs extracted to `src/mcp_nfe_br/schemas/cte/`
- **[BR-CTE-2..4]** `mcp_nfe_br.models.cte`: `BRCTeDocument(InvoiceDocument)` and CT-e party classes (`BRCteEmitente`, `BRCteRemetente`, `BRCteExpedidor`, `BRCteRecebedor`, `BRCteDestinatario`, `BRCteTomador`). Namespace `http://www.portalfiscal.inf.br/cte`, schema 4.00 `[Verified locally]`
  - `buyer` overridden `Optional[InvoiceParty]=None` (no CT-e equivalent — `tomador` is the closest analog); `lines` stays empty (`v_prest.comp` used instead for freight-value components)
- **[BR-CTE-5]** `mcp_nfe_br.utils.cte_access_key.build_cte_access_key` — 44-char `chCTe`, reuses the mod-11 `access_key_check_digit` already shipped for NF-e's `chNFe`
- **[BR-CTE-6]** `mcp_nfe_br.standards.cte_signer.build_cte_signer` — wraps core `XMLDSigSigner` targeting `infCte` (RSA-SHA1, confirmed against MOC CT-e Visão Geral §3.2.4)
- **[BR-CTE-8]** `mcp_nfe_br.standards.cte_generator.CTeGenerator` — modal rodoviário only for v1 (`infModal` is `<xs:any>` in the main schema, so other modais don't break main-document validation, but their payloads are unmodeled)
- **[BR-CTE-9]** `mcp_nfe_br.validators.cte_xsd.CTeXSDValidator` — unsigned/signed auto-select, same pattern as `NFeXSDValidator`; two new tools `br__generate_cte`, `br__validate_cte_xml` (server now exposes 17 tools)
- `context-library/countries/br.md` CT-e section and wire-formats table resolved from `[NEED: verify]` to `[Verified locally]`
- Cancellation success `cStat` code and `infCTeAnu`/`tpCTe=2` mapping remain `[NEED: verify]` — not found in the bundled XSD enum or MOC text search

## v0.5.4 (2026-06-30) — Hardcoded UB12-10 activation dates

- **[BR-INV-2]** Runtime warning in `br__generate_nfe` now states the verified `UB12-10` (Grupo UB IBS/CBS mandatory) activation dates instead of "Implementação futura"
  - Verified directly against NT 2025.002-RTC v1.50 page 41/97 rule text (not the cronograma summary table, which still reads generic "Implementação futura"): homologação from `dhEmi` >= 2026-07-01 (CRT 3=Regime Normal); produção from `dhEmi` >= 2026-08-03 (CRT 3); produção from 2027-01-04 (CRT 1/2/4, Simples Nacional family)
  - Two rule exceptions documented in the warning text: devolução/complementar NF-e referencing a pre-2026 original; items on the monofásico-fuel `cProdANP` table
- **[BR-INV-3]** Re-checked the "ICP-Brasil V10 certificate chain retirement by 2026-12-31" claim against newly bundled `MCT10Vol.IIv.3.0.pdf` and `NT_2026.001_v1.02a - PAA NFe.pdf` — neither confirms it; `specs/nfe/MANIFEST.md` updated, no code change (claim remains `[BLOCKED]` pending a primary ICP-Brasil source)

## v0.5.3 (2026-06-30) — Explicit rounding mode, core re-sync

- **[BR-TL-6]** `_d2`/`_percent` in `nfe_generator.py` and `nfse_generator.py` now pass `ROUND_HALF_UP` explicitly instead of relying on core's default
  - Research finding: `ANEXO I - Leiaute e Regra de Validação - NF-e e NFC-e.pdf` footnote (*4) (not MOC v7.0 itself) requires only 2-decimal rounding with a +/- R$0.01 SEFAZ validation tolerance, no specific rounding mode is mandated
  - `context-library/countries/br.md` markers at lines 145 and 280 cleared with this citation
  - New boundary-case regression tests in `tests/test_standards/test_rounding.py`
- Re-synced to `mcp-einvoicing-core` v1.13.1 (BR-TL-5: `validate_br_cnpj` now rejects an all-equal-character base); lower-bound pin bumped to `>=1.13.1,<2.0.0`
- Fixed `audit/audit_vs_core.py`: missing `SEVERITY_WARNING` import (pre-existing bug, caught by pre-flight lint)

## v0.5.2 (2026-06-19) — NFS-e homologação verification scaffold (Sprint 6)

- **[BR-NFSE-12]** End-to-end ADN homologação verification test scaffold in `tests/test_standards/test_adn_e2e.py`
  - Full lifecycle: generate DPS, sign, submit to ADN, query status, cancel
  - Skipped by default without `BR_CERT_PATH`, `GOVBR_CLIENT_ID`, `GOVBR_CLIENT_SECRET` environment variables
  - `[NEED: manual verification with real ICP-Brasil A1 test certificate and gov.br developer portal credentials]`

## v0.5.1 (2026-06-19) — NFS-e ADN client and gated submission tools (Sprint 5)

- **[BR-NFSE-9]** New `mcp_nfe_br.standards.govbr_auth` module for gov.br federal account OAuth2 authentication
  - `build_govbr_oauth()` returns `OAuthValues` for ADN client
  - Staging and production token URLs; default scope `"openid govbr_empresa"` `[Unverified]`
- **[BR-NFSE-10]** New `mcp_nfe_br.standards.adn_client.ADNClient(BaseEInvoicingClient)` for ADN operations
  - `AuthMode.OAUTH2_CLIENT_CREDENTIALS` with gov.br tokens
  - Single national endpoint; homologação and produção environment split `[Unverified]`
  - Operations: `submit_dps`, `consult_nfse`, `cancel_nfse`
  - Response parsing with `mark_untrusted_fields` (BR-SH-2 parity)
- **[BR-NFSE-11]** Three new MCP tools (server now exposes 15 tools):
  - `br__submit_nfse`: submit signed DPS to ADN, gated with `ConfirmationGate` + `assert_not_read_only`
  - `br__consult_nfse_status`: query NFS-e status by access key (read-only, no gate)
  - `br__cancel_nfse`: request NFS-e cancellation, gated with `ConfirmationGate` + `assert_not_read_only`
- `server.json` `BR_READ_ONLY` description updated to include `br__submit_nfse` and `br__cancel_nfse`
- `caplog` sentinel test verifies gov.br `client_secret` does not appear in log records (BR-SH-1 parity)
- Audit gate: PASS (0 blocking); 203 tests pass

## v0.5.0 (2026-06-19) — NFS-e Nacional (ADN) Phase 2, Sprint 4

- **[BR-NFSE-0 through BR-NFSE-8]** NFS-e Nacional DPS model, generator, XSD validator, signer, and tools
- Audit gate: PASS; 185 tests pass

## v0.4.1 (2026-06-18) — Sprint 3 verification + monitoring

- **[BR-TL-2]** Alphanumeric-CNPJ check-digit algorithm verified against NTCJ DFe 2025.001
- **[BR-TL-4]** Runtime warning for NT 2025.002-RTC UB12-10 activation date
- **[BR-LC-3]** SOAP envelope shapes verified against MOC 7.0
- **[BR-SH-1]** `caplog` sentinel tests for PKCS#12 password non-leakage
- **[BR-SH-2]** SEFAZ response fields wrapped with `mark_untrusted_fields`

## v0.4.0 (2026-06-18) — IBS/CBS readiness plus hardening

- **[BR-TL-3]** Grupo UB per-line emission and Grupo W03 totals in NFeGenerator
- **[BR-SH-3]** XML-escape parity tests
- **[BR-SC-3]** `chave_acesso` PL_010d field validator
- **[BR-LC-2]** `BR_READ_ONLY` env var; drift-detection test
- **[BR-SC-4]** Dropped hardcoded FCP zeros from ICMS00

## v0.3.2 (2026-06-18) — Unblock publish

- **[BR-SC-1 BLOCKING]** Version slot alignment; regression tests
- **[BR-TL-1 HIGH]** Removed emitente-CNPJ fallback in `_pag_block`
- **[BR-LC-1 HIGH]** Complete SEFAZ cUF routing table (all 27 UFs)
- **[BR-SC-2]** Module docstring update for IBS/CBS state

## v0.3.1 (2026-06-15) — SEFAZ webservice integration

- `SefazClient` with SOAP 1.2 over mTLS
- Tools: `br__consult_sefaz_status`, `br__submit_nfe`, `br__distribute_dfe`

## v0.3.0 (2026-06-15) — ICP-Brasil digital signature + signed-schema validation

- `br__sign_nfe` tool with XMLDSigSigner over `infNFe`
- Extended ICMS/PIS/COFINS/IPI tax-code coverage
- IBS/CBS/Imposto Seletivo (Grupo UB/W03) field modeling

## v0.2.0 (2026-06-13) — NF-e/NFC-e generation and XSD validation

- `br__generate_nfe`, `br__validate_nfe_xml`, `br__build_access_key`
- ICMS CST 00/CSOSN 102, PIS/COFINS CST 01/02/04-09, IPI CST 00/49/50/99

## v0.1.0 (2026-06-13) — Initial release

- Project scaffold; `BRInvoice`/`BRInvoiceLine` models
- `br__validate_cpf`, `br__validate_cnpj` tools
