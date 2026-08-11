"""Regression tests for CPF/CNPJ validation re-pointed to mcp-einvoicing-core.

These pin the current behavior of ``validate_cpf``/``validate_cnpj`` after
re-pointing them to
``mcp_einvoicing_core.models.TaxIdentifier.validate_br_cpf``/
``validate_br_cnpj`` (core >=1.5.0). They confirm the bool-returning wrappers
still behave like the pre-re-point local implementation; they do not assert
regulatory correctness beyond the alphanumeric-CNPJ golden fixture below.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf

_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "cnpj_alfanumerico_ntcj_2025_001.json").read_text()
)


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
    # [Verified locally — NTCJ DFe 2025.001 v1.00 §2 worked example, p.6]:
    # golden value from the bundled primary source, pinned in
    # tests/fixtures/cnpj_alfanumerico_ntcj_2025_001.json.
    assert validate_cnpj(_FIXTURE["alphanumeric"]["formatted"]) is True


def test_validate_cnpj_alphanumeric_invalid_check_digit() -> None:
    # [Verified locally — NTCJ DFe 2025.001 v1.00 §2]: see
    # test_validate_cnpj_alphanumeric_valid.
    assert validate_cnpj(_FIXTURE["alphanumeric_invalid_check_digit"]["formatted"]) is False


def test_validate_cnpj_alphanumeric_lowercase_normalized() -> None:
    # [Verified locally — NTCJ DFe 2025.001 v1.00 §2]: lowercase letters
    # are uppercased before checking.
    lowered = _FIXTURE["alphanumeric"]["formatted"].lower()
    assert validate_cnpj(lowered) is True


def test_validate_cnpj_numeric_control_from_fixture() -> None:
    assert validate_cnpj(_FIXTURE["numeric_control"]["formatted"]) is True
