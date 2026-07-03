# mcp-nfe-br 🇧🇷

[English](README.md) | [Portugues (Brasil)](README.pt-BR.md)

<!-- mcp-name: io.github.cmendezs/mcp-nfe-br -->

[![PyPI version](https://badge.fury.io/py/mcp-nfe-br.svg)](https://badge.fury.io/py/mcp-nfe-br)
[![Python](https://img.shields.io/pypi/pyversions/mcp-nfe-br.svg)](https://pypi.org/project/mcp-nfe-br/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

---

## Introdução

`mcp-nfe-br` é um servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io) que fornece ferramentas para a emissão e validação de documentos fiscais eletrônicos brasileiros: **NF-e (modelo 55)**, **NFC-e (modelo 65)**, **NFS-e Nacional** (ADN) e **CT-e (modelo 57)**. Este servidor faz parte da família `mcp-einvoicing-*` / `mcp-*-*`, construída sobre [`mcp-einvoicing-core`](https://github.com/cmendezs/mcp-einvoicing-core), que fornece o modelo de dados base, utilitários HTTP/OAuth2, e a infraestrutura comum de servidores MCP.

**Status atual (v0.6.1):** geração, assinatura ICP-Brasil, validação XSD e submissão gated à SEFAZ/ADN estão implementadas para NF-e/NFC-e (modelo 55/65, schema 4.00) e NFS-e Nacional (ADN, schema v1.01). A cobertura de **CT-e (modelo 57)** — geração, assinatura, validação e submissão de eventos SEFAZ (cancelamento, Carta de Correção) — começou na v0.6.0. O escopo v1 é intencionalmente restrito: **apenas modal rodoviário**, **apenas ICMS CST 00**, e **nenhuma tabela de endpoints de webservice CT-e embutida/verificada** (toda chamada SEFAZ CT-e exige `endpoint_override` explícito). Veja a seção "Ferramentas CT-e (modelo 57)" abaixo e `context-library/countries/br.md` (no repositório de origem) para a referência completa em nível de campo.

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
| `BR_READ_ONLY` | Defina como `1` para desativar as ferramentas de escrita SEFAZ (`br__submit_nfe`, `br__distribute_dfe`, `br__submit_nfse`, `br__cancel_nfse`). Modo seguro para exploração. O ambiente SEFAZ (produção/homologação) é selecionado por chamada via o argumento `tp_amb`. | — |
| `BR_CTE_READ_ONLY` | Defina como `1` para desativar as ferramentas de escrita CT-e (`br__submit_cte`, `br__cancel_cte`, `br__correct_cte`). Mantida distinta de `BR_READ_ONLY` para que NF-e e CT-e possam ser controladas independentemente. | — |
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

## Ferramentas CT-e (modelo 57)

A cobertura de CT-e (Conhecimento de Transporte Eletrônico) começou na v0.6.0. **O escopo v1 é intencionalmente restrito**: apenas modal rodoviário (outros modais retornam erro), apenas ICMS CST 00 (tributação normal), e nenhuma tabela de endpoints SEFAZ CT-e embutida/verificada — toda chamada SEFAZ abaixo exige `endpoint_override` explícito.

### `br__generate_cte`

Gera um documento CT-e 4.00 **não assinado** (`<CTe><infCte>…</infCte></CTe>`) a partir de um objeto `BRCTeDocument`.

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `cte` | `object` | sim | `BRCTeDocument` (modelo 57, modal rodoviário, ICMS CST 00) |

Retorna `{"xml": ..., "chave_acesso": ..., "warnings": [...]}`.

### `br__validate_cte_xml`

Valida um XML de CT-e 4.00 contra o XSD PL_CTe_400 embutido (seleciona automaticamente o schema não assinado ou o oficial assinado, conforme a presença de `<ds:Signature>`).

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `xml_content` | `string` | não* | XML como string |
| `xml_base64` | `string` | não* | XML codificado em base64 |

\* Exatamente um de `xml_content`/`xml_base64` deve ser informado.

### `br__consult_cte_sefaz_status`

Consulta a disponibilidade do webservice SEFAZ CT-e (`CTeStatusServicoV4`). Somente leitura, sem confirmação.

### `br__consult_cte`

Consulta a situação de um CT-e por chave de acesso (`CTeConsultaV4`). Somente leitura, sem confirmação — consulta um documento específico já conhecido, não um lote de dados.

### `br__submit_cte`

Submete um CT-e assinado à autorização SEFAZ (`CTeRecepcaoSincV4`, síncrono). O payload é automaticamente compactado em GZip e codificado em Base64 antes do envio, conforme o MOC CT-e. Requer confirmação em duas etapas (`ConfirmationGate`) e respeita `BR_CTE_READ_ONLY`.

### `br__cancel_cte`

Solicita o cancelamento de um CT-e autorizado (evento `110111`, `CTeRecepcaoEventoV4`). `cStat=135` indica cancelamento homologado. Requer confirmação.

### `br__correct_cte`

Emite uma Carta de Correção Eletrônica (evento `110110`, `CTeRecepcaoEventoV4`). Conforme o Art. 58-B do CONVÊNIO/SINIEF 06/89, a CC-e não pode alterar valores de impostos, dados cadastrais das partes, ou a data de emissão/saída. Requer confirmação.

Ainda não implementado: `br__distribute_cte_dfe` (`CTeDistribuicaoDFe`) — a especificação embutida confirma o formato do payload da requisição, mas não o nome do método, o namespace WSDL, ou o elemento wrapper da mensagem do webservice.

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
