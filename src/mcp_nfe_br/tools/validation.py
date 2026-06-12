"""Party-identifier validation tools (CPF/CNPJ)."""

from __future__ import annotations

from mcp_einvoicing_core.models import TaxIdValidationResult

from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf


def br__validate_cpf(cpf: str) -> TaxIdValidationResult:
    """Validate a Brazilian CPF (individual taxpayer ID).

    Args:
        cpf: CPF string, with or without ``.``/``-`` separators.

    Returns:
        ``TaxIdValidationResult`` with ``valid=True`` and the cleaned 11-digit
        value on success, or ``valid=False`` with an error message.
    """
    digits = "".join(c for c in cpf if c.isdigit())
    if validate_cpf(cpf):
        return TaxIdValidationResult(valid=True, value=digits, country_code="BR")
    return TaxIdValidationResult(
        valid=False,
        country_code="BR",
        error="CPF inválido: formato ou dígitos verificadores incorretos.",
    )


def br__validate_cnpj(cnpj: str) -> TaxIdValidationResult:
    """Validate a Brazilian CNPJ (company tax ID).

    Accepts both the legacy all-numeric form (14 digits) and the
    alphanumeric form introduced by NT 2026.004 / PL_010d (12 alphanumeric
    characters + 2 numeric check digits, production from 2026-07-01).

    Args:
        cnpj: CNPJ string, with or without ``.``/``/``/``-`` separators.

    Returns:
        ``TaxIdValidationResult`` with ``valid=True`` and the cleaned
        14-character value on success, or ``valid=False`` with an error
        message.
    """
    cleaned = "".join(c for c in cnpj if c not in ".-/").upper()
    if validate_cnpj(cnpj):
        return TaxIdValidationResult(valid=True, value=cleaned, country_code="BR")
    return TaxIdValidationResult(
        valid=False,
        country_code="BR",
        error="CNPJ inválido: formato ou dígitos verificadores incorretos.",
    )
