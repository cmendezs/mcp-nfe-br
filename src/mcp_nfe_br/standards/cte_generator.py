"""CT-e (modelo 57, schema 4.00) XML generator.

Assembles an **unsigned** `<CTe><infCte>…</infCte></CTe>` document from a
`BRCTeDocument`. Field order within each group follows
`schemas/cte/cteTiposBasico_v4.00.xsd` `[Verified locally]`.

v1 scope (roadmap BR-CTE-8, "single-modal-first, event-limited"):

- Modal: rodoviário only. `infModal` is `<xs:any processContents="skip">`
  in the main CT-e schema — the main document validates regardless of the
  modal-specific payload's own schema conformance, but this generator only
  emits a minimal, schema-shaped `<rodo><RNTRC>…</RNTRC></rodo>` payload
  for that modal. Other modais raise `DocumentGenerationError`.
- ICMS: CST 00 (tributação normal) only, mirroring `nfe_generator.py`'s
  initial narrow ICMS coverage. Other CT-e ICMS variants
  `[NEED: not modeled]`.
- Optional groups not modeled/emitted: `compl`, `Entrega`, `autXML`,
  `infRespTec`, `infDoc`, `ICMSUFFim`, `infAdFisco`, `veicNovos`, `lacres`,
  `origCalc`/`destCalc`, `gCompraGov`.

`imp/IBSCBS` and `ide/tpPagAnt`+`gPagAntecipado` (Reforma Tributária do
Consumo, NT 2026.002, closes GitHub issue cmendezs/mcp-nfe-br#5) are
emitted when present on the document. Sibling position `[Verified locally]`
against `PL_CTe_400_NT2026.002 RTC_1.00.zip`: `imp` sequence is
`ICMS → vTotTrib? → infAdFisco? → ICMSUFFim? → IBSCBS? → vTotDFe?` (the
three unmodeled optional siblings are simply omitted — skipping an
`xs:sequence` optional element does not break ordering); `ide`'s
`tpPagAnt`/`gPagAntecipado` follow the `toma3`/`toma4` choice, which is
why they are appended after `_tomador_block` below. See models/cte.py
module docstring for the full RTC scope and outstanding `[NEED]` markers.

ICP-Brasil XML-DSig signing is a separate phase (`cte_signer.py`, BR-CTE-6)
— no `<Signature>` element is emitted here.
"""

from __future__ import annotations

import secrets

from mcp_einvoicing_core import BaseDocumentGenerator, DocumentGenerationError, InvoiceDocument
from mcp_einvoicing_core.xml_utils import xml_element, xml_optional

from mcp_nfe_br.models.cte import (
    BRCTeDocument,
    BRCteParty,
    CTeModal,
)
from mcp_nfe_br.utils.cte_access_key import build_cte_access_key

_NAMESPACE = "http://www.portalfiscal.inf.br/cte"
_VERSAO = "4.00"


def _endereco_block(tag: str, end, *, include_fone: bool = False, fone: str | None = None) -> str:
    """CT-e address block (`TEndeEmi`/`TEndereco`): xLgr, nro, xCpl?,
    xBairro, cMun, xMun, CEP?, UF, (fone? — `TEndeEmi`/emit only)."""
    parts = [
        xml_element("xLgr", end.x_lgr),
        xml_element("nro", end.nro),
        xml_optional("xCpl", end.x_cpl),
        xml_element("xBairro", end.x_bairro),
        xml_element("cMun", end.c_mun),
        xml_element("xMun", end.x_mun),
        xml_optional("CEP", end.cep),
        xml_element("UF", end.uf),
    ]
    if include_fone:
        parts.append(xml_optional("fone", fone))
    return xml_element(tag, "".join(p for p in parts if p), unsafe=True)


def _emit_block(cte: BRCTeDocument) -> str:
    emit = cte.emitente
    doc_block = (
        xml_element("CNPJ", emit.cnpj) if emit.cnpj else xml_element("CPF", emit.cpf or "")
    )
    parts = [
        doc_block,
        xml_optional("IE", emit.ie),
        xml_element("xNome", emit.x_nome),
        _endereco_block("enderEmit", emit.endereco, include_fone=True, fone=emit.fone),
        xml_element("CRT", emit.crt.value),
        xml_optional("ISUFEmit", emit.isuf_emit),
    ]
    return xml_element("emit", "".join(p for p in parts if p), unsafe=True)


