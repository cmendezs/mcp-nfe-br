# mcp-nfe-br — Release Notes

## v0.9.0 (2026-09-10) — Adopt core endpoint routing for SEFAZ (CORE-5)

Step 9 (optional) of the core audit's execution ladder. Country-side only; core unchanged
(`mcp_einvoicing_core.endpoints` has existed since core v1.8.0).

- **[CORE-5]** The 25-entry `_SEFAZ_ENDPOINTS` nested dict (13 autorizadores x NF-e/NFC-e
  services, keyed by tpAmb "1"/"2") replaced with `dict[str, EndpointSet]`, the same
  `mcp_einvoicing_core.endpoints.EndpointSet`/`EndpointEnvironment` abstraction PL, IT, and ES
  now share. Every URL verified identical to the prior table before the swap; `get_endpoint()`'s
  observable behaviour is unchanged.
- 305 tests passing (1 skipped, pre-existing); audit gate 0 blocking.

## v0.8.2 (2026-09-09) — SEFAZ raw-SOAP clients adopt the shared 429/503 retry policy (CORE-3)

Step 6 (country wave 2) of the core audit's execution ladder. Completes CORE-3's own
recommended fix, which named `BaseEInvoicingClient._request`,
the Peppol AS4 client, and BR's raw-SOAP path as the three adopters of a shared HTTP transport
hardening layer.

- **[CORE-3]** `SefazClient` (NF-e) and `SefazCTeClient` (CT-e) already inherited the hardened
  `httpx.AsyncClient` (TLS 1.2 floor, `EINVOICING_CERT_PINS` pinning, `trust_env=False`) via
  `_get_client()`/`_get_httpx_client()` — their raw-SOAP `_post_soap` only ever bypassed
  `BaseEInvoicingClient._request`'s business logic, never client construction. What was missing
  was `_request`'s 429/503 retry loop; both clients' `_post_soap` now retry via the same
  `compute_retry_delay`/`self._max_retries` policy `_request` and (since core v1.33.0)
  `AS4TransportClient` use.
- BE/AE/SG checked for the same gap and need no code change: BE's `tools/lookup.py` already
  uses `BaseEInvoicingClient` directly; AE only mentions `PeppolTransmitter` in a docstring; SG
  has no HTTP client code at all.
- `mcp-einvoicing-core` floor pin bumped to `>=1.33.0,<2.0.0`.
- New tests: `test_post_soap_retries_on_503_then_succeeds`,
  `test_post_soap_gives_up_after_max_retries`, in both `test_sefaz_client.py` and
  `test_sefaz_cte_client.py`. 305 tests passing (1 skipped, pre-existing); audit gate 0
  blocking (15 pre-existing warnings, unrelated).

## v0.8.1 (2026-09-07) — NF-e/NFC-e schema PL_010f_v1.04 (NT 2026.007, regulatory-update)

Closes GitHub issue cmendezs/mcp-nfe-br#6, filed by the regulatory watch. SEFAZ published NF-e/NFC-e
XML schema package `PL_010f_v1.04` on 2026-08-31, bundling NT 2026.007 v1.00 and NT 2025.002 v1.50
on top of `PL_010e_v1.02`. Package sourced and reviewed directly (`specs/nfe/xsd_pl010f_v1.04/`).

- **[regulatory-update]** Diffed the official `PL_010f_v1.04` package against the bundled
  `PL_010e_v1.02`: the only substantive change in `leiauteNFe_v4.00.xsd` is NT 2026.007's
  IE-optional issuance path — `emit/IE` gains `minOccurs="0"` (was required), for taxpayers
  exclusively subject to IBS/CBS. Homologação 2026-09-01, **produção 2026-11-03 (still future)**.
  Hand-applied to `leiauteNFe_v4.00.xsd` and `leiauteNFe_v4.00_unsigned.xsd`, cited inline, same
  pattern as the 010e delta. `br__validate_nfe_xml`'s schema-version metadata updated accordingly.
- **Deliberately not implemented**: `BREmitente.ie` (Pydantic field) stays required. Production
  enforcement of the IE-optional path is still future, and there is no IBS/CBS-exclusive-taxpayer
  classification field yet to gate the relaxation correctly — the XSD is now more permissive than
  the model, which is a safe direction (no invalid document can be emitted as a result). Tracked as
  an open (not blocked) roadmap item, activation trigger 2026-11-03.
