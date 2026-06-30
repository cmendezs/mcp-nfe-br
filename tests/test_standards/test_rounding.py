"""Boundary-case regression tests for monetary rounding (BR-TL-6).

`ANEXO I - Leiaute e Regra de Validação - NF-e e NFC-e.pdf` footnote (*4)
requires monetary results to be rounded to 2 decimal places, with a +/-
R$0.01 validation tolerance, but does not mandate a specific rounding mode
`[Verified locally]`. `_d2`/`_percent` pass `ROUND_HALF_UP` explicitly.
This is the boundary case where `ROUND_HALF_UP` and `ROUND_HALF_EVEN`
diverge.
"""

from __future__ import annotations

from decimal import Decimal

from mcp_nfe_br.standards.nfe_generator import _d2 as nfe_d2
from mcp_nfe_br.standards.nfe_generator import _percent as nfe_percent
from mcp_nfe_br.standards.nfse_generator import _d2 as nfse_d2


def test_nfe_d2_rounds_half_up_at_boundary() -> None:
    assert nfe_d2(Decimal("0.005")) == "0.01"
    assert nfe_d2(Decimal("1.025")) == "1.03"


def test_nfe_percent_rounds_half_up_at_boundary() -> None:
    assert nfe_percent(Decimal("0.00005")) == "0.0001"


def test_nfse_d2_rounds_half_up_at_boundary() -> None:
    assert nfse_d2(Decimal("0.005")) == "0.01"
