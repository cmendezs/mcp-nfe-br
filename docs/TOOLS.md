# Tool reference — `mcp_nfe_br`

This file is generated from the MCP server's tool registry by `scripts/gen_tool_reference.py`. Do not edit it by hand; run the script instead.

**Tools:** 22

## `br__build_access_key`

Assemble and check-digit a 44-character NF-e/NFC-e access key (chNFe).

Returns a dict with ``chave_acesso`` (44 characters) and ``cnf`` (the
8-digit random code used, whether provided or generated).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf` | string | yes |  | Código IBGE da UF do emitente (2 dígitos) |
| `dh_emi` | string | yes |  | Data e hora de emissão (ISO 8601, com fuso horário) |
| `cnpj` | string | yes |  | CNPJ do emitente: 14 dígitos numéricos (PL_010c) ou 12 alfanuméricos + 2 dígitos (PL_010d) |
| `modelo` | string | yes |  | Modelo do documento fiscal: '55' (NF-e) ou '65' (NFC-e) |
| `serie` | string | yes |  | Série do documento fiscal |
| `nnf` | string | yes |  | Número do documento fiscal (nNF) |
| `tp_emis` | string | no | `'1'` | Forma de emissão (tpEmis): '1' = normal |
| `c_nf` | string | null | no | `None` | Código numérico aleatório de 8 dígitos (cNF). Gerado se omitido. |

## `br__cancel_cte`

Solicita o cancelamento de um CT-e autorizado (evento `110111`, `CTeRecepcaoEventoV4`).

Constrói, assina (`build_cte_event_signer`, alvo `infEvento`) e submete
o evento de cancelamento. `cStat=135` indica cancelamento homologado
`[Verified locally]` — MOC CT-e Visão Geral v4.00 §6.2.2.

Cancelamento é uma operação irreversível em produção e exige
confirmação em duas etapas (`ConfirmationGate`). Define
`BR_CTE_READ_ONLY=1` para desabilitar. `endpoint_override` é
obrigatório — nenhuma URL de endpoint CT-e está embutida/verificada
nesta versão.

Retorna `cStat`/`xMotivo` ou `error`.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `ch_cte` | string | yes |  | Chave de acesso do CT-e a cancelar (chCTe), 44 caracteres |
| `c_orgao` | string | yes |  | Código IBGE da UF do autorizador (cOrgao), 2 dígitos (ou '90' para SUFRAMA) |
| `cnpj` | string | yes |  | CNPJ do emitente do CT-e (autor do evento) |
| `dh_evento` | string | yes |  | Data e hora do evento (ISO 8601, UTC) |
| `n_prot` | string | yes |  | Número do protocolo de autorização do CT-e original (nProt) |
| `x_just` | string | yes |  | Justificativa do cancelamento |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `endpoint_override` | string | yes |  | URL completa do webservice CTeRecepcaoEventoV4 — obrigatório, ver docstring do módulo. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__cancel_nfse`

Solicitar cancelamento de uma NFS-e no ADN.

Cancelamento é uma operação irreversível e exige confirmação em duas
etapas (``ConfirmationGate``). Defina ``BR_READ_ONLY=1`` para desabilitar.

