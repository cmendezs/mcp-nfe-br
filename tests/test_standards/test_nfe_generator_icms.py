"""Tests for extended ICMS CST/CSOSN coverage in NFeGenerator (v0.3.0 item 3).

Each case generates an NF-e for a single tax code and validates the result
against the bundled unsigned PL_010d XSD (`NFeXSDValidator`), pinning both
the chosen ICMS sub-group name and overall schema validity.
"""

from __future__ import annotations

from mcp_nfe_br.standards.nfe_generator import NFeGenerator
from mcp_nfe_br.validators.nfe_xsd import NFeXSDValidator
from tests.conftest import make_line, make_nfe


def _generate_and_validate(line_overrides: dict[str, object]) -> str:
    invoice = make_nfe(lines=[make_line(**line_overrides)])
    xml = NFeGenerator().generate(invoice)
    result = NFeXSDValidator().validate(xml)
    assert result.valid is True, result.errors
    return xml


def test_icms10_tributada_com_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "10",
            "icms_rate": "18",
            "icms_amount": "18.00",
            "icms_v_bc_st": "118.00",
            "icms_p_icms_st": "20",
            "icms_v_icms_st": "23.60",
        }
    )
    assert "<ICMS10>" in xml
    assert "<vICMSST>23.60</vICMSST>" in xml


def test_icms20_reducao_de_bc() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "20",
            "icms_p_red_bc": "33.3333",
            "icms_rate": "18",
            "icms_amount": "12.00",
        }
    )
    assert "<ICMS20>" in xml
    assert "<pRedBC>33.3333</pRedBC>" in xml


def test_icms30_isenta_com_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "30",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
        }
    )
    assert "<ICMS30>" in xml


def test_icms40_isenta() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "40", "icms_rate": None, "icms_amount": None}
    )
    assert "<ICMS40>" in xml
    assert "<CST>40</CST>" in xml


def test_icms41_nao_tributada() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "41", "icms_rate": None, "icms_amount": None}
    )
    assert "<CST>41</CST>" in xml


def test_icms50_suspensao() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "50", "icms_rate": None, "icms_amount": None}
    )
    assert "<CST>50</CST>" in xml


def test_icms51_diferimento() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "51", "icms_rate": None, "icms_amount": None}
    )
    assert "<ICMS51>" in xml


def test_icms60_cobrado_anteriormente_por_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "60",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st_ret": "100.00",
            "icms_p_st": "18",
            "icms_v_icms_st_ret": "18.00",
        }
    )
    assert "<ICMS60>" in xml
    assert "<vICMSSTRet>18.00</vICMSSTRet>" in xml


def test_icms70_reducao_de_bc_com_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "70",
            "icms_p_red_bc": "20",
            "icms_rate": "18",
            "icms_amount": "14.40",
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
        }
    )
    assert "<ICMS70>" in xml


def test_icms90_outras_com_bc_e_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "90",
            "icms_rate": "18",
            "icms_amount": "18.00",
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
        }
    )
    assert "<ICMS90>" in xml


def test_icms90_outras_sem_campos_opcionais() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "90", "icms_rate": None, "icms_amount": None}
    )
    assert "<ICMS90>" in xml


def test_csosn101_simples_com_credito() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "101",
            "icms_rate": None,
            "icms_amount": None,
            "icms_p_cred_sn": "2.5",
            "icms_v_cred_icms_sn": "2.50",
        }
    )
    assert "<ICMSSN101>" in xml
    assert "<vCredICMSSN>2.50</vCredICMSSN>" in xml


def test_csosn103_isencao_faixa_receita() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "103", "icms_rate": None, "icms_amount": None}
    )
    assert "<ICMSSN102>" in xml
    assert "<CSOSN>103</CSOSN>" in xml


def test_csosn300_imune() -> None:
    xml = _generate_and_validate(
        {"icms_cst": "300", "icms_rate": None, "icms_amount": None}
    )
    assert "<ICMSSN102>" in xml
    assert "<CSOSN>300</CSOSN>" in xml


def test_csosn201_st_com_credito() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "201",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
            "icms_p_cred_sn": "2.5",
            "icms_v_cred_icms_sn": "2.50",
        }
    )
    assert "<ICMSSN201>" in xml


def test_csosn202_st_sem_credito() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "202",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
        }
    )
    assert "<ICMSSN202>" in xml
    assert "<CSOSN>202</CSOSN>" in xml


def test_csosn203_st_sem_credito() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "203",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st": "100.00",
            "icms_p_icms_st": "18",
            "icms_v_icms_st": "18.00",
        }
    )
    assert "<CSOSN>203</CSOSN>" in xml


def test_csosn500_cobrado_anteriormente_por_st() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "500",
            "icms_rate": None,
            "icms_amount": None,
            "icms_v_bc_st_ret": "100.00",
            "icms_p_st": "18",
            "icms_v_icms_st_ret": "18.00",
        }
    )
    assert "<ICMSSN500>" in xml


def test_csosn900_outras() -> None:
    xml = _generate_and_validate(
        {
            "icms_cst": "900",
            "icms_rate": "18",
            "icms_amount": "18.00",
            "icms_p_cred_sn": "1",
            "icms_v_cred_icms_sn": "1.00",
        }
    )
    assert "<ICMSSN900>" in xml


def test_icms_tot_includes_vbcst_and_vst() -> None:
    invoice = make_nfe(
        lines=[
            make_line(
                icms_cst="10",
                icms_rate="18",
                icms_amount="18.00",
                icms_v_bc_st="118.00",
                icms_p_icms_st="20",
                icms_v_icms_st="23.60",
            )
        ]
    )
    xml = NFeGenerator().generate(invoice)
    assert "<vBCST>118.00</vBCST>" in xml
    assert "<vST>23.60</vST>" in xml


# ---------------------------------------------------------------------------
# BR-SC-4: hardcoded pFCP / vFCP removed from ICMS00
# ---------------------------------------------------------------------------


def test_icms00_omits_fcp_fields() -> None:
    xml = _generate_and_validate({"icms_cst": "00", "icms_rate": "18", "icms_amount": "18.00"})
    assert "<ICMS00>" in xml
    # Extract the per-line ICMS00 sub-element only (not ICMSTot which has <vFCP> totals)
    start = xml.index("<ICMS00>")
    end = xml.index("</ICMS00>") + len("</ICMS00>")
    icms00_block = xml[start:end]
    assert "<pFCP>" not in icms00_block
    assert "<vFCP>" not in icms00_block
