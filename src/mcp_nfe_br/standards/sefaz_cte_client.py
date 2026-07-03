"""SOAP 1.2 client for the SEFAZ CT-e webservices (modelo 57, schema 4.00).

Mirrors `sefaz_client.py` (NF-e), reusing the shared envelope/parsing
primitives in `_sefaz_soap.py` (BR-CTE-10). Covers the three CT-e
webservices confirmed against the bundled MOC CT-e Visão Geral v4.00 §4.2,
§4.5, §4.6 `[Verified locally]`:

- ``CTeStatusServicoV4`` — service availability check (`cteStatusServicoCT`).
- ``CTeConsultaV4`` — query CT-e status by access key (`cteConsultaCT`).
- ``CTeRecepcaoSincV4`` — synchronous submission of a signed CT-e
  (`cteRecepcao`). Unlike NF-e's `NFeAutorizacao4`, the payload must be
  GZip-compressed then Base64-encoded before being placed as the
  `cteDadosMsg` wrapper's text content (`[Verified locally]` — MOC CT-e
  Visão Geral v4.00 §3.4.1).

WSDL namespaces for `CTeStatusServicoV4`/`CTeConsultaV4` are
`[Inference — pattern extrapolated from the one WSDL namespace example the
bundled MOC actually shows (CTeRecepcaoSincV4 -> ".../cte/wsdl/CTeRecepcaoSinc",
dropping the "V4" suffix); not independently confirmed for the other two
operations]`.

UF -> endpoint routing table
-----------------------------
Unlike `sefaz_client.py`'s NF-e table (sourced from a live capture of
nfe.fazenda.gov.br/portal/webServices.aspx), **no CT-e endpoint URLs are
bundled or independently verified** — the MOC only points to
https://dfe-portal.svrs.rs.gov.br/CTe/Servicos for the live list, which is
outside the local spec bundle. `get_cte_endpoint` therefore always raises;
every call requires `endpoint_override`. `[NEED: source the CT-e webservice
endpoint table, e.g. from dfe-portal.svrs.rs.gov.br/CTe/Servicos, before
removing this restriction]`.

`CTeDistribuicaoDFe` (the CT-e analog of NF-e's `NFeDistribuicaoDFe`) is
**not implemented here** — the bundled spec (`PL_CTeDistDFe_100`) confirms
the `distDFeInt` payload shape but the MOC does not document that
webservice's method name, WSDL namespace, or message wrapper element.
`[NEED: verify — CTeDistribuicaoDFe webservice details not in the bundled
MOC/NT set]`. See roadmap `BR-CTE-13` for the deferred item.
"""

from __future__ import annotations

import base64
import gzip

from lxml import etree
from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient
from mcp_einvoicing_core.xml_utils import mark_untrusted_fields

from mcp_nfe_br.models.invoice import TipoAmbiente
from mcp_nfe_br.standards._sefaz_soap import parse_response_root, scrape_fields, soap_envelope

_CTE_NS = "http://www.portalfiscal.inf.br/cte"

_CTE_WSDL_NS = {
    "status_servico": "http://www.portalfiscal.inf.br/cte/wsdl/CTeStatusServico",
    "consulta": "http://www.portalfiscal.inf.br/cte/wsdl/CTeConsulta",
    "recepcao": "http://www.portalfiscal.inf.br/cte/wsdl/CTeRecepcaoSinc",
}

_CTE_WSDL_OPERATION = {
    "status_servico": "cteStatusServicoCT",
    "consulta": "cteConsultaCT",
    "recepcao": "cteRecepcao",
}

# No CT-e endpoint URLs are bundled or independently verified — see module docstring.
# [NEED: source the CT-e webservice endpoint table]
_CTE_SEFAZ_ENDPOINTS: dict[str, dict[str, dict[str, str]]] = {}


