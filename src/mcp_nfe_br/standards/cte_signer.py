"""ICP-Brasil XML-DSig signing for CT-e (modelo 57, schema 4.00) documents and events.

Wraps `mcp_einvoicing_core.XMLDSigSigner`, same as `nfe_signer.py`. Two
factories are provided: `build_cte_signer` targets `infCte` (the CT-e
document itself), `build_cte_event_signer` targets `infEvento` (event
submissions — cancelamento, CC-e, roadmap BR-CTE-14/15). RSA-SHA1/SHA-1
confirmed for CT-e against MOC CT-e Visão Geral v4.00 §3.2.4
`[Verified locally]`.

Only ICP-Brasil A1 (PKCS#12 file-based) certificates are supported, via
`XMLDSigSignerConfig.cert_path`/`cert_password`. A3 (hardware token/HSM)
certificates `[NEED: not modeled]`, same limitation as NF-e.
"""

from __future__ import annotations

from mcp_einvoicing_core import XMLDSigSigner, XMLDSigSignerConfig


def build_cte_signer(cert_path: str, cert_password: str | None = None) -> XMLDSigSigner:
    """Return an `XMLDSigSigner` configured for CT-e enveloped XML-DSig.

    Args:
        cert_path: Path to the ICP-Brasil A1 certificate (PKCS#12 `.p12`/`.pfx`).
        cert_password: Passphrase for the PKCS#12 file, or `None` if unprotected.

    Returns:
        An `XMLDSigSigner` using the CT-e-compatible defaults (enveloped
        signature referencing `infCte` by its `Id` attribute, RSA-SHA1 /
        SHA-1).
    """
    return XMLDSigSigner(
        XMLDSigSignerConfig(
            cert_path=cert_path,
            cert_password=cert_password,
            signed_element_local_name="infCte",
        )
    )


def build_cte_event_signer(cert_path: str, cert_password: str | None = None) -> XMLDSigSigner:
    """Return an `XMLDSigSigner` configured for CT-e event (`eventoCTe`)
    enveloped XML-DSig — targets `infEvento` instead of `infCte`.

    `[Verified locally]` — `eventoCTeTiposBasico_v4.00.xsd`: the `Id`
    attribute referenced by `ds:Signature` lives on `<infEvento>`, and
    `<ds:Signature>` is a mandatory sibling of `<infEvento>` inside
    `<eventoCTe>` (same shape as NF-e's own event signing, RSA-SHA1/SHA-1).
    """
    return XMLDSigSigner(
        XMLDSigSignerConfig(
            cert_path=cert_path,
            cert_password=cert_password,
            signed_element_local_name="infEvento",
        )
    )
