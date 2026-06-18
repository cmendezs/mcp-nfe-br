"""SOAP 1.2 client for the SEFAZ NF-e/NFC-e webservices (modelo 55/65, schema 4.00).

Mirrors the structure of `mcp_facturacion_electronica_es.tools.sii` (SOAP-over-mTLS
via `BaseEInvoicingClient(auth_mode=AuthMode.MTLS, ...)`), adapted to the three
SEFAZ webservices needed for v0.3.1:

- ``NFeStatusServico4`` — service availability check (`nfeStatusServicoNF`).
- ``NFeAutorizacao4`` — synchronous autorização of a signed NF-e/NFC-e
  (`nfeAutorizacaoLote`), returns a `protocolo de autorização`.
- ``NFeDistribuicaoDFe`` — DF-e distribution/query (`nfeDistDFeInteresse`),
  per `NT2014.002_v1.30` `[Verified locally]` (bundled under
  `mcp-nfe-br/specs/nfe/`) for the `distDFeInt` payload shape (`tpAmb`,
  `cUFAutor`, `CNPJ`/`CPF`, and one of `distNSU`/`consNSU`/`consChNFe`).

The SOAP element/namespace names for `NFeStatusServico4` and `NFeAutorizacao4`
are `[Unverified]` — they follow the standard SEFAZ WSDL naming convention but
have not been cross-checked against the MOC 7.0 WSDL annex in this bundle.

UF -> endpoint routing table
-----------------------------
SEFAZ NF-e webservices are not hosted centrally: each UF either runs its own
webservice or delegates ("autorizador") to a shared virtual SEFAZ (SVRS —
Sefaz Virtual Rio Grande do Sul, or SVAN — Sefaz Virtual Ambiente Nacional).
`_SEFAZ_ENDPOINTS` and `_CUF_AUTORIZADOR` cover all 27 UFs.
Source: https://www.nfe.fazenda.gov.br/portal/webServices.aspx ("Consulta Web
Services Disponibilizados"), captured 2026-06-18.
`[Unverified — source: nfe.fazenda.gov.br/portal/webServices.aspx, captured 2026-06-18]`
"""

from __future__ import annotations

from lxml import etree
from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient
from mcp_einvoicing_core.xml_utils import safe_fromstring

from mcp_nfe_br.models.invoice import TipoAmbiente

_SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
_NFE_NS = "http://www.portalfiscal.inf.br/nfe"

_WSDL_NS = {
    "status_servico": "http://www.portalfiscal.inf.br/nfe/wsdl/NFeStatusServico4",
    "autorizacao": "http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4",
    "distribuicao_dfe": "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe",
}

_WSDL_OPERATION = {
    "status_servico": "nfeStatusServicoNF",
    "autorizacao": "nfeAutorizacaoLote",
    "distribuicao_dfe": "nfeDistDFeInteresse",
}

