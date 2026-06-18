"""NFS-e Nacional (ADN) generation, validation, and signing tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp_einvoicing_core.exceptions import EInvoicingError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.nfse import NFSeDocument
from mcp_nfe_br.standards.nfse_generator import NFSeGenerator
from mcp_nfe_br.standards.nfse_signer import build_nfse_signer
from mcp_nfe_br.validators.nfse_xsd import NFSeXSDValidator


def br__generate_nfse(
    dps: Annotated[
        dict[str, Any],
        "DPS data matching the NFSeDocument schema (NFS-e Nacional, ADN, schema v1.01)",
    ],
) -> dict[str, object]:
    """Gerar um DPS não assinado para NFS-e Nacional (ADN), schema v1.01.

    O DPS (Declaração de Prestação de Serviços) gerado não contém
    ``<ds:Signature>`` — assine-o com ``br__sign_nfse`` antes de submeter
    ao ADN via ``br__submit_nfse``.

    Returns a dict with:
    - ``xml``: the generated unsigned DPS XML string
    - ``dps_id``: the 45-character DPS Id (``infDPS Id`` attribute)
    - ``warnings``: list of non-fatal notices
    """
    try:
        document = NFSeDocument.model_validate(dps)
    except Exception as exc:
        return {"error": f"Erro na validação do modelo NFSeDocument: {exc}"}

    try:
        xml_string = NFSeGenerator().generate(document)
    except EInvoicingError as exc:
        return {"error": str(exc)}

    dps_id = xml_string.split('Id="DPS', 1)[1].split('"', 1)[0]
    dps_id = "DPS" + dps_id

    warnings: list[str] = [
        "DPS não assinado — use br__sign_nfse com um certificado ICP-Brasil A1 antes da submissão ao ADN.",
        "DPS não transmitido ao ADN — use br__submit_nfse após assinatura.",
        (
            "[BR-NFSE-6/Unverified] O algoritmo de assinatura para NFS-e Nacional "
            "não foi verificado no manual ADN. br__sign_nfse usa RSA-SHA1 (padrão NF-e). "
            "Confirme em manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf antes "
            "de usar em produção."
        ),
    ]

    return {"xml": xml_string, "dps_id": dps_id, "warnings": warnings}


def br__validate_nfse_xml(
    xml_content: Annotated[
        str | None, "XML DPS ou NFSe como string. Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[
        str | None, "XML DPS ou NFSe codificado em base64."
    ] = None,
) -> dict[str, object]:
    """Validar um DPS ou NFSe contra o XSD v1.01 do ADN.

    Seleciona automaticamente o schema com base no elemento raiz:
    - ``<DPS>`` → valida contra ``DPS_v1.01.xsd`` (``<ds:Signature>`` opcional)
    - ``<NFSe>`` → valida contra ``NFSe_v1.01.xsd`` (``<ds:Signature>`` obrigatória)

    Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"valid": False, "errors": [str(exc)]}

    return NFSeXSDValidator().validate(xml_bytes).to_dict()


def br__sign_nfse(
    cert_path: Annotated[
        str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"
    ],
    xml_content: Annotated[
        str | None, "DPS não assinado (saída de br__generate_nfse). Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[
        str | None, "DPS não assinado codificado em base64."
    ] = None,
    cert_password: Annotated[
        str | None, "Senha do certificado A1, se houver"
    ] = None,
) -> dict[str, object]:
    """Aplicar assinatura XML-DSig ICP-Brasil ao DPS da NFS-e Nacional.

    Assina o elemento ``<infDPS>`` com enveloped ``ds:Signature`` adicionada
    como último filho de ``<DPS>``, usando
    ``mcp_nfe_br.standards.nfse_signer.build_nfse_signer``.

    Algoritmo: RSA-SHA1 (padrão XMLDSigSigner).
    `[Unverified para NFS-e Nacional — confirme no manual ADN antes de usar em produção.]`

    Somente certificados A1 (PKCS#12 em arquivo) são suportados.
    A3 (hardware token/HSM) `[NEED: não modelado]`.

    Returns a dict with ``xml`` (the signed DPS) or ``error``.
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"error": str(exc)}

    signer = build_nfse_signer(cert_path, cert_password)
    try:
        signed_xml = signer.sign(xml_bytes)
    except (ImportError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    return {"xml": signed_xml.decode("utf-8")}
