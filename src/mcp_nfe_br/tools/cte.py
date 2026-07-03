"""CT-e (modelo 57) generation, XSD validation, and SEFAZ tools.

Generation/validation tools are v1 scope: modal rodoviário only, ICMS CST 00
only — see `mcp_nfe_br.standards.cte_generator` module docstring
(roadmap BR-CTE-9).

`br__submit_cte` and `br__consult_cte` (roadmap BR-CTE-12) are
mutating/network operations against real SEFAZ infrastructure and are
gated with `assert_not_read_only` + `ConfirmationGate`, mirroring
`mcp_nfe_br.tools.sefaz`. No CT-e endpoint URLs are bundled/verified in
this version — callers must always pass `endpoint_override`
(`SefazCTeClient`/`get_cte_endpoint` docstring). `br__distribute_cte_dfe`
is not implemented — see roadmap BR-CTE-13.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp_einvoicing_core.base_server import assert_not_read_only
from mcp_einvoicing_core.confirmation import ConfirmationGate
from mcp_einvoicing_core.exceptions import EInvoicingError, PlatformError
from mcp_einvoicing_core.xml_utils import resolve_xml_input

from mcp_nfe_br.models.cte import BRCTeDocument
from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards.cte_generator import CTeGenerator
from mcp_nfe_br.standards.sefaz_cte_client import SefazCTeClient
from mcp_nfe_br.validators.cte_xsd import CTeXSDValidator

_READ_ONLY_ENV_VAR = "BR_CTE_READ_ONLY"


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
        assert_not_read_only(_READ_ONLY_ENV_VAR)
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
