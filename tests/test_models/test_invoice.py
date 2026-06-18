"""Tests for IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) model fields.

These pin construction of `BRInvoiceLine`/`BRInvoice` with the new optional
item-level (Grupo UB) and document-level (Grupo W03) field groups added for
v0.3.0 item 5. They do not assert any "mandatory from date X" behavior — the
fields are optional and the activation date remains `[NEED:]` per the module
docstring.
"""

from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# BR-SC-3: chave_acesso PL_010d regex (NT 2026.004)
# ---------------------------------------------------------------------------


def test_chave_acesso_valid_numeric_44chars() -> None:
    import re

    # cUF(35) + AAMM(2606) + CNPJ(11222333000181) + mod(55) + serie(001) +
    # nNF(000000001) + tpEmis(1) + cNF(23456789) + cDV(1) = 44 chars
    numeric_key = "35260611222333000181550010000000011234567891"
    assert len(numeric_key) == 44
    assert re.match(r"^[0-9]{6}[0-9A-Z]{14}[0-9]{24}$", numeric_key)


def test_chave_acesso_valid_alphanumeric_cnpj_segment() -> None:
    # Alphanumeric CNPJ segment (effective 2026-07-01 per NT 2026.004)
    # Structure: 6 digits + 14 alphanum (CNPJ) + 24 digits = 44
    # cUF(35) AAMM(2606) + CNPJ(AB22333000181X) + mod/serie/nNF/tpEmis/cNF/cDV
    alpha_key = "352606AB22333000181X55001000000001123456789" + "1"
    # Build a clean 44-char key: 6 + 14 + 24
    alpha_key = "352606" + "AB22333000181X" + "550010000000011234567891"
    assert len(alpha_key) == 44
    import re
    assert re.match(r"^[0-9]{6}[0-9A-Z]{14}[0-9]{24}$", alpha_key)


def test_chave_acesso_rejects_43_chars() -> None:
    from pydantic import ValidationError

    short_key = "3526061122233300018155001000000001123456789"
    assert len(short_key) == 43
    with pytest.raises(ValidationError):
        make_nfe(chave_acesso=short_key)


def test_chave_acesso_rejects_lowercase_in_cnpj_segment() -> None:
    from pydantic import ValidationError

    # lowercase letters in CNPJ segment position — should be rejected
    lower_key = "352606" + "ab22333000181x" + "550010000000011234567891"
    assert len(lower_key) == 44
    with pytest.raises(ValidationError):
        make_nfe(chave_acesso=lower_key)
