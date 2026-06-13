"""NF-e / NFC-e (modelo 55/65, schema 4.00) XML generator.

Assembles an **unsigned** `<NFe><infNFe>…</infNFe></NFe>` document from a
`BRInvoice`. Field order within each group (`ide`, `emit`, `dest`, `det`,
`total`, `transp`, `pag`) follows `schemas/nfe/leiauteNFe_v4.00.xsd`
(PL_010d) `[Verified locally]`.

ICP-Brasil XML-DSig signing is a later phase — no `<Signature>` element is
emitted. The seam is the returned XML string: a signer would parse it,
insert `<Signature>` as the last child of `<infNFe>`, and re-serialize.

Phase 1 tax-code coverage is intentionally narrow:

- ICMS: CST "00" (`ICMS00`, regime normal) or CSOSN "102" (`ICMSSN102`,
  Simples Nacional). Other codes raise `DocumentGenerationError`
  `[NEED: extend ICMS group coverage]`.
- PIS/COFINS: CST "01"/"02" (`*Aliq`) or "04"-"09" (`*NT`). The group is
  omitted entirely when `pis_cst`/`cofins_cst` is `None` (both are
  `minOccurs="0"` in the schema).
- IPI: CST "00"/"49"/"50"/"99" (`IPITrib`, `cEnq` placeholder "999"
  `[Unverified]`) or any other code (`IPINT`). Omitted when `ipi_cst` is
  `None` (`minOccurs="0"`).

IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) are
`[NEED: not yet modeled]` and not emitted.
"""

from __future__ import annotations

import secrets
from decimal import Decimal

from mcp_einvoicing_core import BaseDocumentGenerator, DocumentGenerationError, InvoiceDocument
from mcp_einvoicing_core.xml_utils import format_amount, format_quantity, xml_element, xml_optional

from mcp_nfe_br.models.invoice import (
    BREndereco,
    BRInvoice,
    BRInvoiceLine,
)
from mcp_nfe_br.utils.access_key import build_access_key

_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
_VERSAO = "4.00"

# Tax-code coverage tables — Phase 1 (see module docstring).
_ICMS_CST_NORMAL = {"00"}
_ICMS_CSOSN_SIMPLES = {"102"}
_PIS_COFINS_ALIQ = {"01", "02"}
_PIS_COFINS_NT = {"04", "05", "06", "07", "08", "09"}
_IPI_TRIBUTADO = {"00", "49", "50", "99"}


def _d2(value: str | Decimal) -> str:
    """Format a monetary value to TDec_1302 (2 decimal places)."""
    return format_amount(Decimal(str(value)), 2)


def _qty(value: str | Decimal) -> str:
    """Format a quantity to TDec_1110v (strip trailing zeros, up to 4 dp)."""
    return format_quantity(Decimal(str(value)), 4)


def _unit_price(value: str | Decimal) -> str:
    """Format a unit price to TDec_1110v (strip trailing zeros, up to 10 dp)."""
    return format_quantity(Decimal(str(value)), 10)


def _percent(value: str | Decimal) -> str:
    """Format a percentage to TDec_0302a04 (2-4 decimal places)."""
    return format_amount(Decimal(str(value)), 4)


def _endereco_block(tag: str, end: BREndereco, *, include_fone: bool = True) -> str:
    parts = [
        xml_element("xLgr", end.x_lgr),
        xml_element("nro", end.nro),
        xml_optional("xCpl", end.x_cpl),
        xml_element("xBairro", end.x_bairro),
        xml_element("cMun", end.c_mun),
        xml_element("xMun", end.x_mun),
        xml_element("UF", end.uf),
        xml_element("CEP", end.cep),
        xml_element("cPais", "1058"),
        xml_element("xPais", "Brasil"),
    ]
    if include_fone:
        parts.append(xml_optional("fone", end.fone))
    return xml_element(tag, "".join(p for p in parts if p), unsafe=True)


def _emit_block(invoice: BRInvoice) -> str:
    emit = invoice.emitente
    doc_block = (
        xml_element("CNPJ", emit.cnpj) if emit.cnpj else xml_element("CPF", emit.cpf or "")
    )
    parts = [
        doc_block,
        xml_element("xNome", emit.x_nome),
        xml_optional("xFant", emit.x_fant),
        _endereco_block("enderEmit", emit.ender_emit),
        xml_element("IE", emit.ie),
        xml_optional("IEST", emit.ie_st),
        xml_optional("IM", emit.im),
        xml_element("CRT", emit.crt.value),
    ]
    return xml_element("emit", "".join(p for p in parts if p), unsafe=True)


