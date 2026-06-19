"""NFS-e Nacional (ADN) generation, validation, signing, and submission tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.exceptions import EInvoicingError, PlatformError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.models.nfse import NFSeDocument
from mcp_nfe_br.standards.adn_client import ADNClient
from mcp_nfe_br.standards.govbr_auth import build_govbr_oauth
from mcp_nfe_br.standards.nfse_generator import NFSeGenerator
from mcp_nfe_br.standards.nfse_signer import build_nfse_signer
from mcp_nfe_br.validators.nfse_xsd import NFSeXSDValidator

_READ_ONLY_ENV_VAR = "BR_READ_ONLY"


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


async def br__submit_nfse(
    client_id: Annotated[str, "Client ID OAuth2 gov.br (registrado no portal de desenvolvedores)"],
    client_secret: Annotated[str, "Client Secret OAuth2 gov.br"],
    xml_content: Annotated[
        str | None, "DPS assinado (saída de br__sign_nfse). Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[str | None, "DPS assinado codificado em base64."] = None,
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    scope: Annotated[str | None, "OAuth2 scope override (padrão: 'openid govbr_empresa')"] = None,
    endpoint_override: Annotated[
        str | None, "URL base do ADN (sobrepõe a URL padrão por ambiente)"
    ] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Submeter um DPS assinado ao ADN para geração da NFS-e Nacional.

    Submissão ao ADN é uma operação irreversível em produção e exige
    confirmação em duas etapas (``ConfirmationGate``). Defina ``BR_READ_ONLY=1``
    para desabilitar esta ferramenta.

    `[Unverified — endpoint ADN, formato de requisição e resposta são inferidos
    de fontes secundárias. Verifique no manual ADN antes do uso em produção.]`

    Retorna campos de status do ADN (``cStat``, ``xMotivo``) e opcionalmente
    o XML da NFS-e gerada (``nfse_xml``).
    """
    try:
        xml_bytes = resolve_xml_input(xml_content, xml_base64)
    except (ValueError, EInvoicingError) as exc:
        return {"error": str(exc)}

    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    try:
        assert_not_read_only(_READ_ONLY_ENV_VAR)
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__submit_nfse",
            summary=(
                f"Submeter DPS ao ADN NFS-e Nacional ({env_label}). "
                "Documentos gerados em produção tornam-se fiscalmente válidos "
                "e não podem ser retratados."
            ),
            token=confirmation_token,
        )

    oauth = build_govbr_oauth(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        homologacao=(ambiente == TipoAmbiente.HOMOLOGACAO),
    )
    client = ADNClient(
        tp_amb=ambiente,
        oauth=oauth,
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.submit_dps(xml_bytes)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result


async def br__consult_nfse_status(
    ch_nfse: Annotated[str, "Chave de acesso da NFS-e (53 caracteres, formato NFS[0-9]{50})"],
    client_id: Annotated[str, "Client ID OAuth2 gov.br"],
    client_secret: Annotated[str, "Client Secret OAuth2 gov.br"],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    scope: Annotated[str | None, "OAuth2 scope override"] = None,
    endpoint_override: Annotated[str | None, "URL base do ADN override"] = None,
) -> dict[str, object]:
    """Consultar o status de uma NFS-e pelo chave de acesso (chNFSe).

    Read-only, não requer confirmação.

    `[Unverified — endpoint e formato de resposta são inferidos.]`
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    oauth = build_govbr_oauth(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        homologacao=(ambiente == TipoAmbiente.HOMOLOGACAO),
    )
    client = ADNClient(
        tp_amb=ambiente,
        oauth=oauth,
        endpoint_override=endpoint_override,
    )
    try:
        return await client.consult_nfse(ch_nfse)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}


async def br__cancel_nfse(
    ch_nfse: Annotated[str, "Chave de acesso da NFS-e a cancelar (53 caracteres)"],
    motivo: Annotated[str, "Motivo do cancelamento (texto livre)"],
    client_id: Annotated[str, "Client ID OAuth2 gov.br"],
    client_secret: Annotated[str, "Client Secret OAuth2 gov.br"],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    scope: Annotated[str | None, "OAuth2 scope override"] = None,
    endpoint_override: Annotated[str | None, "URL base do ADN override"] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Solicitar cancelamento de uma NFS-e no ADN.

    Cancelamento é uma operação irreversível e exige confirmação em duas
    etapas (``ConfirmationGate``). Defina ``BR_READ_ONLY=1`` para desabilitar.

    `[Unverified — endpoint e formato de requisição são inferidos.]`
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    try:
        assert_not_read_only(_READ_ONLY_ENV_VAR)
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__cancel_nfse",
            summary=(
                f"Cancelar NFS-e {ch_nfse} no ADN ({env_label}). "
                "Cancelamento em produção é irreversível."
            ),
            token=confirmation_token,
        )

    oauth = build_govbr_oauth(
        client_id=client_id,
        client_secret=client_secret,
        scope=scope,
        homologacao=(ambiente == TipoAmbiente.HOMOLOGACAO),
    )
    client = ADNClient(
        tp_amb=ambiente,
        oauth=oauth,
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.cancel_nfse(ch_nfse, motivo)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result
