"""Tests for br__validate_cpf and br__validate_cnpj."""

from __future__ import annotations

from mcp_nfe_br.tools.validation import br__validate_cnpj, br__validate_cpf


def test_validate_cpf_valid() -> None:
    result = br__validate_cpf("529.982.247-25")
    assert result.valid is True
    assert result.value == "52998224725"


def test_validate_cpf_invalid_check_digit() -> None:
    result = br__validate_cpf("529.982.247-26")
    assert result.valid is False
    assert result.error is not None


def test_validate_cpf_invalid_length() -> None:
    result = br__validate_cpf("123")
    assert result.valid is False


def test_validate_cpf_repeated_digits() -> None:
    result = br__validate_cpf("111.111.111-11")
    assert result.valid is False


def test_validate_cnpj_invalid_check_digit() -> None:
    result = br__validate_cnpj("11.222.333/0001-80")
    assert result.valid is False
    assert result.error is not None


def test_validate_cnpj_invalid_length() -> None:
    result = br__validate_cnpj("123")
    assert result.valid is False