def _dest_block(invoice: BRInvoice) -> str:
    dest = invoice.destinatario
    if dest is None:
        return ""
    doc_block = ""
    if dest.cnpj:
        doc_block = xml_element("CNPJ", dest.cnpj)
    elif dest.cpf:
        doc_block = xml_element("CPF", dest.cpf)

    parts = [
        doc_block,
        xml_optional("xNome", dest.x_nome),
        _endereco_block("enderDest", dest.ender_dest, include_fone=True) if dest.ender_dest else "",
        xml_element("indIEDest", dest.ind_ie_dest),
        xml_optional("IE", dest.ie),
        xml_optional("email", dest.email),
    ]
    return xml_element("dest", "".join(p for p in parts if p), unsafe=True)


def _icms_block(line: BRInvoiceLine) -> str:
    cst = line.icms_cst
    if cst in _ICMS_CST_NORMAL:
        v_prod = Decimal(line.v_prod)
        inner = "".join(
            [
                xml_element("orig", line.icms_orig),
                xml_element("CST", cst),
                xml_element("modBC", "3"),
                xml_element("vBC", _d2(v_prod)),
                xml_element("pICMS", _percent(line.icms_rate or "0")),
                xml_element("vICMS", _d2(line.icms_amount or "0")),
                xml_element("pFCP", _percent("0")),
                xml_element("vFCP", _d2("0")),
            ]
        )
        return xml_element("ICMS", xml_element("ICMS00", inner, unsafe=True), unsafe=True)
    if cst in _ICMS_CSOSN_SIMPLES:
        inner = "".join(
            [
                xml_element("orig", line.icms_orig),
                xml_element("CSOSN", cst),
            ]
        )
        return xml_element("ICMS", xml_element("ICMSSN102", inner, unsafe=True), unsafe=True)
    raise DocumentGenerationError(
        f"Código de situação tributária do ICMS não suportado na Fase 1: {cst!r} "
        f"(item {line.c_prod}). Suportados: CST {sorted(_ICMS_CST_NORMAL)} "
        f"(ICMS00) ou CSOSN {sorted(_ICMS_CSOSN_SIMPLES)} (ICMSSN102)."
    )


def _pis_cofins_block(tag: str, cst: str | None, amount: str | None, v_prod: Decimal) -> str:
    if cst is None:
        return ""
    aliq_tag = f"{tag}Aliq"
    nt_tag = f"{tag}NT"
    rate_tag = "pPIS" if tag == "PIS" else "pCOFINS"
    value_tag = "vPIS" if tag == "PIS" else "vCOFINS"

    if cst in _PIS_COFINS_ALIQ:
        amt = Decimal(amount or "0")
        rate = (amt / v_prod * Decimal("100")) if v_prod else Decimal("0")
        inner = "".join(
            [
                xml_element("CST", cst),
                xml_element("vBC", _d2(v_prod)),
                xml_element(rate_tag, _percent(rate)),
                xml_element(value_tag, _d2(amt)),
            ]
        )
        return xml_element(tag, xml_element(aliq_tag, inner, unsafe=True), unsafe=True)
    if cst in _PIS_COFINS_NT:
        inner = xml_element("CST", cst)
        return xml_element(tag, xml_element(nt_tag, inner, unsafe=True), unsafe=True)
    raise DocumentGenerationError(
        f"Código de situação tributária do {tag} não suportado na Fase 1: {cst!r}. "
        f"Suportados: {sorted(_PIS_COFINS_ALIQ)} ({aliq_tag}) ou "
        f"{sorted(_PIS_COFINS_NT)} ({nt_tag})."
    )


