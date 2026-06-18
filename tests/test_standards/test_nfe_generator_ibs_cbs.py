"""Tests for IBS/CBS/Imposto Seletivo XML emission (BR-TL-3, NT 2025.002-RTC).

Covers per-line builders (_imposto_seletivo_block, _ibs_cbs_block) and
document-level totals (_ibscbs_tot_xml extension to _icms_tot_block).
"""

from __future__ import annotations

import pytest
from mcp_einvoicing_core import DocumentGenerationError  # noqa: E402

from mcp_nfe_br.models.invoice import (
    BRGrupoCBS,
    BRGrupoCBSTot,
    BRGrupoIBSCBS,
    BRGrupoIBSCBSTot,
    BRGrupoIBSMun,
    BRGrupoIBSTot,
    BRGrupoIBSUF,
    BRGrupoIBSUFTot,
    BRGrupoImpostoSeletivo,
)
from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from tests.conftest import make_line, make_nfe

# ---------------------------------------------------------------------------
# Imposto Seletivo (IS) per-line emission
# ---------------------------------------------------------------------------


def test_is_block_emitted_when_set() -> None:
    line = make_line(
        imposto_seletivo=BRGrupoImpostoSeletivo(
            cst_is="000",
            c_class_trib_is="200001",
            v_bc_is="100.00",
            p_is="10.0000",
            v_is="10.00",
        )
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IS>" in xml
    assert "<cstIS>000</cstIS>" in xml
    assert "<vIS>10.00</vIS>" in xml


def test_is_block_absent_when_none() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert "<IS>" not in xml


def test_is_block_partial_fields_omitted() -> None:
    line = make_line(
        imposto_seletivo=BRGrupoImpostoSeletivo(v_is="5.00")
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IS>" in xml
    assert "<vIS>5.00</vIS>" in xml
    assert "<cstIS>" not in xml


# ---------------------------------------------------------------------------
# IBS/CBS per-line emission — golden-fixture cases
# ---------------------------------------------------------------------------


def test_ibs_cbs_gibsuf_only() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            v_bc="100.00",
            ibs_uf=BRGrupoIBSUF(p_ibs_uf="2.0000", v_ibs_uf="2.00"),
        )
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IBSCBS>" in xml
    assert "<gIBSUF>" in xml
    assert "<vIBSUF>2.00</vIBSUF>" in xml
    assert "<gIBSMun>" not in xml
    assert "<gCBS>" not in xml


def test_ibs_cbs_gibsmun_only() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            v_bc="100.00",
            ibs_mun=BRGrupoIBSMun(p_ibs_mun="1.0000", v_ibs_mun="1.00"),
        )
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IBSCBS>" in xml
    assert "<gIBSMun>" in xml
    assert "<vIBSMun>1.00</vIBSMun>" in xml
    assert "<gIBSUF>" not in xml


def test_ibs_cbs_gcbs_only() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            v_bc="100.00",
            cbs=BRGrupoCBS(p_cbs="9.0000", v_cbs="9.00"),
        )
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IBSCBS>" in xml
    assert "<gCBS>" in xml
    assert "<vCBS>9.00</vCBS>" in xml
    assert "<gIBSUF>" not in xml


def test_ibs_cbs_full_ibscbs() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            v_bc="100.00",
            ibs_uf=BRGrupoIBSUF(p_ibs_uf="2.0000", v_ibs_uf="2.00"),
            ibs_mun=BRGrupoIBSMun(p_ibs_mun="1.0000", v_ibs_mun="1.00"),
            v_ibs="3.00",
            cbs=BRGrupoCBS(p_cbs="9.0000", v_cbs="9.00"),
        )
    )
    xml = NFeGenerator().generate(make_nfe(lines=[line]))
    assert "<IBSCBS>" in xml
    assert "<gIBSUF>" in xml
    assert "<gIBSMun>" in xml
    assert "<gCBS>" in xml
    assert "<vIBS>3.00</vIBS>" in xml


def test_ibs_cbs_absent_when_none() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert "<IBSCBS>" not in xml


# ---------------------------------------------------------------------------
# Partial-population guard (BR-TL-3)
# ---------------------------------------------------------------------------


def test_ibs_cbs_gibsuf_missing_value_raises() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            ibs_uf=BRGrupoIBSUF(p_ibs_uf="2.0000"),  # v_ibs_uf absent
        )
    )
    with pytest.raises(DocumentGenerationError, match="BR-TL-3"):
        NFeGenerator().generate(make_nfe(lines=[line]))


def test_ibs_cbs_gibsmun_missing_value_raises() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            ibs_mun=BRGrupoIBSMun(p_ibs_mun="1.0000"),  # v_ibs_mun absent
        )
    )
    with pytest.raises(DocumentGenerationError, match="BR-TL-3"):
        NFeGenerator().generate(make_nfe(lines=[line]))


def test_ibs_cbs_gcbs_missing_value_raises() -> None:
    line = make_line(
        ibs_cbs=BRGrupoIBSCBS(
            cst="000",
            cbs=BRGrupoCBS(p_cbs="9.0000"),  # v_cbs absent
        )
    )
    with pytest.raises(DocumentGenerationError, match="BR-TL-3"):
        NFeGenerator().generate(make_nfe(lines=[line]))


# ---------------------------------------------------------------------------
# Document-level totals (Grupo W03)
# ---------------------------------------------------------------------------


def test_v_is_tot_emitted_in_icms_tot() -> None:
    invoice = make_nfe(v_is_tot="10.00")
    xml = NFeGenerator().generate(invoice)
    assert "<vISTot>10.00</vISTot>" in xml
    assert "<ICMSTot>" in xml


def test_ibscbs_tot_emitted_when_set() -> None:
    tot = BRGrupoIBSCBSTot(
        v_bc_ibscbs="100.00",
        ibs=BRGrupoIBSTot(
            ibs_uf=BRGrupoIBSUFTot(v_ibs_uf="2.00"),
            v_ibs="3.00",
        ),
        cbs=BRGrupoCBSTot(v_cbs="9.00"),
    )
    invoice = make_nfe(ibscbs_tot=tot)
    xml = NFeGenerator().generate(invoice)
    assert "<IBSCBSTot>" in xml
    assert "<vBCIBSCBS>100.00</vBCIBSCBS>" in xml
    assert "<gIBS>" in xml
    assert "<vIBSUF>2.00</vIBSUF>" in xml
    assert "<gCBS>" in xml
    assert "<vCBS>9.00</vCBS>" in xml


def test_ibscbs_tot_absent_when_none() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert "<IBSCBSTot>" not in xml
    assert "<vISTot>" not in xml
