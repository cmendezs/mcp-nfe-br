"""CPF / CNPJ validation.

CPF: standard public-domain check-digit algorithm (Receita Federal). Not
schema-constrained beyond ``[0-9]{11}`` (TCpf in tiposBasico_v4.00.xsd).

CNPJ: as of schema package PL_010d (NT 2026.004, homologation from
2026-06-01 / production from 2026-07-01), ``TCnpj`` accepts both the legacy
all-numeric form (``[0-9]{14}``, PL_010c) and the new alphanumeric form
(``[0-9A-Z]{12}[0-9]{2}``). [Verified locally — tiposBasico_v4.00.xsd in
both schema packages, see specs/nfe/MANIFEST.md]

The alphanumeric check-digit algorithm below (mod-11, weighted, with each
character converted via ``ord(char) - 48``) is `[Unverified]` — sourced
from third-party tax-compliance writeups, not the primary "NT Conjunta DFe
2025.001" (not in the local spec bundle). Re-verify against the primary
source before relying on this for production validation. See
context-library/countries/br.md "Known gaps and open items".
"""

from __future__ import annotations

_CPF_WEIGHTS_1 = list(range(10, 1, -1))
_CPF_WEIGHTS_2 = list(range(11, 1, -1))

_CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _check_digit(value: str, weights: list[int]) -> int:
    total = sum((ord(c) - 48) * w for c, w in zip(value, weights, strict=True))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def validate_cpf(value: str) -> bool:
    """Validate a CPF number (11 digits, two mod-11 check digits).

    Args:
        value: CPF string. Non-digit characters (``.``, ``-``) are stripped.

    Returns:
        ``True`` if *value* has 11 digits and both check digits match.
    """
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    check1 = _check_digit(digits[:9], _CPF_WEIGHTS_1)
    check2 = _check_digit(digits[:9] + str(check1), _CPF_WEIGHTS_2)
    return digits[9:] == f"{check1}{check2}"


def validate_cnpj(value: str) -> bool:
    """Validate a CNPJ number — legacy numeric (14 digits) or alphanumeric
    (12 alphanumeric characters + 2 numeric check digits, PL_010d / NT 2026.004).

    Args:
        value: CNPJ string. ``.``, ``/``, and ``-`` separators are stripped.

    Returns:
        ``True`` if *value* matches one of the two accepted patterns and
        both check digits match.
    """
    cleaned = "".join(c for c in value if c not in ".-/").upper()
    if len(cleaned) != 14:
        return False

    base, check_digits = cleaned[:12], cleaned[12:]
    if not check_digits.isdigit():
        return False
    if not all(c.isdigit() or c.isalpha() for c in base):
        return False

    check1 = _check_digit(base, _CNPJ_WEIGHTS_1)
    check2 = _check_digit(base + str(check1), _CNPJ_WEIGHTS_2)
    return check_digits == f"{check1}{check2}"
