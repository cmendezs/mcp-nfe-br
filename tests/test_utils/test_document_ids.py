"""Regression tests for CPF/CNPJ validation re-pointed to mcp-einvoicing-core.

These pin the current behavior of ``validate_cpf``/``validate_cnpj`` after
re-pointing them to
``mcp_einvoicing_core.models.TaxIdentifier.validate_br_cpf``/
``validate_br_cnpj`` (core >=1.5.0). They confirm the bool-returning wrappers
still behave like the pre-re-point local implementation; they do not assert
regulatory correctness.
"""

from __future__ import annotations

from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf


def test_validate_cpf_valid() -> None:
    assert validate_cpf("529.982.247-25") is True


def test_validate_cpf_invalid_check_digit() -> None:
    assert validate_cpf("529.982.247-26") is False


def test_validate_cpf_wrong_length() -> None:
    assert validate_cpf("123") is False


def test_validate_cpf_repeated_digits() -> None:
    assert validate_cpf("111.111.111-11") is False


def test_validate_cnpj_legacy_numeric_valid() -> None:
    assert validate_cnpj("11.444.777/0001-61") is True


def test_validate_cnpj_legacy_numeric_invalid_check_digit() -> None:
    assert validate_cnpj("11.222.333/0001-80") is False


def test_validate_cnpj_wrong_length() -> None:
    assert validate_cnpj("123") is False


def test_validate_cnpj_alphanumeric_valid() -> None:
    # [Unverified]-behavior: pins the current mod-11 alphanumeric algorithm
    # (PL_010d / NT 2026.004), sourced from third-party writeups and not yet
    # confirmed against the primary "NT Conjunta DFe 2025.001" source.
    # [NEED: verify against NT Conjunta DFe 2025.001]
    assert validate_cnpj("12.ABC.345/01DE-35") is True


def test_validate_cnpj_alphanumeric_invalid_check_digit() -> None:
    # [Unverified]-behavior: see test_validate_cnpj_alphanumeric_valid.
    assert validate_cnpj("12.ABC.345/01DE-00") is False


def test_validate_cnpj_alphanumeric_lowercase_normalized() -> None:
    # [Unverified]-behavior: lowercase letters are uppercased before checking.
    assert validate_cnpj("12.abc.345/01de-35") is True