def _ipi_block(line: BRInvoiceLine) -> str:
    cst = line.ipi_cst
    if cst is None:
        return ""
    if cst in _IPI_TRIBUTADO:
        v_prod = Decimal(line.v_prod)
        amt = Decimal(line.ipi_amount or "0")
        rate = (amt / v_prod * Decimal("100")) if v_prod else Decimal("0")
        ipi_inner = "".join(
            [
                xml_element("CST", cst),
                xml_element("vBC", _d2(v_prod)),
                xml_element("pIPI", _percent(rate)),
                xml_element("vIPI", _d2(amt)),
            ]
        )
        variant = xml_element("IPITrib", ipi_inner, unsafe=True)
    else:
        variant = xml_element("IPINT", xml_element("CST", cst), unsafe=True)

    inner = xml_element("cEnq", "999") + variant
    return xml_element("IPI", inner, unsafe=True)


def _det_block(line: BRInvoiceLine, n_item: int) -> str:
    prod_parts = [
        xml_element("cProd", line.c_prod),
        xml_element("cEAN", line.c_ean),
        xml_element("xProd", line.description),
        xml_element("NCM", line.ncm),
        xml_optional("CEST", line.cest),
        xml_element("CFOP", line.cfop),
        xml_element("uCom", line.u_com),
        xml_element("qCom", _qty(line.q_com)),
        xml_element("vUnCom", _unit_price(line.v_un_com)),
        xml_element("vProd", _d2(line.v_prod)),
        xml_element("cEANTrib", line.c_ean_trib),
        xml_element("uTrib", line.u_trib),
        xml_element("qTrib", _qty(line.q_trib)),
        xml_element("vUnTrib", _unit_price(line.v_un_trib)),
        xml_element("indTot", line.ind_tot),
    ]
    prod = xml_element("prod", "".join(prod_parts), unsafe=True)

    v_prod = Decimal(line.v_prod)
    imposto_parts = [
        _icms_block(line),
        _ipi_block(line),
        _pis_cofins_block("PIS", line.pis_cst, line.pis_amount, v_prod),
        _pis_cofins_block("COFINS", line.cofins_cst, line.cofins_amount, v_prod),
    ]
    imposto = xml_element("imposto", "".join(p for p in imposto_parts if p), unsafe=True)

    return xml_element("det", prod + imposto, attrs={"nItem": str(n_item)}, unsafe=True)


def _icms_tot_block(invoice: BRInvoice) -> str:
    v_prod = sum((Decimal(line.v_prod) for line in invoice.lines), Decimal("0"))
    v_bc = sum(
        (Decimal(line.v_prod) for line in invoice.lines if line.icms_cst in _ICMS_CST_NORMAL),
        Decimal("0"),
    )
    v_icms = sum(
        (Decimal(line.icms_amount or "0") for line in invoice.lines if line.icms_amount),
        Decimal("0"),
    )
    v_ipi = sum(
        (Decimal(line.ipi_amount or "0") for line in invoice.lines if line.ipi_amount),
        Decimal("0"),
    )
    v_pis = sum(
        (Decimal(line.pis_amount or "0") for line in invoice.lines if line.pis_amount),
        Decimal("0"),
    )
    v_cofins = sum(
        (Decimal(line.cofins_amount or "0") for line in invoice.lines if line.cofins_amount),
        Decimal("0"),
    )
    v_nf = v_prod + v_ipi

    fields = {
        "vBC": v_bc,
        "vICMS": v_icms,
        "vICMSDeson": Decimal("0"),
        "vFCP": Decimal("0"),
        "vBCST": Decimal("0"),
        "vST": Decimal("0"),
        "vFCPST": Decimal("0"),
        "vFCPSTRet": Decimal("0"),
        "vProd": v_prod,
        "vFrete": Decimal("0"),
        "vSeg": Decimal("0"),
        "vDesc": Decimal("0"),
        "vII": Decimal("0"),
        "vIPI": v_ipi,
        "vIPIDevol": Decimal("0"),
        "vPIS": v_pis,
        "vCOFINS": v_cofins,
        "vOutro": Decimal("0"),
        "vNF": v_nf,
    }
    inner = "".join(xml_element(tag, _d2(val)) for tag, val in fields.items())
    return xml_element("total", xml_element("ICMSTot", inner, unsafe=True), unsafe=True)


def _transp_block(invoice: BRInvoice) -> str:
    return xml_element("transp", xml_element("modFrete", invoice.mod_frete), unsafe=True)


