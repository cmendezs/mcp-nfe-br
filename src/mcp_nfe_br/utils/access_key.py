"""NF-e/NFC-e access key (`chNFe`) assembly and check-digit computation.

The access key is a 44-character string: `cUF AAMM CNPJ mod serie nNF tpEmis
cNF cDV` (2+2+14+2+3+9+1+8+1 = 44 chars), `TChNFe` in `tiposBasico_v4.00.xsd`.

Under PL_010c the CNPJ segment is `[0-9]{14}`; under PL_010d (NT 2026.004,
homologation from 2026-06-01 / production from 2026-07-01) it becomes
`[0-9A-Z]{12}[0-9]{2}` — alphanumeric. `[Verified locally]` per
context-library/countries/br.md.

The check-digit algorithm (mod-11, weights 2..9 cycling from the rightmost
character, each character converted via ``ord(char) - 48``) is
`[Unverified]` — sourced from third-party tax-compliance writeups, not the
primary "NT Conjunta DFe 2025.001" (not in the local spec bundle). Re-verify
against the primary source before relying on this for production submissions.
Cover with golden-value tests from a known authorized NF-e.
"""

from __future__ import annotations

import re
from datetime import datetime

_KEY_LENGTH_WITHOUT_DV = 43


def access_key_check_digit(key43: str) -> str:
    """Compute the mod-11 check digit (`cDV`) for a 43-character access key body.

    Weights cycle 2..9 starting from the rightmost character. Each character
    is converted via ``ord(char) - 48`` before weighting, which is equivalent
    to ``int(char)`` for digits 0-9 and supports alphanumeric CNPJ segments
    (PL_010d) without a separate code path.

    Args:
        key43: The first 43 characters of the access key.

    Returns:
        A single decimal digit string ("0"-"9").

    Raises:
        ValueError: If *key43* is not exactly 43 characters.
    """
    if len(key43) != _KEY_LENGTH_WITHOUT_DV:
        raise ValueError(
            f"Access key body must be {_KEY_LENGTH_WITHOUT_DV} characters, got {len(key43)}."
        )

    total = 0
    weight = 2
    for char in reversed(key43):
        total += (ord(char) - 48) * weight
        weight = weight + 1 if weight < 9 else 2

    remainder = total % 11
    return "0" if remainder in (0, 1) else str(11 - remainder)


def build_access_key(
    *,
    cuf: str,
    dh_emi: str,
    cnpj: str,
    modelo: str,
    serie: str,
    nnf: str,
    tp_emis: str,
    cnf: str,
) -> str:
    """Assemble the 44-character NF-e/NFC-e access key (`chNFe`), including `cDV`.

    Args:
        cuf: 2-digit IBGE UF code of the issuer.
        dh_emi: Emission datetime (ISO 8601, with or without timezone).
        cnpj: Issuer CNPJ — 14 numeric digits (PL_010c) or 12 alphanumeric +
            2 numeric check digits (PL_010d).
        modelo: Document model ("55" or "65").
        serie: Series number (zero-padded to 3 digits).
        nnf: Document number (zero-padded to 9 digits).
        tp_emis: Issuance form code (1 digit).
        cnf: 8-digit random numeric code.

    Returns:
        The 44-character access key.

    Raises:
        ValueError: If any component does not match its expected length/pattern.
    """
    if not re.match(r"^\d{2}$", cuf):
        raise ValueError(f"cUF deve ter 2 dígitos numéricos: {cuf!r}")
    if not re.match(r"^[0-9A-Z]{12}[0-9]{2}$", cnpj):
        raise ValueError(f"CNPJ inválido para a chave de acesso: {cnpj!r}")
    if modelo not in ("55", "65"):
        raise ValueError(f"Modelo inválido para a chave de acesso: {modelo!r}")
    if not re.match(r"^\d{8}$", cnf):
        raise ValueError(f"cNF deve ter 8 dígitos numéricos: {cnf!r}")

    dt = datetime.fromisoformat(dh_emi)
    aamm = dt.strftime("%y%m")
    serie_padded = serie.zfill(3)
    nnf_padded = nnf.zfill(9)

    key43 = f"{cuf}{aamm}{cnpj}{modelo}{serie_padded}{nnf_padded}{tp_emis}{cnf}"
    if len(key43) != _KEY_LENGTH_WITHOUT_DV:
        raise ValueError(
            f"Componentes da chave de acesso resultaram em {len(key43)} caracteres, "
            f"esperado {_KEY_LENGTH_WITHOUT_DV}."
        )

    return key43 + access_key_check_digit(key43)
