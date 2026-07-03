"""CT-e event generation (cancelamento, carta de correção) — roadmap BR-CTE-14/15.

Covers the two events in the "event-limited v1" scope decided in the CT-e
scoping plan: `110111` (Cancelamento) and `110110` (Carta de Correção,
CC-e). Both confirmed `[Verified locally]` against the bundled
`evCancCTe_v4.00.xsd`/`evCCeCTe_v4.00.xsd` and MOC CT-e Visão Geral v4.00
§6.2/§6.4. Both events report success as `cStat=135` (`[Verified locally]`
— MOC §6.2.2 "o retorno do status do evento será cStat=135" and §6.4
equivalent text for CC-e).

Event document shape (`TEvento`, `eventoCTeTiposBasico_v4.00.xsd`):
`<eventoCTe><infEvento Id="ID<tpEvento><chCTe><nSeqEvento>">...<detEvento
versaoEvento="4.00"><evCancCTe|evCCeCTe>...</...></detEvento></infEvento>
<ds:Signature/></eventoCTe>`. `detEvento` is `<xs:any processContents="skip">`
in the main event schema (same "outer schema doesn't validate the
event-specific payload" pattern as `infModal` — see `cte_generator.py`).

The `Id` attribute pattern is `ID[0-9]{53}` — `tpEvento` (6) + `chCTe` (44)
+ `nSeqEvento` zero-padded to 3 digits = 53.

Unlike `CTeRecepcaoSincV4`, `CTeRecepcaoEventoV4` uses plain uncompressed
XML (`[Verified locally]` — MOC §5 "Parâmetro da Mensagem da área de
dados: XML sem compactação").

v1 scope: event author identified by CNPJ only (the `CNPJ`/`CPF` choice in
`infEvento` is narrowed to CNPJ, matching the CT-e emitente party, which is
always CNPJ-bound in this package's `BRCteEmitente` model).
"""

from __future__ import annotations

from mcp_einvoicing_core.xml_utils import xml_element

_CTE_NS = "http://www.portalfiscal.inf.br/cte"
_VERSAO_EVENTO = "4.00"

TP_EVENTO_CANCELAMENTO = "110111"
TP_EVENTO_CCE = "110110"

_COND_USO_CCE = (
    "A Carta de Correção é disciplinada pelo Art. 58-B do CONVÊNIO/SINIEF 06/89: "
    "Fica permitida a utilização de carta de correção, para regularização de erro "
    "ocorrido na emissão de documentos fiscais relativos à prestação de serviço de "
    "transporte, desde que o erro não esteja relacionado com: I - as variáveis que "
    "determinam o valor do imposto tais como: base de cálculo, alíquota, diferença "
    "de preço, quantidade, valor da prestação;II - a correção de dados cadastrais "
    "que implique mudança do emitente, tomador, remetente ou do destinatário;III - "
    "a data de emissão ou de saída."
)


def _evento_id(tp_evento: str, ch_cte: str, n_seq_evento: str) -> str:
    return f"ID{tp_evento}{ch_cte}{n_seq_evento.zfill(3)}"


def _evento_envelope(
    *,
    tp_evento: str,
    ch_cte: str,
    c_orgao: str,
    tp_amb: str,
    cnpj: str,
    dh_evento: str,
    n_seq_evento: str,
    det_evento_content: str,
) -> str:
    evento_id = _evento_id(tp_evento, ch_cte, n_seq_evento)
    inf_evento_body = (
        xml_element("cOrgao", c_orgao)
        + xml_element("tpAmb", tp_amb)
        + xml_element("CNPJ", cnpj)
        + xml_element("chCTe", ch_cte)
        + xml_element("dhEvento", dh_evento)
        + xml_element("tpEvento", tp_evento)
        + xml_element("nSeqEvento", n_seq_evento)
        + xml_element(
            "detEvento", det_evento_content, attrs={"versaoEvento": _VERSAO_EVENTO}, unsafe=True
        )
    )
    inf_evento = xml_element("infEvento", inf_evento_body, attrs={"Id": evento_id}, unsafe=True)
    return f'<?xml version="1.0" encoding="UTF-8"?><eventoCTe xmlns="{_CTE_NS}" versao="{_VERSAO_EVENTO}">{inf_evento}</eventoCTe>'


