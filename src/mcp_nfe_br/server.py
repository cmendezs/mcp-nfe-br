"""MCP server entry point — registers all Brazilian NF-e/NFC-e tools."""

from typing import Any

from mcp_einvoicing_core import EInvoicingMCPServer

from mcp_nfe_br.tools.validation import br__validate_cnpj, br__validate_cpf


def _register_br_tools(mcp: Any) -> None:
    """Register all Brazilian NF-e/NFC-e tools onto the shared FastMCP instance."""
    mcp.tool()(br__validate_cnpj)
    mcp.tool()(br__validate_cpf)


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