# Endpoint table: autorizador key -> service -> tpAmb value -> URL.
# Source: https://www.nfe.fazenda.gov.br/portal/webServices.aspx ("Consulta Web Services
# Disponibilizados"), captured 2026-06-18.
# [Unverified — source: nfe.fazenda.gov.br/portal/webServices.aspx, captured 2026-06-18]
_SEFAZ_ENDPOINTS: dict[str, dict[str, dict[str, str]]] = {
    # Ambiente Nacional — NFeDistribuicaoDFe is centralised regardless of cUFAutor.
    "AN": {
        "distribuicao_dfe": {
            "1": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
            "2": "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
        },
    },
    # SEFAZ Virtual Rio Grande do Sul (SVRS) — autorizador for AC, AL, AP, DF, ES, PA,
    # PB, RJ, RN, RO, RR, SC, SE, TO, PI, RS.
    "SVRS": {
        "status_servico": {
            "1": "https://nfe.svrs.rs.gov.br/ws/NfeStatusServico/NFeStatusServico4.asmx",
            "2": "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeStatusServico/NFeStatusServico4.asmx",
        },
        "autorizacao": {
            "1": "https://nfe.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
            "2": "https://nfe-homologacao.svrs.rs.gov.br/ws/NfeAutorizacao/NFeAutorizacao4.asmx",
        },
    },
    # SEFAZ Virtual Ambiente Nacional (SVAN) — autorizador for MA.
    "SVAN": {
        "status_servico": {
            "1": "https://www.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
            "2": "https://hom.sefazvirtual.fazenda.gov.br/NFeStatusServico4/NFeStatusServico4.asmx",
        },
        "autorizacao": {
            "1": "https://www.sefazvirtual.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
            "2": "https://hom.sefazvirtual.fazenda.gov.br/NFeAutorizacao4/NFeAutorizacao4.asmx",
        },
    },
    # São Paulo
    "SP": {
        "status_servico": {
            "1": "https://nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
            "2": "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfestatusservico4.asmx",
        },
        "autorizacao": {
            "1": "https://nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
            "2": "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx",
        },
    },
    # Minas Gerais
    "MG": {
        "status_servico": {
            "1": "https://nfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
            "2": "https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
            "2": "https://hnfe.fazenda.mg.gov.br/nfe2/services/NFeAutorizacao4",
        },
    },
    # Paraná
    "PR": {
        "status_servico": {
            "1": "https://nfe.fazenda.pr.gov.br/nfe/NFeStatusServico4",
            "2": "https://homologacao.nfe.fazenda.pr.gov.br/nfe/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.fazenda.pr.gov.br/nfe/NFeAutorizacao4",
            "2": "https://homologacao.nfe.fazenda.pr.gov.br/nfe/NFeAutorizacao4",
        },
    },
    # Mato Grosso do Sul
    "MS": {
        "status_servico": {
            "1": "https://nfe.fazenda.ms.gov.br/ws/NFeStatusServico4",
            "2": "https://homologacao.nfe.fazenda.ms.gov.br/ws/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.fazenda.ms.gov.br/ws/NFeAutorizacao4",
            "2": "https://homologacao.nfe.fazenda.ms.gov.br/ws/NFeAutorizacao4",
        },
    },
    # Mato Grosso
    "MT": {
        "status_servico": {
            "1": "https://nfe.sefaz.mt.gov.br/nfews/v2/services/NfeStatusServico4",
            "2": "https://homologacao.sefaz.mt.gov.br/nfews/v2/services/NfeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.mt.gov.br/nfews/v2/services/NfeAutorizacao4",
            "2": "https://homologacao.sefaz.mt.gov.br/nfews/v2/services/NfeAutorizacao4",
        },
    },
    # Goiás
    "GO": {
        "status_servico": {
            "1": "https://nfe.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
            "2": "https://homologacao.nfe.sefaz.go.gov.br/nfe/services/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.go.gov.br/nfe/services/NFeAutorizacao4",
            "2": "https://homologacao.nfe.sefaz.go.gov.br/nfe/services/NFeAutorizacao4",
        },
    },
    # Bahia
    "BA": {
        "status_servico": {
            "1": "https://nfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
            "2": "https://hnfe.sefaz.ba.gov.br/webservices/NFeStatusServico4/NFeStatusServico4.asmx",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.ba.gov.br/webservices/NFeAutorizacao4/NFeAutorizacao4.asmx",
            "2": "https://hnfe.sefaz.ba.gov.br/webservices/NFeAutorizacao4/NFeAutorizacao4.asmx",
        },
    },
    # Ceará
    "CE": {
        "status_servico": {
            "1": "https://nfe.sefaz.ce.gov.br/nfe4/services/NFeStatusServico4",
            "2": "https://nfeh.sefaz.ce.gov.br/nfe4/services/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.ce.gov.br/nfe4/services/NFeAutorizacao4",
            "2": "https://nfeh.sefaz.ce.gov.br/nfe4/services/NFeAutorizacao4",
        },
    },
    # Pernambuco
    "PE": {
        "status_servico": {
            "1": "https://nfe.sefaz.pe.gov.br/nfe-service/services/NFeStatusServico4",
            "2": "https://nfehomolog.sefaz.pe.gov.br/nfe-service/services/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.pe.gov.br/nfe-service/services/NFeAutorizacao4",
            "2": "https://nfehomolog.sefaz.pe.gov.br/nfe-service/services/NFeAutorizacao4",
        },
    },
    # Amazonas
    "AM": {
        "status_servico": {
            "1": "https://nfe.sefaz.am.gov.br/services2/services/NFeStatusServico4",
            "2": "https://homnfe.sefaz.am.gov.br/services2/services/NFeStatusServico4",
        },
        "autorizacao": {
            "1": "https://nfe.sefaz.am.gov.br/services2/services/NFeAutorizacao4",
            "2": "https://homnfe.sefaz.am.gov.br/services2/services/NFeAutorizacao4",
        },
    },
}

