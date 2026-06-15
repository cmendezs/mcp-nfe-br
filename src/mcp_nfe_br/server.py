"""MCP server entry point — registers all Brazilian NF-e/NFC-e tools."""

from typing import Any

from mcp_einvoicing_core import EInvoicingMCPServer

from mcp_nfe_br.tools.generation import (
    br__build_access_key,
    br__generate_nfe,
    br__sign_nfe,
    br__validate_nfe_xml,
)
from mcp_nfe_br.tools.sefaz import (
    br__consult_sefaz_status,
    br__distribute_dfe,
    br__submit_nfe,
)
from mcp_nfe_br.tools.validation import br__validate_cnpj, br__validate_cpf


def _register_br_tools(mcp: Any) -> None:
    """Register all Brazilian NF-e/NFC-e tools onto the shared FastMCP instance."""
    mcp.tool()(br__validate_cnpj)
    mcp.tool()(br__validate_cpf)
    mcp.tool()(br__generate_nfe)
    mcp.tool()(br__sign_nfe)
    mcp.tool()(br__validate_nfe_xml)
    mcp.tool()(br__build_access_key)
    mcp.tool()(br__submit_nfe)
    mcp.tool()(br__consult_sefaz_status)
    mcp.tool()(br__distribute_dfe)


mcp = EInvoicingMCPServer(
    "mcp-nfe-br",
    instructions=(
        "Tools for Brazilian electronic invoicing: NF-e (modelo 55) and "
        "NFC-e (modelo 65), schema 4.00, SEFAZ."
    ),
)
mcp.register_plugin(_register_br_tools, "br")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