- Cosmetic: `vNFTot`'s declared type renamed `TDec_1302Opc` → `TDec_1302` in the same package (type
  definitions are byte-identical; `vNFTot` already carried `minOccurs="0"`) — no functional impact.
- The rest of `PL_010f_v1.04`'s diff against `010e` is entirely inside `DFeTiposBasicos_v1.00.xsd`'s
  `TMonofasia` (IBS/CBS single-phase-taxation) group — part of the already-deferred NT 2025.002
  v1.40→v1.50 RTC modeling effort, not re-implemented here (see `specs/nfe/MANIFEST.md`).
- 301 tests passing (1 skipped); audit gate 0 blocking. Patched XSDs re-verified to compile
  (`lxml.etree.XMLSchema`) and the generate→XSD smoke check (audit CHECK_9) still passes.

## v0.8.0 (2026-08-26) — CT-e access key `TChDFe` alphanumeric-CNPJ (BR-CTE-23)

Follow-up to v0.7.0, closing the `TChDFe` item deliberately deferred there.

- **[BR-CTE-23]** The CT-e access-key type `TChDFe` was loosened schema-wide from `[0-9]{44}` to `[0-9]{6}[A-Z0-9]{12}[0-9]{26}` (alphanumeric-CNPJ-ready) in `PL_CTe_400_NT2026.002`. `chave_acesso`'s field validator (`models/cte.py`) and `build_cte_access_key`'s CNPJ regex (`utils/cte_access_key.py`, now `[0-9A-Z]{12}[0-9]{2}`, mirroring the NF-e builder) were updated to match; the shared mod-11 check digit is already alphanumeric-safe (`ord(char)-48`), so no separate code path was needed. Confirmed `[Verified locally]` against `tiposGeralCTe_v4.00.xsd` (`TChDFe`) and `cteTiposBasico_v4.00.xsd` (`infCte/@Id`). Resolves the `[NEED: verify]` marker in `cte_access_key.py`.
- All-numeric keys remain valid (backward-compatible). New tests cover alphanumeric and legacy all-numeric keys; format-error assertion updated. 301 tests passing (1 skipped); audit gate 0 blocking. Core pin unchanged (BR is non-CII, unaffected by core v1.21.0).

## v0.7.0 (2026-08-17) — CT-e IBS/CBS, Reforma Tributária do Consumo (NT 2026.002, BR-CTE-2026-08)

Closes GitHub issue cmendezs/mcp-nfe-br#5, filed by the regulatory watch (2026-W34). Full NT PDF (`CTe_Nota_Tecnica_2026_002 v1.01.pdf`) and the schema package (`PL_CTe_400_NT2026.002 RTC_1.00.zip`) were sourced and reviewed directly (`specs/cte/`).