# cUF (IBGE) -> autorizador key in `_SEFAZ_ENDPOINTS`.
# Source: https://www.nfe.fazenda.gov.br/portal/webServices.aspx, captured 2026-06-18.
# [Unverified — source: nfe.fazenda.gov.br/portal/webServices.aspx, captured 2026-06-18]
_CUF_AUTORIZADOR: dict[str, str] = {
    "12": "SVRS",  # AC
    "27": "SVRS",  # AL
    "16": "SVRS",  # AP
    "13": "AM",    # AM
    "29": "BA",    # BA
    "23": "CE",    # CE
    "53": "SVRS",  # DF
    "32": "SVRS",  # ES
    "52": "GO",    # GO
    "21": "SVAN",  # MA
    "15": "SVRS",  # PA
    "25": "SVRS",  # PB
    "26": "PE",    # PE
    "33": "SVRS",  # RJ
    "28": "SVRS",  # SE
    "17": "SVRS",  # TO
    "35": "SP",    # SP
    "31": "MG",    # MG
    "41": "PR",    # PR
    "43": "SVRS",  # RS
    "50": "MS",    # MS
    "51": "MT",    # MT
    "22": "SVRS",  # PI
    "24": "SVRS",  # RN
    "11": "SVRS",  # RO
    "14": "SVRS",  # RR
    "42": "SVRS",  # SC
}


def _autorizador_for(cuf: str) -> str:
    autorizador = _CUF_AUTORIZADOR.get(cuf)
    if autorizador is None:
        raise ValueError(
            f"No SEFAZ autorizador configured for cUF={cuf!r}. "
            "[NEED: complete the cUF -> autorizador routing table] "
            "Pass endpoint_override to SefazClient to use this cUF."
        )
    return autorizador


def get_endpoint(service: str, cuf: str, tp_amb: TipoAmbiente) -> str:
    """Resolve the SOAP endpoint URL for *service* / *cuf* / *tp_amb*.

    Args:
        service: One of ``"status_servico"``, ``"autorizacao"``,
            ``"distribuicao_dfe"``.
        cuf: 2-digit IBGE UF code of the autorizador (`cUF`/`cUFAutor`).
            For ``distribuicao_dfe`` this is ignored — the Ambiente Nacional
            endpoint is always used.
        tp_amb: `TipoAmbiente.PRODUCAO` or `TipoAmbiente.HOMOLOGACAO`.

    Raises:
        ValueError: If no endpoint is configured for the given inputs.
    """
    if service == "distribuicao_dfe":
        autorizador = "AN"
    else:
        autorizador = _autorizador_for(cuf)

    services = _SEFAZ_ENDPOINTS.get(autorizador, {})
    by_env = services.get(service)
    if by_env is None or tp_amb.value not in by_env:
        raise ValueError(
            f"No {service!r} endpoint configured for autorizador={autorizador!r}, "
            f"tpAmb={tp_amb.value!r}. [NEED: complete _SEFAZ_ENDPOINTS]"
        )
    return by_env[tp_amb.value]


# ---------------------------------------------------------------------------
# SOAP envelope builders
# ---------------------------------------------------------------------------


def _soap_envelope(service: str, payload: etree._Element) -> bytes:
    """Wrap *payload* in a SOAP 1.2 envelope for the given SEFAZ *service*."""
    nsmap = {"soap": _SOAP_NS}
    envelope = etree.Element(f"{{{_SOAP_NS}}}Envelope", nsmap=nsmap)
    etree.SubElement(envelope, f"{{{_SOAP_NS}}}Header")
    body = etree.SubElement(envelope, f"{{{_SOAP_NS}}}Body")

    wsdl_ns = _WSDL_NS[service]
    operation = etree.SubElement(body, f"{{{wsdl_ns}}}{_WSDL_OPERATION[service]}")
    nfe_dados_msg = etree.SubElement(operation, f"{{{wsdl_ns}}}nfeDadosMsg")
    nfe_dados_msg.append(payload)

    return etree.tostring(envelope, xml_declaration=True, encoding="UTF-8")


def build_status_servico_envelope(cuf: str, tp_amb: TipoAmbiente) -> bytes:
    """Build the `NFeStatusServico4` (`nfeStatusServicoNF`) SOAP envelope.

    `[Unverified]` — `consStatServ` element/attribute names follow the
    standard SEFAZ webservice convention but are not cross-checked against
    the MOC 7.0 WSDL annex.
    """
    cons_stat_serv = etree.Element(
        f"{{{_NFE_NS}}}consStatServ", nsmap={None: _NFE_NS}, versao="4.00"
    )
    etree.SubElement(cons_stat_serv, f"{{{_NFE_NS}}}tpAmb").text = tp_amb.value
    etree.SubElement(cons_stat_serv, f"{{{_NFE_NS}}}cUF").text = cuf
    etree.SubElement(cons_stat_serv, f"{{{_NFE_NS}}}xServ").text = "STATUS"

    return _soap_envelope("status_servico", cons_stat_serv)


