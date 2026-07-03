"""Tests for CT-e ICP-Brasil XML-DSig signer construction (roadmap BR-CTE-6).

End-to-end sign/validate coverage (analogous to test_nfe_signer.py) is
deferred to BR-CTE-8/9 once `CTeGenerator`/`CTeXSDValidator` exist — this
only pins the signer factory's config against a real `XMLDSigSigner`.
"""

from __future__ import annotations

from pathlib import Path

from mcp_einvoicing_core import XMLDSigSigner

from mcp_nfe_br.standards.cte_signer import build_cte_signer


def test_build_cte_signer_returns_xmldsig_signer(p12_path: Path) -> None:
    signer = build_cte_signer(str(p12_path), "test")
    assert isinstance(signer, XMLDSigSigner)


def test_build_cte_signer_targets_infcte(p12_path: Path) -> None:
    signer = build_cte_signer(str(p12_path), "test")
    assert signer._config.signed_element_local_name == "infCte"
