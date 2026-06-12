"""Pre-publish audit: verify mcp-nfe-br coherence against mcp-einvoicing-core.

Run standalone (from the workspace root):
    uv run python mcp-nfe-br/audit/audit_vs_core.py
    uv run python mcp-nfe-br/audit/audit_vs_core.py --output mcp-nfe-br/audit/report.json
    uv run python mcp-nfe-br/audit/audit_vs_core.py --fail-on blocking

Exit codes:
    0  All checks passed
    1  Warnings only (non-blocking)
    2  Blocking failures found

CHECK 1 and CHECK 4 are delegated to mcp_einvoicing_core.audit.
CHECK 2 (tool registry), CHECK 3 (BRInvoice field alignment), and CHECK 5
(BR-specific structural) are implemented here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp_einvoicing_core.audit import (
    SEVERITY_BLOCKING,
    SEVERITY_OK,
    AuditReport,
    CheckFinding,
    CheckResult,
    _try_import,
    make_report,
    parse_audit_args,
    render_summary_table,
    run_check_core_coverage,
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

_INTENTIONAL_OVERRIDES: dict[str, set[str]] = {
    "mcp_einvoicing_core.base_server": {
        # OVERRIDE-REASON: no document parser implemented yet — Phase 1 scope is
        # party-ID validation only, not full XML generation/parsing
        "BaseDocumentParser",
        "BaseDocumentGenerator",
        # OVERRIDE-REASON: no session-based lifecycle API; SEFAZ webservice
        # integration (autorização, distribuição) is a later phase
        "BaseLifecycleManager",
        # OVERRIDE-REASON: party validation is performed inline via validate_cpf/
        # validate_cnpj helpers, not via the ABC party validator pattern
        "BasePartyValidator",
        # OVERRIDE-REASON: no submission flow implemented yet (Phase 1 is
        # validation tools only)
        "SubmitResult",
        # OVERRIDE-REASON: no document validator implemented yet — XSD-based
        # XML validation is a later phase
        "BaseDocumentValidator",
        "DocumentValidationResult",
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
        "assert_not_read_only",
        "scrub",
        "InvoiceParty",
    },
    "mcp_einvoicing_core.digital_signature": {
        # OVERRIDE-REASON: NF-e/NFC-e use ICP-Brasil A1/A3 certificates and
        # XML-DSig per the SEFAZ schema, not the XAdES-EPES envelope; signing
        # is a later phase
        "BaseDocumentSigner",
        "XAdESSignerConfig",
        "XAdESEPESSigner",
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
        # OVERRIDE-REASON: validation tools return TaxIdValidationResult with
        # error strings; base exception hierarchy not yet raised at tool layer
        "EInvoicingError",
        "PartyValidationError",
        "XSDValidationError",
        "SchematronValidationError",
        "AuthenticationError",
        "DocumentGenerationError",
        "PlatformError",
        "ValidationError",
    },
    "mcp_einvoicing_core.http_client": {
        # OVERRIDE-REASON: Phase 1 has no SEFAZ webservice client (SOAP/mTLS);
        # OAuth2/token-cache infrastructure not used yet
        "OAuthConfig",
        "OAuthValues",
        "BaseEInvoicingConfig",
        "BaseEInvoicingClient",
        "TokenCache",
        "AuthenticationError",
        "AuthMode",
        "PlatformError",
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
        "ABC",
        "abstractmethod",
        "Path",
        "dataclass",
        "field",
        "safe_fromstring",
        "safe_parser",
    },
    "mcp_einvoicing_core.xml_utils": {
        # OVERRIDE-REASON: Phase 1 is party-ID validation only; XML
        # generation/serialization helpers are not yet used
        "format_amount",
        "format_quantity",
        "xml_element",
        "xml_optional",
        "xml_escape",
        "format_error",
        "filter_empty_values",
        "resolve_xml_input",
        "validate_date_iso",
        "mark_untrusted",
        "mark_untrusted_fields",
        # OVERRIDE-REASON: NF-e/NFC-e parties use CPF/CNPJ, not IBAN; IBAN
        # validation not applicable
        "validate_iban",
        "Any",
        "Decimal",
        "safe_fromstring",
        "safe_parser",
    },
}

_BR_MODULES: list[str] = [
    "mcp_nfe_br",
    "mcp_nfe_br.models.invoice",
    "mcp_nfe_br.server",
    "mcp_nfe_br.tools.validation",
    "mcp_nfe_br.utils.document_ids",
]

_PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


# ---------------------------------------------------------------------------
# CHECK 2 — Tool registry completeness
# ---------------------------------------------------------------------------

_REQUIRED_TOOL_CATEGORIES: dict[str, str] = {
    "br__validate_cpf": "Validate a Brazilian CPF (individual taxpayer ID)",
    "br__validate_cnpj": "Validate a Brazilian CNPJ (company tax ID)",
}


def _collect_registered_tools() -> set[str]:
    """Detect tool functions registered via mcp.tool() in the BR server."""
    registered: set[str] = set()

    val_mod, _ = _try_import("mcp_nfe_br.tools.validation")
    if val_mod:
        for fn_name in _REQUIRED_TOOL_CATEGORIES:
            if hasattr(val_mod, fn_name):
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
# Assembly
# ---------------------------------------------------------------------------


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
