"""Brazilian invoice models — extend mcp-einvoicing-core InvoiceDocument.

NF-e (modelo 55) and NFC-e (modelo 65) share a single XSD schema family
(`http://www.portalfiscal.inf.br/nfe`, schema 4.00) and are distinguished
only by the `mod` field. Both predate and are structurally unrelated to
EN 16931 (CEN TC 434) — `mcp-nfe-br` therefore follows the non-EN16931
pathway: `BRInvoice` extends `InvoiceDocument`, not `EN16931Invoice`.

See context-library/countries/br.md for the verified field-level reference
(decimal types, CNPJ/CPF formats, access-key structure, schema versions).
"""

from __future__ import annotations

from enum import StrEnum

from mcp_einvoicing_core import InvoiceLineItem
from mcp_einvoicing_core.models import InvoiceDocument
from pydantic import Field


class NFeModelo(StrEnum):
    """Document model code (`mod` field). Source: leiauteNFe_v4.00.xsd, TMod."""

    NFE = "55"
    NFCE = "65"


class TipoOperacao(StrEnum):
    """Operation direction (`tpNF` field): 0 = entrada, 1 = saída."""

    ENTRADA = "0"
    SAIDA = "1"


class BRInvoiceLine(InvoiceLineItem):  # type: ignore[misc]
    """NF-e/NFC-e invoice line (Grupo I — Produtos e Serviços).

    Brazil has no single VAT; ``vat_rate``/``vat_exemption_code`` from
    ``InvoiceLineItem`` are not used. ICMS, IPI, PIS, and COFINS are modeled
    as separate per-line tax fields. The IBS/CBS/Imposto Seletivo fields
    introduced by NT 2025.002-RTC (Grupo UB) are `[NEED: not yet modeled —
    field-level detail pending, see br.md "Known gaps"]`.
    """

    ncm: str = Field(
        ..., min_length=8, max_length=8, description="Código NCM (Nomenclatura Comum do Mercosul)"
    )
    cfop: str = Field(
        ..., min_length=4, max_length=4, description="Código Fiscal de Operações e Prestações"
    )
    icms_cst: str | None = Field(
        default=None, description="Código de Situação Tributária do ICMS"
    )
    icms_rate: str | None = Field(default=None, description="Alíquota do ICMS (%)")
    icms_amount: str | None = Field(default=None, description="Valor do ICMS")
    ipi_cst: str | None = Field(default=None, description="Código de Situação Tributária do IPI")
    ipi_rate: str | None = Field(default=None, description="Alíquota do IPI (%)")
    ipi_amount: str | None = Field(default=None, description="Valor do IPI")
    pis_cst: str | None = Field(default=None, description="Código de Situação Tributária do PIS")
    pis_amount: str | None = Field(default=None, description="Valor do PIS")
    cofins_cst: str | None = Field(
        default=None, description="Código de Situação Tributária do COFINS"
    )
    cofins_amount: str | None = Field(default=None, description="Valor do COFINS")


class BRInvoice(InvoiceDocument):  # type: ignore[misc]
    """NF-e / NFC-e document (Grupo B — Identificação da Nota Fiscal eletrônica).

    Extends ``InvoiceDocument`` with the fields required by the NF-e/NFC-e
    schema 4.00 that have no EN 16931 equivalent: document model (55/65),
    series, access key, and operation nature/direction.
    """

    modelo: NFeModelo = Field(..., description="Modelo do documento fiscal: 55 (NF-e) ou 65 (NFC-e)")
    serie: str = Field(..., max_length=3, description="Série do documento fiscal")
    chave_acesso: str | None = Field(
        default=None,
        max_length=44,
        description=(
            "Chave de acesso (44 caracteres). Sob PL_010d (NT 2026.004, "
            "vigente a partir de 2026-07-01) o segmento do CNPJ torna-se "
            "alfanumérico — ver br.md."
        ),
    )
    natureza_operacao: str = Field(..., description="Natureza da Operação")
    tipo_operacao: TipoOperacao = Field(..., description="Tipo de Operação: 0=entrada, 1=saída")
    protocolo_autorizacao: str | None = Field(
        default=None, description="Protocolo de autorização de uso retornado pela SEFAZ"
    )
    lines: list[BRInvoiceLine] = Field(default_factory=list)  # type: ignore[assignment]