`[Unverified — endpoint e formato de requisição são inferidos.]`

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `ch_nfse` | string | yes |  | Chave de acesso da NFS-e a cancelar (53 caracteres) |
| `motivo` | string | yes |  | Motivo do cancelamento (texto livre) |
| `client_id` | string | yes |  | Client ID OAuth2 gov.br |
| `client_secret` | string | yes |  | Client Secret OAuth2 gov.br |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `scope` | string | null | no | `None` | OAuth2 scope override |
| `endpoint_override` | string | null | no | `None` | URL base do ADN override |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__consult_cte`

Consulta a situação de um CT-e por chave de acesso (`CTeConsultaV4`).

Read-only — não requer confirmação (consulta um CT-e específico e já
conhecido pela chave de acesso, não um lote de dados fiscais de
terceiros — diferente de `br__distribute_dfe` no NF-e). Nenhuma URL de
endpoint CT-e está embutida/verificada nesta versão —
`endpoint_override` é obrigatório.

Retorna `cStat`/`xMotivo`/`protCTe` (quando aplicável) ou `error`.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `ch_cte` | string | yes |  | Chave de acesso do CT-e (chCTe), 44 caracteres |
| `c_uf` | string | yes |  | Código IBGE da UF do autorizador (cUF), 2 dígitos |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `endpoint_override` | string | yes |  | URL completa do webservice CTeConsultaV4 — obrigatório, ver docstring do módulo. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |

## `br__consult_cte_sefaz_status`

Consulta a disponibilidade do webservice SEFAZ CT-e (`CTeStatusServicoV4`).

Read-only — não requer confirmação. Nenhuma URL de endpoint CT-e está
embutida/verificada nesta versão — `endpoint_override` é obrigatório
(ver `mcp_nfe_br.standards.sefaz_cte_client` docstring).

Retorna `cStat`/`xMotivo` (`cStat=107` indica serviço em operação
`[Unverified]`, mesmo código do padrão NF-e).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf` | string | yes |  | Código IBGE da UF do autorizador (cUF), 2 dígitos |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `endpoint_override` | string | yes |  | URL completa do webservice CTeStatusServicoV4 — obrigatório, ver docstring do módulo. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |

## `br__consult_nfse_status`

Consultar o status de uma NFS-e pelo chave de acesso (chNFSe).

Read-only, não requer confirmação.

`[Unverified — endpoint e formato de resposta são inferidos.]`

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `ch_nfse` | string | yes |  | Chave de acesso da NFS-e (53 caracteres, formato NFS[0-9]{50}) |
| `client_id` | string | yes |  | Client ID OAuth2 gov.br |
| `client_secret` | string | yes |  | Client Secret OAuth2 gov.br |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `scope` | string | null | no | `None` | OAuth2 scope override |
| `endpoint_override` | string | null | no | `None` | URL base do ADN override |

## `br__consult_sefaz_status`

Consulta a disponibilidade do webservice SEFAZ (`NFeStatusServico4`).

Read-only — não requer confirmação. Retorna `cStat`/`xMotivo` (`cStat=107`
indica serviço em operação `[Unverified]`).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf` | string | yes |  | Código IBGE da UF do autorizador (cUF), 2 dígitos |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `endpoint_override` | string | null | no | `None` | URL completa do webservice NFeStatusServico4 (sobrepõe a tabela de roteamento por UF) |

## `br__correct_cte`

Emite uma Carta de Correção Eletrônica para um CT-e (evento `110110`, `CTeRecepcaoEventoV4`).

Constrói, assina (`build_cte_event_signer`, alvo `infEvento`) e submete
o evento de CC-e. `cStat=135` indica CC-e homologada `[Verified
locally]` — MOC CT-e Visão Geral v4.00 §6.4. Por força do Art. 58-B do
CONVÊNIO/SINIEF 06/89, a CC-e não pode alterar valores de impostos,
dados cadastrais das partes, ou a data de emissão/saída.

Exige confirmação em duas etapas (`ConfirmationGate`). Define
`BR_CTE_READ_ONLY=1` para desabilitar. `endpoint_override` é
obrigatório.

Retorna `cStat`/`xMotivo` ou `error`.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `ch_cte` | string | yes |  | Chave de acesso do CT-e a corrigir (chCTe), 44 caracteres |
| `c_orgao` | string | yes |  | Código IBGE da UF do autorizador (cOrgao), 2 dígitos (ou '90' para SUFRAMA) |
| `cnpj` | string | yes |  | CNPJ do emitente do CT-e (autor do evento) |
| `dh_evento` | string | yes |  | Data e hora do evento (ISO 8601, UTC) |
| `correcoes` | array[object] | yes |  | Lista de correções. Cada item: 'grupo_alterado', 'campo_alterado', 'valor_alterado', e opcionalmente 'nro_item_alterado'. |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `endpoint_override` | string | yes |  | URL completa do webservice CTeRecepcaoEventoV4 — obrigatório, ver docstring do módulo. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__distribute_dfe`