def build_autorizacao_envelope(
    signed_nfe_xml: bytes, id_lote: str, tp_amb: TipoAmbiente, ind_sinc: str = "1"
) -> bytes:
    """Build the `NFeAutorizacao4` (`nfeAutorizacaoLote`) SOAP envelope.

    Args:
        signed_nfe_xml: A signed `<NFe>...</NFe>` document (output of
            `br__sign_nfe`).
        id_lote: Batch identifier (`idLote`), up to 15 digits.
        tp_amb: `TipoAmbiente.PRODUCAO` or `TipoAmbiente.HOMOLOGACAO`.
        ind_sinc: `indSinc` — `"1"` (synchronous, default) returns the
            `protNFe` directly; `"0"` (asynchronous) returns a receipt
            number for later polling. `[Unverified]`

    `[Unverified]` — `enviNFe` element/attribute names follow the standard
    SEFAZ webservice convention but are not cross-checked against the MOC 7.0
    WSDL annex.
    """
    envi_nfe = etree.Element(f"{{{_NFE_NS}}}enviNFe", nsmap={None: _NFE_NS}, versao="4.00")
    etree.SubElement(envi_nfe, f"{{{_NFE_NS}}}idLote").text = id_lote
    etree.SubElement(envi_nfe, f"{{{_NFE_NS}}}indSinc").text = ind_sinc

    nfe_element = safe_fromstring(signed_nfe_xml)
    envi_nfe.append(nfe_element)

    return _soap_envelope("autorizacao", envi_nfe)


def build_dist_dfe_envelope(
    tp_amb: TipoAmbiente,
    c_uf_autor: str,
    document_id: str,
    document_id_type: str = "CNPJ",
    ult_nsu: str | None = None,
    nsu: str | None = None,
    ch_nfe: str | None = None,
) -> bytes:
    """Build the `NFeDistribuicaoDFe` (`nfeDistDFeInteresse`) SOAP envelope.

    Per `NT2014.002_v1.30` `[Verified locally]`, exactly one of *ult_nsu*,
    *nsu*, or *ch_nfe* must be provided, selecting `distNSU`, `consNSU`, or
    `consChNFe` respectively.

    Args:
        tp_amb: `TipoAmbiente.PRODUCAO` or `TipoAmbiente.HOMOLOGACAO`.
        c_uf_autor: `cUFAutor` — 2-digit IBGE UF code of the autorizador.
        document_id: CNPJ or CPF of the interested party.
        document_id_type: `"CNPJ"` (14 digits, or 12 alphanumeric + 2 per
            PL_010d) or `"CPF"` (11 digits).
        ult_nsu: `distNSU/ultNSU` — last NSU received (set-distribution mode).
        nsu: `consNSU/NSU` — specific NSU to query (point query mode).
        ch_nfe: `consChNFe/chNFe` — 44-character access key to query.

    Raises:
        ValueError: If zero or more than one of *ult_nsu*, *nsu*, *ch_nfe* is
            provided, or *document_id_type* is invalid.
    """
    modes = [m for m in (ult_nsu, nsu, ch_nfe) if m is not None]
    if len(modes) != 1:
        raise ValueError("Exactly one of ult_nsu, nsu, or ch_nfe must be provided.")
    if document_id_type not in ("CNPJ", "CPF"):
        raise ValueError(f"document_id_type must be 'CNPJ' or 'CPF', got {document_id_type!r}")

    dist_dfe_int = etree.Element(
        f"{{{_NFE_NS}}}distDFeInt", nsmap={None: _NFE_NS}, versao="1.01"
    )
    etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}tpAmb").text = tp_amb.value
    etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}cUFAutor").text = c_uf_autor
    etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}{document_id_type}").text = document_id

    if ult_nsu is not None:
        dist_nsu = etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}distNSU")
        etree.SubElement(dist_nsu, f"{{{_NFE_NS}}}ultNSU").text = ult_nsu
    elif nsu is not None:
        cons_nsu = etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}consNSU")
        etree.SubElement(cons_nsu, f"{{{_NFE_NS}}}NSU").text = nsu
    else:
        cons_ch_nfe = etree.SubElement(dist_dfe_int, f"{{{_NFE_NS}}}consChNFe")
        etree.SubElement(cons_ch_nfe, f"{{{_NFE_NS}}}chNFe").text = ch_nfe

    return _soap_envelope("distribuicao_dfe", dist_dfe_int)