def _party_block(tag: str, ender_tag: str, party: BRCteParty | None) -> str:
    """Generic block for `rem`/`exped`/`receb`/`dest` — all share the same
    field order: CNPJ|CPF, IE?, xNome, fone?, ender<X>, email?."""
    if party is None:
        return ""
    doc_block = xml_element("CNPJ", party.cnpj) if party.cnpj else xml_element("CPF", party.cpf or "")
    parts = [
        doc_block,
        xml_optional("IE", party.ie),
        xml_element("xNome", party.x_nome),
        xml_optional("fone", party.fone),
        _endereco_block(ender_tag, party.endereco),
        xml_optional("email", party.email),
    ]
    return xml_element(tag, "".join(p for p in parts if p), unsafe=True)


def _ide_block(cte: BRCTeDocument, *, c_ct: str, cdv: str) -> str:
    parts = [
        xml_element("cUF", cte.c_uf),
        xml_element("cCT", c_ct),
        xml_element("CFOP", cte.cfop),
        xml_element("natOp", cte.nat_op),
        xml_element("mod", cte.mod.value),
        xml_element("serie", cte.serie),
        xml_element("nCT", cte.n_ct),
        xml_element("dhEmi", cte.dh_emi),
        xml_element("tpImp", "1"),
        xml_element("tpEmis", "1"),
        xml_element("cDV", cdv),
        xml_element("tpAmb", cte.tp_amb),
        xml_element("tpCTe", cte.tp_cte.value),
        xml_element("procEmi", "0"),
        xml_element("verProc", "mcp-nfe-br"),
        xml_element("cMunEnv", cte.c_mun_ini),
        xml_element("xMunEnv", cte.x_mun_ini),
        xml_element("UFEnv", cte.uf_ini),
        xml_element("modal", cte.modal.value),
        xml_element("tpServ", cte.tp_serv.value),
        xml_element("cMunIni", cte.c_mun_ini),
        xml_element("xMunIni", cte.x_mun_ini),
        xml_element("UFIni", cte.uf_ini),
        xml_element("cMunFim", cte.c_mun_fim),
        xml_element("xMunFim", cte.x_mun_fim),
        xml_element("UFFim", cte.uf_fim),
        xml_element("retira", cte.retira),
        xml_element("indIEToma", cte.tomador.ind_ie_toma),
        _tomador_block(cte),
        xml_optional("tpPagAnt", cte.tp_pag_ant),
        _pag_antecipado_block(cte),
    ]
    return xml_element("ide", "".join(p for p in parts if p), unsafe=True)


def _pag_antecipado_block(cte: BRCTeDocument) -> str:
    if not cte.pag_antecipado:
        return ""
    keys = "".join(xml_element("chCTePagAnt", key) for key in cte.pag_antecipado)
    return xml_element("gPagAntecipado", keys, unsafe=True)


def _tomador_block(cte: BRCTeDocument) -> str:
    tomador = cte.tomador
    if tomador.papel is not None:
        return xml_element("toma3", xml_element("toma", tomador.papel.value), unsafe=True)
    outros = tomador.outros
    assert outros is not None  # guaranteed by BRCteTomador.check_one_choice
    doc_block = xml_element("CNPJ", outros.cnpj) if outros.cnpj else xml_element("CPF", outros.cpf or "")
    parts = [
        xml_element("toma", "4"),
        doc_block,
        xml_optional("IE", outros.ie),
        xml_element("xNome", outros.x_nome),
        xml_optional("fone", outros.fone),
        _endereco_block("enderToma", outros.endereco),
        xml_optional("email", outros.email),
    ]
    return xml_element("toma4", "".join(p for p in parts if p), unsafe=True)


def _v_prest_block(cte: BRCTeDocument) -> str:
    v_prest = cte.v_prest
    comps = "".join(
        xml_element("Comp", xml_element("xNome", c.x_nome) + xml_element("vComp", c.v_comp), unsafe=True)
        for c in v_prest.comp
    )
    parts = [
        xml_element("vTPrest", v_prest.v_tprest),
        xml_element("vRec", v_prest.v_rec),
        comps,
    ]
    return xml_element("vPrest", "".join(p for p in parts if p), unsafe=True)


def _imp_block(cte: BRCTeDocument) -> str:
    icms = cte.imp.icms
    icms00 = xml_element(
        "ICMS00",
        xml_element("CST", icms.cst) + xml_element("vBC", icms.v_bc) + xml_element("pICMS", icms.p_icms) + xml_element("vICMS", icms.v_icms),
        unsafe=True,
    )
    parts = [
        xml_element("ICMS", icms00, unsafe=True),
        xml_optional("vTotTrib", cte.imp.v_tot_trib),
        _ibscbs_block(cte),
    ]
    return xml_element("imp", "".join(p for p in parts if p), unsafe=True)