def _pag_block(invoice: BRInvoice) -> str:
    emit = invoice.emitente
    fallback_cnpj = emit.cnpj or (emit.cpf or "").zfill(14)
    fallback_uf = emit.ender_emit.uf

    det_pags = []
    for pag in invoice.pagamentos:
        parts = [
            xml_optional("indPag", pag.ind_pag),
            xml_element("tPag", pag.t_pag),
            xml_optional("xPag", pag.x_pag),
            xml_element("vPag", _d2(pag.v_pag)),
            xml_optional("dPag", pag.d_pag),
            xml_element("CNPJPag", pag.cnpj_pag or fallback_cnpj),
            xml_element("UFPag", pag.uf_pag or fallback_uf),
        ]
        det_pags.append(xml_element("detPag", "".join(p for p in parts if p), unsafe=True))

    return xml_element("pag", "".join(det_pags), unsafe=True)


def _ide_block(invoice: BRInvoice, *, cnf: str, cdv: str) -> str:
    parts = [
        xml_element("cUF", invoice.c_uf),
        xml_element("cNF", cnf),
        xml_element("natOp", invoice.natureza_operacao),
        xml_element("mod", invoice.modelo.value),
        xml_element("serie", invoice.serie),
        xml_element("nNF", invoice.nnf),
        xml_element("dhEmi", invoice.dh_emi),
        xml_element("tpNF", invoice.tipo_operacao.value),
        xml_element("idDest", invoice.id_dest),
        xml_element("cMunFG", invoice.c_mun_fg),
        xml_element("tpImp", invoice.tp_imp),
        xml_element("tpEmis", invoice.tp_emis),
        xml_element("cDV", cdv),
        xml_element("tpAmb", invoice.tp_amb.value),
        xml_element("finNFe", invoice.fin_nfe),
        xml_element("indFinal", invoice.ind_final),
        xml_element("indPres", invoice.ind_pres),
        xml_element("procEmi", invoice.proc_emi),
        xml_element("verProc", invoice.ver_proc),
    ]
    return xml_element("ide", "".join(parts), unsafe=True)


class NFeGenerator(BaseDocumentGenerator):
    """Generates unsigned NF-e/NFC-e (modelo 55/65, schema 4.00) XML."""

    def get_format_name(self) -> str:
        return "NF-e/NFC-e 4.00"

    def get_country_code(self) -> str:
        return "BR"

    def get_namespace(self) -> str:
        return _NAMESPACE

    def generate(self, document: InvoiceDocument) -> str:
        if not isinstance(document, BRInvoice):
            raise DocumentGenerationError(
                f"NFeGenerator requer um BRInvoice, recebido {type(document).__name__}."
            )
        invoice = document

        if not invoice.lines:
            raise DocumentGenerationError("A NF-e/NFC-e requer ao menos um item (Grupo det/prod).")

        cnf = invoice.c_nf or f"{secrets.randbelow(10**8):08d}"
        cnpj_for_key = invoice.emitente.cnpj or (invoice.emitente.cpf or "").zfill(14)
        access_key = build_access_key(
            cuf=invoice.c_uf,
            dh_emi=invoice.dh_emi,
            cnpj=cnpj_for_key,
            modelo=invoice.modelo.value,
            serie=invoice.serie,
            nnf=invoice.nnf,
            tp_emis=invoice.tp_emis,
            cnf=cnf,
        )
        if invoice.chave_acesso is not None and invoice.chave_acesso != access_key:
            raise DocumentGenerationError(
                "A chave de acesso informada não corresponde aos dados do documento: "
                f"esperado {access_key!r}, recebido {invoice.chave_acesso!r}."
            )
        cdv = access_key[-1]

        ide = _ide_block(invoice, cnf=cnf, cdv=cdv)
        emit = _emit_block(invoice)
        dest = _dest_block(invoice)
        dets = "".join(
            _det_block(line, n_item) for n_item, line in enumerate(invoice.lines, start=1)
        )
        total = _icms_tot_block(invoice)
        transp = _transp_block(invoice)
        pag = _pag_block(invoice)

        inf_nfe_body = ide + emit + dest + dets + total + transp + pag
        inf_nfe = xml_element(
            "infNFe",
            inf_nfe_body,
            attrs={"Id": f"NFe{access_key}", "versao": _VERSAO},
            unsafe=True,
        )
        return f'<?xml version="1.0" encoding="UTF-8"?><NFe xmlns="{_NAMESPACE}">{inf_nfe}</NFe>'
