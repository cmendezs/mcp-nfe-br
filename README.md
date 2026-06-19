# mcp-nfe-br 🇧🇷

[English](README.md) | [Portugues (Brasil)](README.pt-BR.md)

<!-- mcp-name: io.github.cmendezs/mcp-nfe-br -->

[![PyPI version](https://badge.fury.io/py/mcp-nfe-br.svg)](https://badge.fury.io/py/mcp-nfe-br)
[![Python](https://img.shields.io/pypi/pyversions/mcp-nfe-br.svg)](https://pypi.org/project/mcp-nfe-br/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Introduction

`mcp-nfe-br` is an [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server providing tools for issuing and validating Brazilian electronic fiscal documents: **NF-e (modelo 55)** and **NFC-e (modelo 65)**, per SEFAZ XML schema version 4.00. This server is part of the `mcp-einvoicing-*` / `mcp-*-*` family, built on [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core), which provides the base data model, HTTP/OAuth2 utilities, and shared MCP server infrastructure.

**Current status (v0.2.0):** Phase 1 of the roadmap, covering CPF/CNPJ tax-ID validation, **unsigned NF-e/NFC-e XML generation**, and **XSD validation** against the official PL_010d schema (unsigned variant). ICP-Brasil digital signing and SEFAZ webservice submission are planned for future releases. Generated documents are **unsigned** and are not transmitted to SEFAZ by this server. NFS-e (service invoices) and CT-e (transport documents) are later phases, out of scope for this version.

---

## Installation

### Requirements

- Python ≥ 3.11
- [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core) (installed automatically as a dependency)

### Using `uv` (recommended)

```bash
uv add mcp-nfe-br
```

### Using `pip`

```bash
pip install mcp-nfe-br
```

### From source

```bash
git clone https://github.com/cmendezs/mcp-nfe-br.git
cd mcp-nfe-br
uv sync --all-extras
```

---

## Configuration

Add the server to your MCP client configuration. For Claude Desktop, edit `claude_desktop_config.json`:

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

For a local development installation:

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

### Environment variables

| Variable | Description | Default |
|---|---|---|
| `BR_READ_ONLY` | Set to `1` to disable SEFAZ write tools (`br__submit_nfe`, `br__distribute_dfe`). Safe mode for exploration. The SEFAZ environment (production/homologation) is selected per call via the `tp_amb` argument. | — |
| `LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

---

## Available tools

### `br__validate_cpf`

Validates a CPF (Cadastro de Pessoas Físicas), the individual taxpayer identification number, using the Receita Federal modulo 11 algorithm.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `cpf` | `string` | yes | CPF with or without `.`/`-` separators |

Returns a `TaxIdValidationResult` with `valid=True` and the cleaned value (11 digits) on success, or `valid=False` with an error message in Portuguese.

---

### `br__validate_cnpj`

Validates a CNPJ (Cadastro Nacional da Pessoa Jurídica), the business taxpayer identification number. Accepts both the traditional numeric format (14 digits) and the alphanumeric format introduced by NT 2026.004 (PL_010d), effective in homologation from 2026-06-01 and in production from 2026-07-01.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `cnpj` | `string` | yes | CNPJ with or without `.`/`/`/`-` separators |

Returns a `TaxIdValidationResult` with `valid=True` and the cleaned value (14 characters) on success, or `valid=False` with an error message in Portuguese.

> ⚠️ **[Unverified]**: the check-digit algorithm for the alphanumeric CNPJ format was implemented based on secondary sources, as the primary source ("NT Conjunta DFe 2025.001") is not yet available locally. See `context-library/countries/br.md` for details.

---

### `br__generate_nfe`

Generates an **unsigned** NF-e/NFC-e 4.00 document (`<NFe><infNFe>…</infNFe></NFe>`) from a `BRInvoice` object.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `invoice` | `object` | yes | `BRInvoice` document (modelo 55 or 65, groups `ide`/`emit`/`dest`/`det`/`total`/`transp`/`pag`) |

Returns `{"xml": ..., "chave_acesso": ..., "warnings": [...]}`. The warnings in Portuguese remind that the document is **not signed** (ICP-Brasil) and **was not transmitted to SEFAZ**. Both steps are the responsibility of a separate process.

Phase 1 coverage for per-item tax groups:

| Tax | Supported codes | Behavior |
|---|---|---|
| ICMS | CST `00` (normal regime) or CSOSN `102` (Simples Nacional) | other codes raise `DocumentGenerationError` |
| PIS/COFINS | CST `01`/`02` (rate-based) or `04`-`09` (non-taxed) | group omitted if `pis_cst`/`cofins_cst` are `None` |
| IPI | CST `00`/`49`/`50`/`99` (taxed) or other (non-taxed) | group omitted if `ipi_cst` is `None` |

`[NEED: IBS/CBS/Imposto Seletivo — Grupo UB/W03 (NT 2025.002-RTC) not yet modeled, see context-library/countries/br.md "Known gaps"]`.

---

### `br__validate_nfe_xml`

Validates an NF-e/NFC-e 4.00 XML document against the official PL_010d XSD (local "unsigned" variant, see note below).

| Parameter | Type | Required | Description |
|---|---|---|---|
| `xml_content` | `string` | no* | XML as a string |
| `xml_base64` | `string` | no* | Base64-encoded XML |

\* Exactly one of `xml_content`/`xml_base64` must be provided.

Returns `{"valid": bool, "errors": [...], "metadata": {"schema_version": ...}}`.

> **[Inference]**: the official XSD (`nfe_v4.00.xsd`/`leiauteNFe_v4.00.xsd`, PL_010d) requires `<ds:Signature>` as a mandatory child of `<NFe>`. Since Phase 1 generates unsigned documents, this tool validates against a local derived copy (`nfe_v4.00_unsigned.xsd`) where `<ds:Signature>` has been made optional (`minOccurs="0"`). Validation of **signed** documents (future phase) should use the official XSD without modifications.

---

### `br__build_access_key`

Builds an access key (`chNFe`, 44 characters) with a modulo 11 check digit, from the components `cUF`, `dhEmi`, issuer CNPJ, model, series, and document number.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `c_uf` | `string` | yes | IBGE state code (2 digits) |
| `dh_emi` | `string` | yes | Issue date/time (ISO 8601) |
| `cnpj` | `string` | yes | Issuer CNPJ (numeric or alphanumeric PL_010d) |
| `modelo` | `string` | yes | `55` (NF-e) or `65` (NFC-e) |
| `serie` | `string` | yes | Document series |
| `nnf` | `string` | yes | Document number |
| `tp_emis` | `string` | no | Issuance type (default `"1"`) |
| `c_nf` | `string` | no | Random numeric code (cNF, 8 digits); auto-generated if omitted |

Returns `{"chave_acesso": ..., "cnf": ...}`.

---

## Architecture

```
mcp-nfe-br/
├── src/
│   └── mcp_nfe_br/
│       ├── __init__.py
│       ├── server.py              # MCP entry point and tool registration
│       ├── models/
│       │   ├── __init__.py
│       │   └── invoice.py         # BRInvoice, BRInvoiceLine, NFeModelo, TipoOperacao
│       ├── standards/
│       │   ├── __init__.py
│       │   └── nfe_generator.py   # NFeGenerator — generates unsigned NF-e/NFC-e 4.00
│       ├── validators/
│       │   ├── __init__.py
│       │   └── nfe_xsd.py         # NFeXSDValidator — validates against PL_010d XSD (unsigned variant)
│       ├── schemas/nfe/           # Bundled XSDs (official + "_unsigned" variants)
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── validation.py      # br__validate_cpf, br__validate_cnpj
│       │   └── generation.py      # br__generate_nfe, br__validate_nfe_xml, br__build_access_key
│       └── utils/
│           ├── __init__.py
│           ├── document_ids.py    # validate_cpf, validate_cnpj
│           └── access_key.py      # build_access_key, access_key_check_digit
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_tools/
│   │   ├── test_validation.py
│   │   └── test_generation.py
│   ├── test_standards/
│   │   └── test_nfe_generator.py
│   ├── test_validators/
│   │   └── test_nfe_xsd.py
│   └── test_utils/
│       └── test_access_key.py
├── specs/nfe/                     # Normative material (XSDs, MOC, Technical Notes, not published)
├── audit/
│   ├── audit_vs_core.py
│   └── report.json
├── .github/workflows/publish.yml
├── pyproject.toml
├── RELEASE.md
└── LICENSE
```

### Relationship with `mcp-einvoicing-core`

`mcp-einvoicing-core` provides:
- Base Pydantic models for invoices, parties, line items, and validation results (`InvoiceDocument`, `InvoiceLineItem`, `TaxIdValidationResult`)
- Shared MCP server infrastructure (`EInvoicingMCPServer`)
- HTTP/OAuth2 client, token cache, structured logging, exception hierarchy

`mcp-nfe-br` adds Brazil-specific logic:
- `BRInvoice` (extends `InvoiceDocument`, as NF-e/NFC-e has no EN 16931 lineage)
- Group I fields (NCM, CFOP, ICMS/IPI/PIS/COFINS) in `BRInvoiceLine`
- CPF/CNPJ validation (including the alphanumeric CNPJ from NT 2026.004)

---

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

```bash
git clone https://github.com/cmendezs/mcp-nfe-br.git
cd mcp-nfe-br
uv sync --all-extras
uv run pytest
uv run ruff check src/mcp_nfe_br tests audit
uv run mypy src/mcp_nfe_br
```

---

## Other e-invoicing MCP servers

| Country | Server |
|---------|--------|
| 🌍 Global | [mcp-einvoicing-core](https://github.com/cmendezs/mcp-einvoicing-core) |
| 🇧🇪 Belgium | [mcp-einvoicing-be](https://github.com/cmendezs/mcp-einvoicing-be) |
| 🇧🇷 Brazil | [mcp-nfe-br](https://github.com/cmendezs/mcp-nfe-br) |
| 🇫🇷 France | [mcp-facture-electronique-fr](https://github.com/cmendezs/mcp-facture-electronique-fr) |
| 🇩🇪 Germany | [mcp-einvoicing-de](https://github.com/cmendezs/mcp-einvoicing-de) |
| 🇮🇹 Italy | [mcp-fattura-elettronica-it](https://github.com/cmendezs/mcp-fattura-elettronica-it) |
| 🇵🇱 Poland | [mcp-ksef-pl](https://github.com/cmendezs/mcp-ksef-pl) |
| 🇪🇸 Spain | [mcp-facturacion-electronica-es](https://github.com/cmendezs/mcp-facturacion-electronica-es) |

---

## License

This project is licensed under **Apache 2.0**. See [LICENSE](LICENSE) for details.

---

## Changelog

See [RELEASE.md](RELEASE.md) for the full version history.