def _dif_block(tag: str, dif) -> str:
    if dif is None:
        return ""
    return xml_element(tag, xml_element("pDif", dif.p_dif) + xml_element("vDif", dif.v_dif), unsafe=True)


def _red_block(tag: str, red) -> str:
    if red is None:
        return ""
    return xml_element(
        tag, xml_element("pRedAliq", red.p_red_aliq) + xml_element("pAliqEfet", red.p_aliq_efet), unsafe=True
    )


def _alczfmcbs_block(alc) -> str:
    if alc is None:
        return ""
    return xml_element(
        "gALCZFMCBS",
        xml_element("pAliqEfetRegCBS", alc.p_aliq_efet_reg_cbs) + xml_element("vTribRegCBS", alc.v_trib_reg_cbs),
        unsafe=True,
    )


def _trib_regular_block(reg) -> str:
    if reg is None:
        return ""
    parts = (
        xml_element("CSTReg", reg.cst_reg)
        + xml_element("cClassTribReg", reg.c_class_trib_reg)
        + xml_element("pAliqEfetRegIBSUF", reg.p_aliq_efet_reg_ibsuf)
        + xml_element("vTribRegIBSUF", reg.v_trib_reg_ibsuf)
        + xml_element("pAliqEfetRegIBSMun", reg.p_aliq_efet_reg_ibsmun)
        + xml_element("vTribRegIBSMun", reg.v_trib_reg_ibsmun)
        + xml_element("pAliqEfetRegCBS", reg.p_aliq_efet_reg_cbs)
        + xml_element("vTribRegCBS", reg.v_trib_reg_cbs)
    )
    return xml_element("gTribRegular", parts, unsafe=True)


def _trib_compra_gov_block(cg) -> str:
    if cg is None:
        return ""
    parts = (
        xml_element("pAliqIBSUF", cg.p_aliq_ibsuf)
        + xml_element("vTribIBSUF", cg.v_trib_ibsuf)
        + xml_element("pAliqIBSMun", cg.p_aliq_ibsmun)
        + xml_element("vTribIBSMun", cg.v_trib_ibsmun)
        + xml_element("pAliqCBS", cg.p_aliq_cbs)
        + xml_element("vTribCBS", cg.v_trib_cbs)
    )
    return xml_element("gTribCompraGov", parts, unsafe=True)


def _estorno_cred_block(ec) -> str:
    if ec is None:
        return ""
    return xml_element(
        "gEstornoCred",
        xml_element("vIBSEstCred", ec.v_ibs_est_cred) + xml_element("vCBSEstCred", ec.v_cbs_est_cred),
        unsafe=True,
    )


def _ibscbs_block(cte: BRCTeDocument) -> str:
    """`imp/IBSCBS` (`TTribCTe`). Sequence `[Verified locally]` against
    `PL_CTe_400_NT2026.002 RTC_1.00.zip`: `CST → cClassTrib → indDoacao? →
    gIBSCBS? → gEstornoCred?`; `gIBSCBS` (`TCIBS`) is `vBC → gIBSUF →
    gIBSMun → vIBS → gCBS → gTribRegular? → gTribCompraGov?`. `gDevTrib` is
    intentionally never emitted — `BRCTeDocument.check_no_devolucao_for_cte`
    rejects it at the model layer before a document reaches the generator
    (NT 2026.002 RV 5.001-003: not valid for CT-e)."""
    ibscbs = cte.imp.ibscbs
    if ibscbs is None:
        return ""
    parts = [
        xml_element("CST", ibscbs.cst),
        xml_element("cClassTrib", ibscbs.c_class_trib),
        xml_optional("indDoacao", ibscbs.ind_doacao),
    ]
    g = ibscbs.g_ibscbs
    if g is not None:
        ibsuf = xml_element(
            "gIBSUF",
            xml_element("pIBSUF", g.g_ibsuf.p_ibsuf)
            + _dif_block("gDif", g.g_ibsuf.g_dif)
            + _red_block("gRed", g.g_ibsuf.g_red)
            + xml_element("vIBSUF", g.g_ibsuf.v_ibsuf),
            unsafe=True,
        )
        ibsmun = xml_element(
            "gIBSMun",
            xml_element("pIBSMun", g.g_ibsmun.p_ibsmun)
            + _dif_block("gDif", g.g_ibsmun.g_dif)
            + _red_block("gRed", g.g_ibsmun.g_red)
            + xml_element("vIBSMun", g.g_ibsmun.v_ibsmun),
            unsafe=True,
        )
        cbs = xml_element(
            "gCBS",
            xml_element("pCBS", g.g_cbs.p_cbs)
            + _dif_block("gDif", g.g_cbs.g_dif)
            + _red_block("gRed", g.g_cbs.g_red)
            + _alczfmcbs_block(g.g_cbs.g_alczfmcbs)
            + xml_element("vCBS", g.g_cbs.v_cbs),
            unsafe=True,
        )
        g_ibscbs = xml_element(
            "gIBSCBS",
            xml_element("vBC", g.v_bc)
            + ibsuf
            + ibsmun
            + xml_element("vIBS", g.v_ibs)
            + cbs
            + _trib_regular_block(g.g_trib_regular)
            + _trib_compra_gov_block(g.g_trib_compra_gov),
            unsafe=True,
        )
        parts.append(g_ibscbs)
    parts.append(_estorno_cred_block(ibscbs.g_estorno_cred))
    return xml_element("IBSCBS", "".join(p for p in parts if p), unsafe=True)


