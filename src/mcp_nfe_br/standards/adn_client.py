"""REST client for the NFS-e Nacional ADN (Ambiente de Dados Nacional).

Provides submit, query-status, and cancel operations against the single
national ADN endpoint. Authentication is via gov.br OAuth2 Bearer token
(see ``govbr_auth.py``).

`[Unverified — ADN API endpoint URLs, request/response shapes, and HTTP
methods are inferred from secondary sources and the XSD structure. Verify
against manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf and the
ADN Swagger/OpenAPI spec before production use.]`

Environment split:
- Homologacao: ``https://adn-hom.estaleiro.serpro.gov.br``
- Producao: ``https://adn.estaleiro.serpro.gov.br``

`[Unverified — base URLs are from secondary sources. Confirm in the official
ADN contributor manual.]`
"""

from __future__ import annotations

import logging

from mcp_einvoicing_core.exceptions import PlatformError
from mcp_einvoicing_core.http_client import AuthMode, BaseEInvoicingClient, OAuthValues
from mcp_einvoicing_core.xml_utils import mark_untrusted_fields, safe_fromstring

from mcp_nfe_br.models.invoice import TipoAmbiente

logger = logging.getLogger(__name__)

_ADN_BASE_URLS: dict[str, str] = {
    "1": "https://adn.estaleiro.serpro.gov.br",
    "2": "https://adn-hom.estaleiro.serpro.gov.br",
}

_ADN_UNTRUSTED_FIELDS: set[str] = {"xMotivo", "verAplic", "chNFSe", "nNFSe"}


def _parse_adn_xml_response(content: bytes) -> dict[str, object]:
    """Extract common ADN response fields from XML.

    `[Unverified — response XML structure inferred from the NFS-e v1.01 XSD
    NFSe/retEnviDPS types. Confirm against actual ADN responses.]`
    """
    root = safe_fromstring(content)
    result: dict[str, object] = {}
    for field in ("cStat", "xMotivo", "verAplic", "dhRecbto", "nNFSe", "chNFSe"):
        elems = root.xpath(f".//*[local-name()='{field}']")
        if elems:
            result[field] = elems[0].text

    nfse_elem = root.xpath(".//*[local-name()='NFSe']")
    if nfse_elem:
        result["nfse_xml"] = (
            b"<?xml version='1.0' encoding='UTF-8'?>"
            + __import__("lxml").etree.tostring(nfse_elem[0])
        ).decode("utf-8")

    return mark_untrusted_fields(result, _ADN_UNTRUSTED_FIELDS)


class ADNClient(BaseEInvoicingClient):
    """REST client for ADN NFS-e Nacional operations.

    Uses ``AuthMode.OAUTH2_CLIENT_CREDENTIALS`` with gov.br tokens.

    `[Unverified — API paths, HTTP methods, and content types are inferred.
    Verify against the official ADN API documentation.]`
    """

    def __init__(
        self,
        tp_amb: TipoAmbiente,
        oauth: OAuthValues,
        endpoint_override: str | None = None,
        http_timeout: float = 60.0,
    ) -> None:
        self._tp_amb = tp_amb
        base_url = endpoint_override or _ADN_BASE_URLS[tp_amb.value]
        super().__init__(
            base_url=base_url,
            auth_mode=AuthMode.OAUTH2_CLIENT_CREDENTIALS,
            oauth_config=oauth,
            http_timeout=http_timeout,
        )

    async def submit_dps(self, signed_dps_xml: bytes) -> dict[str, object]:
        """Submit a signed DPS to the ADN for NFS-e generation.

        `[Unverified — POST path /api/v1/dps and Content-Type
        application/xml are inferred. Confirm in ADN manual.]`

        Args:
            signed_dps_xml: A signed ``<DPS>`` document (output of
                ``br__sign_nfse``).

        Returns:
            Parsed ADN response with ``cStat``, ``xMotivo``, and optionally
            the generated ``nfse_xml``.
        """
        client = await self._get_client()
        response = await client.post(
            f"{self._base_url}/api/v1/dps",
            content=signed_dps_xml,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        if not response.is_success:
            raise PlatformError(
                response.status_code,
                f"ADN returned HTTP {response.status_code}",
            )
        return {
            "status_code": response.status_code,
            **_parse_adn_xml_response(response.content),
        }

    async def consult_nfse(self, ch_nfse: str) -> dict[str, object]:
        """Query the status of an NFS-e by its access key (chNFSe).

        `[Unverified — GET path /api/v1/nfse/{chNFSe} is inferred.]`

        Args:
            ch_nfse: The NFS-e access key (53 chars, ``NFS[0-9]{50}``).

        Returns:
            Parsed ADN response with status fields and optionally the NFS-e XML.
        """
        client = await self._get_client()
        response = await client.get(
            f"{self._base_url}/api/v1/nfse/{ch_nfse}",
        )
        if not response.is_success:
            raise PlatformError(
                response.status_code,
                f"ADN returned HTTP {response.status_code}",
            )
        return {
            "status_code": response.status_code,
            **_parse_adn_xml_response(response.content),
        }

    async def cancel_nfse(
        self,
        ch_nfse: str,
        motivo: str,
    ) -> dict[str, object]:
        """Request cancellation of an NFS-e.

        `[Unverified — POST path /api/v1/nfse/{chNFSe}/cancelar and request
        body shape are inferred. Confirm in ADN manual.]`

        Args:
            ch_nfse: The NFS-e access key to cancel.
            motivo: Reason for cancellation (free text).

        Returns:
            Parsed ADN response with cancellation status.
        """
        from lxml import etree

        pedido = etree.Element("pedCancNFSe")
        etree.SubElement(pedido, "chNFSe").text = ch_nfse
        etree.SubElement(pedido, "xMotivo").text = motivo
        body = etree.tostring(pedido, xml_declaration=True, encoding="UTF-8")

        client = await self._get_client()
        response = await client.post(
            f"{self._base_url}/api/v1/nfse/{ch_nfse}/cancelar",
            content=body,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        if not response.is_success:
            raise PlatformError(
                response.status_code,
                f"ADN returned HTTP {response.status_code}",
            )
        return {
            "status_code": response.status_code,
            **_parse_adn_xml_response(response.content),
        }