Consulta/distribui DF-e via `NFeDistribuicaoDFe` (`NT2014.002_v1.30`, `[Verified locally]`).

Exatamente um de `ult_nsu`, `nsu`, ou `ch_nfe` deve ser informado,
selecionando `distNSU`, `consNSU`, ou `consChNFe` respectivamente.

Esta ferramenta consulta dados fiscais de terceiros vinculados ao
certificado e requer confirmação em duas etapas. Define
`BR_READ_ONLY=1` para desabilitar.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf_autor` | string | yes |  | Código IBGE da UF autorizadora (cUFAutor), 2 dígitos |
| `document_id` | string | yes |  | CNPJ ou CPF do interessado |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `document_id_type` | string | no | `'CNPJ'` | Tipo de document_id: 'CNPJ' ou 'CPF' |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `ult_nsu` | string | null | no | `None` | distNSU/ultNSU — último NSU recebido (modo distribuição em lote) |
| `nsu` | string | null | no | `None` | consNSU/NSU — NSU específico a consultar |
| `ch_nfe` | string | null | no | `None` | consChNFe/chNFe — chave de acesso (44 caracteres) a consultar |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `endpoint_override` | string | null | no | `None` | URL completa do webservice NFeDistribuicaoDFe (sobrepõe o endpoint do Ambiente Nacional) |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__generate_cte`

Generate an unsigned CT-e XML (modelo 57, schema 4.00).

v1 supports modal rodoviário only and ICMS CST 00 (tributação normal)
only — other modais/CSTs raise an error. The returned
`<CTe><infCte>…</infCte></CTe>` document does not include
`<Signature>` — sign it with `br__sign_cte` (roadmap BR-CTE-6 factory,
tool not yet registered) before SEFAZ submission.

