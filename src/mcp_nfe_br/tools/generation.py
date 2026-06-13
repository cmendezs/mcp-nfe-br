"""NF-e/NFC-e generation, XSD validation, and access-key tools."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from mcp_einvoicing_core.exceptions import EInvoicingError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.invoice import BRInvoice
from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from mcp_nfe_br.utils.access_key import build_access_key
from mcp_nfe_br.validators.nfe_xsd import NFeXSDValidator


def br__generate_nfe(
    invoice: Annotated[
        dict[str, Any],
        "Invoice data matching the BRInvoice schema (modelo 55 = NF-e, modelo 65 = NFC-e)",
    ],
) -> dict[str, object]:
    """Generate an unsigned NF-e/NFC-e XML (modelo 55/65, schema 4.00).

    The returned `<NFe><infNFe>…</infNFe></NFe>` document does not include
    `<Signature>` — ICP-Brasil XML-DSig signing and SEFAZ webservice
    submission are not implemented in this phase.

    Returns a dict with:
    - ``xml``: the generated NF-e/NFC-e XML string
    - ``chave_acesso``: the computed 44-character access key (chNFe)
    - ``warnings``: list of non-fatal notices
    """
    document = BRInvoice.model_validate(invoice)

    try:
        xml_string = NFeGenerator().generate(document)
    except EInvoicingError as exc:
        return {"error": str(exc)}

    chave_acesso = xml_string.split('Id="NFe', 1)[1].split('"', 1)[0]

    warnings: list[str] = [
        "Documento não assinado (ICP-Brasil XML-DSig não implementado nesta fase).",
        "Documento não transmitido à SEFAZ (submissão via webservice não implementada nesta fase).",
    ]

    return {"xml": xml_string, "chave_acesso": chave_acesso, "warnings": warnings}


def br__validate_nfe_xml(
    xml_content: Annotated[
        str | None, "Raw NF-e/NFC-e XML string. Provide either xml_content or xml_base64."
    ] = None,
    xml_base64: Annotated[
        str | None, "Base64-encoded NF-e/NFC-e XML bytes."
    ] = None,
) -> dict[str, object]:
    """Validate an NF-e/NFC-e XML (modelo 55/65, schema 4.00) against the bundled PL_010d XSD.

    Validates the unsigned `<NFe><infNFe>…</infNFe></NFe>` structure (the
    `<Signature>` element, if present, is not required by the bundled
    schema variant — see ``NFeXSDValidator``).

    Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"valid": False, "errors": [str(exc)]}

    return NFeXSDValidator().validate(xml_bytes).to_dict()


def br__build_access_key(
    c_uf: Annotated[str, "Código IBGE da UF do emitente (2 dígitos)"],
    dh_emi: Annotated[str, "Data e hora de emissão (ISO 8601, com fuso horário)"],
    cnpj: Annotated[
        str, "CNPJ do emitente: 14 dígitos numéricos (PL_010c) ou 12 alfanuméricos + 2 dígitos (PL_010d)"
    ],
    modelo: Annotated[str, "Modelo do documento fiscal: '55' (NF-e) ou '65' (NFC-e)"],
    serie: Annotated[str, "Série do documento fiscal"],
    nnf: Annotated[str, "Número do documento fiscal (nNF)"],
    tp_emis: Annotated[str, "Forma de emissão (tpEmis): '1' = normal"] = "1",
    c_nf: Annotated[
        str | None, "Código numérico aleatório de 8 dígitos (cNF). Gerado se omitido."
    ] = None,
) -> dict[str, object]:
    """Assemble and check-digit a 44-character NF-e/NFC-e access key (chNFe).

    Returns a dict with ``chave_acesso`` (44 characters) and ``cnf`` (the
    8-digit random code used, whether provided or generated).
    """
    cnf_value = c_nf or f"{secrets.randbelow(10**8):08d}"

    try:
        chave_acesso = build_access_key(
            cuf=c_uf,
            dh_emi=dh_emi,
            cnpj=cnpj,
            modelo=modelo,
            serie=serie,
            nnf=nnf,
            tp_emis=tp_emis,
            cnf=cnf_value,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    return {"chave_acesso": chave_acesso, "cnf": cnf_value}
