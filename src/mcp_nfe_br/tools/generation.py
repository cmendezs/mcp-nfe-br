"""NF-e/NFC-e generation, XSD validation, and access-key tools."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from mcp_einvoicing_core.exceptions import EInvoicingError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.invoice import BRInvoice
from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from mcp_nfe_br.standards.nfe_signer import build_nfe_signer
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
    `<Signature>` — sign it with `br__sign_nfe` before SEFAZ submission.
    SEFAZ webservice submission itself is not implemented in this phase.

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
        "Documento não assinado (use br__sign_nfe com um certificado ICP-Brasil A1 antes da submissão à SEFAZ).",
        "Documento não transmitido à SEFAZ (submissão via webservice não implementada nesta fase).",
        (
            "[BR-TL-4/BR-INV-2] NT 2025.002-RTC v1.50, regra UB12-10 (Grupo UB — IBS/CBS/IS "
            "item-level) torna-se obrigatória: homologação a partir de NF-e com dhEmi >= "
            "2026-07-01 (CRT 3=Regime Normal); produção a partir de dhEmi >= 2026-08-03 (CRT "
            "3); produção a partir de 2027-01-04 para CRT 1/2/4 (Simples Nacional/MEI). "
            "Exceções: NF-e de devolução/complementar referenciando original anterior a 2026; "
            "itens na tabela de combustíveis sujeitos à tributação monofásica (cProdANP). "
            "[NEED: remover este aviso após 2026-08-03, ou antes se NT 2025.002 v1.51+ alterar "
            "novamente a data]"
        ),
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

    `NFeXSDValidator` selects the schema automatically: documents without a
    `<ds:Signature>` are validated against the unsigned derivative; signed
    documents (produced by `br__sign_nfe`) are validated against the
    unmodified official schema, which requires `<ds:Signature>`.

    Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"valid": False, "errors": [str(exc)]}

    return NFeXSDValidator().validate(xml_bytes).to_dict()


def br__sign_nfe(
    cert_path: Annotated[
        str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"
    ],
    xml_content: Annotated[
        str | None, "XML NF-e/NFC-e não assinado. Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[
        str | None, "XML NF-e/NFC-e não assinado, codificado em base64."
    ] = None,
    cert_password: Annotated[
        str | None, "Senha do certificado A1, se houver"
    ] = None,
) -> dict[str, object]:
    """Apply an ICP-Brasil enveloped XML-DSig signature to an NF-e/NFC-e XML.

    Signs `<infNFe>` per MOC 7.0 Table 4-2 (RSA-SHA1 / SHA-1, enveloped
    transform, `ds:Signature` appended as the last child of `<NFe>`) using
    `mcp_nfe_br.standards.nfe_signer.build_nfe_signer`.

    Only ICP-Brasil A1 (PKCS#12 file-based) certificates are supported.
    A3 (hardware token/HSM) certificates `[NEED: not modeled]`.

    Returns a dict with ``xml`` (the signed document) or ``error``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"error": str(exc)}

    signer = build_nfe_signer(cert_path, cert_password)
    try:
        signed_xml = signer.sign(xml_bytes)
    except (ImportError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    return {"xml": signed_xml.decode("utf-8")}


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