def _inf_carga_block(cte: BRCTeDocument) -> str:
    carga = cte.inf_carga
    inf_qs = "".join(
        xml_element(
            "infQ",
            xml_element("cUnid", q.c_unid) + xml_element("tpMed", q.tp_med) + xml_element("qCarga", q.q_carga),
            unsafe=True,
        )
        for q in carga.inf_q
    )
    parts = [
        xml_optional("vCarga", carga.v_carga),
        xml_element("proPred", carga.pro_pred),
        xml_optional("xOutCat", carga.x_out_cat),
        inf_qs,
    ]
    return xml_element("infCarga", "".join(p for p in parts if p), unsafe=True)


def _inf_modal_block(cte: BRCTeDocument) -> str:
    modal_data = cte.inf_modal
    if modal_data.modal != CTeModal.RODOVIARIO:
        raise DocumentGenerationError(
            f"CTeGenerator v1 só suporta modal rodoviário; recebido {modal_data.modal!r} "
            "[NEED: not modeled — see roadmap BR-CTE-8]."
        )
    rodo = xml_element("rodo", xml_element("RNTRC", modal_data.rntrc or ""), unsafe=True)
    return xml_element("infModal", rodo, attrs={"versaoModal": modal_data.versao_modal}, unsafe=True)


class CTeGenerator(BaseDocumentGenerator[InvoiceDocument]):
    """Generates unsigned CT-e (modelo 57, schema 4.00) XML. Modal rodoviário only — see module docstring."""

    def get_format_name(self) -> str:
        return "CT-e 4.00"

    def get_country_code(self) -> str:
        return "BR"

    def get_namespace(self) -> str:
        return _NAMESPACE

    def generate(self, document: InvoiceDocument) -> str:
        if not isinstance(document, BRCTeDocument):
            raise DocumentGenerationError(
                f"CTeGenerator requer um BRCTeDocument, recebido {type(document).__name__}."
            )
        cte = document

        c_ct = f"{secrets.randbelow(10**8):08d}"
        cnpj_for_key = cte.emitente.cnpj or (cte.emitente.cpf or "").zfill(14)
        access_key = build_cte_access_key(
            cuf=cte.c_uf,
            dh_emi=cte.dh_emi,
            cnpj=cnpj_for_key,
            serie=cte.serie,
            n_ct=cte.n_ct,
            tp_emis="1",
            c_ct=c_ct,
        )
        if cte.chave_acesso is not None and cte.chave_acesso != access_key:
            raise DocumentGenerationError(
                "A chave de acesso informada não corresponde aos dados do documento: "
                f"esperado {access_key!r}, recebido {cte.chave_acesso!r}."
            )
        cdv = access_key[-1]

        ide = _ide_block(cte, c_ct=c_ct, cdv=cdv)
        emit = _emit_block(cte)
        rem = _party_block("rem", "enderReme", cte.remetente)
        exped = _party_block("exped", "enderExped", cte.expedidor)
        receb = _party_block("receb", "enderReceb", cte.recebedor)
        dest = _party_block("dest", "enderDest", cte.destinatario)
        v_prest = _v_prest_block(cte)
        imp = _imp_block(cte)
        inf_carga = _inf_carga_block(cte)
        inf_modal = _inf_modal_block(cte)

        inf_cte_norm = xml_element("infCTeNorm", inf_carga + inf_modal, unsafe=True)

        inf_cte_body = ide + emit + rem + exped + receb + dest + v_prest + imp + inf_cte_norm
        inf_cte = xml_element(
            "infCte",
            inf_cte_body,
            attrs={"Id": f"CTe{access_key}", "versao": _VERSAO},
            unsafe=True,
        )
        return f'<?xml version="1.0" encoding="UTF-8"?><CTe xmlns="{_NAMESPACE}">{inf_cte}</CTe>'