def get_cte_endpoint(service: str, cuf: str, tp_amb: TipoAmbiente) -> str:
    """Resolve the SOAP endpoint URL for a CT-e *service*/*cuf*/*tp_amb*.

    Always raises in this version — no CT-e endpoint table is bundled or
    verified. Callers must pass `endpoint_override` to `SefazCTeClient`.
    """
    raise ValueError(
        f"No CT-e endpoint configured for service={service!r}, cUF={cuf!r}, "
        f"tpAmb={tp_amb.value!r}. [NEED: source the CT-e webservice endpoint "
        "table, e.g. from dfe-portal.svrs.rs.gov.br/CTe/Servicos] "
        "Pass endpoint_override to SefazCTeClient to use this cUF."
    )


def build_cte_status_servico_envelope(cuf: str, tp_amb: TipoAmbiente) -> bytes:
    """Build the `CTeStatusServicoV4` (`cteStatusServicoCT`) SOAP envelope.

    `[Verified locally — MOC CT-e Visão Geral v4.00 §4.6]` — root
    ``consStatServCTe``, fields ``versao`` (attr), ``tpAmb``, ``cUF``,
    ``xServ``="STATUS" (mirrors NF-e's `consStatServ` shape, confirmed
    against `consStatServCTe_v4.00.xsd`).
    """
    cons_stat_serv = etree.Element(
        f"{{{_CTE_NS}}}consStatServCTe", nsmap={None: _CTE_NS}, versao="4.00"
    )
    etree.SubElement(cons_stat_serv, f"{{{_CTE_NS}}}tpAmb").text = tp_amb.value
    etree.SubElement(cons_stat_serv, f"{{{_CTE_NS}}}cUF").text = cuf
    etree.SubElement(cons_stat_serv, f"{{{_CTE_NS}}}xServ").text = "STATUS"

    return soap_envelope(
        wsdl_namespace=_CTE_WSDL_NS["status_servico"],
        operation=_CTE_WSDL_OPERATION["status_servico"],
        dados_msg_element="cteDadosMsg",
        payload_element=cons_stat_serv,
    )


def build_cte_consulta_envelope(ch_cte: str, tp_amb: TipoAmbiente) -> bytes:
    """Build the `CTeConsultaV4` (`cteConsultaCT`) SOAP envelope, querying by access key.

    `[Verified locally — MOC CT-e Visão Geral v4.00 §4.5]` — root
    ``consSitCTe``, fields ``versao`` (attr), ``tpAmb``, ``xServ``="CONSULTAR",
    ``chCTe`` (confirmed against `consSitCTe_v4.00.xsd`).
    """
    cons_sit_cte = etree.Element(f"{{{_CTE_NS}}}consSitCTe", nsmap={None: _CTE_NS}, versao="4.00")
    etree.SubElement(cons_sit_cte, f"{{{_CTE_NS}}}tpAmb").text = tp_amb.value
    etree.SubElement(cons_sit_cte, f"{{{_CTE_NS}}}xServ").text = "CONSULTAR"
    etree.SubElement(cons_sit_cte, f"{{{_CTE_NS}}}chCTe").text = ch_cte

    return soap_envelope(
        wsdl_namespace=_CTE_WSDL_NS["consulta"],
        operation=_CTE_WSDL_OPERATION["consulta"],
        dados_msg_element="cteDadosMsg",
        payload_element=cons_sit_cte,
    )


def build_cte_recepcao_envelope(signed_cte_xml: bytes) -> bytes:
    """Build the `CTeRecepcaoSincV4` (`cteRecepcao`) SOAP envelope.

    Args:
        signed_cte_xml: A signed `<CTe>...</CTe>` document (output of
            `br__sign_cte`).

    `[Verified locally — MOC CT-e Visão Geral v4.00 §3.4.1, §4.2]` — the
    full `<CTe>` document is GZip-compressed then Base64-encoded and placed
    as the `cteDadosMsg` wrapper's text content.
    """
    compressed = gzip.compress(signed_cte_xml)
    encoded = base64.b64encode(compressed).decode("ascii")

    return soap_envelope(
        wsdl_namespace=_CTE_WSDL_NS["recepcao"],
        operation=_CTE_WSDL_OPERATION["recepcao"],
        dados_msg_element="cteDadosMsg",
        payload_text=encoded,
    )