# ---------------------------------------------------------------------------
# SOAP response parsing
# ---------------------------------------------------------------------------


def parse_sefaz_response(response_xml: bytes) -> dict[str, object]:
    """Extract common SEFAZ response fields (`cStat`, `xMotivo`, `protNFe`, etc.).

    Uses namespace-agnostic `local-name()` lookups (per the
    `mcp-facturacion-electronica-es` SII precedent) since the response
    namespace varies by webservice/autorizador.
    """
    root = safe_fromstring(response_xml)

    result: dict[str, object] = {}
    for field in ("cStat", "xMotivo", "tpAmb", "verAplic", "dhRecbto", "nRec", "cUF"):
        elems = root.xpath(f".//*[local-name()='{field}']")
        if elems:
            result[field] = elems[0].text

    prot_nfe = root.xpath(".//*[local-name()='protNFe']")
    if prot_nfe:
        prot = {}
        for field in ("chNFe", "tpAmb", "verAplic", "dhRecbto", "nProt", "digVal", "cStat", "xMotivo"):
            elems = prot_nfe[0].xpath(f".//*[local-name()='{field}']")
            if elems:
                prot[field] = elems[0].text
        result["protNFe"] = prot

    return result


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class SefazClient(BaseEInvoicingClient):
    """SOAP 1.2 client for SEFAZ NF-e/NFC-e webservices over ICP-Brasil mTLS.

    Reuses `BaseEInvoicingClient`'s `AuthMode.MTLS` transport (A1 PKCS#12
    certificate) — mirrors `mcp-facturacion-electronica-es`'s SII client.
    """

    def __init__(
        self,
        cuf: str,
        tp_amb: TipoAmbiente,
        cert_path: str,
        cert_password: str | None = None,
        service: str = "autorizacao",
        endpoint_override: str | None = None,
        http_timeout: float = 60.0,
    ) -> None:
        self._cuf = cuf
        self._tp_amb = tp_amb
        base_url = endpoint_override or get_endpoint(service, cuf, tp_amb)
        super().__init__(
            base_url=base_url,
            auth_mode=AuthMode.MTLS,
            cert_path=cert_path,
            cert_password=cert_password,
            http_timeout=http_timeout,
        )

    async def _post_soap(self, envelope: bytes) -> dict[str, object]:
        """POST a SOAP 1.2 envelope and parse the response.

        Bypasses `BaseEInvoicingClient._request` (JSON/form/multipart-oriented,
        no support for a raw body + custom `Content-Type`) and instead uses
        the long-lived `httpx.AsyncClient` from `_get_client()` directly —
        the documented transport-injection seam also used by tests.
        """
        client = await self._get_client()
        response = await client.post(
            self._base_url,
            content=envelope,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        )
        if not response.is_success:
            raise PlatformError(
                response.status_code,
                f"SEFAZ webservice returned HTTP {response.status_code}: "
                f"{response.text[:500]}",
            )
        return {
            "status_code": response.status_code,
            **parse_sefaz_response(response.content),
        }

    async def consultar_status_servico(self) -> dict[str, object]:
        """Call `NFeStatusServico4` and return the parsed `cStat`/`xMotivo`."""
        envelope = build_status_servico_envelope(self._cuf, self._tp_amb)
        return await self._post_soap(envelope)

    async def autorizar_nfe(self, signed_nfe_xml: bytes, id_lote: str) -> dict[str, object]:
        """Call `NFeAutorizacao4` (synchronous) and return the parsed `protNFe`."""
        envelope = build_autorizacao_envelope(signed_nfe_xml, id_lote, self._tp_amb)
        return await self._post_soap(envelope)

    async def distribuir_dfe(
        self,
        document_id: str,
        document_id_type: str = "CNPJ",
        ult_nsu: str | None = None,
        nsu: str | None = None,
        ch_nfe: str | None = None,
    ) -> dict[str, object]:
        """Call `NFeDistribuicaoDFe` and return the parsed `cStat`/`xMotivo`."""
        envelope = build_dist_dfe_envelope(
            self._tp_amb,
            self._cuf,
            document_id,
            document_id_type=document_id_type,
            ult_nsu=ult_nsu,
            nsu=nsu,
            ch_nfe=ch_nfe,
        )
        return await self._post_soap(envelope)
