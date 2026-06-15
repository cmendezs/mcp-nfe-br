"""ICP-Brasil XML-DSig signing for NF-e/NFC-e (modelo 55/65, schema 4.00).

Wraps :class:`mcp_einvoicing_core.XMLDSigSigner` — the enveloped
XML-DSig-over-``infNFe`` signer added to core in v1.5.0. The default
:class:`mcp_einvoicing_core.XMLDSigSignerConfig` (``infNFe``/``Id``
reference, RSA-SHA1 signature, SHA-1 digest) already matches NF-e/NFC-e
per MOC 7.0 Table 4-2 `[Verified locally]`, so no NF-e-specific overrides
are needed.

Only ICP-Brasil A1 (PKCS#12 file-based) certificates are supported, via
``XMLDSigSignerConfig.cert_path``/``cert_password``. A3 (hardware
token/HSM) certificates `[NEED: not modeled]` — `_load_pkcs12` in core
reads a PKCS#12 file from disk and has no HSM/PKCS#11 slot support.
"""

from __future__ import annotations

from mcp_einvoicing_core import XMLDSigSigner, XMLDSigSignerConfig


def build_nfe_signer(cert_path: str, cert_password: str | None = None) -> XMLDSigSigner:
    """Return an `XMLDSigSigner` configured for NF-e/NFC-e enveloped XML-DSig.

    Args:
        cert_path: Path to the ICP-Brasil A1 certificate (PKCS#12 `.p12`/`.pfx`).
        cert_password: Passphrase for the PKCS#12 file, or `None` if unprotected.

    Returns:
        An `XMLDSigSigner` using the NF-e-compatible defaults (enveloped
        signature referencing `infNFe` by its `Id` attribute, RSA-SHA1 /
        SHA-1).
    """
    return XMLDSigSigner(XMLDSigSignerConfig(cert_path=cert_path, cert_password=cert_password))
