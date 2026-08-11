"""Tests for CT-e (modelo 57) models (roadmap BR-CTE-2..4, 7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_nfe_br.models.cte import (
    BRCteInfModal,
    BRCteParty,
    BRCteTomador,
    BRCteVPrest,
    CTeModal,
    CTeModelo,
    CTeTomadorPapel,
)
from tests.conftest import make_cte, make_cte_emitente, make_cte_remetente, make_endereco


def test_make_cte_round_trips() -> None:
    cte = make_cte()
    assert cte.mod == CTeModelo.CTE
    assert cte.modal == CTeModal.RODOVIARIO
    assert cte.buyer is None
    assert cte.lines == []


def test_cte_party_requires_exactly_one_of_cnpj_cpf() -> None:
    with pytest.raises(ValidationError, match="CNPJ ou CPF"):
        BRCteParty(x_nome="Teste", endereco=make_endereco())
    with pytest.raises(ValidationError, match="CNPJ ou CPF"):
        BRCteParty(x_nome="Teste", endereco=make_endereco(), cnpj="11222333000181", cpf="11144477735")


def test_cte_party_rejects_invalid_cnpj() -> None:
    with pytest.raises(ValidationError, match="CNPJ inválido"):
        make_cte_emitente(cnpj="00000000000000")


def test_cte_party_rejects_alphanumeric_cnpj() -> None:
    """BR-CTE-T1 (decided): CT-e's TCnpj (tiposGeralCTe_v4.00.xsd) is all-numeric,
    unlike NF-e's PL_010d schema — reject alphanumeric CNPJ at the party layer."""
    with pytest.raises(ValidationError, match="CNPJ numérico de 14 dígitos"):
        make_cte_emitente(cnpj="12ABC34501DE35")


def test_cte_party_accepts_numeric_cnpj() -> None:
    party = make_cte_emitente(cnpj="11222333000181")
    assert party.cnpj == "11222333000181"


def test_cte_tomador_requires_exactly_one_choice() -> None:
    with pytest.raises(ValidationError, match="papel.*ou.*outros"):
        BRCteTomador(ind_ie_toma="1")
    with pytest.raises(ValidationError, match="papel.*ou.*outros"):
        BRCteTomador(papel=CTeTomadorPapel.REMETENTE, outros=make_cte_remetente(), ind_ie_toma="1")


def test_cte_tomador_toma3_accepts_papel_only() -> None:
    tomador = BRCteTomador(papel=CTeTomadorPapel.DESTINATARIO, ind_ie_toma="9")
    assert tomador.papel == CTeTomadorPapel.DESTINATARIO
    assert tomador.outros is None


def test_cte_modal_consistency_enforced() -> None:
    with pytest.raises(ValidationError, match="inf_modal.modal"):
        make_cte(inf_modal=BRCteInfModal(modal=CTeModal.AEREO))


def test_cte_v_prest_comp_defaults_empty() -> None:
    v_prest = BRCteVPrest(v_tprest="100.00", v_rec="100.00")
    assert v_prest.comp == []


def test_cte_chave_acesso_format_validation() -> None:
    with pytest.raises(ValidationError, match="44 dígitos"):
        make_cte(chave_acesso="X" * 44)