# Free-text and identifier fields from SEFAZ CT-e responses that must be
# treated as untrusted external input to prevent prompt injection.
_CTE_UNTRUSTED_FIELDS: set[str] = {"xMotivo", "verAplic", "chCTe"}


def parse_cte_sefaz_response(response_xml: bytes) -> dict[str, object]:
    """Extract common SEFAZ CT-e response fields (`cStat`, `xMotivo`, `protCTe`, etc.).

    Mirrors `sefaz_client.parse_sefaz_response`, substituting `protCTe` for
    `protNFe` and `chCTe` for `chNFe`.
    """
    root = parse_response_root(response_xml)

    result = scrape_fields(root, ("cStat", "xMotivo", "tpAmb", "verAplic", "dhRecbto", "nRec", "cUF"))

    prot_cte = root.xpath(".//*[local-name()='protCTe']")
    if prot_cte:
        prot = scrape_fields(
            prot_cte[0], ("chCTe", "tpAmb", "verAplic", "dhRecbto", "nProt", "digVal", "cStat", "xMotivo")
        )
        result["protCTe"] = mark_untrusted_fields(prot, _CTE_UNTRUSTED_FIELDS)

    return mark_untrusted_fields(result, _CTE_UNTRUSTED_FIELDS)


class SefazCTeClient(BaseEInvoicingClient):
    """SOAP 1.2 client for SEFAZ CT-e webservices over ICP-Brasil mTLS.

    Reuses `BaseEInvoicingClient`'s `AuthMode.MTLS` transport, same pattern
    as `SefazClient` (NF-e). `endpoint_override` is required in this
    version — see module docstring.
    """

    def __init__(
        self,
        cuf: str,
        tp_amb: TipoAmbiente,
        cert_path: str,
        cert_password: str | None = None,
        service: str = "recepcao",
        endpoint_override: str | None = None,
        http_timeout: float = 60.0,
    ) -> None:
        self._cuf = cuf
        self._tp_amb = tp_amb
        base_url = endpoint_override or get_cte_endpoint(service, cuf, tp_amb)
        super().__init__(
            base_url=base_url,
            auth_mode=AuthMode.MTLS,
            cert_path=cert_path,
            cert_password=cert_password,
            http_timeout=http_timeout,
        )

    async def _post_soap(self, envelope: bytes) -> dict[str, object]:
        """POST a SOAP 1.2 envelope and parse the response — see
        `SefazClient._post_soap` for the transport-injection rationale."""
        client = await self._get_client()
        response = await client.post(
            self._base_url,
            content=envelope,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        )
        if not response.is_success:
            raise PlatformError(
                response.status_code,
                f"SEFAZ CT-e webservice returned HTTP {response.status_code}",
            )
        return {
            "status_code": response.status_code,
            **parse_cte_sefaz_response(response.content),
        }

    async def consultar_status_servico(self) -> dict[str, object]:
        """Call `CTeStatusServicoV4` and return the parsed `cStat`/`xMotivo`."""
        envelope = build_cte_status_servico_envelope(self._cuf, self._tp_amb)
        return await self._post_soap(envelope)

    async def consultar_cte(self, ch_cte: str) -> dict[str, object]:
        """Call `CTeConsultaV4` and return the parsed `cStat`/`protCTe`."""
        envelope = build_cte_consulta_envelope(ch_cte, self._tp_amb)
        return await self._post_soap(envelope)

    async def autorizar_cte(self, signed_cte_xml: bytes) -> dict[str, object]:
        """Call `CTeRecepcaoSincV4` (synchronous) and return the parsed `protCTe`."""
        envelope = build_cte_recepcao_envelope(signed_cte_xml)
        return await self._post_soap(envelope)
