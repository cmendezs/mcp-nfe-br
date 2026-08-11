"""Shared pytest fixtures for mcp-nfe-br tests."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from mcp_einvoicing_core.models import InvoiceParty, TaxIdentifier

from mcp_nfe_br.models.cte import (
    BRCTeDocument,
    BRCteEmitente,
    BRCteICMS00,
    BRCteImp,
    BRCteInfCarga,
    BRCteInfModal,
    BRCteInfQ,
    BRCteRemetente,
    BRCteTomador,
    BRCteVPrest,
    CTeModal,
    CTeModelo,
    CTeTipoServico,
    CTeTomadorPapel,
)
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
from mcp_nfe_br.models.nfse import (
    NFSeCServ,
    NFSeDocument,
    NFSeEndereco,
    NFSeLocPrest,
    NFSeOpSimplesNacional,
    NFSePrestador,
    NFSeRegimeTributacao,
    NFSeServ,
    NFSeTipoRetISSQN,
    NFSeTomador,
    NFSeTotTrib,
    NFSeTribISSQN,
    NFSeTribMunicipal,
    NFSeValores,
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


def _generate_test_p12(path: Path, password: bytes | None = b"test") -> None:
    """Write a minimal self-signed RSA cert as PKCS#12 to *path*."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(days=365)
        )
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=(
            serialization.BestAvailableEncryption(password)
            if password
            else serialization.NoEncryption()
        ),
    )
    path.write_bytes(p12_bytes)


@pytest.fixture()
def p12_path(tmp_path: Path) -> Path:
    """Path to a self-signed PKCS#12 test certificate, password ``"test"``."""
    p = tmp_path / "cert.p12"
    _generate_test_p12(p, password=b"test")
    return p


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


def make_cte_emitente(**overrides: object) -> BRCteEmitente:
    data: dict[str, object] = {
        "cnpj": "11222333000181",
        "x_nome": "Transportadora Teste LTDA",
        "ie": "123456789",
        "endereco": make_endereco(),
        "crt": RegimeTributario.REGIME_NORMAL,
    }
    data.update(overrides)
    return BRCteEmitente.model_validate(data)


def make_cte_remetente(**overrides: object) -> BRCteRemetente:
    data: dict[str, object] = {
        "cnpj": "11444777000161",
        "x_nome": "Remetente Teste LTDA",
        "endereco": make_endereco(),
    }
    data.update(overrides)
    return BRCteRemetente.model_validate(data)


def make_cte(**overrides: object) -> BRCTeDocument:
    """Build a sample modelo-57 CT-e (modal rodoviário, tomador=remetente)."""
    data: dict[str, object] = {
        "document_type": "57",
        "date": "2026-07-03",
        "number": "1",
        "seller": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
            name="Transportadora Teste LTDA",
        ),
        "mod": CTeModelo.CTE,
        "serie": "1",
        "n_ct": "1",
        "nat_op": "Prestação de serviço de transporte",
        "tp_serv": CTeTipoServico.NORMAL,
        "modal": CTeModal.RODOVIARIO,
        "dh_emi": "2026-07-03T10:00:00-03:00",
        "c_uf": "35",
        "cfop": "5352",
        "tp_amb": "2",
        "c_mun_ini": "3550308",
        "x_mun_ini": "Sao Paulo",
        "uf_ini": "SP",
        "c_mun_fim": "3304557",
        "x_mun_fim": "Rio de Janeiro",
        "uf_fim": "RJ",
        "retira": "1",
        "emitente": make_cte_emitente(),
        "remetente": make_cte_remetente(),
        "tomador": BRCteTomador(papel=CTeTomadorPapel.REMETENTE, ind_ie_toma="1"),
        "v_prest": BRCteVPrest(v_tprest="100.00", v_rec="100.00"),
        "imp": BRCteImp(icms=BRCteICMS00(v_bc="100.00", p_icms="12.00", v_icms="12.00")),
        "inf_carga": BRCteInfCarga(
            v_carga="1000.00",
            pro_pred="Eletrônicos",
            inf_q=[BRCteInfQ(c_unid="01", tp_med="PESO BRUTO", q_carga="100.0000")],
        ),
        "inf_modal": BRCteInfModal(modal=CTeModal.RODOVIARIO, rntrc="12345678"),
    }
    data.update(overrides)
    return BRCTeDocument.model_validate(data)


def make_nfse_endereco(**overrides: object) -> NFSeEndereco:
    data: dict[str, object] = {
        "x_lgr": "Rua Teste",
        "nro": "123",
        "x_bairro": "Centro",
        "c_mun": "3550308",
        "cep": "01000000",
    }
    data.update(overrides)
    return NFSeEndereco.model_validate(data)


def make_nfse_prestador(**overrides: object) -> NFSePrestador:
    data: dict[str, object] = {
        "cnpj": "11222333000181",
        "x_nome": "Prestador Teste LTDA",
        "end": make_nfse_endereco(),
        "reg_trib": NFSeRegimeTributacao(
            op_simp_nac=NFSeOpSimplesNacional.NAO_OPTANTE, reg_esp_trib="0"
        ),
    }
    data.update(overrides)
    return NFSePrestador.model_validate(data)


def make_nfse_tomador(**overrides: object) -> NFSeTomador:
    data: dict[str, object] = {
        "cpf": "11144477735",
        "x_nome": "Tomador Teste",
        "end": make_nfse_endereco(x_lgr="Avenida Teste", nro="456"),
    }
    data.update(overrides)
    return NFSeTomador.model_validate(data)


def make_nfse(**overrides: object) -> NFSeDocument:
    """Build a fully-populated DPS: prestador + tomador (national addresses),
    regTrib with regEspTrib, tribMun with pAliq, dCompet dashed."""
    data: dict[str, object] = {
        "document_type": "DPS",
        "date": "2026-07-01",
        "number": "1",
        "seller": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11222333000181"),
            name="Prestador Teste LTDA",
        ),
        "buyer": InvoiceParty(
            tax_id=TaxIdentifier(country_code="BR", identifier="11144477735"),
            name="Tomador Teste",
        ),
        "tp_amb": TipoAmbiente.HOMOLOGACAO,
        "serie": "1",
        "n_dps": "1",
        "d_compet": "2026-07-01",
        "c_loc_emi": "3550308",
        "prest": make_nfse_prestador(),
        "toma": make_nfse_tomador(),
        "serv": NFSeServ(
            loc_prest=NFSeLocPrest(c_loc_prestacao="3550308"),
            c_serv=NFSeCServ(c_trib_nac="010101", x_desc_serv="Serviço de teste"),
        ),
        "valores": NFSeValores(
            v_serv="100.00",
            trib_mun=NFSeTribMunicipal(
                trib_issqn=NFSeTribISSQN.TRIBUTAVEL,
                tp_ret_issqn=NFSeTipoRetISSQN.NAO_RETIDO,
                p_aliq="5.00",
            ),
            tot_trib=NFSeTotTrib(ind_tot_trib="0"),
        ),
    }
    data.update(overrides)
    return NFSeDocument.model_validate(data)
