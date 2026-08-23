"""NFS-e Nacional (ADN) DPS XML generator, schema v1.01.

Assembles an **unsigned** ``<DPS><infDPS>…</infDPS></DPS>`` document from an
``NFSeDocument``. Field order within each group follows ``tiposComplexos_v1.01.xsd``
(TCInfDPS, TCInfoPrestador, TCServ, TCInfoValores, TCTribMunicipal, TCTribTotal)
`[Verified locally]`.

The ``infDPS`` element carries an ``Id`` attribute (type ``TSIdDPS``, 45 chars,
pattern ``DPS[0-9]{42}``). Formation rule `[Verified locally — tiposSimples_v1.01.xsd]`:
  "DPS" + cLocEmi(7) + tpInscFederal(1) + inscFederal(14) + serie(5) + nDPS(15)
  where tpInscFederal = "1" for CNPJ, "2" for CPF, and CPF is zero-padded to 14
  by prepending "000".

The ``DPS`` root element carries ``versao="1.01"`` and
``xmlns="http://www.sped.fazenda.gov.br/nfse"``. Child elements inherit the
namespace and are serialized without an explicit prefix.

Signing (inserting ``<ds:Signature>`` over ``infDPS``) is handled separately
by ``mcp_nfe_br.standards.nfse_signer``; the returned XML contains no
Signature element.

Not yet emitted (``[NEED: not modeled for v0.5.0]``):
- ``subst`` (NFS-e substitution)
- ``interm`` (intermediário)
- ``comExt``, ``obra``, ``atvEvento``, ``infoCompl`` (service sub-groups)
- ``vDescCondIncond``, ``vDedRed`` (discounts/deductions in valores)
- ``tribFed`` (PIS, COFINS, IR, CSLL, INSS, INSS-PR)
- ``exigSusp``, ``BM`` (suspended exigibility, municipal benefit)
- ``IBSCBS`` IBS/CBS group in DPS (field modeled but emission deferred)
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from mcp_einvoicing_core import BaseDocumentGenerator, DocumentGenerationError, InvoiceDocument
from mcp_einvoicing_core.xml_utils import format_amount, xml_element, xml_optional

from mcp_nfe_br.models.nfse import (
    NFSeCServ,
    NFSeDocument,
    NFSeEndereco,
    NFSeLocPrest,
    NFSePrestador,
    NFSeTomador,
    NFSeTotTrib,
    NFSeTribMunicipal,
    NFSeValores,
)

_NAMESPACE = "http://www.sped.fazenda.gov.br/nfse"
_VERSAO = "1.01"


def _d2(value: str | Decimal) -> str:
    """Format a monetary value to 2 decimal places (TSDec15V2).

    `ROUND_HALF_UP` mirrors the rounding choice made for NF-e/NFC-e (see
    `nfe_generator._d2`), for consistency across BR sub-formats. The ADN
    manuals for NFS-e Nacional have not been read for a specific rounding
    rule `[NEED: confirm against ADN manual]`.
    """
    return format_amount(Decimal(str(value)), 2, rounding_mode=ROUND_HALF_UP)


def _el(tag: str, text: str) -> str:
    return xml_element(tag, text)


def _opt(tag: str, value: str | None) -> str:
    return xml_optional(tag, value)


def _build_dps_id(doc: NFSeDocument) -> str:
    """Build the 45-char DPS Id from NFSeDocument fields.

    Format: "DPS" + cLocEmi(7) + tpInscFederal(1) + inscFederal(14)
            + serie(5, zero-padded left) + nDPS(15, zero-padded left)
    `[Verified locally — tiposSimples_v1.01.xsd TSIdDPS]`
    """
    if doc.prest.cnpj:
        tp_inscr = "1"
        raw = doc.prest.cnpj.replace(".", "").replace("/", "").replace("-", "")
        inscr = raw.zfill(14)
    else:
        tp_inscr = "2"
        raw_cpf = (doc.prest.cpf or "").replace(".", "").replace("-", "")
        inscr = ("000" + raw_cpf.zfill(11))[:14]

    serie_padded = doc.serie.zfill(5)
    ndps_padded = doc.n_dps.zfill(15)

    return f"DPS{doc.c_loc_emi}{tp_inscr}{inscr}{serie_padded}{ndps_padded}"


def _wrap(tag: str, inner: str) -> str:
    return xml_element(tag, inner, unsafe=True)


def _normalize_d_compet(value: str) -> str:
    """Normalize `dCompet` to `TSData`'s dashed `YYYY-MM-DD` form.

    `TSData`'s pattern is dashed ISO despite the XSD's own annotation text
    saying "(AAAAMMDD)"; an 8-digit `AAAAMMDD` input is defensively converted.
    `[Verified locally — tiposSimples_v1.01.xsd TSData]`
    """
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value


def _build_endereco(end: NFSeEndereco) -> str:
    """Build `<end>` per `TCEndereco`: choice(endNac|endExt), xLgr, nro, xCpl?, xBairro.

    `endExt` requires `cPais, cEndPost, xCidade, xEstProvReg` (`TCEnderExt`), none of
    which are modeled on `NFSeEndereco` besides `c_pais`; only the national path
    (`endNac` = `cMun, CEP`) is emitted `[NEED: endExt not modeled]`.
    """
    if end.c_pais:
        raise DocumentGenerationError(
            "Endereço no exterior (endExt) ainda não é suportado "
            "[NEED: TCEnderExt requer cEndPost/xCidade/xEstProvReg, não modelados]."
        )
    end_choice = _wrap("endNac", _el("cMun", end.c_mun) + _el("CEP", end.cep))
    parts = [
        end_choice,
        _el("xLgr", end.x_lgr),
        _el("nro", end.nro),
        _opt("xCpl", end.x_cpl),
        _el("xBairro", end.x_bairro),
    ]
    return _wrap("end", "".join(p for p in parts if p))


def _build_reg_trib(prest: NFSePrestador) -> str:
    rt = prest.reg_trib
    parts: list[str] = [_el("opSimpNac", rt.op_simp_nac.value)]
    if rt.reg_ap_trib_sn is not None:
        parts.append(_el("regApTribSN", rt.reg_ap_trib_sn))
    parts.append(_el("regEspTrib", rt.reg_esp_trib))
    return _wrap("regTrib", "".join(parts))


def _build_prestador(prest: NFSePrestador) -> str:
    parts: list[str] = []
    if prest.cnpj:
        parts.append(_el("CNPJ", prest.cnpj.replace(".", "").replace("/", "").replace("-", "")))
    else:
        parts.append(_el("CPF", (prest.cpf or "").replace(".", "").replace("-", "").zfill(11)))
    if prest.im:
        parts.append(_el("IM", prest.im))
    if prest.x_nome:
        parts.append(_el("xNome", prest.x_nome))
    if prest.end:
        parts.append(_build_endereco(prest.end))
    if prest.fone:
        parts.append(_el("fone", prest.fone))
    if prest.email:
        parts.append(_el("email", prest.email))
    parts.append(_build_reg_trib(prest))
    return _wrap("prest", "".join(parts))


def _build_pessoa(tag: str, pessoa: NFSeTomador) -> str:
    parts: list[str] = []
    if pessoa.cnpj:
        parts.append(_el("CNPJ", pessoa.cnpj.replace(".", "").replace("/", "").replace("-", "")))
    else:
        parts.append(_el("CPF", (pessoa.cpf or "").replace(".", "").replace("-", "").zfill(11)))
    if pessoa.im:
        parts.append(_el("IM", pessoa.im))
    if pessoa.x_nome:
        parts.append(_el("xNome", pessoa.x_nome))
    if pessoa.end:
        parts.append(_build_endereco(pessoa.end))
    if pessoa.fone:
        parts.append(_el("fone", pessoa.fone))
    if pessoa.email:
        parts.append(_el("email", pessoa.email))
    return _wrap(tag, "".join(parts))


def _build_loc_prest(loc: NFSeLocPrest) -> str:
    if loc.c_loc_prestacao:
        inner = _el("cLocPrestacao", loc.c_loc_prestacao)
    else:
        inner = _el("cPaisPrestacao", loc.c_pais_prestacao or "")
    return _wrap("locPrest", inner)


def _build_c_serv(cs: NFSeCServ) -> str:
    parts: list[str] = [_el("cTribNac", cs.c_trib_nac)]
    if cs.c_trib_mun:
        parts.append(_el("cTribMun", cs.c_trib_mun))
    parts.append(_el("xDescServ", cs.x_desc_serv))
    if cs.c_nbs:
        parts.append(_el("cNBS", cs.c_nbs))
    return _wrap("cServ", "".join(parts))


def _build_trib_mun(t: NFSeTribMunicipal) -> str:
    """Build `<tribMun>` per `TCTribMunicipal` order: tribISSQN, …, tpRetISSQN, pAliq?."""
    parts: list[str] = [
        _el("tribISSQN", t.trib_issqn.value),
        _el("tpRetISSQN", t.tp_ret_issqn.value),
    ]
    if t.p_aliq is not None:
        parts.append(_el("pAliq", t.p_aliq))
    return _wrap("tribMun", "".join(parts))


def _build_tot_trib(tt: NFSeTotTrib) -> str:
    if tt.ind_tot_trib is not None:
        inner = _el("indTotTrib", tt.ind_tot_trib)
    elif tt.p_tot_trib_sn is not None:
        inner = _el("pTotTribSN", _d2(tt.p_tot_trib_sn))
    elif tt.p_tot_trib is not None:
        percent_inner = (
            _el("pTotTribFed", _d2(tt.p_tot_trib))
            + _el("pTotTribEst", "0.00")
            + _el("pTotTribMun", "0.00")
        )
        inner = _wrap("pTotTrib", percent_inner)
    else:
        monetary_inner = (
            _el("vTotTribFed", _d2(tt.v_tot_trib_fed or "0"))
            + _el("vTotTribEst", _d2(tt.v_tot_trib_est or "0"))
            + _el("vTotTribMun", _d2(tt.v_tot_trib_mun or "0"))
        )
        inner = _wrap("vTotTrib", monetary_inner)
    return _wrap("totTrib", inner)


def _build_valores(v: NFSeValores) -> str:
    v_serv_prest = _wrap("vServPrest", _el("vServ", _d2(v.v_serv)))
    trib_inner = _build_trib_mun(v.trib_mun) + _build_tot_trib(v.tot_trib)
    trib = _wrap("trib", trib_inner)
    return _wrap("valores", v_serv_prest + trib)


class NFSeGenerator(BaseDocumentGenerator[InvoiceDocument]):
    """Generates unsigned DPS XML for NFS-e Nacional (ADN), schema v1.01.

    Returns the XML string. The caller must sign with ``br__sign_nfse``
    (``nfse_signer.build_nfse_signer``) before submitting to ADN.
    """

    def get_format_name(self) -> str:
        return "NFS-e DPS 1.01"

    def get_country_code(self) -> str:
        return "BR"

    def get_namespace(self) -> str:
        return _NAMESPACE

    def generate(self, document: InvoiceDocument) -> str:
        if not isinstance(document, NFSeDocument):
            raise DocumentGenerationError(
                f"NFSeGenerator expects NFSeDocument, got {type(document).__name__}"
            )
        return self._generate_dps(document)

    def _generate_dps(self, doc: NFSeDocument) -> str:
        dps_id = _build_dps_id(doc)

        # Use the document date field; append a time zone if only a date string.
        date_str = str(doc.date)
        dh_emi = date_str if "T" in date_str else f"{date_str}T00:00:00-03:00"

        inf_parts: list[str] = [
            _el("tpAmb", doc.tp_amb.value),
            _el("dhEmi", dh_emi),
            _el("verAplic", doc.ver_aplic),
            _el("serie", doc.serie),
            _el("nDPS", doc.n_dps),
            _el("dCompet", _normalize_d_compet(doc.d_compet)),
            _el("tpEmit", doc.tp_emit.value),
            _el("cLocEmi", doc.c_loc_emi),
            _build_prestador(doc.prest),
        ]

        if doc.toma is not None:
            inf_parts.append(_build_pessoa("toma", doc.toma))

        serv_inner = _build_loc_prest(doc.serv.loc_prest) + _build_c_serv(doc.serv.c_serv)
        inf_parts.append(_wrap("serv", serv_inner))
        inf_parts.append(_build_valores(doc.valores))

        inf_dps = xml_element(
            "infDPS",
            "".join(inf_parts),
            attrs={"Id": dps_id},
            unsafe=True,
        )

        root_content = inf_dps
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<DPS versao="{_VERSAO}" xmlns="{_NAMESPACE}">{root_content}</DPS>'
        )
