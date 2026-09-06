import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import starlightLlmsTxt from "starlight-llms-txt";

export default defineConfig({
  site: "https://cmendezs.github.io",
  base: "/mcp-nfe-br/",
  integrations: [
    starlight({
      title: "mcp-nfe-br",
      description: "MCP server for Brazilian electronic invoicing (NF-e / NFC-e)",
      customCss: ["./src/styles/docs-theme.css"],
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/cmendezs/mcp-nfe-br" },
      ],
      locales: {
        root: { label: "English", lang: "en" },
        "pt-br": { label: "Português (Brasil)", lang: "pt-BR" },
      },
      sidebar: [
        { label: "Overview", link: "/" },
        { label: "Tools", link: "/tools/" },
        { label: "Changelog", link: "/changelog/" },
        { label: "Contributing", link: "/contributing/" },
        { label: "Security", link: "/security/" },
        { label: "Code of Conduct", link: "/code-of-conduct/" },
      ],
      plugins: [
        starlightLlmsTxt({
          projectName: "mcp-nfe-br",
          description: "MCP server for Brazilian electronic invoicing (NF-e / NFC-e)",
          customSets: [
            {
              label: "Key links",
              description: "PyPI and MCP registry entries",
              links: ["https://pypi.org/project/mcp-nfe-br/", "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.cmendezs/mcp-nfe-br"],
            },
          ],
        }),
      ],
    }),
  ],
});
