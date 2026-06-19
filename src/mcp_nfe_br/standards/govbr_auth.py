"""Gov.br federal account OAuth2 authentication for NFS-e Nacional ADN.

The ADN (Ambiente de Dados Nacional) uses gov.br as its identity provider.
Contributors authenticate via OAuth2 client_credentials flow to obtain a
Bearer token for ADN API calls (submit, query, cancel).

`[Unverified — manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf not
yet fully read. Token URL, scopes, and grant type are inferred from the gov.br
developer documentation pattern and secondary sources. Verify against the
official ADN contributor manual before production use.]`

Only machine-to-machine (client_credentials) flow is implemented. Interactive
(authorization_code) flow for individual contributors is
`[NEED: not modeled]`.
"""

from __future__ import annotations

from mcp_einvoicing_core.http_client import OAuthValues

_GOVBR_TOKEN_URL_PROD = "https://sso.acesso.gov.br/token"
_GOVBR_TOKEN_URL_HOM = "https://sso.staging.acesso.gov.br/token"

_GOVBR_NFSE_SCOPE = "openid govbr_empresa"


def build_govbr_oauth(
    client_id: str,
    client_secret: str,
    scope: str | None = None,
    homologacao: bool = True,
) -> OAuthValues:
    """Build an ``OAuthValues`` for gov.br ADN authentication.

    Args:
        client_id: Gov.br OAuth2 client ID (registered at gov.br developer portal).
        client_secret: Gov.br OAuth2 client secret.
        scope: OAuth2 scope override. Defaults to ``"openid govbr_empresa"``
            ``[Unverified — confirm in ADN manual]``.
        homologacao: If ``True`` (default), use the staging token URL.
            Set to ``False`` for production.

    Returns:
        An ``OAuthValues`` ready to pass to ``ADNClient``.
    """
    token_url = _GOVBR_TOKEN_URL_HOM if homologacao else _GOVBR_TOKEN_URL_PROD
    return OAuthValues(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        scope=scope or _GOVBR_NFSE_SCOPE,
    )
