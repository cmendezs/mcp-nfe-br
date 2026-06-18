# NFS-e Nacional / ADN specs — inventory

Normative source material for NFS-e Nacional (Padrão Nacional / Ambiente de Dados
Nacional — ADN), schema v1.01. PDFs and XLSX annexes are gitignored (large binaries,
not published) — this manifest is the checked-in index. Source: user-supplied bundle
from `/Users/christophe/Downloads/BR/NFS-e/`, retrieved 2026-06.

See [`context-library/countries/br.md`](../../../context-library/countries/br.md) for
the distilled compliance reference derived from these files (NFS-e Nacional section).

## XSD schema package

| Version | File (zip) | Status |
|---|---|---|
| v1.01 (2026-02-09) | `nfse-esquemas_xsd-v1-01-20260209.zip` | Extracted to `mcp_nfe_br/schemas/nfse/` — files listed below |

### Extracted XSDs (v1.01, bundled in `src/mcp_nfe_br/schemas/nfse/`)

| File | Role |
|---|---|
| `NFSe_v1.01.xsd` | Root schema for the NFS-e returned by ADN; root element `NFSe`, type `TCNFSe`; `<ds:Signature>` mandatory |
| `DPS_v1.01.xsd` | Root schema for the DPS submitted by the contributor; root element `DPS`, type `TCDPS`; `<ds:Signature>` optional (`minOccurs="0"`) |
| `tiposComplexos_v1.01.xsd` | Complex types included by both NFSe and DPS schemas |
| `tiposSimples_v1.01.xsd` | Simple types and string patterns |
| `xmldsig-core-schema.xsd` | W3C XML-DSig core schema (same as the one bundled with NF-e) |

Key structural facts `[Verified locally — tiposSimples_v1.01.xsd, tiposComplexos_v1.01.xsd]`:

- **Namespace**: `http://www.sped.fazenda.gov.br/nfse`
- **DPS signed element**: `infDPS` with `Id` attribute (type `TSIdDPS`)
- **DPS ID format**: `DPS[0-9]{42}` (45 chars) — "DPS" + cLocEmi(7) + tpInscFederal(1) + inscFederal(14) + serie(5) + nDPS(15)
- **NFSe ID format**: `NFS[0-9]{50}` (53 chars) — "NFS" + cLocEmi(7) + tpAmb(1) + tpInscFederal(1) + inscFederal(14) + nNFSe(13) + anoMes(4) + codNum(9) + DV(1)
- **Signature algorithm**: `[Unverified — not specified in XSD; assume RSA-SHA1 per XMLDSigSigner defaults pending NFS-e manual review]`

## PDFs (gitignored)

| File | Covers |
|---|---|
| `manual-contribuintes-apis-adn-sistema-nacional-nfse.pdf` | ADN API for contributors |
| `manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf` | Public issuer API for contributors (v1.2, Oct 2025) |
| `manual-contribuintes-emissor-publico-api-emissao-decisao-administrativa-e-judicial.pdf` | API for administrative/judicial issuance |
| `manual-municipios-apis-adn-sistema-nacional-nfs-e-v1-2-out21025.pdf` | ADN API for municipalities |
| `manual-municipios-cnc-api-sistema-nacional-nfs-e-v1-2-out21025.pdf` | CNC API for municipalities |
| `manual-municipios-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out21025.pdf` | Public issuer API for municipalities |
| `guia-emissorpubliconacionalweb_snnfse-ern-v12.pdf` | Public national issuer web guide |

## XLSX annexes (gitignored)

| File | Content |
|---|---|
| `anexo_a-municipio_ibge-paises_iso2-v1-00-snnfse-20251210.xlsx` | IBGE municipality codes + ISO2 country codes |
| `anexo_b-nbs2-lista_servico_nacional-snnfse-v1-01-20260122.xlsx` | NBS 2.0 national service list |
| `anexo_c-indop_ibscbs-snnfse-v1-01-20260122.xlsx` | IBS/CBS classification codes (indOP) |
| `anexo_i-sefin_adn-dps_nfse-snnfse-v1-01-20260209.xlsx` | DPS/NFS-e field layout |
| `anexo_ii-sefin_adn-pedregevt_evt-snnfse-v1-01-20260122.xlsx` | Event registration layout |
| `anexo_iii-cnc-snnfse-v1-00-20251216.xlsx` | CNC layout |
| `anexo_iv-adn-snnfse-v1-00-20251216.xlsx` | ADN layout |
| `anexo_v-painel_adm_municipal-snnfse-v1-00-20251216.xlsx` | Municipal admin panel |
