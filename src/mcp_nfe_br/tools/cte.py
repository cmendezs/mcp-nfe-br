"""CT-e (modelo 57) generation, XSD validation, and SEFAZ tools.

Generation/validation tools are v1 scope: modal rodoviário only, ICMS CST 00
only — see `mcp_nfe_br.standards.cte_generator` module docstring
(roadmap BR-CTE-9).

`br__submit_cte`, `br__cancel_cte`, and `br__correct_cte` (roadmap
BR-CTE-12, BR-CTE-14/15) are mutating/network operations against real
SEFAZ infrastructure and are gated with `assert_not_read_only` +
`ConfirmationGate`, mirroring `mcp_nfe_br.tools.sefaz`. `br__consult_cte`
and `br__consult_cte_sefaz_status` are read-only. No CT-e endpoint URLs
are bundled/verified in this version — callers must always pass
`endpoint_override` (`SefazCTeClient`/`get_cte_endpoint` docstring).
`br__distribute_cte_dfe` is not implemented — see roadmap BR-CTE-13.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.exceptions import EInvoicingError, PlatformError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.cte import BRCTeDocument
from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.cte_events import build_cancelamento_event_xml, build_correcao_event_xml
from mcp_nfe_br.standards.cte_generator import CTeGenerator
from mcp_nfe_br.standards.cte_signer import build_cte_event_signer
from mcp_nfe_br.standards.sefaz_cte_client import SefazCTeClient
from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator

_READ_ONLY_ENV_VAR = "BR_CTE_READ_ONLY"
_MASTER_READ_ONLY_ENV_VAR = "BR_READ_ONLY"


def _assert_cte_not_read_only() -> None:
    """Block CT-e mutating tools when either read-only switch is set (BR-S1).

    `BR_READ_ONLY` is the package-wide master switch (already honored by the
    NF-e and NFS-e mutating tools); `BR_CTE_READ_ONLY` is the CT-e-specific
    gate. Either being truthy blocks — a "safe demo" operator who sets only
    `BR_READ_ONLY=1` must not leave CT-e submit/cancel/correct callable.
    """
    assert_not_read_only(_MASTER_READ_ONLY_ENV_VAR)
    assert_not_read_only(_READ_ONLY_ENV_VAR)


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
    try:
        document = BRCTeDocument.model_validate(cte)
    except Exception as exc:
        return {"error": f"Erro na validação do modelo BRCTeDocument: {exc}"}

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


async def br__consult_cte_sefaz_status(
    c_uf: Annotated[str, "Código IBGE da UF do autorizador (cUF), 2 dígitos"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    endpoint_override: Annotated[
        str, "URL completa do webservice CTeStatusServicoV4 — obrigatório, ver docstring do módulo."
    ],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
) -> dict[str, object]:
    """Consulta a disponibilidade do webservice SEFAZ CT-e (`CTeStatusServicoV4`).

    Read-only — não requer confirmação. Nenhuma URL de endpoint CT-e está
    embutida/verificada nesta versão — `endpoint_override` é obrigatório
    (ver `mcp_nfe_br.standards.sefaz_cte_client` docstring).

    Retorna `cStat`/`xMotivo` (`cStat=107` indica serviço em operação
    `[Unverified]`, mesmo código do padrão NF-e).
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    client = SefazCTeClient(
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


async def br__consult_cte(
    ch_cte: Annotated[str, "Chave de acesso do CT-e (chCTe), 44 caracteres"],
    c_uf: Annotated[str, "Código IBGE da UF do autorizador (cUF), 2 dígitos"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    endpoint_override: Annotated[
        str, "URL completa do webservice CTeConsultaV4 — obrigatório, ver docstring do módulo."
    ],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
) -> dict[str, object]:
    """Consulta a situação de um CT-e por chave de acesso (`CTeConsultaV4`).

    Read-only — não requer confirmação (consulta um CT-e específico e já
    conhecido pela chave de acesso, não um lote de dados fiscais de
    terceiros — diferente de `br__distribute_dfe` no NF-e). Nenhuma URL de
    endpoint CT-e está embutida/verificada nesta versão —
    `endpoint_override` é obrigatório.

    Retorna `cStat`/`xMotivo`/`protCTe` (quando aplicável) ou `error`.
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    client = SefazCTeClient(
        cuf=c_uf,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="consulta",
        endpoint_override=endpoint_override,
    )
    try:
        return await client.consultar_cte(ch_cte)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}


async def br__submit_cte(
    c_uf: Annotated[str, "Código IBGE da UF do autorizador (cUF), 2 dígitos"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    endpoint_override: Annotated[
        str, "URL completa do webservice CTeRecepcaoSincV4 — obrigatório, ver docstring do módulo."
    ],
    xml_content: Annotated[
        str | None, "XML CT-e assinado (saída de br__sign_cte). Informe xml_content ou xml_base64."
    ] = None,
    xml_base64: Annotated[str | None, "XML CT-e assinado, codificado em base64."] = None,
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Submete um CT-e assinado à autorização SEFAZ (`CTeRecepcaoSincV4`, síncrono).

    O payload é automaticamente compactado em GZip e codificado em Base64
    antes do envio, conforme exigido pelo MOC CT-e §3.4.1 `[Verified locally]`.

    Submissão para SEFAZ é uma operação irreversível em produção e exige
    confirmação em duas etapas (`ConfirmationGate`). Define
    `BR_CTE_READ_ONLY=1` para desabilitar esta ferramenta. Nenhuma URL de
    endpoint CT-e está embutida/verificada nesta versão —
    `endpoint_override` é obrigatório.

    Retorna `protCTe` (incluindo `nProt`, o `protocolo de autorização`) em
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
        _assert_cte_not_read_only()
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__submit_cte",
            summary=(
                f"Submeter CT-e à autorização SEFAZ ({env_label}, cUF={c_uf}). "
                "Documentos autorizados em produção tornam-se fiscalmente válidos "
                "e não podem ser retratados."
            ),
            token=confirmation_token,
        )

    client = SefazCTeClient(
        cuf=c_uf,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="recepcao",
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.autorizar_cte(xml_bytes)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result


async def br__cancel_cte(
    ch_cte: Annotated[str, "Chave de acesso do CT-e a cancelar (chCTe), 44 caracteres"],
    c_orgao: Annotated[str, "Código IBGE da UF do autorizador (cOrgao), 2 dígitos (ou '90' para SUFRAMA)"],
    cnpj: Annotated[str, "CNPJ do emitente do CT-e (autor do evento)"],
    dh_evento: Annotated[str, "Data e hora do evento (ISO 8601, UTC)"],
    n_prot: Annotated[str, "Número do protocolo de autorização do CT-e original (nProt)"],
    x_just: Annotated[str, "Justificativa do cancelamento"],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    endpoint_override: Annotated[
        str, "URL completa do webservice CTeRecepcaoEventoV4 — obrigatório, ver docstring do módulo."
    ],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Solicita o cancelamento de um CT-e autorizado (evento `110111`, `CTeRecepcaoEventoV4`).

    Constrói, assina (`build_cte_event_signer`, alvo `infEvento`) e submete
    o evento de cancelamento. `cStat=135` indica cancelamento homologado
    `[Verified locally]` — MOC CT-e Visão Geral v4.00 §6.2.2.

    Cancelamento é uma operação irreversível em produção e exige
    confirmação em duas etapas (`ConfirmationGate`). Define
    `BR_CTE_READ_ONLY=1` para desabilitar. `endpoint_override` é
    obrigatório — nenhuma URL de endpoint CT-e está embutida/verificada
    nesta versão.

    Retorna `cStat`/`xMotivo` ou `error`.
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    try:
        _assert_cte_not_read_only()
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__cancel_cte",
            summary=(
                f"Cancelar CT-e {ch_cte} via SEFAZ ({env_label}). "
                "Cancelamentos homologados em produção não podem ser desfeitos."
            ),
            token=confirmation_token,
        )

    event_xml = build_cancelamento_event_xml(
        ch_cte=ch_cte,
        c_orgao=c_orgao,
        tp_amb=tp_amb,
        cnpj=cnpj,
        dh_evento=dh_evento,
        n_prot=n_prot,
        x_just=x_just,
    )
    signer = build_cte_event_signer(cert_path, cert_password)
    try:
        signed_event_xml = signer.sign(event_xml.encode("utf-8"))
    except (ImportError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    client = SefazCTeClient(
        cuf=c_orgao,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="evento",
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.enviar_evento(signed_event_xml)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result


async def br__correct_cte(
    ch_cte: Annotated[str, "Chave de acesso do CT-e a corrigir (chCTe), 44 caracteres"],
    c_orgao: Annotated[str, "Código IBGE da UF do autorizador (cOrgao), 2 dígitos (ou '90' para SUFRAMA)"],
    cnpj: Annotated[str, "CNPJ do emitente do CT-e (autor do evento)"],
    dh_evento: Annotated[str, "Data e hora do evento (ISO 8601, UTC)"],
    correcoes: Annotated[
        list[dict[str, str]],
        (
            "Lista de correções. Cada item: 'grupo_alterado', 'campo_alterado', "
            "'valor_alterado', e opcionalmente 'nro_item_alterado'."
        ),
    ],
    cert_path: Annotated[str, "Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx)"],
    endpoint_override: Annotated[
        str, "URL completa do webservice CTeRecepcaoEventoV4 — obrigatório, ver docstring do módulo."
    ],
    tp_amb: Annotated[
        str, "Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação"
    ] = "2",
    cert_password: Annotated[str | None, "Senha do certificado A1, se houver"] = None,
    confirmation_token: Annotated[
        str | None, "Token de confirmação obtido de uma chamada anterior pendente."
    ] = None,
) -> dict[str, object]:
    """Emite uma Carta de Correção Eletrônica para um CT-e (evento `110110`, `CTeRecepcaoEventoV4`).

    Constrói, assina (`build_cte_event_signer`, alvo `infEvento`) e submete
    o evento de CC-e. `cStat=135` indica CC-e homologada `[Verified
    locally]` — MOC CT-e Visão Geral v4.00 §6.4. Por força do Art. 58-B do
    CONVÊNIO/SINIEF 06/89, a CC-e não pode alterar valores de impostos,
    dados cadastrais das partes, ou a data de emissão/saída.

    Exige confirmação em duas etapas (`ConfirmationGate`). Define
    `BR_CTE_READ_ONLY=1` para desabilitar. `endpoint_override` é
    obrigatório.

    Retorna `cStat`/`xMotivo` ou `error`.
    """
    try:
        ambiente = TipoAmbiente(tp_amb)
    except ValueError:
        return {"error": f"tp_amb inválido: {tp_amb!r}. Use '1' ou '2'."}

    try:
        _assert_cte_not_read_only()
    except PlatformError as exc:
        return {"error": str(exc)}

    gate = ConfirmationGate.get_default()
    if not gate.is_confirmed(confirmation_token):
        env_label = "produção" if ambiente == TipoAmbiente.PRODUCAO else "homologação"
        return gate.pending_response(
            action="br__correct_cte",
            summary=(
                f"Emitir Carta de Correção para o CT-e {ch_cte} via SEFAZ ({env_label}). "
                "CC-e homologada em produção não pode ser retratada."
            ),
            token=confirmation_token,
        )

    try:
        event_xml = build_correcao_event_xml(
            ch_cte=ch_cte,
            c_orgao=c_orgao,
            tp_amb=tp_amb,
            cnpj=cnpj,
            dh_evento=dh_evento,
            correcoes=correcoes,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    signer = build_cte_event_signer(cert_path, cert_password)
    try:
        signed_event_xml = signer.sign(event_xml.encode("utf-8"))
    except (ImportError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    client = SefazCTeClient(
        cuf=c_orgao,
        tp_amb=ambiente,
        cert_path=cert_path,
        cert_password=cert_password,
        service="evento",
        endpoint_override=endpoint_override,
    )
    try:
        result = await client.enviar_evento(signed_event_xml)
    except (PlatformError, ValueError, OSError) as exc:
        return {"error": str(exc)}

    gate.consume(confirmation_token)
    return result
