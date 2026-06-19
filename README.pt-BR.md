# mcp-nfe-br 🇧🇷

[English](README.md) | [Portugues (Brasil)](README.pt-BR.md)

<!-- mcp-name: io.github.cmendezs/mcp-nfe-br -->

[![PyPI version](https://badge.fury.io/py/mcp-nfe-br.svg)](https://badge.fury.io/py/mcp-nfe-br)
[![Python](https://img.shields.io/pypi/pyversions/mcp-nfe-br.svg)](https://pypi.org/project/mcp-nfe-br/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Introdução

`mcp-nfe-br` é um servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io) que fornece ferramentas para a emissão e validação de documentos fiscais eletrônicos brasileiros: **NF-e (modelo 55)** e **NFC-e (modelo 65)**, conforme o leiaute XML versão 4.00 da SEFAZ. Este servidor faz parte da família `mcp-einvoicing-*` / `mcp-*-*`, construída sobre [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core), que fornece o modelo de dados base, utilitários HTTP/OAuth2, e a infraestrutura comum de servidores MCP.

**Status atual (v0.2.0):** fase 1 do roadmap, cobrindo validação de CPF/CNPJ, **geração de XML NF-e/NFC-e (não assinado)** e **validação contra o XSD oficial (PL_010d, variante sem assinatura)**. Assinatura digital ICP-Brasil e integração com os webservices da SEFAZ estão planejadas para versões futuras. Os documentos gerados são **não assinados** e não são transmitidos à SEFAZ por este servidor. NFS-e (nota fiscal de serviços) e CT-e (conhecimento de transporte) são fases posteriores, fora do escopo desta versão.

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
| `BR_READ_ONLY` | Defina como `1` para desativar as ferramentas de escrita SEFAZ (`br__submit_nfe`, `br__distribute_dfe`). Modo seguro para exploração. O ambiente SEFAZ (produção/homologação) é selecionado por chamada via o argumento `tp_amb`. | — |
| `LOG_LEVEL` | Nível de log: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

---

## Ferramentas disponíveis

### `br__validate_cpf`

Valida um CPF (Cadastro de Pessoas Físicas), número de identificação fiscal de pessoa física, conforme o algoritmo módulo 11 da Receita Federal.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cpf` | `string` | sim | CPF com ou sem separadores `.`/`-` |

Retorna um `TaxIdValidationResult` com `valid=True` e o valor limpo (11 dígitos) em caso de sucesso, ou `valid=False` com mensagem de erro em português.

---

### `br__validate_cnpj`

Valida um CNPJ (Cadastro Nacional da Pessoa Jurídica), número de identificação fiscal de pessoa jurídica. Aceita tanto o formato numérico tradicional (14 dígitos) quanto o formato alfanumérico introduzido pela NT 2026.004 (PL_010d), com vigência em homologação a partir de 2026-06-01 e em produção a partir de 2026-07-01.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cnpj` | `string` | sim | CNPJ com ou sem separadores `.`/`/`/`-` |

Retorna um `TaxIdValidationResult` com `valid=True` e o valor limpo (14 caracteres) em caso de sucesso, ou `valid=False` com mensagem de erro em português.

> ⚠️ **[Unverified]**: o algoritmo de dígito verificador para o formato alfanumérico do CNPJ foi implementado com base em fontes secundárias, pois a fonte primária ("NT Conjunta DFe 2025.001") ainda não está disponível localmente. Veja `context-library/countries/br.md` para detalhes.

---

### `br__generate_nfe`

Gera um documento NF-e/NFC-e 4.00 **não assinado** (`<NFe><infNFe>…</infNFe></NFe>`) a partir de um objeto `BRInvoice`.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `invoice` | `object` | sim | Documento `BRInvoice` (modelo 55 ou 65, grupos `ide`/`emit`/`dest`/`det`/`total`/`transp`/`pag`) |

Retorna `{"xml": ..., "chave_acesso": ..., "warnings": [...]}`. Os avisos em português lembram que o documento **não está assinado** (ICP-Brasil) e **não foi transmitido à SEFAZ**. Ambas as etapas ficam a cargo de um processo separado.

Cobertura da fase 1 para os grupos de tributos por item:

| Tributo | Códigos suportados | Comportamento |
|---|---|---|
| ICMS | CST `00` (regime normal) ou CSOSN `102` (Simples Nacional) | outros códigos geram `DocumentGenerationError` |
| PIS/COFINS | CST `01`/`02` (alíquota) ou `04`-`09` (não tributado) | grupo omitido se `pis_cst`/`cofins_cst` forem `None` |
| IPI | CST `00`/`49`/`50`/`99` (tributado) ou outro (não tributado) | grupo omitido se `ipi_cst` for `None` |

`[NEED: IBS/CBS/Imposto Seletivo — Grupo UB/W03 (NT 2025.002-RTC) ainda não modelado, ver context-library/countries/br.md "Known gaps"]`.

---

### `br__validate_nfe_xml`

Valida um XML NF-e/NFC-e 4.00 contra o XSD oficial PL_010d (variante local "sem assinatura", veja nota abaixo).

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `xml_content` | `string` | não* | XML como string |
| `xml_base64` | `string` | não* | XML codificado em base64 |

\* Exatamente um de `xml_content`/`xml_base64` deve ser informado.

Retorna `{"valid": bool, "errors": [...], "metadata": {"schema_version": ...}}`.

> **[Inference]**: o XSD oficial (`nfe_v4.00.xsd`/`leiauteNFe_v4.00.xsd`, PL_010d) exige `<ds:Signature>` como filho obrigatório de `<NFe>`. Como a fase 1 gera documentos não assinados, esta ferramenta valida contra uma cópia derivada local (`nfe_v4.00_unsigned.xsd`) onde `<ds:Signature>` passou a ser opcional (`minOccurs="0"`). A validação de documentos **assinados** (fase futura) deve usar o XSD oficial sem modificações.

---

### `br__build_access_key`

Monta uma chave de acesso (`chNFe`, 44 caracteres) com dígito verificador módulo 11, a partir dos componentes `cUF`, `dhEmi`, CNPJ do emitente, modelo, série e número do documento.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `c_uf` | `string` | sim | Código IBGE da UF (2 dígitos) |
| `dh_emi` | `string` | sim | Data/hora de emissão (ISO 8601) |
| `cnpj` | `string` | sim | CNPJ do emitente (numérico ou alfanumérico PL_010d) |
| `modelo` | `string` | sim | `55` (NF-e) ou `65` (NFC-e) |
| `serie` | `string` | sim | Série do documento |
| `nnf` | `string` | sim | Número do documento |
| `tp_emis` | `string` | não | Forma de emissão (padrão `"1"`) |
| `c_nf` | `string` | não | Código numérico aleatório (cNF, 8 dígitos); gerado automaticamente se omitido |

Retorna `{"chave_acesso": ..., "cnf": ...}`.

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
│       ├── standards/
│       │   ├── __init__.py
│       │   └── nfe_generator.py   # NFeGenerator — gera NF-e/NFC-e 4.00 não assinada
│       ├── validators/
│       │   ├── __init__.py
│       │   └── nfe_xsd.py         # NFeXSDValidator — valida contra XSD PL_010d (variante sem assinatura)
│       ├── schemas/nfe/           # XSDs bundled (oficiais + variantes "_unsigned")
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
- `BRInvoice` (extensão de `InvoiceDocument`, pois NF-e/NFC-e não tem ascendência EN 16931)
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

## Outros servidores MCP de faturação eletrônica

| País | Servidor |
|---------|--------|
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

Este projeto está licenciado sob **Apache 2.0**. Veja [LICENSE](LICENSE) para detalhes.

---

## Changelog

Veja [RELEASE.md](RELEASE.md) para o histórico completo de versões.
