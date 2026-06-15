"""SEFAZ webservice tools: autorização, status de serviço, distribuição DF-e.

All tools here are mutating/network operations (submit and consult against
real SEFAZ infrastructure) and are gated with `assert_not_read_only` +
`ConfirmationGate`, following the `mcp-facturacion-electronica-es` SII
precedent. End-to-end verification requires a real ICP-Brasil A1 test
certificate against a homologation environment (`tpAmb=2`)
`[NEED: manual verification with real certificate]`.
"""

from __future__ import annotations

from typing import Annotated

from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.exceptions import EInvoicingError, PlatformError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.sefaz_client import SefazClient

_READ_ONLY_ENV_VAR = "BR_READ_ONLY"


async def br__consult_sefaz_status(
    c_uf: Annotated[str, "Código IBGE da UF do autorizador (cUF), 2 dígitos"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    endpoint_override: Annotated[
        str | None,
        "URL completa do webservice NFeStatusServico4 (sobrepõe a tabela de roteamento por UF)",
    ] = None,
) -> dict[str, object]:
    """Consulta a disponibilidade do webservice SEFAZ (`NFeStatusServico4`).

    Read-only — não requer confirmação. Retorna `cStat`/`xMotivo` (`cStat=107`
    indica serviço em operação `[Unverified]`).
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    client = SefazClient(
        cuf=c_uf,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="status_servico",
        endpoint_override=endpoint_override,
    )
    try:
        return await client.consultar_status_servico()
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}


async def br__submit_nfe(
    c_uf: Annotated[str, "Código IBGE da UF do autorizador (cUF), 2 dígitos"],
    id_lote: Annotated[str, "Identificador do lote (idLote), até 15 dígitos"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    xml_content: Annotated[
        str | None, "XML NF-e/NFC-e assinado (saída de br__sign_nfe). Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[str | None, "XML NF-e/NFC-e assinado, codificado em base64."] = None,
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    endpoint_override: Annotated[
        str | None,
        "URL completa do webservice NFeAutorizacao4 (sobrepõe a tabela de roteamento por UF)",
    ] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Submete um NF-e/NFC-e assinado à autorização SEFAZ (`NFeAutorizacao4`, síncrono).

    Submissão para SEFAZ é uma operação irreversível em produção e exige
    confirmação em duas etapas (`ConfirmationGate`). Define `BR_READ_ONLY=1`
    para desabilitar esta ferramenta.

    Retorna `protNFe` (incluindo `nProt`, o `protocolo de autorização`) em
    caso de sucesso, ou `error`.
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
            action="br__submit_nfe",
            summary=(
                f"Submeter NF-e/NFC-e (lote {id_lote}) à autorização SEFAZ "
                f"({env_label}, cUF={c_uf}). Documentos autorizados em produção "
                "tornam-se fiscalmente válidos e não podem ser retratados."
            ),
            token=confirmation_token,
        )

    client = SefazClient(
        cuf=c_uf,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="autorizacao",
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.autorizar_nfe(xml_bytes, id_lote)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result


async def br__distribute_dfe(
    c_uf_autor: Annotated[str, "Código IBGE da UF autorizadora (cUFAutor), 2 dígitos"],
    document_id: Annotated[str, "CNPJ ou CPF do interessado"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    document_id_type: Annotated[str, "Tipo de document_id: 'CNPJ' ou 'CPF'"] = "CNPJ",
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    ult_nsu: Annotated[
        str | None, "distNSU/ultNSU — último NSU recebido (modo distribuição em lote)"
    ] = None,
    nsu: Annotated[str | None, "consNSU/NSU — NSU específico a consultar"] = None,
    ch_nfe: Annotated[str | None, "consChNFe/chNFe — chave de acesso (44 caracteres) a consultar"] = None,
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    endpoint_override: Annotated[
        str | None,
        "URL completa do webservice NFeDistribuicaoDFe (sobrepõe o endpoint do Ambiente Nacional)",
    ] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Consulta/distribui DF-e via `NFeDistribuicaoDFe` (`NT2014.002_v1.30`, `[Verified locally]`).

    Exatamente um de `ult_nsu`, `nsu`, ou `ch_nfe` deve ser informado,
    selecionando `distNSU`, `consNSU`, ou `consChNFe` respectivamente.

    Esta ferramenta consulta dados fiscais de terceiros vinculados ao
    certificado e requer confirmação em duas etapas. Define
    `BR_READ_ONLY=1` para desabilitar.
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    modes = [m for m in (ult_nsu, nsu, ch_nfe) if m is not None]
    if len(modes) != 1:
        return {"error": "Informe exatamente um de ult_nsu, nsu, ou ch_nfe."}

    try:
        assert_not_read_only(_READ_ONLY_ENV_VAR)
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__distribute_dfe",
            summary=(
                f"Consultar NFeDistribuicaoDFe para {document_id_type}={document_id} "
                f"({env_label}). Retorna documentos fiscais associados ao certificado."
            ),
            token=confirmation_token,
        )

    client = SefazClient(
        cuf=c_uf_autor,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="distribuicao_dfe",
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.distribuir_dfe(
            document_id,
            document_id_type=document_id_type,
            ult_nsu=ult_nsu,
            nsu=nsu,
            ch_nfe=ch_nfe,
        )
    except (PlatformError, OSError, ValueError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result
