"""Shared pytest fixtures for mcp-nfe-br tests."""

from __future__ import annotations

from pathlib import Path

from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

from mcp_nfe_br.models.invoice import (
    BREmitente,
    BREndereco,
    BRInvoice,
    BRInvoiceLine,
    BRPagamento,
    NFeModelo,
    RegimeTributario,
    TipoAmbiente,
    TipoOperacao,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def make_endereco(**overrides: object) -> BREndereco:
    data: dict[str, object] = {
        "x_lgr": "Rua Teste",
        "nro": "123",
        "x_bairro": "Centro",
        "c_mun": "3550308",
        "x_mun": "Sao Paulo",
        "uf": "SP",
        "cep": "01000000",
    }
    data.update(overrides)
    return BREndereco.model_validate(data)


def make_emitente(**overrides: object) -> BREmitente:
    data: dict[str, object] = {
        "cnpj": "11222333000181",
        "x_nome": "Empresa Teste LTDA",
        "ender_emit": make_endereco(),
        "ie": "123456789",
        "crt": RegimeTributario.REGIME_NORMAL,
    }
    data.update(overrides)
    return BREmitente.model_validate(data)


def make_line(**overrides: object) -> BRInvoiceLine:
    data: dict[str, object] = {
        "line_number": 1,
        "description": "Produto Teste",
        "unit_price": "100.00",
        "total_price": "100.00",
        "c_prod": "P001",
        "ncm": "61091000",
        "cfop": "5102",
        "u_com": "UN",
        "q_com": "1",
        "v_un_com": "100.00",
        "v_prod": "100.00",
        "u_trib": "UN",
        "q_trib": "1",
        "v_un_trib": "100.00",
        "icms_cst": "00",
        "icms_rate": "18",
        "icms_amount": "18.00",
        "pis_cst": "01",
        "pis_amount": "1.65",
        "cofins_cst": "01",
        "cofins_amount": "7.60",
    }
    data.update(overrides)
    return BRInvoiceLine.model_validate(data)


def make_nfe(**overrides: object) -> BRInvoice:
    """Build a sample modelo-55 NF-e (regime normal, ICMS00/PIS-COFINS Aliq, with destinatario)."""
    data: dict[str, object] = {
        "document_type": "55",
        "date": "2026-06-13",
        "number": "1",
        "seller": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
            name="Empresa Teste LTDA",
        ),
        "buyer": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11144477735"),
            name="Cliente Teste",
        ),
        "modelo": NFeModelo.NFE,
        "serie": "1",
        "nnf": "1",
        "natureza_operacao": "Venda de mercadoria",
        "tipo_operacao": TipoOperacao.SAIDA,
        "c_uf": "35",
        "dh_emi": "2026-06-13T10:00:00-03:00",
        "id_dest": "1",
        "c_mun_fg": "3550308",
        "tp_amb": TipoAmbiente.HOMOLOGACAO,
        "ind_final": "1",
        "ind_pres": "1",
        "emitente": make_emitente(),
        "destinatario": {"cpf": "11144477735", "x_nome": "Cliente Teste", "ind_ie_dest": "9"},
        "pagamentos": [BRPagamento(t_pag="01", v_pag="100.00")],
        "lines": [make_line()],
    }
    data.update(overrides)
    return BRInvoice.model_validate(data)


def make_nfce(**overrides: object) -> BRInvoice:
    """Build a sample modelo-65 NFC-e (Simples Nacional / ICMSSN102, no destinatario)."""
    data: dict[str, object] = {
        "document_type": "65",
        "date": "2026-06-13",
        "number": "1",
        "seller": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
            name="Empresa Teste LTDA",
        ),
        "buyer": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
            name="Consumidor",
        ),
        "modelo": NFeModelo.NFCE,
        "serie": "1",
        "nnf": "1",
        "natureza_operacao": "Venda de mercadoria",
        "tipo_operacao": TipoOperacao.SAIDA,
        "c_uf": "35",
        "dh_emi": "2026-06-13T10:00:00-03:00",
        "id_dest": "1",
        "c_mun_fg": "3550308",
        "tp_amb": TipoAmbiente.HOMOLOGACAO,
        "tp_imp": "4",
        "ind_final": "1",
        "ind_pres": "1",
        "emitente": make_emitente(crt=RegimeTributario.SIMPLES_NACIONAL),
        "destinatario": None,
        "pagamentos": [BRPagamento(t_pag="01", v_pag="10.00")],
        "lines": [
            make_line(
                c_prod="P002",
                unit_price="10.00",
                total_price="10.00",
                v_un_com="10.00",
                v_prod="10.00",
                v_un_trib="10.00",
                icms_cst="102",
                icms_rate=None,
                icms_amount=None,
                pis_cst=None,
                pis_amount=None,
                cofins_cst=None,
                cofins_amount=None,
            )
        ],
    }
    data.update(overrides)
    return BRInvoice.model_validate(data)