Returns a dict with:
- ``xml``: the generated CT-e XML string
- ``chave_acesso``: the computed 44-character access key (chCTe)
- ``warnings``: list of non-fatal notices

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cte` | object | yes |  | CT-e data matching the BRCTeDocument schema (modelo 57) |

## `br__generate_nfe`

Generate an unsigned NF-e/NFC-e XML (modelo 55/65, schema 4.00).

The returned `<NFe><infNFe>…</infNFe></NFe>` document does not include
`<Signature>` — sign it with `br__sign_nfe` before SEFAZ submission.
SEFAZ webservice submission itself is not implemented in this phase.

Returns a dict with:
- ``xml``: the generated NF-e/NFC-e XML string
- ``chave_acesso``: the computed 44-character access key (chNFe)
- ``warnings``: list of non-fatal notices

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `invoice` | object | yes |  | Invoice data matching the BRInvoice schema (modelo 55 = NF-e, modelo 65 = NFC-e) |

## `br__generate_nfse`

Gerar um DPS não assinado para NFS-e Nacional (ADN), schema v1.01.

O DPS (Declaração de Prestação de Serviços) gerado não contém
``<ds:Signature>`` — assine-o com ``br__sign_nfse`` antes de submeter
ao ADN via ``br__submit_nfse``.

Returns a dict with:
- ``xml``: the generated unsigned DPS XML string
- ``dps_id``: the 45-character DPS Id (``infDPS Id`` attribute)
- ``warnings``: list of non-fatal notices

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `dps` | object | yes |  | DPS data matching the NFSeDocument schema (NFS-e Nacional, ADN, schema v1.01) |

## `br__sign_nfe`

Apply an ICP-Brasil enveloped XML-DSig signature to an NF-e/NFC-e XML.

Signs `<infNFe>` per MOC 7.0 Table 4-2 (RSA-SHA1 / SHA-1, enveloped
transform, `ds:Signature` appended as the last child of `<NFe>`) using
`mcp_nfe_br.standards.nfe_signer.build_nfe_signer`.

Only ICP-Brasil A1 (PKCS#12 file-based) certificates are supported.
A3 (hardware token/HSM) certificates `[NEED: not modeled]`.

Returns a dict with ``xml`` (the signed document) or ``error``.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `xml_content` | string | null | no | `None` | XML NF-e/NFC-e não assinado. Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | XML NF-e/NFC-e não assinado, codificado em base64. |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |

## `br__sign_nfse`

Aplicar assinatura XML-DSig ICP-Brasil ao DPS da NFS-e Nacional.

Assina o elemento ``<infDPS>`` com enveloped ``ds:Signature`` adicionada
como último filho de ``<DPS>``, usando
``mcp_nfe_br.standards.nfse_signer.build_nfse_signer``.

Algoritmo: RSA-SHA1 (padrão XMLDSigSigner).
`[Unverified para NFS-e Nacional — confirme no manual ADN antes de usar em produção.]`

Somente certificados A1 (PKCS#12 em arquivo) são suportados.
A3 (hardware token/HSM) `[NEED: não modelado]`.

Returns a dict with ``xml`` (the signed DPS) or ``error``.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `xml_content` | string | null | no | `None` | DPS não assinado (saída de br__generate_nfse). Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | DPS não assinado codificado em base64. |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |

## `br__submit_cte`

Submete um CT-e assinado à autorização SEFAZ (`CTeRecepcaoSincV4`, síncrono).

O payload é automaticamente compactado em GZip e codificado em Base64
antes do envio, conforme exigido pelo MOC CT-e §3.4.1 `[Verified locally]`.

Submissão para SEFAZ é uma operação irreversível em produção e exige
confirmação em duas etapas (`ConfirmationGate`). Define
`BR_CTE_READ_ONLY=1` para desabilitar esta ferramenta. Nenhuma URL de
endpoint CT-e está embutida/verificada nesta versão —
`endpoint_override` é obrigatório.

Retorna `protCTe` (incluindo `nProt`, o `protocolo de autorização`) em
caso de sucesso, ou `error`.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf` | string | yes |  | Código IBGE da UF do autorizador (cUF), 2 dígitos |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `endpoint_override` | string | yes |  | URL completa do webservice CTeRecepcaoSincV4 — obrigatório, ver docstring do módulo. |
| `xml_content` | string | null | no | `None` | XML CT-e assinado (saída de br__sign_cte). Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | XML CT-e assinado, codificado em base64. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__submit_nfe`

Submete um NF-e/NFC-e assinado à autorização SEFAZ (`NFeAutorizacao4`, síncrono).

Submissão para SEFAZ é uma operação irreversível em produção e exige
confirmação em duas etapas (`ConfirmationGate`). Define `BR_READ_ONLY=1`
para desabilitar esta ferramenta.

Retorna `protNFe` (incluindo `nProt`, o `protocolo de autorização`) em
caso de sucesso, ou `error`.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `c_uf` | string | yes |  | Código IBGE da UF do autorizador (cUF), 2 dígitos |
| `id_lote` | string | yes |  | Identificador do lote (idLote), até 15 dígitos |
| `cert_path` | string | yes |  | Caminho local para o certificado ICP-Brasil A1 (.p12/.pfx) |
| `xml_content` | string | null | no | `None` | XML NF-e/NFC-e assinado (saída de br__sign_nfe). Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | XML NF-e/NFC-e assinado, codificado em base64. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `cert_password` | string | null | no | `None` | Senha do certificado A1, se houver |
| `endpoint_override` | string | null | no | `None` | URL completa do webservice NFeAutorizacao4 (sobrepõe a tabela de roteamento por UF) |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__submit_nfse`

