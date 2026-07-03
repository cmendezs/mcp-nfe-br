"""CT-e (modelo 57) generation and XSD validation tools (roadmap BR-CTE-9).

v1 scope: modal rodoviário only, ICMS CST 00 only — see
`mcp_nfe_br.standards.cte_generator` module docstring.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp_einvoicing_core.exceptions import EInvoicingError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.cte import BRCTeDocument
from mcp_nfe_br.standards.cte_generator import CTeGenerator
from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator


def br__generate_cte(
    cte: Annotated[dict[str, Any], "CT-e data matching the BRCTeDocument schema (modelo 57)"],
) -> dict[str, object]:
    """Generate an unsigned CT-e XML (modelo 57, schema 4.00).

    v1 supports modal rodoviário only and ICMS CST 00 (tributação normal)
    only — other modais/CSTs raise an error. The returned
    `<CTe><infCte>…</infCte></CTe>` document does not include
    `<Signature>` — sign it with `br__sign_cte` (roadmap BR-CTE-6 factory,
    tool not yet registered) before SEFAZ submission.

    Returns a dict with:
    - ``xml``: the generated CT-e XML string
    - ``chave_acesso``: the computed 44-character access key (chCTe)
    - ``warnings``: list of non-fatal notices
    """
    document = BRCTeDocument.model_validate(cte)

    try:
        xml_string = CTeGenerator().generate(document)
    except EInvoicingError as exc:
        return {"error": str(exc)}

    chave_acesso = xml_string.split('Id="CTe', 1)[1].split('"', 1)[0]

    warnings: list[str] = [
        "Documento não assinado (use um certificado ICP-Brasil A1 antes da submissão à SEFAZ).",
        "Documento não transmitido à SEFAZ (submissão via webservice não implementada nesta fase).",
        "v1 suporta apenas modal rodoviário e ICMS CST 00 [NEED: extend — ver roadmap BR-CTE-8].",
    ]

    return {"xml": xml_string, "chave_acesso": chave_acesso, "warnings": warnings}


def br__validate_cte_xml(
    xml_content: Annotated[
        str | None, "Raw CT-e XML string. Provide either xml_content or xml_base64."
    ] = None,
    xml_base64: Annotated[
        str | None, "Base64-encoded CT-e XML bytes."
    ] = None,
) -> dict[str, object]:
    """Validate a CT-e XML (modelo 57, schema 4.00) against the bundled PL_CTe_400 XSD.

    `CTeXSDValidator` selects the schema automatically: documents without a
    `<ds:Signature>` are validated against the unsigned derivative; signed
    documents are validated against the unmodified official schema, which
    requires `<ds:Signature>`.

    Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"valid": False, "errors": [str(exc)]}

    return CTeXSDValidator().validate(xml_bytes).to_dict()
