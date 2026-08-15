# NFS-e Via (Exploração de Via) specs — inventory

> **Seed only — not yet implemented.** `mcp-nfe-br` does **not** support NFS-e Via.
> These files are bundled as reference material for a future support decision.
> Tracked as roadmap item **BR-NFSE-VIA-2026-08**.

**NFS-e Via** = *Nota Fiscal de Serviço eletrônica de Exploração de Via* — a national
NFS-e sub-standard for **road/toll-concession (exploração de via) services**, instituted
by **Resolução CGNFS-E Nº 9** (published 2025-12-30, DOU), part of the Reforma Tributária
do Consumo (IBS/CBS, EC 132/2023), in force from **2026-01-01**. It has its **own schema
set** (`NFSeVia_v1.00`), distinct from NFS-e Nacional's DPS/NFSe (`v1.01`).

Surfaced during the NT 008 (BR-NFSE-2026-08) DANFSE triage on 2026-08-15. Source: user-supplied
bundle from `/Users/christophe/Downloads/Digital Invoicing/BR/tmp/`, retrieved 2026-08.
PDFs and ZIPs are gitignored (large binaries) — this manifest is the checked-in index.

## XSD schema package (extracted, tracked in `specs/nfse-via/schemas/`)

Source zip: `arquivos-xsd-16dez2025.zip` (2025-12-16, gitignored). `[Verified locally — listing only; not yet reviewed for structure]`

| File | Role |
|---|---|
| `NFSeVia_v1.00.xsd` | Root schema for the NFS-e Via document |
| `EventoVia_v1.00.xsd` | Event schema |
| `ProcNFSeVia_v1.00.xsd` | Processed-NFS-e Via wrapper |
| `ProcEventoVia_v1.00.xsd` | Processed-event wrapper |
| `tiposComplexos_v1.00.xsd` | Complex types |
| `tiposEventos_v1.00.xsd` | Event types |
| `tiposSimples_v1.00.xsd` | Simple types / string patterns |
| `xmldsig-core-schema_v1.00.xsd` | W3C XML-DSig core schema |

## Notas Técnicas (gitignored PDFs)

| File | Covers |
|---|---|
| `nt-006-se-cgnfse-leiaute-nfse-via-v20260128.pdf` | NT 006 — leiaute (layout) of the NFS-e Via, v1.0 (2026-01-22 doc; cover dated 2026-01-28). Ratifies the schema published 2025-12-23. |

## Guides and manuals (gitignored PDFs)

| File | Covers |
|---|---|
| `anexo-i_guia-da-parametrizacao-do-portal-das-concessionarias-nfs-e_via-v1-0_producao.pdf` | Anexo I — concessionárias portal parametrization guide |
| `anexo-ii-guia-para-utilizacao-das-api2019s-nfs-e_via-v1-0_producao.pdf` | Anexo II — NFS-e Via API usage guide |
| `anexo-iii-2013-guia-do-portal-do-homologador-nfs-e_via-v1-0_producao.pdf` | Anexo III — homologador portal guide |
| `anexo-v-guia-para-utilizacao-das-api-municipios-v1-1.pdf` | Anexo V — municipality API usage guide (v1.1) |
| `manual-para-emissao-da-nfs-e-via-nfs-e_via-v1-0_producao.pdf` | NFS-e Via issuance manual |
| `passo-a-passo-para-emissao-da-nfs-e_via-v1-0_producao.pdf` | NFS-e Via step-by-step issuance guide |

## XLSX annexes (tracked)

| File | Content |
|---|---|
| `anexo-iv_leiautesrn_adn-snnfsevia_v1-00-producao-20260126.xlsx` | Anexo IV — DPS/NFS-e Via field layout + validation rules (LeiautesRN, ADN-SN NFS-e Via v1.00) |

## Authority

- Portal: https://www.gov.br/nfse/pt-br/nfs-e-via/documentacao-tecnica
- Instituting act: Resolução CGNFS-E Nº 9 (2025-12-30, DOU)
