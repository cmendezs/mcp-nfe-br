"""CPF / CNPJ validation.

CPF: standard public-domain check-digit algorithm (Receita Federal). Not
schema-constrained beyond ``[0-9]{11}`` (TCpf in tiposBasico_v4.00.xsd).

CNPJ: as of schema package PL_010d (NT 2026.004, homologation from
2026-06-01 / production from 2026-07-01), ``TCnpj`` accepts both the legacy
all-numeric form (``[0-9]{14}``, PL_010c) and the new alphanumeric form
(``[0-9A-Z]{12}[0-9]{2}``). [Verified locally — tiposBasico_v4.00.xsd in
both schema packages, see specs/nfe/MANIFEST.md]

The alphanumeric check-digit algorithm (mod-11, weighted, with each
character converted via ``ord(char) - 48``) is `[Unverified]` — sourced
from third-party tax-compliance writeups, not the primary "NT Conjunta DFe
2025.001" (not in the local spec bundle). [NEED: verify against NT Conjunta
DFe 2025.001]. Re-verify against the primary source before relying on this
for production validation. See context-library/countries/br.md "Known gaps
and open items".

The validation algorithms themselves now live in
``mcp_einvoicing_core.models.TaxIdentifier.validate_br_cpf`` /
``validate_br_cnpj`` (core >=1.5.0). ``validate_cpf`` and ``validate_cnpj``
below are thin bool-returning re-exports kept for backward compatibility
with this package's callers and the audit's structural check.
"""

from __future__ import annotations

from mcp_einvoicing_core.models import TaxIdentifier


def validate_cpf(value: str) -> bool:
    """Validate a CPF number (11 digits, two mod-11 check digits).

    Thin wrapper around
    :meth:`mcp_einvoicing_core.models.TaxIdentifier.validate_br_cpf`.

    Args:
        value: CPF string. Non-digit characters (``.``, ``-``) are stripped.

    Returns:
        ``True`` if *value* has 11 digits and both check digits match.
    """
    valid, _ = TaxIdentifier.validate_br_cpf(value)
    return valid


def validate_cnpj(value: str) -> bool:
    """Validate a CNPJ number — legacy numeric (14 digits) or alphanumeric
    (12 alphanumeric characters + 2 numeric check digits, PL_010d / NT 2026.004).

    Thin wrapper around
    :meth:`mcp_einvoicing_core.models.TaxIdentifier.validate_br_cnpj`.
    `[Unverified]` for the alphanumeric form; see module docstring.

    Args:
        value: CNPJ string. ``.``, ``/``, and ``-`` separators are stripped.

    Returns:
        ``True`` if *value* matches one of the two accepted patterns and
        both check digits match.
    """
    valid, _ = TaxIdentifier.validate_br_cnpj(value)
    return valid
