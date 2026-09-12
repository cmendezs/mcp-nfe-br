"""Pre-publish audit: verify mcp-nfe-br coherence against mcp-einvoicing-core.

Run standalone (from this repo's own root):
    uv run python audit/audit_vs_core.py
    uv run python audit/audit_vs_core.py --output audit/report.json
    uv run python mcp-nfe-br/audit/audit_vs_core.py --fail-on blocking

Exit codes:
    0  All checks passed
    1  Warnings only (non-blocking)
    2  Blocking failures found

CHECK 1 and CHECK 4 are delegated to mcp_einvoicing_core.audit.
CHECK 2 (tool registry), CHECK 3 (BRInvoice field alignment), CHECK 5
(BR-specific structural), CHECK 6 (NFSeDocument structural), CHECK 7
(parallel-implementation detector), CHECK 8 (BRCTeDocument structural,
BR-CTE-16), and CHECK 9 (functional generate→XSD smoke check, BR-L3)
are implemented here.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

from mcp_einvoicing_core.audit import (
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    SEVERITY_WARNING,
    AuditReport,
    CheckFinding,
    CheckResult,
    _try_import,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
    run_check_no_internal_references,
    run_check_resource_paths,
    run_check_version_compatibility,
)

# ---------------------------------------------------------------------------
# CHECK 1 configuration — country-specific constants
# ---------------------------------------------------------------------------

# NF-e / NFC-e (modelo 55/65, schema 4.00) predate and have no EN 16931
# lineage — non-EN16931 pathway, BRInvoice extends InvoiceDocument.
_IS_EN16931_FAMILY: bool | None = False
_PRIMARY_INVOICE_CLASS: tuple[str, str] | None = (
    "mcp_nfe_br.models.invoice",
    "BRInvoice",
)
# NFS-e Nacional (ADN) primary model — also InvoiceDocument (non-EN16931 pathway)
_NFSE_INVOICE_CLASS: tuple[str, str] = (
    "mcp_nfe_br.models.nfse",
    "NFSeDocument",
)

_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {
    "mcp_einvoicing_core.base_server": {
        # OVERRIDE-REASON: no document parser implemented yet — Phase 1 scope is
        # generation and XSD validation only, not parsing of received documents
        "BaseDocumentParser",
        # OVERRIDE-REASON: SEFAZ NFeAutorizacao4 (v0.3.1, standards/sefaz_client.py
        # + tools/sefaz.py) is a stateless synchronous SOAP call returning a
        # protNFe/protocolo de autorização directly — it does not fit the
        # session-based submit/get_status/search lifecycle (KSeF, FR FlowClient,
        # BE AS4) that BaseLifecycleManager models. Mirrors the ES SII precedent
        # (also a direct SOAP client, not a BaseLifecycleManager subclass).
        "BaseLifecycleManager",
        # OVERRIDE-REASON: party validation is performed inline via validate_cpf/
        # validate_cnpj helpers, not via the ABC party validator pattern
        "BasePartyValidator",
        # OVERRIDE-REASON: br__submit_nfe returns the parsed protNFe dict
        # directly (NFeAutorizacao4 is synchronous, no session_ref) rather than
        # the session-oriented SubmitResult shape — see BaseLifecycleManager
        # override reason above
        "SubmitResult",
        # OVERRIDE-REASON: mcp-nfe-br uses EInvoicingMCPServer directly; the
        # raw FastMCP handle is not imported in package code
        "FastMCP",
        # OVERRIDE-REASON: stdlib re-export; mcp-nfe-br imports abstractmethod
        # from abc directly where needed
        "abstractmethod",
        "ABC",
        "Any",
        # OVERRIDE-REASON: third-party re-export; pydantic BaseModel/Field
        # imported from pydantic directly in mcp-nfe-br models
        "BaseModel",
        "Field",
        "scrub",
        "InvoiceParty",
        # OVERRIDE-REASON: Generic/TypeVar (typing) are used internally by
        # base_server.py to parameterize BaseDocumentGenerator/BaseDocumentValidator
        # over document types; mcp-nfe-br's own classes subclass the concrete
        # generics directly and do not need the typing symbols themselves.
        "Generic",
        "TypeVar",
    },
    "mcp_einvoicing_core.digital_signature": {
        # OVERRIDE-REASON: NF-e/NFC-e use ICP-Brasil A1 certificates and plain
        # enveloped XML-DSig (XMLDSigSigner/XMLDSigSignerConfig, wired in
        # standards/nfe_signer.py and br__sign_nfe, v0.3.0 item 1), not the
        # XAdES-EPES envelope (ES Facturae/TicketBAI)
        "BaseDocumentSigner",
        "XAdESSignerConfig",
        "XAdESEPESSigner",
        # OVERRIDE-REASON: NF-e/NFC-e signing uses XMLDSigSigner exclusively
        # (see reason above); CAdES (PKCS#7) is FatturaPA's signing scheme, not
        # ICP-Brasil's — CAdESSigner/CAdESSignerConfig are not applicable here.
        "CAdESSigner",
        "CAdESSignerConfig",
        # OVERRIDE-REASON: load_certificate_der (core v1.16.0) is a helper for
        # country packages building custom auth claims from a cert's public
        # bytes (e.g. ES FACe's JWS "username" claim); BR has no such flow.
        "load_certificate_der",
        "ABC",
        "abstractmethod",
        "dataclass",
        "datetime",
        "field",
        "safe_fromstring",
        "timezone",
    },
    "mcp_einvoicing_core.download_rules": {
        # OVERRIDE-REASON: BR spec artefacts (XSDs, MOC, Notas Técnicas) are
        # bundled manually into specs/; the artefact-download framework is not used
        "DownloadSpec",
        "download_artefacts",
        "main",
        "Path",
        "dataclass",
        "field",
        "entry_points",
    },
    "mcp_einvoicing_core.en16931": {
        # OVERRIDE-REASON: NF-e/NFC-e has no EN 16931 lineage; none of the
        # en16931 module is used
        "EN16931Invoice",
        "EN16931LineItem",
        "EN16931Tax",
        "EN16931Party",
        "EN16931Address",
        "EN16931AllowanceCharge",
        # OVERRIDE-REASON: NF-e/NFC-e payment means (tPag) are modeled
        # separately; EN16931PaymentMeans not used (non-EN16931 pathway)
        "EN16931PaymentMeans",
        "BaseModel",
        "Decimal",
        "Field",
        "date",
        "field_validator",
        "model_validator",
    },
    "mcp_einvoicing_core.exceptions": {
        # OVERRIDE-REASON: CPF/CNPJ validation tools return TaxIdValidationResult
        # with error strings; PartyValidationError not raised at tool layer
        "PartyValidationError",
        # OVERRIDE-REASON: NF-e/NFC-e use XSD-based validation; the Schematron
        # exception hierarchy is not used
        "XSDValidationError",
        "SchematronValidationError",
        # OVERRIDE-REASON: SefazClient raises PlatformError directly (now used,
        # v0.3.1); 401-retry/AuthenticationError path is not reached by
        # AuthMode.MTLS (no bearer token to invalidate)
        "AuthenticationError",
        "ValidationError",
    },
    "mcp_einvoicing_core.http_client": {
        # OVERRIDE-REASON: SefazClient (v0.3.1) uses AuthMode.MTLS only;
        # OAuth2/token-cache infrastructure (OAuthConfig/OAuthValues/TokenCache)
        # is not applicable to ICP-Brasil certificate auth
        "OAuthConfig",
        "OAuthValues",
        "BaseEInvoicingConfig",
        "TokenCache",
        "AuthenticationError",
        # OVERRIDE-REASON: JWSConfig (core v1.16.0) configures RS256/x5c JWT
        # auth for platforms like ES FACe; SefazClient uses AuthMode.MTLS only.
        "JWSConfig",
        # OVERRIDE-REASON: compute_retry_delay (core v1.16.2) backs
        # BaseEInvoicingClient._request's retry loop; SefazClient._post_soap
        # bypasses _request entirely (raw SOAP body, custom Content-Type — see
        # sefaz_client.py docstring) and does a single POST with no retry loop.
        "compute_retry_delay",
        "Any",
        "BaseModel",
        "BaseSettings",
        "Enum",
        "Field",
        "Path",
        "field_validator",
        "parsedate_to_datetime",
        "urlparse",
    },
    "mcp_einvoicing_core.models": {
        # OVERRIDE-REASON: stdlib/third-party re-exports in models; mcp-nfe-br
        # imports from pydantic/stdlib directly
        "BaseModel",
        "Decimal",
        "Field",
        "field_validator",
        "model_validator",
        # OVERRIDE-REASON: BRInvoice models ICMS/IPI/PIS/COFINS per line instead
        # of a single VAT summary; core VATSummary not used
        "VATSummary",
        "PaymentTerms",
        "InvoiceParty",
        "PartyAddress",
        # OVERRIDE-REASON: no document validator implemented yet (XSD-based
        # validation is a later phase)
        "DocumentValidationResult",
        # OVERRIDE-REASON: validation tools use TaxIdValidationResult directly;
        # the generic TaxIdentifier model is not used
        "TaxIdentifier",
    },
    "mcp_einvoicing_core.pdf": {
        # OVERRIDE-REASON: DANFE/DANFCE generation (PDF) is a later phase
        "PDFEmbedder",
    },
    "mcp_einvoicing_core.peppol": {
        # OVERRIDE-REASON: Brazil is not on the Peppol network; NF-e/NFC-e use
        # the SEFAZ clearance model
        "PeppolLookupResult",
        "PeppolServiceInfo",
        "PEPPOL_BIS_BILLING_30",
        "PeppolEnvironment",
        "PeppolSMPClient",
        "PeppolParticipantId",
        "PlatformError",
        "Enum",
        "dataclass",
        "field",
        "safe_fromstring",
    },
    "mcp_einvoicing_core.profile_registry": {
        # OVERRIDE-REASON: NF-e/NFC-e profile (modelo 55/65, schema 4.00) is not
        # yet registered in the core profile/syntax registry
        "ProfileEntry",
        "ProfileRegistry",
        "set_profile_registry",
        "dataclass",
    },
    "mcp_einvoicing_core.qr": {
        # OVERRIDE-REASON: NFC-e QR code generation (consulta pública) is a
        # later phase
        "generate_qr_png_base64",
    },
    "mcp_einvoicing_core.schematron": {
        # OVERRIDE-REASON: NF-e/NFC-e use XSD-based validation (leiauteNFe_v4.00.xsd),
        # not Schematron; XSD/JSON validator ABCs not yet subclassed
        "SchematronValidator",
        "BaseStructuredValidator",
        "BaseXSDValidator",
        "BaseJSONValidator",
        "ValidationMessage",
        "ValidationResult",
        # OVERRIDE-REASON: SaxonSchematronValidator/get_xslt_version/
        # load_schematron_validator are Schematron/SVRL-only helpers (Saxon XSLT
        # execution); NF-e/NFC-e use XSD-only validation, same reason as the
        # other schematron.py symbols excluded above.
        "SaxonSchematronValidator",
        "get_xslt_version",
        "load_schematron_validator",
        "ABC",
        "abstractmethod",
        "Path",
        "dataclass",
        "field",
        "safe_fromstring",
        "safe_parser",
    },
    "mcp_einvoicing_core.xml_utils": {
        # OVERRIDE-REASON: not used by the NF-e/NFC-e generator or validator
        "xml_escape",
        "format_error",
        "filter_empty_values",
        "validate_date_iso",
        "mark_untrusted",
        "mark_untrusted_fields",
        # OVERRIDE-REASON: NF-e/NFC-e parties use CPF/CNPJ, not IBAN; IBAN
        # validation not applicable
        "validate_iban",
        "Any",
        "Decimal",
    },
}

_BR_MODULES: list[str] = [
    "mcp_nfe_br",
    "mcp_nfe_br.models.invoice",
    "mcp_nfe_br.models.nfse",
    "mcp_nfe_br.models.cte",
    "mcp_nfe_br.server",
    "mcp_nfe_br.tools.validation",
    "mcp_nfe_br.tools.generation",
    "mcp_nfe_br.tools.sefaz",
    "mcp_nfe_br.tools.nfse",
    "mcp_nfe_br.tools.cte",
    "mcp_nfe_br.utils.document_ids",
    "mcp_nfe_br.utils.access_key",
    "mcp_nfe_br.utils.cte_access_key",
    "mcp_nfe_br.standards.nfe_generator",
    "mcp_nfe_br.standards.nfe_signer",
    "mcp_nfe_br.standards.nfse_generator",
    "mcp_nfe_br.standards.nfse_signer",
    "mcp_nfe_br.standards.sefaz_client",
    "mcp_nfe_br.standards._sefaz_soap",
    "mcp_nfe_br.standards.sefaz_cte_client",
    "mcp_nfe_br.standards.cte_generator",
    "mcp_nfe_br.standards.cte_signer",
    "mcp_nfe_br.standards.cte_events",
    "mcp_nfe_br.validators.nfe_xsd",
    "mcp_nfe_br.validators.nfse_xsd",
    "mcp_nfe_br.validators.cte_xsd",
]

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"

# CHECK 7 configuration — every runtime resource directory this package's
# own modules resolve at import time (CORE-1, core v1.32.0). BR resolves its
# XSDs via importlib.resources (validators/{nfe,nfse,cte}_xsd.py's
# _SCHEMA_PACKAGE + files()), not a __file__-relative hop count, so it is
# architecturally immune to the CORE-1 bug class — but we still exercise the
# real resolution here (with no resource_paths declared, CHECK 7 only
# reports a [SKIP] WARNING, indistinguishable from "never checked";
# declaring these makes the immunity explicit and catches a genuine
# packaging regression, e.g. a missing package-data declaration, that
# importlib.resources itself does not rule out).
import importlib.resources  # noqa: E402

import mcp_nfe_br  # noqa: E402

_PACKAGE_ROOT = Path(mcp_nfe_br.__file__).resolve().parent
_RESOURCE_PATHS: dict[str, Path] = {
    "mcp_nfe_br.validators.nfe_xsd._SCHEMA_PACKAGE": Path(
        str(importlib.resources.files("mcp_nfe_br.schemas.nfe"))
    ),
    "mcp_nfe_br.validators.nfse_xsd._SCHEMA_PACKAGE": Path(
        str(importlib.resources.files("mcp_nfe_br.schemas.nfse"))
    ),
    "mcp_nfe_br.validators.cte_xsd._SCHEMA_PACKAGE": Path(
        str(importlib.resources.files("mcp_nfe_br.schemas.cte"))
    ),
}


# ---------------------------------------------------------------------------
# CHECK 2 — Tool registry completeness
# ---------------------------------------------------------------------------

_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    # NF-e / NFC-e tools
    "br__validate_cpf": "Validate a Brazilian CPF (individual taxpayer ID)",
    "br__validate_cnpj": "Validate a Brazilian CNPJ (company tax ID)",
    "br__generate_nfe": "Generate an unsigned NF-e/NFC-e 4.00 XML document",
    "br__sign_nfe": "Apply ICP-Brasil XML-DSig signature to an NF-e/NFC-e 4.00 document",
    "br__validate_nfe_xml": "Validate NF-e/NFC-e 4.00 XML against the bundled PL_010d XSD",
    "br__build_access_key": "Assemble and check-digit a 44-character chNFe access key",
    "br__submit_nfe": "Submit a signed NF-e/NFC-e to SEFAZ NFeAutorizacao4 (autorização)",
    "br__consult_sefaz_status": "Check SEFAZ webservice availability (NFeStatusServico4)",
    "br__distribute_dfe": "Query/distribute DF-e via SEFAZ NFeDistribuicaoDFe",
    # NFS-e Nacional (ADN) tools — Sprint 4 (v0.5.0)
    "br__generate_nfse": "Generate an unsigned DPS for NFS-e Nacional (ADN, schema v1.01)",
    "br__validate_nfse_xml": "Validate DPS or NFSe XML against the bundled ADN v1.01 XSD",
    "br__sign_nfse": "Apply ICP-Brasil XML-DSig signature to an NFS-e Nacional DPS (infDPS)",
    "br__submit_nfse": "Submit a signed DPS to the ADN for NFS-e Nacional issuance",
    "br__consult_nfse_status": "Query an NFS-e's status by access key (chNFSe) via the ADN",
    "br__cancel_nfse": "Request NFS-e cancellation via the ADN",
    # CT-e (modelo 57) tools — Phase 3, v1 (BR-CTE-9/12/14/15)
    "br__generate_cte": "Generate an unsigned CT-e 4.00 XML document (modal rodoviário, ICMS CST 00)",
    "br__validate_cte_xml": "Validate CT-e 4.00 XML against the bundled PL_CTe_400 XSD",
    "br__consult_cte_sefaz_status": "Check SEFAZ CT-e webservice availability (CTeStatusServicoV4)",
    "br__consult_cte": "Query a CT-e's status by access key (CTeConsultaV4)",
    "br__submit_cte": "Submit a signed CT-e to SEFAZ CTeRecepcaoSincV4 (autorização)",
    "br__cancel_cte": "Request CT-e cancellation via event 110111 (CTeRecepcaoEventoV4)",
    "br__correct_cte": "Issue a Carta de Correção Eletrônica via event 110110 (CTeRecepcaoEventoV4)",
}

_TOOL_MODULES: tuple[str, ...] = (
    "mcp_nfe_br.tools.validation",
    "mcp_nfe_br.tools.generation",
    "mcp_nfe_br.tools.sefaz",
    "mcp_nfe_br.tools.nfse",
    "mcp_nfe_br.tools.cte",
)


def _collect_registered_tools() -> set[str]:
    """Detect tool functions registered via mcp.tool() in the BR server."""
    registered: set[str] = set()

    for mod_path in _TOOL_MODULES:
        mod, _ = _try_import(mod_path)
        if mod:
            for fn_name in _REQUIRED_TOOL_CATEGORIES:
                if hasattr(mod, fn_name):
                    registered.add(fn_name)

    return registered


def run_check_2() -> CheckResult:
    """CHECK 2 — Tool registry completeness."""
    result = CheckResult(check_id="CHECK_2", name="Tool registry completeness")
    registered = _collect_registered_tools()

    for tool_name, description in _REQUIRED_TOOL_CATEGORIES.items():
        tag = "[OK]" if tool_name in registered else "[MISSING_TOOL]"
        sev = SEVERITY_OK if tool_name in registered else SEVERITY_BLOCKING
        result.findings.append(
            CheckFinding(
                check_id="CHECK_2",
                tag=tag,
                severity=sev,
                symbol=tool_name,
                message=(
                    f"Tool '{tool_name}' is registered. ({description})"
                    if tool_name in registered
                    else (
                        f"Required tool '{tool_name}' ({description}) could not be detected. "
                        "Ensure it is defined in the appropriate tools module and registered "
                        "in server.py via mcp.tool()()."
                    )
                ),
            )
        )

    for tool_name in sorted(registered - set(_REQUIRED_TOOL_CATEGORIES)):
        result.findings.append(
            CheckFinding(
                check_id="CHECK_2",
                tag="[EXTRA]",
                severity=SEVERITY_OK,
                symbol=tool_name,
                message=f"Tool '{tool_name}' is present but not in the required tool spec.",
            )
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 3 — Model field alignment (BRInvoice)
# ---------------------------------------------------------------------------

_CORE_MANDATORY_FIELDS: dict[str, str] = {
    "document_type": "Country-specific document type code (modelo 55/65)",
    "date": "Invoice date (YYYY-MM-DD)",
    "number": "Invoice / document number",
    "seller": "Emitente",
    "buyer": "Destinatário",
    "lines": "Itens (BRInvoiceLine — Grupo I)",
}

_BR_SPECIFIC_FIELDS: dict[str, str] = {
    "modelo": "Modelo do documento fiscal (55=NF-e, 65=NFC-e)",
    "serie": "Série do documento fiscal",
    "chave_acesso": "Chave de acesso (44 caracteres)",
    "tipo_operacao": "Tipo de Operação (0=entrada, 1=saída)",
}


def run_check_3() -> CheckResult:
    """CHECK 3 — Model field alignment (BRInvoice)."""
    result = CheckResult(check_id="CHECK_3", name="Model field alignment")

    mod, err = _try_import("mcp_nfe_br.models.invoice")
    if mod is None:
        result.skipped = True
        result.skip_reason = f"Could not import BR invoice models: {err}"
        return result

    invoice_cls = getattr(mod, "BRInvoice", None)
    if invoice_cls is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_3",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="BRInvoice",
                message="BRInvoice class not found in mcp_nfe_br.models.invoice.",
            )
        )
        return result

    model_fields = set(invoice_cls.model_fields.keys())

    for field_name, description in {**_CORE_MANDATORY_FIELDS, **_BR_SPECIFIC_FIELDS}.items():
        tag = "[OK]" if field_name in model_fields else "[FIELD_MISSING]"
        sev = SEVERITY_OK if field_name in model_fields else SEVERITY_BLOCKING
        result.findings.append(
            CheckFinding(
                check_id="CHECK_3",
                tag=tag,
                severity=sev,
                symbol=f"BRInvoice.{field_name}",
                message=(
                    f"Field present. {description}"
                    if field_name in model_fields
                    else f"Field '{field_name}' ({description}) is absent from BRInvoice."
                ),
            )
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 5 — BR-specific structural checks
# ---------------------------------------------------------------------------


def run_check_5() -> CheckResult:
    """CHECK 5 — BR-specific structural and completeness checks."""
    result = CheckResult(check_id="CHECK_5", name="BR-specific structural checks")

    server_mod, err = _try_import("mcp_nfe_br.server")
    if server_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_5",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.server",
                message=f"Could not import server module: {err}",
            )
        )
        return result

    for attr in ("mcp", "main"):
        tag = "[OK]" if hasattr(server_mod, attr) else "[MISSING]"
        sev = SEVERITY_OK if hasattr(server_mod, attr) else SEVERITY_BLOCKING
        result.findings.append(
            CheckFinding(
                check_id="CHECK_5",
                tag=tag,
                severity=sev,
                symbol=f"server.{attr}",
                message=(
                    f"server.{attr} is present."
                    if hasattr(server_mod, attr)
                    else f"server.{attr} is missing — required for MCP server operation."
                ),
            )
        )

    mcp_obj = getattr(server_mod, "mcp", None)
    core_mod, _ = _try_import("mcp_einvoicing_core")
    server_cls = getattr(core_mod, "EInvoicingMCPServer", None) if core_mod else None
    if mcp_obj is not None and server_cls is not None:
        if isinstance(mcp_obj, server_cls):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_5",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="server.mcp",
                    message="server.mcp is an EInvoicingMCPServer instance.",
                )
            )
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_5",
                    tag="[WRONG_TYPE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="server.mcp",
                    message=(
                        f"server.mcp is {type(mcp_obj).__name__}, expected EInvoicingMCPServer."
                    ),
                )
            )

    # CPF/CNPJ validators must be importable and round-trip a known-good value
    utils_mod, _ = _try_import("mcp_nfe_br.utils.document_ids")
    if utils_mod:
        for fn_name in ("validate_cpf", "validate_cnpj"):
            tag = "[OK]" if hasattr(utils_mod, fn_name) else "[MISSING]"
            sev = SEVERITY_OK if hasattr(utils_mod, fn_name) else SEVERITY_BLOCKING
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_5",
                    tag=tag,
                    severity=sev,
                    symbol=f"utils.document_ids.{fn_name}",
                    message=(
                        f"{fn_name} is present."
                        if hasattr(utils_mod, fn_name)
                        else f"{fn_name} is missing from utils.document_ids."
                    ),
                )
            )
    else:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_5",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.utils.document_ids",
                message="Could not import mcp_nfe_br.utils.document_ids.",
            )
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 6 — NFSeDocument structural checks (BR-NFSE-8)
# ---------------------------------------------------------------------------


def _assert_concrete(result: CheckResult, check_id: str, cls: type, symbol: str) -> None:
    """Append a finding asserting *cls* is instantiable, not merely a correct subclass.

    `issubclass(cls, BaseDocumentGenerator)` is `True` even for a class that fails to
    implement all abstract methods — BR-NFSE-C1 (NFSeGenerator missing get_format_name/
    get_country_code) passed the gate for exactly this reason. `inspect.isabstract`
    catches it directly (BR-L3).
    """
    if inspect.isabstract(cls):
        missing = sorted(getattr(cls, "__abstractmethods__", ()))
        result.findings.append(
            CheckFinding(
                check_id=check_id,
                tag="[ABSTRACT]",
                severity=SEVERITY_BLOCKING,
                symbol=symbol,
                message=(
                    f"{symbol} is abstract and cannot be instantiated "
                    f"(missing: {', '.join(missing) or 'unknown'}) — a BR-NFSE-C1-class defect."
                ),
            )
        )
    else:
        result.findings.append(
            CheckFinding(
                check_id=check_id,
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol=symbol,
                message=f"{symbol} is concrete (instantiable).",
            )
        )


def run_check_6() -> CheckResult:
    """CHECK 6 — NFSeDocument subclasses InvoiceDocument; no local signer/XSD/HTTP reimplementation."""
    result = CheckResult(check_id="CHECK_6", name="NFSeDocument structural checks")

    mod, err = _try_import("mcp_nfe_br.models.nfse")
    if mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.models.nfse",
                message=f"Could not import NFS-e model module: {err}",
            )
        )
        return result

    nfse_cls = getattr(mod, "NFSeDocument", None)
    if nfse_cls is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="NFSeDocument",
                message="NFSeDocument class not found in mcp_nfe_br.models.nfse.",
            )
        )
        return result

    # Must subclass InvoiceDocument (non-EN16931 pathway, same as BRInvoice)
    core_mod, _ = _try_import("mcp_einvoicing_core.models")
    invoice_doc_cls = getattr(core_mod, "InvoiceDocument", None) if core_mod else None
    if invoice_doc_cls is not None:
        is_subclass = issubclass(nfse_cls, invoice_doc_cls)
        tag = "[OK]" if is_subclass else "[WRONG_BASE]"
        sev = SEVERITY_OK if is_subclass else SEVERITY_BLOCKING
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag=tag,
                severity=sev,
                symbol="NFSeDocument",
                message=(
                    "NFSeDocument correctly subclasses InvoiceDocument (non-EN16931 pathway)."
                    if is_subclass
                    else "NFSeDocument must subclass InvoiceDocument from mcp_einvoicing_core.models."
                ),
            )
        )

    # _IS_EN16931_FAMILY must be False
    flag = getattr(nfse_cls, "_IS_EN16931_FAMILY", None)
    if flag is False or flag is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol="NFSeDocument._IS_EN16931_FAMILY",
                message="_IS_EN16931_FAMILY is False (non-EN16931 pathway confirmed).",
            )
        )
    else:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[WRONG_VALUE]",
                severity=SEVERITY_BLOCKING,
                symbol="NFSeDocument._IS_EN16931_FAMILY",
                message=f"_IS_EN16931_FAMILY must be False for NFS-e Nacional; got {flag!r}.",
            )
        )

    # Verify NFS-e generator does not reimplement local XMLDSigSigner or XSD validator
    gen_mod, gen_err = _try_import("mcp_nfe_br.standards.nfse_generator")
    if gen_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.standards.nfse_generator",
                message=f"NFSeGenerator module missing: {gen_err}",
            )
        )
    else:
        from mcp_einvoicing_core import BaseDocumentGenerator

        gen_cls = getattr(gen_mod, "NFSeGenerator", None)
        if gen_cls and issubclass(gen_cls, BaseDocumentGenerator):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_6",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="NFSeGenerator",
                    message="NFSeGenerator subclasses BaseDocumentGenerator.",
                )
            )
            _assert_concrete(result, "CHECK_6", gen_cls, "NFSeGenerator")
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_6",
                    tag="[WRONG_BASE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="NFSeGenerator",
                    message="NFSeGenerator must subclass BaseDocumentGenerator.",
                )
            )

    # Verify NFSeXSDValidator subclasses BaseDocumentValidator
    val_mod, val_err = _try_import("mcp_nfe_br.validators.nfse_xsd")
    if val_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_6",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.validators.nfse_xsd",
                message=f"NFSeXSDValidator module missing: {val_err}",
            )
        )
    else:
        from mcp_einvoicing_core import BaseDocumentValidator

        val_cls = getattr(val_mod, "NFSeXSDValidator", None)
        if val_cls and issubclass(val_cls, BaseDocumentValidator):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_6",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="NFSeXSDValidator",
                    message="NFSeXSDValidator subclasses BaseDocumentValidator.",
                )
            )
            _assert_concrete(result, "CHECK_6", val_cls, "NFSeXSDValidator")
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_6",
                    tag="[WRONG_BASE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="NFSeXSDValidator",
                    message="NFSeXSDValidator must subclass BaseDocumentValidator.",
                )
            )

    return result


# ---------------------------------------------------------------------------
# CHECK 8 — BRCTeDocument structural checks (BR-CTE-16)
# ---------------------------------------------------------------------------

# CT-e is exempt from CHECK 3's buyer/lines field-alignment rule (which
# applies only to BRInvoice): `BRCTeDocument.buyer` is intentionally
# Optional[InvoiceParty]=None (no CT-e equivalent — see roadmap BR-CTE-5),
# and `lines` intentionally stays empty (freight-value components live
# under `v_prest.comp` instead). CHECK 3 never scans BRCTeDocument, so no
# override registration is needed — this comment documents the exemption
# for anyone tempted to extend CHECK 3 to cover it.


def run_check_8() -> CheckResult:
    """CHECK 8 — BRCTeDocument subclasses InvoiceDocument; CTeGenerator/
    CTeXSDValidator subclass the correct core ABCs; no local reimplementation."""
    result = CheckResult(check_id="CHECK_8", name="BRCTeDocument structural checks")

    mod, err = _try_import("mcp_nfe_br.models.cte")
    if mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.models.cte",
                message=f"Could not import CT-e model module: {err}",
            )
        )
        return result

    cte_cls = getattr(mod, "BRCTeDocument", None)
    if cte_cls is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="BRCTeDocument",
                message="BRCTeDocument class not found in mcp_nfe_br.models.cte.",
            )
        )
        return result

    # Must subclass InvoiceDocument (non-EN16931 pathway, same as BRInvoice/NFSeDocument)
    core_mod, _ = _try_import("mcp_einvoicing_core.models")
    invoice_doc_cls = getattr(core_mod, "InvoiceDocument", None) if core_mod else None
    if invoice_doc_cls is not None:
        is_subclass = issubclass(cte_cls, invoice_doc_cls)
        tag = "[OK]" if is_subclass else "[WRONG_BASE]"
        sev = SEVERITY_OK if is_subclass else SEVERITY_BLOCKING
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag=tag,
                severity=sev,
                symbol="BRCTeDocument",
                message=(
                    "BRCTeDocument correctly subclasses InvoiceDocument (non-EN16931 pathway)."
                    if is_subclass
                    else "BRCTeDocument must subclass InvoiceDocument from mcp_einvoicing_core.models."
                ),
            )
        )

    # Verify CTeGenerator subclasses BaseDocumentGenerator (no local reimplementation)
    gen_mod, gen_err = _try_import("mcp_nfe_br.standards.cte_generator")
    if gen_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.standards.cte_generator",
                message=f"CTeGenerator module missing: {gen_err}",
            )
        )
    else:
        from mcp_einvoicing_core import BaseDocumentGenerator

        gen_cls = getattr(gen_mod, "CTeGenerator", None)
        if gen_cls and issubclass(gen_cls, BaseDocumentGenerator):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="CTeGenerator",
                    message="CTeGenerator subclasses BaseDocumentGenerator.",
                )
            )
            _assert_concrete(result, "CHECK_8", gen_cls, "CTeGenerator")
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[WRONG_BASE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="CTeGenerator",
                    message="CTeGenerator must subclass BaseDocumentGenerator.",
                )
            )

    # Verify CTeXSDValidator subclasses BaseDocumentValidator
    val_mod, val_err = _try_import("mcp_nfe_br.validators.cte_xsd")
    if val_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.validators.cte_xsd",
                message=f"CTeXSDValidator module missing: {val_err}",
            )
        )
    else:
        from mcp_einvoicing_core import BaseDocumentValidator

        val_cls = getattr(val_mod, "CTeXSDValidator", None)
        if val_cls and issubclass(val_cls, BaseDocumentValidator):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="CTeXSDValidator",
                    message="CTeXSDValidator subclasses BaseDocumentValidator.",
                )
            )
            _assert_concrete(result, "CHECK_8", val_cls, "CTeXSDValidator")
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[WRONG_BASE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="CTeXSDValidator",
                    message="CTeXSDValidator must subclass BaseDocumentValidator.",
                )
            )

    # Verify SefazCTeClient subclasses BaseEInvoicingClient (reuses AuthMode.MTLS transport)
    client_mod, client_err = _try_import("mcp_nfe_br.standards.sefaz_cte_client")
    if client_mod is None:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_8",
                tag="[MISSING]",
                severity=SEVERITY_BLOCKING,
                symbol="mcp_nfe_br.standards.sefaz_cte_client",
                message=f"SefazCTeClient module missing: {client_err}",
            )
        )
    else:
        from mcp_einvoicing_core.http_client import BaseEInvoicingClient

        client_cls = getattr(client_mod, "SefazCTeClient", None)
        if client_cls and issubclass(client_cls, BaseEInvoicingClient):
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol="SefazCTeClient",
                    message="SefazCTeClient subclasses BaseEInvoicingClient.",
                )
            )
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_8",
                    tag="[WRONG_BASE]",
                    severity=SEVERITY_BLOCKING,
                    symbol="SefazCTeClient",
                    message="SefazCTeClient must subclass BaseEInvoicingClient.",
                )
            )

    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CHECK 7 — Parallel-implementation detector (Phase 0a.2)
# ---------------------------------------------------------------------------

_CORE_CAPABILITIES: list[tuple[str, str, list[str]]] = [
    (
        "cii_ubl_conversion",
        "mcp_einvoicing_core.convert",
        [
            "convert_wire_format",
        ],
    ),
    (
        "peppol_participant_lookup",
        "mcp_einvoicing_core.peppol",
        [
            "PeppolSMPClient",
        ],
    ),
    (
        "en16931_cii_parsing",
        "mcp_einvoicing_core.wire_formats",
        [
            "EN16931CIIParser",
            "EN16931CIISerializer",
        ],
    ),
    (
        "en16931_ubl_parsing",
        "mcp_einvoicing_core.wire_formats",
        [
            "EN16931UBLParser",
            "EN16931UBLSerializer",
        ],
    ),
    (
        "schematron_validation",
        "mcp_einvoicing_core.schematron",
        [
            "SchematronValidator",
        ],
    ),
    (
        "xades_xmldsig_signing",
        "mcp_einvoicing_core.digital_signature",
        [
            "XAdESEPESSigner",
            "XMLDSigSigner",
        ],
    ),
    (
        "http_client",
        "mcp_einvoicing_core.http_client",
        [
            "BaseEInvoicingClient",
        ],
    ),
    (
        "routing_identifier_validation",
        "mcp_einvoicing_core.routing",
        [
            "RoutingIdentifier",
        ],
    ),
    (
        "peppol_as4_transport",
        "mcp_einvoicing_core.peppol.transport",
        [
            "AS4MessageEnvelope",
            "AS4TransportClient",
            "PeppolTransmitter",
        ],
    ),
]

_INTENTIONAL_PARALLEL_IMPLEMENTATIONS: dict[tuple[str, str], str] = {}


def run_check_10() -> CheckResult:
    """CHECK 10 — Parallel-implementation scan."""
    import ast

    result = CheckResult(check_id="CHECK_10", name="Parallel-implementation detector")

    pkg_root = Path(__file__).parent.parent / "src" / "mcp_nfe_br"
    if not pkg_root.is_dir():
        result.findings.append(
            CheckFinding(
                check_id="CHECK_10",
                tag="[SKIP]",
                severity=SEVERITY_OK,
                symbol="mcp_nfe_br",
                message="Package source directory not found; skipping parallel-implementation scan.",
            )
        )
        return result

    defined_names: dict[str, str] = {}
    for py_file in pkg_root.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names[node.name] = str(py_file.relative_to(pkg_root.parent.parent))

    found_any = False
    for cap_tag, core_module, symbols in _CORE_CAPABILITIES:
        for symbol in symbols:
            if symbol not in defined_names:
                continue

            override_key = (cap_tag, symbol)
            if override_key in _INTENTIONAL_PARALLEL_IMPLEMENTATIONS:
                result.findings.append(
                    CheckFinding(
                        check_id="CHECK_10",
                        tag="[OVERRIDE]",
                        severity=SEVERITY_OK,
                        symbol=symbol,
                        message=(
                            f"Parallel implementation of {symbol} ({cap_tag}) in "
                            f"{defined_names[symbol]} is intentional: "
                            f"{_INTENTIONAL_PARALLEL_IMPLEMENTATIONS[override_key]}"
                        ),
                    )
                )
                continue

            found_any = True
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_10",
                    tag="[PARALLEL]",
                    severity=SEVERITY_WARNING,
                    symbol=symbol,
                    message=(
                        f"Country package defines {symbol!r} in {defined_names[symbol]}, "
                        f"which mirrors core capability {cap_tag!r} from {core_module}. "
                        "Delegate to the core symbol or register in "
                        "_INTENTIONAL_PARALLEL_IMPLEMENTATIONS with a justification."
                    ),
                )
            )

    if not found_any and not result.findings:
        result.findings.append(
            CheckFinding(
                check_id="CHECK_10",
                tag="[OK]",
                severity=SEVERITY_OK,
                symbol="*",
                message="No parallel implementations of core capabilities detected.",
            )
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 9 — Functional generate→XSD smoke check per sub-format (BR-L3)
# ---------------------------------------------------------------------------


def _smoke_nfe() -> tuple[str, bool, list[str]]:
    from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

    from mcp_nfe_br.models.invoice import (
        BREmitente,
        BREndereco,
        BRInvoice,
        BRInvoiceLine,
        BRPagamento,
        NFeModelo,
        RegimeTributario,
        TipoAmbiente,
        TipoOperacao,
    )
    from mcp_nfe_br.standards.nfe_generator import NFeGenerator
    from mcp_nfe_br.validators.nfe_xsd import NFeXSDValidator

    endereco = BREndereco.model_validate(
        {
            "x_lgr": "Rua Teste",
            "nro": "123",
            "x_bairro": "Centro",
            "c_mun": "3550308",
            "x_mun": "Sao Paulo",
            "uf": "SP",
            "cep": "01000000",
        }
    )
    emitente = BREmitente.model_validate(
        {
            "cnpj": "11222333000181",
            "x_nome": "Empresa Teste LTDA",
            "ender_emit": endereco,
            "ie": "123456789",
            "crt": RegimeTributario.REGIME_NORMAL,
        }
    )
    line = BRInvoiceLine.model_validate(
        {
            "line_number": 1,
            "description": "Produto Teste",
            "unit_price": "100.00",
            "total_price": "100.00",
            "c_prod": "P001",
            "ncm": "61091000",
            "cfop": "5102",
            "u_com": "UN",
            "q_com": "1",
            "v_un_com": "100.00",
            "v_prod": "100.00",
            "u_trib": "UN",
            "q_trib": "1",
            "v_un_trib": "100.00",
            "icms_cst": "00",
            "icms_rate": "18",
            "icms_amount": "18.00",
            "pis_cst": "01",
            "pis_amount": "1.65",
            "cofins_cst": "01",
            "cofins_amount": "7.60",
        }
    )
    doc = BRInvoice.model_validate(
        {
            "document_type": "55",
            "date": "2026-06-13",
            "number": "1",
            "seller": InvoiceParty(
                tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
                name="Empresa Teste LTDA",
            ),
            "buyer": InvoiceParty(
                tax_id=TaxIdentifier(country_code="BR", identifier="11144477735"),
                name="Cliente Teste",
            ),
            "modelo": NFeModelo.NFE,
            "serie": "1",
            "nnf": "1",
            "natureza_operacao": "Venda de mercadoria",
            "tipo_operacao": TipoOperacao.SAIDA,
            "c_uf": "35",
            "dh_emi": "2026-06-13T10:00:00-03:00",
            "id_dest": "1",
            "c_mun_fg": "3550308",
            "tp_amb": TipoAmbiente.HOMOLOGACAO,
            "ind_final": "1",
            "ind_pres": "1",
            "emitente": emitente,
            "destinatario": {"cpf": "11144477735", "x_nome": "Cliente Teste", "ind_ie_dest": "9"},
            "pagamentos": [BRPagamento(t_pag="01", v_pag="100.00")],
            "lines": [line],
        }
    )
    xml = NFeGenerator().generate(doc)
    result = NFeXSDValidator().validate(xml)
    return "NF-e", result.valid, result.errors


def _smoke_nfse() -> tuple[str, bool, list[str]]:
    from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

    from mcp_nfe_br.models.invoice import TipoAmbiente
    from mcp_nfe_br.models.nfse import (
        NFSeCServ,
        NFSeDocument,
        NFSeEndereco,
        NFSeLocPrest,
        NFSeOpSimplesNacional,
        NFSePrestador,
        NFSeRegimeTributacao,
        NFSeServ,
        NFSeTipoRetISSQN,
        NFSeTomador,
        NFSeTotTrib,
        NFSeTribISSQN,
        NFSeTribMunicipal,
        NFSeValores,
    )
    from mcp_nfe_br.standards.nfse_generator import NFSeGenerator
    from mcp_nfe_br.validators.nfse_xsd import NFSeXSDValidator

    endereco = NFSeEndereco.model_validate(
        {
            "x_lgr": "Rua Teste",
            "nro": "123",
            "x_bairro": "Centro",
            "c_mun": "3550308",
            "cep": "01000000",
        }
    )
    prestador = NFSePrestador.model_validate(
        {
            "cnpj": "11222333000181",
            "x_nome": "Prestador Teste LTDA",
            "end": endereco,
            "reg_trib": NFSeRegimeTributacao(
                op_simp_nac=NFSeOpSimplesNacional.NAO_OPTANTE, reg_esp_trib="0"
            ),
        }
    )
    tomador = NFSeTomador.model_validate(
        {
            "cpf": "11144477735",
            "x_nome": "Tomador Teste",
            "end": endereco,
        }
    )
    doc = NFSeDocument.model_validate(
        {
            "document_type": "DPS",
            "date": "2026-07-01",
            "number": "1",
            "seller": InvoiceParty(
                tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
                name="Prestador Teste LTDA",
            ),
            "buyer": InvoiceParty(
                tax_id=TaxIdentifier(country_code="BR", identifier="11144477735"),
                name="Tomador Teste",
            ),
            "tp_amb": TipoAmbiente.HOMOLOGACAO,
            "serie": "1",
            "n_dps": "1",
            "d_compet": "2026-07-01",
            "c_loc_emi": "3550308",
            "prest": prestador,
            "toma": tomador,
            "serv": NFSeServ(
                loc_prest=NFSeLocPrest(c_loc_prestacao="3550308"),
                c_serv=NFSeCServ(c_trib_nac="010101", x_desc_serv="Serviço de teste"),
            ),
            "valores": NFSeValores(
                v_serv="100.00",
                trib_mun=NFSeTribMunicipal(
                    trib_issqn=NFSeTribISSQN.TRIBUTAVEL,
                    tp_ret_issqn=NFSeTipoRetISSQN.NAO_RETIDO,
                    p_aliq="5.00",
                ),
                tot_trib=NFSeTotTrib(ind_tot_trib="0"),
            ),
        }
    )
    xml = NFSeGenerator().generate(doc)
    result = NFSeXSDValidator().validate(xml)
    return "NFS-e", result.valid, result.errors


def _smoke_cte() -> tuple[str, bool, list[str]]:
    from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

    from mcp_nfe_br.models.cte import (
        BRCTeDocument,
        BRCteEmitente,
        BRCteICMS00,
        BRCteImp,
        BRCteInfCarga,
        BRCteInfModal,
        BRCteInfQ,
        BRCteRemetente,
        BRCteTomador,
        BRCteVPrest,
        CTeModal,
        CTeModelo,
        CTeTipoServico,
        CTeTomadorPapel,
    )
    from mcp_nfe_br.models.invoice import BREndereco, RegimeTributario
    from mcp_nfe_br.standards.cte_generator import CTeGenerator
    from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator

    endereco = BREndereco.model_validate(
        {
            "x_lgr": "Rua Teste",
            "nro": "123",
            "x_bairro": "Centro",
            "c_mun": "3550308",
            "x_mun": "Sao Paulo",
            "uf": "SP",
            "cep": "01000000",
        }
    )
    emitente = BRCteEmitente.model_validate(
        {
            "cnpj": "11222333000181",
            "x_nome": "Transportadora Teste LTDA",
            "ie": "123456789",
            "endereco": endereco,
            "crt": RegimeTributario.REGIME_NORMAL,
        }
    )
    remetente = BRCteRemetente.model_validate(
        {
            "cnpj": "11444777000161",
            "x_nome": "Remetente Teste LTDA",
            "endereco": endereco,
        }
    )
    doc = BRCTeDocument.model_validate(
        {
            "document_type": "57",
            "date": "2026-07-03",
            "number": "1",
            "seller": InvoiceParty(
                tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
                name="Transportadora Teste LTDA",
            ),
            "mod": CTeModelo.CTE,
            "serie": "1",
            "n_ct": "1",
            "nat_op": "Prestação de serviço de transporte",
            "tp_serv": CTeTipoServico.NORMAL,
            "modal": CTeModal.RODOVIARIO,
            "dh_emi": "2026-07-03T10:00:00-03:00",
            "c_uf": "35",
            "cfop": "5352",
            "tp_amb": "2",
            "c_mun_ini": "3550308",
            "x_mun_ini": "Sao Paulo",
            "uf_ini": "SP",
            "c_mun_fim": "3304557",
            "x_mun_fim": "Rio de Janeiro",
            "uf_fim": "RJ",
            "retira": "1",
            "emitente": emitente,
            "remetente": remetente,
            "tomador": BRCteTomador(papel=CTeTomadorPapel.REMETENTE, ind_ie_toma="1"),
            "v_prest": BRCteVPrest(v_tprest="100.00", v_rec="100.00"),
            "imp": BRCteImp(icms=BRCteICMS00(v_bc="100.00", p_icms="12.00", v_icms="12.00")),
            "inf_carga": BRCteInfCarga(
                v_carga="1000.00",
                pro_pred="Eletrônicos",
                inf_q=[BRCteInfQ(c_unid="01", tp_med="PESO BRUTO", q_carga="100.0000")],
            ),
            "inf_modal": BRCteInfModal(modal=CTeModal.RODOVIARIO, rntrc="12345678"),
        }
    )
    xml = CTeGenerator().generate(doc)
    result = CTeXSDValidator().validate(xml)
    return "CT-e", result.valid, result.errors


def run_check_9() -> CheckResult:
    """CHECK 9 — Functional generate→XSD round-trip smoke check, one per sub-format.

    CHECK 6/8 only verify that generators/validators are the right *type*
    (subclass + concrete); neither exercises a real document. This is the
    check that would have caught BR-NFSE-C1..C5: every sub-format must
    build a minimal document, generate it, and XSD-validate the output
    (BR-L3).
    """
    result = CheckResult(check_id="CHECK_9", name="Functional generate→XSD smoke check")

    for smoke_fn in (_smoke_nfe, _smoke_nfse, _smoke_cte):
        try:
            sub_format, valid, errors = smoke_fn()
        except Exception as exc:  # noqa: BLE001 - any failure here is a gate finding
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_9",
                    tag="[SMOKE_ERROR]",
                    severity=SEVERITY_BLOCKING,
                    symbol=smoke_fn.__name__,
                    message=f"Generate→XSD smoke check raised: {type(exc).__name__}: {exc}",
                )
            )
            continue

        if valid:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_9",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol=sub_format,
                    message=f"{sub_format}: minimal document generates and validates against its bundled XSD.",
                )
            )
        else:
            result.findings.append(
                CheckFinding(
                    check_id="CHECK_9",
                    tag="[XSD_INVALID]",
                    severity=SEVERITY_BLOCKING,
                    symbol=sub_format,
                    message=f"{sub_format}: generated XML fails XSD validation: {'; '.join(errors)}",
                )
            )

    return result


def run_audit() -> AuditReport:
    """Execute all checks and return the aggregated AuditReport. No side effects."""
    report = make_report("mcp-nfe-br", _PYPROJECT)

    report.checks.append(
        run_check_core_coverage(
            package_name="mcp-nfe-br",
            package_modules=_BR_MODULES,
            intentional_overrides=_INTENTIONAL_OVERRIDES,
            is_en16931_family=_IS_EN16931_FAMILY,
            primary_invoice_class=_PRIMARY_INVOICE_CLASS,
        )
    )
    report.checks.append(run_check_2())
    report.checks.append(run_check_3())
    report.checks.append(
        run_check_version_compatibility(
            package_name="mcp-nfe-br",
            pyproject_path=_PYPROJECT,
        )
    )
    report.checks.append(run_check_5())
    report.checks.append(run_check_6())
    report.checks.append(
        run_check_resource_paths(
            package_root=_PACKAGE_ROOT,
            resource_paths=_RESOURCE_PATHS,
        )
    )
    report.checks.append(run_check_8())
    report.checks.append(run_check_9())
    report.checks.append(run_check_10())

    report.checks.append(run_check_no_internal_references(repo_root=_PYPROJECT.parent))

    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_audit_args("Pre-publish audit: mcp-nfe-br vs mcp-einvoicing-core", argv)
    report = run_audit()

    output_path = Path(args.output) if args.output else Path("audit/report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    if not args.quiet:
        print(render_summary_table(report))
        print(f"\nJSON report written to: {output_path}")

    if args.fail_on == "never":
        return 0
    if args.fail_on == "warnings":
        return min(report.exit_code, 2)
    return 2 if report.total_blocking > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
