"""Tests for CT-e (modelo 57) models (roadmap BR-CTE-2..4, 7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_nfe_br.models.cte import (
    BRCteALCZFMCBS,
    BRCteCBS,
    BRCteDevTrib,
    BRCteIBSCBS,
    BRCteIBSMun,
    BRCteIBSUF,
    BRCteImp,
    BRCteImpIBSCBS,
    BRCteInfModal,
    BRCteParty,
    BRCteTomador,
    BRCteVPrest,
    CTeModal,
    CTeModelo,
    CTeTomadorPapel,
)
from tests.conftest import make_cte, make_cte_emitente, make_cte_remetente, make_endereco

_ZFM_ENDERECO = make_endereco(c_mun="1302603", x_mun="Manaus", uf="AM")


def _make_ibscbs(**overrides: object) -> BRCteImpIBSCBS:
    data: dict[str, object] = {
        "cst": "000",
        "c_class_trib": "000001",
        "g_ibscbs": BRCteIBSCBS(
            v_bc="100.00",
            g_ibsuf=BRCteIBSUF(p_ibsuf="0.10", v_ibsuf="0.10"),
            g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
            v_ibs="0.10",
            g_cbs=BRCteCBS(p_cbs="0.90", v_cbs="0.90"),
        ),
    }
    data.update(overrides)
    return BRCteImpIBSCBS.model_validate(data)


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


# --- Reforma Tributária do Consumo (NT 2026.002) — closes GitHub issue cmendezs/mcp-nfe-br#5 ---


def test_cte_accepts_ibscbs_when_route_and_parties_in_zfm() -> None:
    cte = make_cte(
        c_mun_ini="1302603",
        x_mun_ini="Manaus",
        uf_ini="AM",
        c_mun_fim="1302603",
        x_mun_fim="Manaus",
        uf_fim="AM",
        emitente=make_cte_emitente(isuf_emit="12345678", endereco=_ZFM_ENDERECO),
        remetente=make_cte_remetente(endereco=_ZFM_ENDERECO),
        tomador=BRCteTomador(papel=CTeTomadorPapel.REMETENTE, ind_ie_toma="1"),
        imp=BRCteImp(
            icms=make_cte().imp.icms,
            ibscbs=_make_ibscbs(
                g_ibscbs=BRCteIBSCBS(
                    v_bc="100.00",
                    g_ibsuf=BRCteIBSUF(p_ibsuf="0.10", v_ibsuf="0.10"),
                    g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
                    v_ibs="0.10",
                    g_cbs=BRCteCBS(
                        p_cbs="0.00",
                        g_alczfmcbs=BRCteALCZFMCBS(p_aliq_efet_reg_cbs="0.90", v_trib_reg_cbs="0.90"),
                        v_cbs="0.00",
                    ),
                )
            ),
        ),
    )
    assert cte.imp.ibscbs is not None
    assert cte.imp.ibscbs.g_ibscbs.g_cbs.g_alczfmcbs.v_trib_reg_cbs == "0.90"


def test_cte_rejects_isuf_emit_outside_zfm_alc() -> None:
    """NT 2026.002 RV 4.001 — default fixture emitente is in São Paulo."""
    with pytest.raises(ValidationError, match="RV 4.001"):
        make_cte(emitente=make_cte_emitente(isuf_emit="12345678"))


def test_cte_rejects_devolucao_group_for_cte() -> None:
    """NT 2026.002 RV 5.001-003 — gDevTrib is never valid for CT-e."""
    with pytest.raises(ValidationError, match="RV 5.001-003"):
        make_cte(
            imp=BRCteImp(
                icms=make_cte().imp.icms,
                ibscbs=_make_ibscbs(
                    g_ibscbs=BRCteIBSCBS(
                        v_bc="100.00",
                        g_ibsuf=BRCteIBSUF(
                            p_ibsuf="0.10", v_ibsuf="0.10", g_dev_trib=BRCteDevTrib(v_dev_trib="1.00")
                        ),
                        g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
                        v_ibs="0.10",
                        g_cbs=BRCteCBS(p_cbs="0.90", v_cbs="0.90"),
                    )
                ),
            )
        )


def test_cte_rejects_alczfmcbs_without_suframa() -> None:
    """NT 2026.002 RV 6.003."""
    with pytest.raises(ValidationError, match="RV 6.003"):
        make_cte(
            c_mun_ini="1302603",
            x_mun_ini="Manaus",
            uf_ini="AM",
            c_mun_fim="1302603",
            x_mun_fim="Manaus",
            uf_fim="AM",
            emitente=make_cte_emitente(endereco=_ZFM_ENDERECO),  # no isuf_emit
            imp=BRCteImp(
                icms=make_cte().imp.icms,
                ibscbs=_make_ibscbs(
                    g_ibscbs=BRCteIBSCBS(
                        v_bc="100.00",
                        g_ibsuf=BRCteIBSUF(p_ibsuf="0.10", v_ibsuf="0.10"),
                        g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
                        v_ibs="0.10",
                        g_cbs=BRCteCBS(
                            p_cbs="0.00",
                            g_alczfmcbs=BRCteALCZFMCBS(p_aliq_efet_reg_cbs="0.90", v_trib_reg_cbs="0.90"),
                            v_cbs="0.00",
                        ),
                    )
                ),
            ),
        )


def test_cte_rejects_alczfmcbs_route_outside_incentivized_area() -> None:
    """NT 2026.002 RV 6.004 — default fixture route is São Paulo -> Rio de Janeiro."""
    with pytest.raises(ValidationError, match="RV 6.004"):
        make_cte(
            emitente=make_cte_emitente(isuf_emit="12345678", endereco=_ZFM_ENDERECO),
            imp=BRCteImp(
                icms=make_cte().imp.icms,
                ibscbs=_make_ibscbs(
                    g_ibscbs=BRCteIBSCBS(
                        v_bc="100.00",
                        g_ibsuf=BRCteIBSUF(p_ibsuf="0.10", v_ibsuf="0.10"),
                        g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
                        v_ibs="0.10",
                        g_cbs=BRCteCBS(
                            p_cbs="0.00",
                            g_alczfmcbs=BRCteALCZFMCBS(p_aliq_efet_reg_cbs="0.90", v_trib_reg_cbs="0.90"),
                            v_cbs="0.00",
                        ),
                    )
                ),
            ),
        )


def test_cte_rejects_v_trib_reg_cbs_arithmetic_mismatch() -> None:
    """NT 2026.002 RV 6.005 — vTribRegCBS must equal vBC x pAliqEfetRegCBS / 100."""
    with pytest.raises(ValidationError, match="RV 6.005"):
        make_cte(
            c_mun_ini="1302603",
            x_mun_ini="Manaus",
            uf_ini="AM",
            c_mun_fim="1302603",
            x_mun_fim="Manaus",
            uf_fim="AM",
            emitente=make_cte_emitente(isuf_emit="12345678", endereco=_ZFM_ENDERECO),
            remetente=make_cte_remetente(endereco=_ZFM_ENDERECO),
            tomador=BRCteTomador(papel=CTeTomadorPapel.REMETENTE, ind_ie_toma="1"),
            imp=BRCteImp(
                icms=make_cte().imp.icms,
                ibscbs=_make_ibscbs(
                    g_ibscbs=BRCteIBSCBS(
                        v_bc="100.00",
                        g_ibsuf=BRCteIBSUF(p_ibsuf="0.10", v_ibsuf="0.10"),
                        g_ibsmun=BRCteIBSMun(p_ibsmun="0.00", v_ibsmun="0.00"),
                        v_ibs="0.10",
                        g_cbs=BRCteCBS(
                            p_cbs="0.00",
                            g_alczfmcbs=BRCteALCZFMCBS(p_aliq_efet_reg_cbs="0.90", v_trib_reg_cbs="99.99"),
                            v_cbs="0.00",
                        ),
                    )
                ),
            ),
        )


def test_cte_pag_antecipado_requires_tp_pag_ant_3() -> None:
    """NT 2026.002 RV 7.001/002."""
    key = "35070111222333000181000012300000000123456789012"[:44]
    with pytest.raises(ValidationError, match="RV 7.001"):
        make_cte(pag_antecipado=[key])
    with pytest.raises(ValidationError, match="RV 7.002"):
        make_cte(tp_pag_ant="3")


def test_cte_pag_antecipado_rejects_duplicates() -> None:
    """NT 2026.002 RV 7.011."""
    emit = make_cte_emitente(cnpj="11222333000181")
    key = "35070111222333" + "0" * 30  # cUF+AAMM(6) + CNPJ-Base(8) + resto
    assert len(key) == 44
    with pytest.raises(ValidationError, match="RV 7.011"):
        make_cte(tp_pag_ant="3", emitente=emit, pag_antecipado=[key, key])


def test_cte_pag_antecipado_rejects_cnpj_base_mismatch() -> None:
    """NT 2026.002 RV 7.010 — chCTePagAnt's embedded CNPJ-Base must match the emitente's."""
    emit = make_cte_emitente(cnpj="11222333000181")
    mismatched_key = "35070199999999" + "0" * 30
    assert len(mismatched_key) == 44
    with pytest.raises(ValidationError, match="RV 7.010"):
        make_cte(tp_pag_ant="3", emitente=emit, pag_antecipado=[mismatched_key])


def test_cte_pag_antecipado_accepts_matching_cnpj_base() -> None:
    emit = make_cte_emitente(cnpj="11222333000181")
    key = "35070111222333" + "0" * 30
    cte = make_cte(tp_pag_ant="3", emitente=emit, pag_antecipado=[key])
    assert cte.pag_antecipado == [key]


def test_cte_pag_antecipado_rejects_bad_format() -> None:
    with pytest.raises(ValidationError, match="44 caracteres"):
        make_cte(tp_pag_ant="3", pag_antecipado=["too-short"])
