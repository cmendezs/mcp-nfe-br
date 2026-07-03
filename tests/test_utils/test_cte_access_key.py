"""Tests for CT-e access-key (chCTe) assembly (roadmap BR-CTE-5)."""

from __future__ import annotations

import pytest

from mcp_nfe_br.utils.access_key import access_key_check_digit
from mcp_nfe_br.utils.cte_access_key import build_cte_access_key


def test_build_cte_access_key_length_and_check_digit() -> None:
    chave = build_cte_access_key(
        cuf="35",
        dh_emi="2026-07-03T10:00:00-03:00",
        cnpj="11222333000181",
        serie="1",
        n_ct="1",
        tp_emis="1",
        c_ct="12345678",
    )
    assert len(chave) == 44
    assert access_key_check_digit(chave[:43]) == chave[43]
    assert chave[6:20] == "11222333000181"
    assert chave[20:22] == "57"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"cuf": "3"}, "cUF"),
        ({"cnpj": "123"}, "CNPJ"),
        ({"c_ct": "123"}, "cCT"),
    ],
)
def test_build_cte_access_key_invalid_components(kwargs: dict[str, str], match: str) -> None:
    base = {
        "cuf": "35",
        "dh_emi": "2026-07-03T10:00:00-03:00",
        "cnpj": "11222333000181",
        "serie": "1",
        "n_ct": "1",
        "tp_emis": "1",
        "c_ct": "12345678",
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=match):
        build_cte_access_key(**base)