- **[BR-CTE-2026-08]** `imp/IBSCBS` (full `TCIBS` tree: `vBC`, `gIBSUF`, `gIBSMun`, `vIBS`, `gCBS` incl. `gALCZFMCBS`/`gDif`/`gRed`, `gTribRegular`, `gTribCompraGov`), `emit/ISUFEmit` (Suframa registration), and `ide/tpPagAnt`+`gPagAntecipado` (antecipação de pagamento) added to `BRCTeDocument` and wired into `CTeGenerator`. Sibling ordering `[Verified locally]` against the schema package, not guessed from the NT's prose/diagrams — `imp` sequence is `ICMS → vTotTrib? → IBSCBS?`; `ide` tail is `...toma3/toma4 → tpPagAnt? → gPagAntecipado?`
- **[BR-CTE-2026-08]** Self-contained NT business rules enforced as `model_validator`s on `BRCTeDocument`: RV 4.001 (emitente município must be ZFM/ALC when Suframa informed), RV 5.001-003 (devolução group never valid for CT-e), RV 6.003 (Suframa required when CBS-zero-rate claimed), RV 6.004 (route+parties municipality matching for CBS-zero-rate), RV 6.005 (`vTribRegCBS` arithmetic), RV 7.001/002 (antecipação self-consistency), RV 7.010 (referenced key's embedded CNPJ-Base must match emitente), RV 7.011 (no duplicate antecipação keys)
- **[BR-CTE-2026-08]** Bundled runtime schema (`mcp_nfe_br/schemas/cte/`) upgraded wholesale to `PL_CTe_400_NT2026.002 RTC_1.00` (the previously-bundled `PL_CTe_400` predates the RTC fields entirely); `_unsigned` derivatives regenerated by patching the single `ds:Signature` occurrence in `TCTe` to `minOccurs="0"`, same mechanical transform as the pre-existing derivative. `inutCTe*`/`distDFe/` (unrelated features, absent from the new NT-specific package) were left untouched
- **Deliberately not implemented** (see `br.md` CT-e section and roadmap `BR-CTE-21`): RV 6.001/002 (CBS rate 0.90% exception table needs `cClassTrib` data not supplied), RV 7.003-009 (need a live SEFAZ "Acesso BD CTe" lookup), Suframa digit-verifier (algorithm not published in the NT)
- **Discovered but out of scope** (`BR-CTE-22`, `BR-CTE-23`): the same schema package also ships a new `TCTeSimp` document type and `pgtoVinc` group, belonging to a different Nota Técnica (NT 2026.001); the CT-e access-key type (`TChDFe`) changed schema-wide to an alphanumeric-CNPJ-ready pattern, but `chave_acesso`/`build_cte_access_key` were deliberately left untouched — only the new `pag_antecipado` field uses the new pattern
- Because the schema upgrade replaced whole files rather than patching individual elements, two unrelated deltas from the same official `PL_CTe_400_NT2026.002` package came along incidentally: a `classDuto` field on the dutoviário modal payload (modal not implemented by this generator — zero code impact) and a loosened event-ID pattern in `eventoCTeTiposBasico_v4.00.xsd` (`ID[0-9]{53}` → `ID[0-9]{12}[A-Z0-9]{12}[0-9]{29}`, a strict superset — existing all-numeric IDs still match, confirmed by the full CT-e event test suite passing unchanged)
- 12 new tests (model validators + generate→XSD round-trip with the new fields); 299 tests passing (1 skipped); audit gate 0 blocking

## v0.6.5 (2026-08-14) — Official 010e_v.1.02 schema verification (BR-NFE-2026-08)

Follow-up to v0.6.4: the official schema package `PL_010e_v1.02.zip` (plus `PL_010d_v1.03.zip`, `PL_NFeDistDFe_104.zip`, `Eventos_RTC.zip`, and NT 2026.002 v1.10) was sourced from the SEFAZ portal's "Esquemas XML NF-e" listing and reviewed directly (`specs/nfe/`). This confirmed v0.6.4's NT-text-derived `tpImp`/`tpEmis`/`indPres` patch was accurate, and surfaced structural detail the NT text alone did not give: two undocumented new elements and the exact alert-message group shape.

- **[BR-NFE-2026-08]** New optional elements confirmed only by diffing the official XSD (not documented in NT 2026.002/2026.003 text): `cIndOp` (`ide` group, `[0-9]{6}`, "Código indicador do local da operação de fornecimento") and `ISUFEmit` (`emit` group, `[0-9]{8,9}`, "Inscrição do emitente na Suframa") — both likely NT 2025.002-RTC fields bundled opportunistically into the 010e release. Added to `leiauteNFe_v4.00.xsd`/`_unsigned.xsd`, `BRInvoice.c_ind_op`, `BREmitente.isuf_emit`, and wired into `NFeGenerator`. New tests `test_c_ind_op_passes`, `test_isuf_emit_passes`
- **[BR-NFE-2026-08]** `protNFe/infProt`'s alert-message group structurally confirmed: a bare `<xs:sequence minOccurs="0" maxOccurs="5">` of `cMsg`/`xMsg` pairs (no wrapping element name), resolving v0.6.4's `[NEED: official XSD]` gap. XSD cardinality fixed (was effectively 0-1) and `xMsg` maxLength corrected 200→255. `sefaz_client.py` gains `parse_sefaz_response` support via new `_sefaz_soap.scrape_alert_messages`, exposing `protNFe["alerts"]` as a list of `{cMsg, xMsg}` dicts (`xMsg` marked untrusted, per the existing `xMotivo` convention). New tests `test_parse_sefaz_response_prot_nfe_with_alert`, `test_parse_sefaz_response_prot_nfe_without_alert_has_no_alerts_key`
- **[BR-NFE-2026-08]** NT 2026.002 v1.10 (July 2026) reviewed: the leiaute table is identical to v1.00 (no further field-level changes), but the validation-rule catalogue shifted — rule `BA02-35` (reject outbound NF-e referencing modelo 65/59), previously believed to be in production since 03/08/2026, was actually deferred to 05/10/2026 along with several other rules; 11 rules were removed from the catalogue entirely. Corrected in `br.md`. No code impact (the business-rule catalogue is not enforced by the XSD-only validator either way)
- **[BR-NFE-2026-08]** `PL_010d_v1.03.zip` and `PL_NFeDistDFe_104.zip` reviewed for completeness: `010d_v1.03` confirms the CNPJ-alfa track has not merged with the DANFE-Tipo-2 track (010e); `PL_NFeDistDFe_104`'s `distDFeInt_v1.01.xsd` payload shape is unchanged from what `SefazClient` already implements — no code change needed for either
- **Still deliberately out of scope** (tracked in `br.md` "Known gaps"): NT 2026.002's full SEFAZ business-rule catalogue restricting `tpImp=6` documents (XSD-only validator, IBS/CBS precedent); NT 2026.003's printed-DANFE layout (no DANFE-rendering tool); `Eventos_RTC.zip` (sourced but not reviewed — belongs to the separate IBS/CBS effort)

287 tests passing (up from 283); audit gate 0 blocking.

## v0.6.4 (2026-08-14) — DANFE Simplificado Tipo 2 schema support (BR-NFE-2026-08)

SEFAZ published NF-e/NFC-e XML schema package `010e_v.1.02` on 2026-07-10, bundling NT 2025.002 v1.40, NT 2026.002 v1.0, and NT 2026.003 v1.0 on top of the already-bundled PL_010d. NT 2025.002 v1.40 needs no action (superseded locally by the already-bundled v1.50). NT 2026.002 and NT 2026.003 were sourced locally and reviewed (`specs/nfe/`); the official `010e_v.1.02` schema ZIP itself was not obtained — only the two NT PDFs, whose leiaute tables gave precise, citable field-level detail for the change below.

- **[BR-NFE-2026-08]** `tpImp` gains value `6` ("DANFE Simplificado Tipo 2"); `tpEmis=9` and `indPres=4` are redefined (broadened scope, same enumeration values — no XSD change needed for those two beyond documentation) by NT 2026.002 v1.00, in effect in SEFAZ production since 2026-08-03. `leiauteNFe_v4.00.xsd` and `leiauteNFe_v4.00_unsigned.xsd` refreshed to accept `tpImp=6`; both XSDs' `tpImp`/`tpEmis`/`indPres` documentation updated with inline `NT_2026.002_v1.00.pdf` citations. `BRInvoice.tp_imp`/`tp_emis`/`ind_pres` field descriptions updated to match. New regression test `test_danfe_simplificado_tipo_2_tp_imp_passes` (generate→XSD round-trip with `tpImp=6`)
- **Not in scope for this release**: NT 2026.002's SEFAZ business-rule catalogue restricting `tpImp=6` documents (CFOP whitelist, item-group exclusions, etc.) is not enforced — `br__validate_nfe_xml` is XSD-only, consistent with the existing IBS/CBS precedent; the new `cStat=120`/`PR13` alert-message response group is not parsed by `sefaz_client.py` (its production date, 2026-10-05, has not yet arrived, and the NT does not name the exact wrapper element); NT 2026.003's printed-DANFE layout is out of scope — this package does not render DANFE PDFs

283 tests passing (up from 282); audit gate 0 blocking.

## v0.6.3 (2026-08-11) — Restore NFS-e generation (BLOCKING), CT-e/gate hardening

Implements all 13 findings from the BR country audit 2026-07, originally scoped as three sprints (v0.6.3/v0.6.4/v0.6.5) and bundled into this single release since all were implemented together and none are breaking changes.

- **[BR-NFSE-C1 BLOCKING]** `NFSeGenerator` was abstract (missing `get_format_name`/`get_country_code`), so `br__generate_nfse` raised an uncaught `TypeError` on every call — NFS-e Nacional generation had never actually worked since it shipped in v0.5.0. Now implements all three abstract methods; `br__generate_nfse`'s `except` broadened to catch model/type errors cleanly. New `tests/test_standards/test_nfse_generator.py`
- **[BR-NFSE-C2 HIGH]** DPS `<end>` violated `TCEndereco` — missing the mandatory `endNac`/`endExt` choice wrapper, and emitted `xMun`/`UF`/`fone`/`cPais`/`xPais` which are not `TCEndereco` members at all. `_build_endereco` rewritten to emit `<endNac><cMun/><CEP/></endNac>` then `xLgr, nro, xCpl?, xBairro`; foreign addresses (`endExt`) now raise `DocumentGenerationError` since `TCEnderExt`'s required fields (`cEndPost`/`xCidade`/`xEstProvReg`) are not modeled
- **[BR-NFSE-C3 HIGH]** DPS `regTrib` omitted the mandatory `regEspTrib` (`TCRegTrib` has no `minOccurs` on it). `NFSeRegimeTributacao.reg_esp_trib` made required, default `"0"` (Nenhum)
- **[BR-NFSE-C4 HIGH]** DPS `tribMun` emitted `pAliq` before `tpRetISSQN`; schema order is `tpRetISSQN` then `pAliq`. Reordered
- **[BR-NFSE-C5 MEDIUM]** DPS `dCompet` was emitted `AAAAMMDD`; `TSData` requires dashed `YYYY-MM-DD`. New `_normalize_d_compet` defensively converts 8-digit input
- **[BR-NFSE-C6 MEDIUM]** Bundled `TSSerieDPS` pattern `^0{0,4}\d{1,5}$` had literal `^`/`$` characters (XSD/libxml2 implicit-anchor semantics), rejecting every real `serie` value — stripped in `tiposSimples_v1.01.xsd` as a documented local schema derivative (`specs/nfse/MANIFEST.md`)
- New `tests/test_validators/test_nfse_xsd.py` — a single fully-populated DPS generate→XSD round-trip that guards C2 through C6 together
- **[BR-CTE-T1 MEDIUM]** CT-e access-key/party layers disagreed on alphanumeric CNPJ: `BRCteParty` accepted it, `build_cte_access_key`/`check_chave_acesso_format` rejected it. Decided: reject alphanumeric CNPJ at `BRCteParty.check_cnpj` — the bundled CT-e v4.00 schema's `TCnpj` is `[0-9]{14}` only, unlike NF-e's alphanumeric-capable PL_010d. All three layers now agree
- **[BR-T2 MEDIUM]** Alphanumeric CNPJ check-digit algorithm promoted from `[Unverified]` to `[Verified locally]` against the primary source (NT Conjunta DFe 2025.001 v1.00, §2 worked example p.6 — not "Annex I" as previously assumed). New golden fixture `tests/fixtures/cnpj_alfanumerico_ntcj_2025_001.json`
- **[BR-L1 MEDIUM]** `br__generate_cte` called `BRCTeDocument.model_validate` outside `try/except`, leaking raw pydantic `ValidationError` (with input values) to the MCP client. Wrapped, mirroring `br__generate_nfse`
- **[BR-L3 MEDIUM, gate gap]** `audit_vs_core.py` CHECK 6/8 verified generator *subclassing* but not *concreteness*, so BR-NFSE-C1 (a BLOCKING defect) passed the gate green. New `_assert_concrete` helper adds `inspect.isabstract(...) is False` assertions; new **CHECK 9** runs a functional generate→XSD smoke check per sub-format (NF-e, NFS-e, CT-e) — the check that would have caught BR-NFSE-C1..C5
- **[BR-L2 LOW]** Gate `_REQUIRED_TOOL_CATEGORIES` omitted 4 registered tools (`br__sign_nfe`, `br__submit_nfse`, `br__consult_nfse_status`, `br__cancel_nfse`); added
- **[BR-S1 LOW]** `BR_READ_ONLY` did not gate CT-e mutating tools (only `BR_CTE_READ_ONLY` did). New `_assert_cte_not_read_only()` helper: CT-e submit/cancel/correct now honor **either** variable; `server.json`/README descriptions corrected
- **[BR-S2 LOW]** CT-e event XML (`cte_events`) was only checked for well-formedness in tests. New payload-level XSD validation against `evCancCTe_v4.00.xsd`/`evCCeCTe_v4.00.xsd`

282 tests passing (up from 264); audit gate 0 blocking.

## v0.6.2 (2026-07-03) — CT-e events, audit CHECK 8, docs (BR-CTE-14..17)

- **[BR-CTE-14]** New `mcp_nfe_br.standards.cte_events` module — builds `eventoCTe` XML for cancelamento (event `110111`); `build_cte_event_signer` added to `cte_signer.py` (targets `infEvento`); `enviar_evento` added to `SefazCTeClient` (`CTeRecepcaoEventoV4`, plain uncompressed XML unlike `CTeRecepcaoSincV4`). New gated tool `br__cancel_cte`
- **[BR-CTE-15]** `build_correcao_event_xml` (CC-e, event `110110`) and gated tool `br__correct_cte`. Both events confirmed `cStat=135` on success (MOC CT-e Visão Geral §6.2.2, §6.4) — resolves the `[NEED: verify]` marker in `br.md`. Server now exposes 22 tools
- **[BR-CTE-16]** New audit CHECK 8 in `audit/audit_vs_core.py`: `BRCTeDocument` subclasses `InvoiceDocument`; `CTeGenerator`/`CTeXSDValidator`/`SefazCTeClient` subclass the correct core ABCs. `_BR_MODULES` extended with all 9 CT-e modules; `_REQUIRED_TOOL_CATEGORIES`/`_TOOL_MODULES` extended with the 7 CT-e tools — CHECK 1/CHECK 2 both pass with zero new warnings, confirming no undeclared core overrides
- **[BR-CTE-17]** README.md/README.pt-BR.md: new "CT-e (modelo 57) tools" section, `BR_CTE_READ_ONLY` documented, stale "CT-e out of scope" intro claim removed. Homologação verification **not done** — requires a real ICP-Brasil A1 test certificate, `[NEED: manual verification]`

## v0.6.1 (2026-07-03) — CT-e SEFAZ submission/consultation (BR-CTE-10..12)

- **[BR-CTE-10]** Extracted `mcp_nfe_br.standards._sefaz_soap` (private shared SOAP envelope/response-parsing helper: `soap_envelope`, `scrape_fields`, `parse_response_root`); refactored `sefaz_client.py` to use it. All 48 existing NF-e SEFAZ tests pass unchanged, confirming the extraction preserves behavior
- **[BR-CTE-11]** `mcp_nfe_br.standards.sefaz_cte_client.SefazCTeClient` — covers `CTeStatusServicoV4`/`CTeConsultaV4` (plain XML) and `CTeRecepcaoSincV4` (GZip+Base64 payload, a structurally different shape from NF-e, confirmed against MOC CT-e Visão Geral §3.4.1)
  - No CT-e endpoint URLs are bundled or independently verified (the MOC only points to the live dfe-portal.svrs.rs.gov.br listing) — `get_cte_endpoint` always raises; `endpoint_override` is mandatory on every call
- **[BR-CTE-12]** Three new tools (server now exposes 20 tools): `br__submit_cte` (gated), `br__consult_cte_sefaz_status` (read-only), `br__consult_cte` (read-only — queries one already-known chCTe, not a bulk pull, per the CT-e scoping plan's tool table). New `BR_CTE_READ_ONLY` env var, kept distinct from `BR_READ_ONLY`
- `br__distribute_cte_dfe` (CTeDistribuicaoDFe) is **not implemented** — the bundled spec confirms the `distDFeInt` payload shape but not the webservice's method/namespace/wrapper details; deferred as `BR-CTE-13` `[NEED: verify]`
- `br__build_cte_access_key` MCP tool wrapper also deferred (the underlying `build_cte_access_key` util has existed since BR-CTE-5)

## v0.6.0 (2026-07-03) — CT-e (modelo 57) Phase 3, v1 (BR-CTE-1..9)

CT-e (Conhecimento de Transporte Eletrônico) work begins, per explicit user request (previously deferred). v1 scope: modal rodoviário only, ICMS CST 00 (tributação normal) only, event tools deferred.

- Spec bundle sourced from https://dfeportal.svrs.rs.gov.br/Cte/Documentos and bundled under `specs/cte/` (MOC CT-e 4.00, `PL_CTe_400.zip`, `PL_CTeDistDFe_100.zip`, 14 Notas Técnicas); XSDs extracted to `src/mcp_nfe_br/schemas/cte/`
- **[BR-CTE-2..4]** `mcp_nfe_br.models.cte`: `BRCTeDocument(InvoiceDocument)` and CT-e party classes (`BRCteEmitente`, `BRCteRemetente`, `BRCteExpedidor`, `BRCteRecebedor`, `BRCteDestinatario`, `BRCteTomador`). Namespace `http://www.portalfiscal.inf.br/cte`, schema 4.00 `[Verified locally]`
  - `buyer` overridden `Optional[InvoiceParty]=None` (no CT-e equivalent — `tomador` is the closest analog); `lines` stays empty (`v_prest.comp` used instead for freight-value components)
- **[BR-CTE-5]** `mcp_nfe_br.utils.cte_access_key.build_cte_access_key` — 44-char `chCTe`, reuses the mod-11 `access_key_check_digit` already shipped for NF-e's `chNFe`
- **[BR-CTE-6]** `mcp_nfe_br.standards.cte_signer.build_cte_signer` — wraps core `XMLDSigSigner` targeting `infCte` (RSA-SHA1, confirmed against MOC CT-e Visão Geral §3.2.4)
- **[BR-CTE-8]** `mcp_nfe_br.standards.cte_generator.CTeGenerator` — modal rodoviário only for v1 (`infModal` is `<xs:any>` in the main schema, so other modais don't break main-document validation, but their payloads are unmodeled)
- **[BR-CTE-9]** `mcp_nfe_br.validators.cte_xsd.CTeXSDValidator` — unsigned/signed auto-select, same pattern as `NFeXSDValidator`; two new tools `br__generate_cte`, `br__validate_cte_xml` (server now exposes 17 tools)
- Cancellation success `cStat` code and `infCTeAnu`/`tpCTe=2` mapping remain `[NEED: verify]` — not found in the bundled XSD enum or MOC text search

## v0.5.4 (2026-06-30) — Hardcoded UB12-10 activation dates

- **[BR-INV-2]** Runtime warning in `br__generate_nfe` now states the verified `UB12-10` (Grupo UB IBS/CBS mandatory) activation dates instead of "Implementação futura"
  - Verified directly against NT 2025.002-RTC v1.50 page 41/97 rule text (not the cronograma summary table, which still reads generic "Implementação futura"): homologação from `dhEmi` >= 2026-07-01 (CRT 3=Regime Normal); produção from `dhEmi` >= 2026-08-03 (CRT 3); produção from 2027-01-04 (CRT 1/2/4, Simples Nacional family)
  - Two rule exceptions documented in the warning text: devolução/complementar NF-e referencing a pre-2026 original; items on the monofásico-fuel `cProdANP` table
- **[BR-INV-3]** Re-checked the "ICP-Brasil V10 certificate chain retirement by 2026-12-31" claim against newly bundled `MCT10Vol.IIv.3.0.pdf` and `NT_2026.001_v1.02a - PAA NFe.pdf` — neither confirms it; `specs/nfe/MANIFEST.md` updated, no code change (claim remains `[BLOCKED]` pending a primary ICP-Brasil source)

## v0.5.3 (2026-06-30) — Explicit rounding mode, core re-sync

- **[BR-TL-6]** `_d2`/`_percent` in `nfe_generator.py` and `nfse_generator.py` now pass `ROUND_HALF_UP` explicitly instead of relying on core's default
  - Research finding: `ANEXO I - Leiaute e Regra de Validação - NF-e e NFC-e.pdf` footnote (*4) (not MOC v7.0 itself) requires only 2-decimal rounding with a +/- R$0.01 SEFAZ validation tolerance, no specific rounding mode is mandated
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