def build_cancelamento_event_xml(
    *,
    ch_cte: str,
    c_orgao: str,
    tp_amb: str,
    cnpj: str,
    dh_evento: str,
    n_prot: str,
    x_just: str,
    n_seq_evento: str = "1",
) -> str:
    """Build an unsigned `eventoCTe` for `110111` (Cancelamento).

    `[Verified locally]` — `evCancCTe_v4.00.xsd`: `descEvento` fixed to
    "Cancelamento", `nProt` (protocol from the original authorization),
    `xJust` (justification).

    Args:
        ch_cte: 44-character access key of the CT-e to cancel.
        c_orgao: `cOrgao` — 2-digit IBGE UF code (or "90" for SUFRAMA).
        tp_amb: `"1"` (produção) or `"2"` (homologação).
        cnpj: CNPJ of the event's author (the CT-e emitente).
        dh_evento: Event datetime, ISO 8601 UTC.
        n_prot: Authorization protocol number (`nProt`) of the original CT-e.
        x_just: Cancellation justification text.
        n_seq_evento: Event sequence number (default `"1"`).

    Returns:
        The unsigned `<eventoCTe>` XML string.
    """
    det_evento = xml_element(
        "evCancCTe",
        xml_element("descEvento", "Cancelamento")
        + xml_element("nProt", n_prot)
        + xml_element("xJust", x_just),
        unsafe=True,
    )
    return _evento_envelope(
        tp_evento=TP_EVENTO_CANCELAMENTO,
        ch_cte=ch_cte,
        c_orgao=c_orgao,
        tp_amb=tp_amb,
        cnpj=cnpj,
        dh_evento=dh_evento,
        n_seq_evento=n_seq_evento,
        det_evento_content=det_evento,
    )


def build_correcao_event_xml(
    *,
    ch_cte: str,
    c_orgao: str,
    tp_amb: str,
    cnpj: str,
    dh_evento: str,
    correcoes: list[dict[str, str]],
    n_seq_evento: str = "1",
) -> str:
    """Build an unsigned `eventoCTe` for `110110` (Carta de Correção).

    `[Verified locally]` — `evCCeCTe_v4.00.xsd`: `descEvento` fixed to
    "Carta de Correção", one or more `infCorrecao` groups, `xCondUso` fixed
    to the literal legal-text enumeration (Art. 58-B CONVÊNIO/SINIEF 06/89).

    Args:
        ch_cte: 44-character access key of the CT-e being corrected.
        c_orgao: `cOrgao` — 2-digit IBGE UF code.
        tp_amb: `"1"` (produção) or `"2"` (homologação).
        cnpj: CNPJ of the event's author.
        dh_evento: Event datetime, ISO 8601 UTC.
        correcoes: List of correction dicts, each with keys
            `grupo_alterado`, `campo_alterado`, `valor_alterado`, and
            optionally `nro_item_alterado`.
        n_seq_evento: Event sequence number (default `"1"`).

    Raises:
        ValueError: If *correcoes* is empty.

    Returns:
        The unsigned `<eventoCTe>` XML string.
    """
    if not correcoes:
        raise ValueError("Carta de Correção requer ao menos um item em `correcoes`.")

    inf_correcoes = "".join(
        xml_element(
            "infCorrecao",
            xml_element("grupoAlterado", c["grupo_alterado"])
            + xml_element("campoAlterado", c["campo_alterado"])
            + xml_element("valorAlterado", c["valor_alterado"])
            + (
                xml_element("nroItemAlterado", c["nro_item_alterado"])
                if c.get("nro_item_alterado")
                else ""
            ),
            unsafe=True,
        )
        for c in correcoes
    )
    det_evento = xml_element(
        "evCCeCTe",
        xml_element("descEvento", "Carta de Correção")
        + inf_correcoes
        + xml_element("xCondUso", _COND_USO_CCE),
        unsafe=True,
    )
    return _evento_envelope(
        tp_evento=TP_EVENTO_CCE,
        ch_cte=ch_cte,
        c_orgao=c_orgao,
        tp_amb=tp_amb,
        cnpj=cnpj,
        dh_evento=dh_evento,
        n_seq_evento=n_seq_evento,
        det_evento_content=det_evento,
    )
