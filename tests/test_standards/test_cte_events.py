"""Tests for CT-e event generation (roadmap BR-CTE-14/15)."""

from __future__ import annotations

import pytest
from lxml import etree

from mcp_nfe_br.standards.cte_events import (
    TP_EVENTO_CANCELAMENTO,
    TP_EVENTO_CCE,
    build_cancelamento_event_xml,
    build_correcao_event_xml,
)

_CH_CTE = "35260711222333000181570010000000011212199180"


def test_build_cancelamento_event_xml_shape() -> None:
    xml = build_cancelamento_event_xml(
        ch_cte=_CH_CTE,
        c_orgao="35",
        tp_amb="2",
        cnpj="11222333000181",
        dh_evento="2026-07-03T10:00:00Z",
        n_prot="135250000000001",
        x_just="Erro de digitação no destinatário, requer emissão de novo CT-e.",
    )
    root = etree.fromstring(xml.encode("utf-8"))
    assert root.tag.endswith("eventoCTe")

    inf_evento = root[0]
    assert inf_evento.tag.endswith("infEvento")
    evento_id = inf_evento.get("Id")
    assert evento_id == f"ID{TP_EVENTO_CANCELAMENTO}{_CH_CTE}001"
    assert len(evento_id) == 55  # "ID" + 53 digits

    assert f"<tpEvento>{TP_EVENTO_CANCELAMENTO}</tpEvento>" in xml
    assert f"<chCTe>{_CH_CTE}</chCTe>" in xml
    assert "<evCancCTe>" in xml
    assert "<descEvento>Cancelamento</descEvento>" in xml
    assert "<nProt>135250000000001</nProt>" in xml


def test_build_correcao_event_xml_shape() -> None:
    xml = build_correcao_event_xml(
        ch_cte=_CH_CTE,
        c_orgao="35",
        tp_amb="2",
        cnpj="11222333000181",
        dh_evento="2026-07-03T10:00:00Z",
        correcoes=[
            {"grupo_alterado": "rem", "campo_alterado": "xNome", "valor_alterado": "Nome Correto LTDA"}
        ],
    )
    root = etree.fromstring(xml.encode("utf-8"))
    inf_evento = root[0]
    evento_id = inf_evento.get("Id")
    assert evento_id == f"ID{TP_EVENTO_CCE}{_CH_CTE}001"

    assert f"<tpEvento>{TP_EVENTO_CCE}</tpEvento>" in xml
    assert "<evCCeCTe>" in xml
    assert "<descEvento>Carta de Correção</descEvento>" in xml
    assert "<grupoAlterado>rem</grupoAlterado>" in xml
    assert "<campoAlterado>xNome</campoAlterado>" in xml
    assert "<valorAlterado>Nome Correto LTDA</valorAlterado>" in xml
    assert "Art. 58-B" in xml


def test_build_correcao_event_xml_multiple_correcoes() -> None:
    xml = build_correcao_event_xml(
        ch_cte=_CH_CTE,
        c_orgao="35",
        tp_amb="2",
        cnpj="11222333000181",
        dh_evento="2026-07-03T10:00:00Z",
        correcoes=[
            {"grupo_alterado": "rem", "campo_alterado": "xNome", "valor_alterado": "A"},
            {
                "grupo_alterado": "det",
                "campo_alterado": "xOutCat",
                "valor_alterado": "B",
                "nro_item_alterado": "1",
            },
        ],
    )
    assert xml.count("<infCorrecao>") == 2
    assert "<nroItemAlterado>1</nroItemAlterado>" in xml


def test_build_correcao_event_xml_requires_at_least_one_correction() -> None:
    with pytest.raises(ValueError, match="ao menos um"):
        build_correcao_event_xml(
            ch_cte=_CH_CTE,
            c_orgao="35",
            tp_amb="2",
            cnpj="11222333000181",
            dh_evento="2026-07-03T10:00:00Z",
            correcoes=[],
        )
