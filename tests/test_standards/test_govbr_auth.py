"""Tests for mcp_nfe_br.standards.govbr_auth."""

from mcp_nfe_br.standards.govbr_auth import (
    _GOVBR_NFSE_SCOPE,
    _GOVBR_TOKEN_URL_HOM,
    _GOVBR_TOKEN_URL_PROD,
    build_govbr_oauth,
)


def test_build_govbr_oauth_homologacao_defaults():
    oauth = build_govbr_oauth("my_id", "my_secret")
    assert oauth.token_url == _GOVBR_TOKEN_URL_HOM
    assert oauth.client_id == "my_id"
    assert oauth.client_secret == "my_secret"
    assert oauth.scope == _GOVBR_NFSE_SCOPE


def test_build_govbr_oauth_producao():
    oauth = build_govbr_oauth("id", "secret", homologacao=False)
    assert oauth.token_url == _GOVBR_TOKEN_URL_PROD


def test_build_govbr_oauth_custom_scope():
    oauth = build_govbr_oauth("id", "secret", scope="custom_scope")
    assert oauth.scope == "custom_scope"
