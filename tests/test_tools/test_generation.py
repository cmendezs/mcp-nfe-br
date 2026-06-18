"""Tests for br__generate_nfe, br__sign_nfe, br__validate_nfe_xml, and br__build_access_key."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from mcp_nfe_br.tools.generation import (
    br__build_access_key,
    br__generate_nfe,
    br__sign_nfe,
    br__validate_nfe_xml,
)
from tests.conftest import make_nfce, make_nfe


def test_generate_nfe_returns_xml_and_chave() -> None:
    result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    assert "xml" in result
    assert result["chave_acesso"]
    assert len(result["chave_acesso"]) == 44
    assert "<Signature" not in result["xml"]
    assert result["warnings"]


def test_generate_nfce_returns_xml() -> None:
    result = br__generate_nfe(make_nfce().model_dump(mode="json"))
    assert "<mod>65</mod>" in result["xml"]


def test_generate_unsupported_tax_code_returns_error() -> None:
    data = make_nfe().model_dump(mode="json")
    data["lines"][0]["icms_cst"] = "21"
    result = br__generate_nfe(data)
    assert "error" in result


def test_sign_nfe_returns_signed_xml(p12_path: Path) -> None:
    gen_result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    sign_result = br__sign_nfe(
        cert_path=str(p12_path), xml_content=gen_result["xml"], cert_password="test"
    )
    assert "<ds:Signature" in sign_result["xml"]


def test_sign_then_validate_nfe_uses_signed_schema(p12_path: Path) -> None:
    gen_result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    sign_result = br__sign_nfe(
        cert_path=str(p12_path), xml_content=gen_result["xml"], cert_password="test"
    )
    val_result = br__validate_nfe_xml(xml_content=sign_result["xml"])
    assert val_result["valid"] is True
    assert "official signed schema" in val_result["schema_version"]


def test_sign_nfe_missing_cert_returns_error() -> None:
    gen_result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    result = br__sign_nfe(cert_path="/nonexistent/cert.p12", xml_content=gen_result["xml"])
    assert "error" in result


def test_sign_nfe_requires_xml_input(p12_path: Path) -> None:
    result = br__sign_nfe(cert_path=str(p12_path))
    assert "error" in result


def test_round_trip_generate_then_validate_nfe() -> None:
    gen_result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    val_result = br__validate_nfe_xml(xml_content=gen_result["xml"])
    assert val_result["valid"] is True


def test_round_trip_generate_then_validate_nfce() -> None:
    gen_result = br__generate_nfe(make_nfce().model_dump(mode="json"))
    val_result = br__validate_nfe_xml(xml_content=gen_result["xml"])
    assert val_result["valid"] is True


def test_validate_requires_xml_input() -> None:
    result = br__validate_nfe_xml()
    assert result["valid"] is False


def test_build_access_key_returns_44_chars() -> None:
    result = br__build_access_key(
        c_uf="35",
        dh_emi="2026-06-13T10:00:00-03:00",
        cnpj="11222333000181",
        modelo="55",
        serie="1",
        nnf="1",
        c_nf="12345678",
    )
    assert result["chave_acesso"] == result["chave_acesso"]
    assert len(result["chave_acesso"]) == 44
    assert result["cnf"] == "12345678"


def test_build_access_key_generates_cnf_when_omitted() -> None:
    result = br__build_access_key(
        c_uf="35",
        dh_emi="2026-06-13T10:00:00-03:00",
        cnpj="11222333000181",
        modelo="55",
        serie="1",
        nnf="1",
    )
    assert len(result["cnf"]) == 8


def test_build_access_key_invalid_input_returns_error() -> None:
    result = br__build_access_key(
        c_uf="3",
        dh_emi="2026-06-13T10:00:00-03:00",
        cnpj="11222333000181",
        modelo="55",
        serie="1",
        nnf="1",
    )
    assert "error" in result


# ---------------------------------------------------------------------------
# BR-SH-1: wrong PKCS#12 password must not appear in any log record
# ---------------------------------------------------------------------------

_SENTINEL_PASSWORD = "s3cr3t-do-not-log"


def test_sign_nfe_wrong_password_does_not_log_password(
    p12_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """BR-SH-1: wrong cert password traceback must not appear in log records."""
    gen_result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    with caplog.at_level(logging.DEBUG):
        result = br__sign_nfe(
            cert_path=str(p12_path),
            xml_content=gen_result["xml"],
            cert_password=_SENTINEL_PASSWORD,
        )
    assert "error" in result
    for record in caplog.records:
        assert _SENTINEL_PASSWORD not in record.getMessage()


def test_generate_nfe_ub12_10_warning_present() -> None:
    """BR-TL-4: br__generate_nfe must include UB12-10 activation-date warning."""
    result = br__generate_nfe(make_nfe().model_dump(mode="json"))
    warnings = result.get("warnings", [])
    assert any("UB12-10" in w for w in warnings), "UB12-10 warning must appear in br__generate_nfe"
