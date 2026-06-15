"""Tests for IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) model fields.

These pin construction of `BRInvoiceLine`/`BRInvoice` with the new optional
item-level (Grupo UB) and document-level (Grupo W03) field groups added for
v0.3.0 item 5. They do not assert any "mandatory from date X" behavior — the
fields are optional and the activation date remains `[NEED:]` per the module
docstring.
"""

from __future__ import annotations

from mcp_nfe_br.models.invoice import (
    BRGrupoCBS,
    BRGrupoCBSTot,
    BRGrupoIBSCBS,
    BRGrupoIBSCBSTot,
    BRGrupoIBSMun,
    BRGrupoIBSMunTot,
    BRGrupoIBSTot,
    BRGrupoIBSUF,
    BRGrupoIBSUFTot,
    BRGrupoImpostoSeletivo,
)
from tests.conftest import make_line, make_nfe


def test_invoice_line_without_ibs_cbs_fields_unaffected() -> None:
    line = make_line()
    assert line.imposto_seletivo is None
    assert line.ibs_cbs is None


def test_invoice_line_with_imposto_seletivo() -> None:
    line = make_line(
        imposto_seletivo=BRGrupoImpostoSeletivo(
            cst_is="000",
            c_class_trib_is="200001",
            v_bc_is="100.00",
            p_is="10.00",
            v_is="10.00",
        )
    )
    assert line.imposto_seletivo is not None
    assert line.imposto_seletivo.v_is == "10.00"


def test_invoice_line_with_ibs_cbs() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            c_class_trib="000001",
            v_bc="100.00",
            ibs_uf=BRGrupoIBSUF(p_ibs_uf="0.10", v_ibs_uf="0.10"),
            ibs_mun=BRGrupoIBSMun(p_ibs_mun="0.05", v_ibs_mun="0.05"),
            v_ibs="0.15",
            cbs=BRGrupoCBS(p_cbs="0.90", v_cbs="0.90"),
        )
    )
    assert line.ibs_cbs is not None
    assert line.ibs_cbs.ibs_uf is not None
    assert line.ibs_cbs.ibs_uf.v_ibs_uf == "0.10"
    assert line.ibs_cbs.cbs is not None
    assert line.ibs_cbs.cbs.v_cbs == "0.90"


def test_invoice_without_w03_totals_unaffected() -> None:
    nfe = make_nfe()
    assert nfe.v_is_tot is None
    assert nfe.ibscbs_tot is None
    assert nfe.v_nf_tot is None


def test_invoice_with_w03_totals() -> None:
    nfe = make_nfe(
        v_is_tot="10.00",
        ibscbs_tot=BRGrupoIBSCBSTot(
            v_bc_ibscbs="100.00",
            ibs=BRGrupoIBSTot(
                ibs_uf=BRGrupoIBSUFTot(v_ibs_uf="0.10"),
                ibs_mun=BRGrupoIBSMunTot(v_ibs_mun="0.05"),
                v_ibs="0.15",
            ),
            cbs=BRGrupoCBSTot(v_cbs="0.90"),
        ),
        v_nf_tot="111.05",
    )
    assert nfe.v_is_tot == "10.00"
    assert nfe.ibscbs_tot is not None
    assert nfe.ibscbs_tot.ibs is not None
    assert nfe.ibscbs_tot.ibs.v_ibs == "0.15"
    assert nfe.ibscbs_tot.cbs is not None
    assert nfe.ibscbs_tot.cbs.v_cbs == "0.90"
    assert nfe.v_nf_tot == "111.05"
