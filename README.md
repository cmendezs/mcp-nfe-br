# mcp-nfe-br 🇧🇷

<!-- mcp-name: io.github.cmendezs/mcp-nfe-br -->

[![PyPI version](https://badge.fury.io/py/mcp-nfe-br.svg)](https://badge.fury.io/py/mcp-nfe-br)
[![Python](https://img.shields.io/pypi/pyversions/mcp-nfe-br.svg)](https://pypi.org/project/mcp-nfe-br/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Introdução

`mcp-nfe-br` é um servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io) que fornece ferramentas para a emissão e validação de documentos fiscais eletrônicos brasileiros: **NF-e (modelo 55)** e **NFC-e (modelo 65)**, conforme o leiaute XML versão 4.00 da SEFAZ. Este servidor faz parte da família `mcp-einvoicing-*` / `mcp-*-*`, construída sobre [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core), que fornece o modelo de dados base, utilitários HTTP/OAuth2, e a infraestrutura comum de servidores MCP.

**Status atual (v0.1.0):** fase 1 do roadmap — ferramentas de validação de CPF/CNPJ. Geração e validação de XML NF-e/NFC-e, assinatura digital ICP-Brasil, e integração com os webservices da SEFAZ estão planejados para versões futuras. NFS-e (nota fiscal de serviços) e CT-e (conhecimento de transporte) são fases posteriores, fora do escopo desta versão.

## English summary

`mcp-nfe-br` is an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server providing tools for Brazilian electronic fiscal documents: **NF-e (modelo 55)** and **NFC-e (modelo 65)**, per SEFAZ XML schema 4.00. It is part of the `mcp-*-*` family built on [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core).

**Current status (v0.1.0):** Phase 1 of the roadmap — CPF/CNPJ tax-ID validation tools only. NF-e/NFC-e XML generation and validation, ICP-Brasil digital signing, and SEFAZ webservice integration are planned for future releases. NFS-e and CT-e are later phases, out of scope for this version.

---

## Instalação

### Requisitos

- Python ≥ 3.11
- [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core) (instalado automaticamente como dependência)

### Usando `uv` (recomendado)

```bash
uv add mcp-nfe-br
```

### Usando `pip`

```bash
pip install mcp-nfe-br
```

### A partir do código-fonte

```bash
git clone https://github.com/cmendezs/mcp-nfe-br.git
cd mcp-nfe-br
uv sync --all-extras
```

---

## Configuração

Adicione o servidor à configuração do seu cliente MCP. Para o Claude Desktop, edite `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "nfe-br": {
      "command": "uvx",
      "args": ["mcp-nfe-br"]
    }
  }
}
```

Para uma instalação local de desenvolvimento:

```json
{
  "mcpServers": {
    "nfe-br": {
      "command": "uv",
      "args": ["run", "mcp-nfe-br"],
      "cwd": "/path/to/mcp-nfe-br"
    }
  }
}
```

### Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `SEFAZ_ENV` | Ambiente SEFAZ: `producao` ou `homologacao` | `homologacao` |
| `LOG_LEVEL` | Nível de log: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

---

## Ferramentas disponíveis

### `br__validate_cpf`

Valida um CPF (Cadastro de Pessoas Físicas) — número de identificação fiscal de pessoa física, conforme o algoritmo módulo 11 da Receita Federal.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cpf` | `string` | sim | CPF com ou sem separadores `.`/`-` |

Retorna um `TaxIdValidationResult` com `valid=True` e o valor limpo (11 dígitos) em caso de sucesso, ou `valid=False` com mensagem de erro em português.

---

### `br__validate_cnpj`

Valida um CNPJ (Cadastro Nacional da Pessoa Jurídica) — número de identificação fiscal de pessoa jurídica. Aceita tanto o formato numérico tradicional (14 dígitos) quanto o formato alfanumérico introduzido pela NT 2026.004 (PL_010d), com vigência em homologação a partir de 2026-06-01 e em produção a partir de 2026-07-01.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cnpj` | `string` | sim | CNPJ com ou sem separadores `.`/`/`/`-` |

Retorna um `TaxIdValidationResult` com `valid=True` e o valor limpo (14 caracteres) em caso de sucesso, ou `valid=False` com mensagem de erro em português.

> ⚠️ **[Unverified]**: o algoritmo de dígito verificador para o formato alfanumérico do CNPJ foi implementado com base em fontes secundárias, pois a fonte primária ("NT Conjunta DFe 2025.001") ainda não está disponível localmente. Veja `context-library/countries/br.md` para detalhes.

---

## Arquitetura

```
mcp-nfe-br/
├── src/
│   └── mcp_nfe_br/
│       ├── __init__.py
│       ├── server.py              # ponto de entrada MCP e registro de ferramentas
│       ├── models/
│       │   ├── __init__.py
│       │   └── invoice.py         # BRInvoice, BRInvoiceLine, NFeModelo, TipoOperacao
│       ├── tools/
│       │   ├── __init__.py
│       │   └── validation.py      # br__validate_cpf, br__validate_cnpj
│       └── utils/
│           ├── __init__.py
│           └── document_ids.py    # validate_cpf, validate_cnpj
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   └── test_tools/
│       └── test_validation.py
├── specs/nfe/                     # material normativo (XSDs, MOC, Notas Técnicas — não publicado)
├── audit/
│   ├── audit_vs_core.py
│   └── report.json
├── .github/workflows/publish.yml
├── pyproject.toml
├── RELEASE.md
└── LICENSE
```

### Relação com `mcp-einvoicing-core`

`mcp-einvoicing-core` fornece:
- Modelos Pydantic base para faturas, partes, itens e resultados de validação (`InvoiceDocument`, `InvoiceLineItem`, `TaxIdValidationResult`)
- Infraestrutura comum de servidor MCP (`EInvoicingMCPServer`)
- Cliente HTTP/OAuth2, cache de tokens, logging estruturado, hierarquia de exceções

`mcp-nfe-br` adiciona a lógica específica do Brasil:
- `BRInvoice` (extensão de `InvoiceDocument` — NF-e/NFC-e não tem ascendência EN 16931)
- Campos de Grupo I (NCM, CFOP, ICMS/IPI/PIS/COFINS) em `BRInvoiceLine`
- Validação de CPF/CNPJ (incluindo o CNPJ alfanumérico da NT 2026.004)

---

## Contribuindo

Contribuições são bem-vindas. Abra uma issue para discutir mudanças significativas antes de enviar um pull request.

```bash
git clone https://github.com/cmendezs/mcp-nfe-br.git
cd mcp-nfe-br
uv sync --all-extras
uv run pytest
uv run ruff check src/mcp_nfe_br tests audit
uv run mypy src/mcp_nfe_br
```

---

## Outros servidores MCP de faturamento eletrônico

| País | Servidor |
|---|---|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Bélgica | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brasil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 França | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Alemanha | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Itália | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Polônia | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Espanha | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

---

## Licença

Este projeto está licenciado sob **Apache 2.0** — veja [LICENSE](LICENSE) para detalhes.

---

## Changelog

Veja [RELEASE.md](RELEASE.md) para o histórico completo de versões.
