"""Tests for NFeGenerator (NF-e/NFC-e 4.00 XML generation)."""

from __future__ import annotations

import pytest
from mcp_einvoicing_core import DocumentGenerationError
from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from tests.conftest import make_emitente, make_line, make_nfce, make_nfe


def test_generate_nfe_root_and_namespace() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">' in xml
    assert "<infNFe " in xml
    assert 'versao="4.00"' in xml
    assert "<Signature" not in xml


def test_generate_nfe_access_key_in_id_attribute() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert 'Id="NFe352606' in xml


def test_generate_nfe_modelo_55() -> None:
    xml = NFeGenerator().generate(make_nfe())
    assert "<mod>55</mod>" in xml


def test_generate_nfce_modelo_65_omits_dest() -> None:
    xml = NFeGenerator().generate(make_nfce())
    assert "<mod>65</mod>" in xml
    assert "<dest>" not in xml
    assert "ICMSSN102" in xml


def test_generate_rejects_non_br_invoice() -> None:
    from mcp_einvoicing_core.models import InvoiceDocument

    seller = InvoiceParty(
        tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"), name="X"
    )
    buyer = InvoiceParty(
        tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"), name="Y"
    )
    doc = InvoiceDocument(document_type="55", date="2026-06-13", number="1", seller=seller, buyer=buyer)
    with pytest.raises(DocumentGenerationError, match="BRInvoice"):
        NFeGenerator().generate(doc)


def test_generate_rejects_unsupported_icms_cst() -> None:
    invoice = make_nfe(lines=[make_line(icms_cst="21")])
    with pytest.raises(DocumentGenerationError, match="ICMS"):
        NFeGenerator().generate(invoice)


def test_generate_rejects_unsupported_pis_cst() -> None:
    invoice = make_nfe(lines=[make_line(pis_cst="50")])
    with pytest.raises(DocumentGenerationError, match="PIS"):
        NFeGenerator().generate(invoice)


def test_generate_omits_optional_tax_groups_when_none() -> None:
    invoice = make_nfe(
        lines=[make_line(pis_cst=None, pis_amount=None, cofins_cst=None, cofins_amount=None, ipi_cst=None)]
    )
    xml = NFeGenerator().generate(invoice)
    assert "<PIS>" not in xml
    assert "<COFINS>" not in xml
    assert "<IPI>" not in xml


def test_generate_includes_ipi_when_present() -> None:
    invoice = make_nfe(lines=[make_line(ipi_cst="99", ipi_amount="5.00")])
    xml = NFeGenerator().generate(invoice)
    assert "<IPI>" in xml
    assert "<IPINT>" in xml or "<IPITrib>" in xml


def test_generate_with_cpf_emitente_pads_access_key() -> None:
    emit = make_emitente(cnpj=None, cpf="52998224725")
    invoice = make_nfe(emitente=emit)
    xml = NFeGenerator().generate(invoice)
    assert "<CPF>52998224725</CPF>" in xml
    assert 'Id="NFe35260600052998224725550010000000011' in xml


def test_chave_acesso_mismatch_raises() -> None:
    invoice = make_nfe(chave_acesso="0" * 44)
    with pytest.raises(DocumentGenerationError, match="chave de acesso"):
        NFeGenerator().generate(invoice)


def test_generate_requires_at_least_one_line() -> None:
    invoice = make_nfe()
    object.__setattr__(invoice, "lines", [])
    with pytest.raises(DocumentGenerationError, match="item"):
        NFeGenerator().generate(invoice)
