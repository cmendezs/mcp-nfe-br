"""ICP-Brasil XML-DSig signing for NFS-e Nacional (ADN) DPS documents.

Wraps :class:`mcp_einvoicing_core.XMLDSigSigner` to sign the ``infDPS``
element in a Declaração de Prestação de Serviços (DPS).

The signed element is ``infDPS`` with its ``Id`` attribute (type ``TSIdDPS``,
45 chars), confirmed from ``tiposComplexos_v1.01.xsd`` and
``tiposSimples_v1.01.xsd`` `[Verified locally]`.

Signature algorithm: RSA-SHA1 / SHA-1 (``XMLDSigSignerConfig`` defaults),
matching NF-e/NFC-e per MOC 7.0. `[Unverified for NFS-e — NFS-e manuals
in local bundle not yet read; RSA-SHA256 may be required for NFS-e Nacional.
Re-read manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf before
submitting signed DPS in production.]`

Only ICP-Brasil A1 (PKCS#12 file-based) certificates are supported.
A3 (hardware token / HSM) is `[NEED: not modeled]`.
"""

from __future__ import annotations

from mcp_einvoicing_core import XMLDSigSigner, XMLDSigSignerConfig


def build_nfse_signer(cert_path: str, cert_password: str | None = None) -> XMLDSigSigner:
    """Return an ``XMLDSigSigner`` configured for NFS-e Nacional DPS signing.

    Signs the ``infDPS`` element (``Id`` attribute) in a DPS document with an
    enveloped ``ds:Signature`` appended as the last child of ``<DPS>``.

    Args:
        cert_path: Path to the ICP-Brasil A1 certificate (PKCS#12 ``.p12`` / ``.pfx``).
        cert_password: Passphrase for the PKCS#12 file, or ``None`` if unprotected.

    Returns:
        An ``XMLDSigSigner`` configured to sign ``infDPS`` by its ``Id`` attribute.

    Note:
        The signature algorithm defaults to RSA-SHA1 (same as NF-e). `[Unverified
        for NFS-e Nacional — confirm against NFS-e manual before production use.]`
    """
    return XMLDSigSigner(
        XMLDSigSignerConfig(
            cert_path=cert_path,
            cert_password=cert_password,
            signed_element_local_name="infDPS",
        )
    )
