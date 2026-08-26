"""CT-e access key (`chCTe`) assembly and check-digit computation.

The CT-e access key is a 44-character string with the same layout as
`chNFe`: `cUF AAMM CNPJ mod serie nCT tpEmis cCT cDV`
(2+2+14+2+3+9+1+8+1 = 44 chars). Under `PL_CTe_400_NT2026.002` the
access-key type `TChDFe` is `[0-9]{6}[A-Z0-9]{12}[0-9]{26}` — the 12-char
CNPJ root+branch segment is alphanumeric, mirroring NF-e's `TChNFe` under
PL_010d. Confirmed against the `Id` attribute pattern
`CTe[0-9]{6}[A-Z0-9]{12}[0-9]{26}` in
`schemas/cte/cteTiposBasico_v4.00.xsd` and `TChDFe` in
`schemas/cte/tiposGeralCTe_v4.00.xsd` `[Verified locally]` (BR-CTE-23).

Reuses `access_key_check_digit` from `mcp_nfe_br.utils.access_key` — the
mod-11 check-digit algorithm is doc-type-agnostic and already alphanumeric-
safe (each character converted via ``ord(char) - 48``), so it covers both
legacy all-numeric and new alphanumeric-CNPJ keys with no separate path.

`mod` is fixed to `"57"` for CT-e modelo 57 (CT-e OS, modelo 67, is a
distinct root schema and out of scope — see roadmap BR-CTE-18).
"""

from __future__ import annotations

import re
from datetime import datetime

from mcp_nfe_br.utils.access_key import access_key_check_digit

_KEY_LENGTH_WITHOUT_DV = 43
_CTE_MODELO = "57"


def build_cte_access_key(
    *,
    cuf: str,
    dh_emi: str,
    cnpj: str,
    serie: str,
    n_ct: str,
    tp_emis: str,
    c_ct: str,
) -> str:
    """Assemble the 44-character CT-e access key (`chCTe`), including `cDV`.

    Args:
        cuf: 2-digit IBGE UF code of the issuer.
        dh_emi: Emission datetime (ISO 8601, with or without timezone).
        cnpj: Issuer CNPJ — 14 numeric digits, or 12 alphanumeric root+branch
            characters plus 2 numeric check digits (alphanumeric CNPJ, TChDFe).
        serie: Series number (zero-padded to 3 digits).
        n_ct: CT-e document number (zero-padded to 9 digits).
        tp_emis: Issuance form code (1 digit).
        c_ct: 8-digit random numeric code.

    Returns:
        The 44-character access key.

    Raises:
        ValueError: If any component does not match its expected length/pattern.
    """
    if not re.match(r"^\d{2}$", cuf):
        raise ValueError(f"cUF deve ter 2 dígitos numéricos: {cuf!r}")
    if not re.match(r"^[0-9A-Z]{12}[0-9]{2}$", cnpj):
        raise ValueError(f"CNPJ inválido para a chave de acesso do CT-e: {cnpj!r}")
    if not re.match(r"^\d{8}$", c_ct):
        raise ValueError(f"cCT deve ter 8 dígitos numéricos: {c_ct!r}")

    dt = datetime.fromisoformat(dh_emi)
    aamm = dt.strftime("%y%m")
    serie_padded = serie.zfill(3)
    n_ct_padded = n_ct.zfill(9)

    key43 = f"{cuf}{aamm}{cnpj}{_CTE_MODELO}{serie_padded}{n_ct_padded}{tp_emis}{c_ct}"
    if len(key43) != _KEY_LENGTH_WITHOUT_DV:
        raise ValueError(
            f"Componentes da chave de acesso do CT-e resultaram em {len(key43)} "
            f"caracteres, esperado {_KEY_LENGTH_WITHOUT_DV}."
        )

    return key43 + access_key_check_digit(key43)
