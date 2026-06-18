# NF-e / NFC-e specs — inventory

Normative source material for NF-e (modelo 55) and NFC-e (modelo 65), schema 4.00.
PDFs and ZIPs are gitignored (large binaries, not published) — this manifest is the
checked-in index. Source: user-supplied bundle from `nfe.fazenda.gov.br` /
`portalfiscal.inf.br`, retrieved 2026-06-12.

See [`context-library/countries/br.md`](../../../context-library/countries/br.md) for
the distilled compliance reference derived from these files.

## XSD schema packages

| Directory | Package | Status | Notes |
|---|---|---|---|
| `xsd/` | PL_010c (NT2022.002 v1.30) | **Current production schema** | Namespace `http://www.portalfiscal.inf.br/nfe`, schema 4.00. `TCnpj` = `[0-9]{14}`, `TCpf` = `[0-9]{11}`. |
| `xsd_pl010d_cnpj_alfa/` | PL_010d (NT 2026.004 v1.01) | **Next schema** — homologation up to 2026-06-15, production from 2026-07-01 | `TCnpj` becomes `[0-9A-Z]{12}[0-9]{2}`; `TChNFe` (access key) becomes `[0-9]{6}[0-9A-Z]{12}[0-9]{26}`. |

## PDFs (gitignored — see `*.pdf` entries in `.gitignore`)

| File | Covers |
|---|---|
| `Manual de Orientação ao Contribuinte - MOC - versão 7.0 - NF-e e NFC-e.pdf` | Primary MOC — overall NF-e/NFC-e orientation |
| `ANEXO I - Leiaute e Regra de Validação - NF-e e NFC-e.pdf` | Field-by-field layout and validation rules |
| `ANEXO II -Manual EspecificaçõesTécnicas - Danfe-Código-Barras.pdf` | DANFE barcode spec |
| `Anexo III - Manual de Contingência - NF-e.pdf` | NF-e contingency modes |
| `Anexo IV - Manual de Contingência - NFC-e.pdf` | NFC-e contingency modes |
| `NT2014.002_v1.30 - WsNFeDistribuicaoDFe.pdf` | Distribution/query webservice — needed for submission/query tools |
| `NT_2025.002_v1.50_RTC_NF-e_IBS_CBS_IS.pdf` | Tax reform (IBS/CBS/IS) layout and validation-rule changes |
| `NT_2026.004_v1.01_AlteraSchemaNFCeNFeCNPJAlfa.pdf` | CNPJ alfanumérico schema changes (source for `xsd_pl010d_cnpj_alfa/`) |
| `DFe NTCJ 2025.001_CNPJ Alfa_v1.00.pdf` | NT Conjunta DFe 2025.001 v1.00 (25 April 2025) — primary source for alphanumeric CNPJ check-digit algorithm; includes JS + VB.NET reference implementations (Annex I/II) |
| `NT_2024.003- Produtos AGRO NF-e - v 1.10_Rev.pdf` | Agricultural products fields |
| `NT_2020.001 v1.60 - Manifestação do destinatário.pdf` | Recipient manifestation events |
| `NT2022.002v1.30a - Equiparação Exportação e outras alterações.pdf` | Export equivalence and other changes (source for `xsd/` PL_010c) |

## Not yet retrieved

- Instrução Normativa RFB nº 2.229/2024 (CNPJ alfanumérico, primary text — not yet retrieved)
- Lei Complementar 214/2025 (Reforma Tributária do Consumo, primary text)
- Instrução Normativa RFB nº 2.229/2024 (CNPJ alfanumérico, primary text)