Submeter um DPS assinado ao ADN para geração da NFS-e Nacional.

Submissão ao ADN é uma operação irreversível em produção e exige
confirmação em duas etapas (``ConfirmationGate``). Defina ``BR_READ_ONLY=1``
para desabilitar esta ferramenta.

`[Unverified — endpoint ADN, formato de requisição e resposta são inferidos
de fontes secundárias. Verifique no manual ADN antes do uso em produção.]`

Retorna campos de status do ADN (``cStat``, ``xMotivo``) e opcionalmente
o XML da NFS-e gerada (``nfse_xml``).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `client_id` | string | yes |  | Client ID OAuth2 gov.br (registrado no portal de desenvolvedores) |
| `client_secret` | string | yes |  | Client Secret OAuth2 gov.br |
| `xml_content` | string | null | no | `None` | DPS assinado (saída de br__sign_nfse). Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | DPS assinado codificado em base64. |
| `tp_amb` | string | no | `'2'` | Identificação do Ambiente (tpAmb): '1' = produção, '2' = homologação |
| `scope` | string | null | no | `None` | OAuth2 scope override (padrão: 'openid govbr_empresa') |
| `endpoint_override` | string | null | no | `None` | URL base do ADN (sobrepõe a URL padrão por ambiente) |
| `confirmation_token` | string | null | no | `None` | Token de confirmação obtido de uma chamada anterior pendente. |

## `br__validate_cnpj`

Validate a Brazilian CNPJ (company tax ID).

Accepts both the legacy all-numeric form (14 digits) and the
alphanumeric form introduced by NT 2026.004 / PL_010d (12 alphanumeric
characters + 2 numeric check digits, production from 2026-07-01).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cnpj` | string | yes |  | CNPJ string, with or without ``.``/``/``/``-`` separators. |

## `br__validate_cpf`

Validate a Brazilian CPF (individual taxpayer ID).

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `cpf` | string | yes |  | CPF string, with or without ``.``/``-`` separators. |

## `br__validate_cte_xml`

Validate a CT-e XML (modelo 57, schema 4.00) against the bundled PL_CTe_400 XSD.

`CTeXSDValidator` selects the schema automatically: documents without a
`<ds:Signature>` are validated against the unsigned derivative; signed
documents are validated against the unmodified official schema, which
requires `<ds:Signature>`.

Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | null | no | `None` | Raw CT-e XML string. Provide either xml_content or xml_base64. |
| `xml_base64` | string | null | no | `None` | Base64-encoded CT-e XML bytes. |

## `br__validate_nfe_xml`

Validate an NF-e/NFC-e XML (modelo 55/65, schema 4.00) against the bundled PL_010d XSD.

`NFeXSDValidator` selects the schema automatically: documents without a
`<ds:Signature>` are validated against the unsigned derivative; signed
documents (produced by `br__sign_nfe`) are validated against the
unmodified official schema, which requires `<ds:Signature>`.

Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | null | no | `None` | Raw NF-e/NFC-e XML string. Provide either xml_content or xml_base64. |
| `xml_base64` | string | null | no | `None` | Base64-encoded NF-e/NFC-e XML bytes. |

## `br__validate_nfse_xml`

Validar um DPS ou NFSe contra o XSD v1.01 do ADN.

Seleciona automaticamente o schema com base no elemento raiz:
- ``<DPS>`` → valida contra ``DPS_v1.01.xsd`` (``<ds:Signature>`` opcional)
- ``<NFSe>`` → valida contra ``NFSe_v1.01.xsd`` (``<ds:Signature>`` obrigatória)

Returns a dict with ``valid``, ``errors``, ``warnings``, and ``schema_version``.

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `xml_content` | string | null | no | `None` | XML DPS ou NFSe como string. Informe xml_content ou xml_base64. |
| `xml_base64` | string | null | no | `None` | XML DPS ou NFSe codificado em base64. |
