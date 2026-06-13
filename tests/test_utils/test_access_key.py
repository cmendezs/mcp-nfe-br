"""Tests for access-key (chNFe) assembly and check-digit computation."""

from __future__ import annotations

import pytest

from mcp_nfe_br.utils.access_key import access_key_check_digit, build_access_key


def test_check_digit_length_validation() -> None:
    with pytest.raises(ValueError, match="43 characters"):
        access_key_check_digit("123")


def test_check_digit_is_single_digit() -> None:
    key43 = "3526061122233300018155001000000001172443365"
    digit = access_key_check_digit(key43)
    assert len(digit) == 1
    assert digit.isdigit()


def test_build_access_key_length_and_check_digit() -> None:
    chave = build_access_key(
        cuf="35",
        dh_emi="2026-06-13T10:00:00-03:00",
        cnpj="11222333000181",
        modelo="55",
        serie="1",
        nnf="1",
        tp_emis="1",
        cnf="12345678",
    )
    assert len(chave) == 44
    assert access_key_check_digit(chave[:43]) == chave[43]


def test_build_access_key_accepts_alphanumeric_cnpj() -> None:
    chave = build_access_key(
        cuf="35",
        dh_emi="2026-06-13T10:00:00-03:00",
        cnpj="ABCDEF12345601",
        modelo="65",
        serie="1",
        nnf="1",
        tp_emis="1",
        cnf="00000001",
    )
    assert len(chave) == 44
    assert chave[:2] == "35"
    assert chave[6:20] == "ABCDEF12345601"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"cuf": "3"}, "cUF"),
        ({"cnpj": "123"}, "CNPJ"),
        ({"modelo": "99"}, "Modelo"),
        ({"cnf": "123"}, "cNF"),
    ],
)
def test_build_access_key_invalid_components(kwargs: dict[str, str], match: str) -> None:
    base = {
        "cuf": "35",
        "dh_emi": "2026-06-13T10:00:00-03:00",
        "cnpj": "11222333000181",
        "modelo": "55",
        "serie": "1",
        "nnf": "1",
        "tp_emis": "1",
        "cnf": "12345678",
    }
    base.update(kwargs)
    with pytest.raises(ValueError, match=match):
        build_access_key(**base)
