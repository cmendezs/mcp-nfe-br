"""Brazilian invoice models — extend mcp-einvoicing-core InvoiceDocument.

NF-e (modelo 55) and NFC-e (modelo 65) share a single XSD schema family
(`http://www.portalfiscal.inf.br/nfe`, schema 4.00) and are distinguished
only by the `mod` field. Both predate and are structurally unrelated to
EN 16931 (CEN TC 434) — `mcp-nfe-br` therefore follows the non-EN16931
pathway: `BRInvoice` extends `InvoiceDocument`, not `EN16931Invoice`.

See context-library/countries/br.md for the verified field-level reference
(decimal types, CNPJ/CPF formats, access-key structure, schema versions).

Field-level structure (groups `ide`, `emit`, `dest`, `det`, `total`,
`transp`, `pag`) is `[Verified locally]` against
`schemas/nfe/leiauteNFe_v4.00.xsd` (PL_010d).

IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) are
`[NEED: not yet modeled — field-level detail and mandatory date pending,
see br.md "Known gaps"]`.
"""

from __future__ import annotations

from enum import StrEnum

from mcp_einvoicing_core import InvoiceLineItem
from mcp_einvoicing_core.models import InvoiceDocument
from pydantic import BaseModel, Field, field_validator, model_validator

from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf


class NFeModelo(StrEnum):
    """Document model code (`mod` field). Source: leiauteNFe_v4.00.xsd, TMod."""

    NFE = "55"
    NFCE = "65"


class TipoOperacao(StrEnum):
    """Operation direction (`tpNF` field): 0 = entrada, 1 = saída."""

    ENTRADA = "0"
    SAIDA = "1"


class TipoAmbiente(StrEnum):
    """Identificação do Ambiente (`tpAmb`): 1 = produção, 2 = homologação."""

    PRODUCAO = "1"
    HOMOLOGACAO = "2"


class RegimeTributario(StrEnum):
    """Código de Regime Tributário (`CRT`): 1=Simples Nacional, 2=Simples
    Nacional - excesso de sublimite de receita bruta, 3=Regime Normal."""

    SIMPLES_NACIONAL = "1"
    SIMPLES_NACIONAL_EXCESSO = "2"
    REGIME_NORMAL = "3"


class BREndereco(BaseModel):
    """Endereço (Grupo `enderEmit` / `enderDest`), `TEnderEmi`/`TEndereco`.

    `c_mun` is the IBGE municipality code (`TCodMunIBGE`, 7 digits).
    Country is implicitly Brasil (cPais=1058 / xPais=BRASIL), set by the
    generator — not modeled here.
    """

    x_lgr: str = Field(..., description="Logradouro")
    nro: str = Field(..., description="Número")
    x_cpl: str | None = Field(default=None, description="Complemento")
    x_bairro: str = Field(..., description="Bairro")
    c_mun: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município")
    x_mun: str = Field(..., description="Nome do município")
    uf: str = Field(..., min_length=2, max_length=2, description="Sigla da UF")
    cep: str = Field(..., description="CEP")
    fone: str | None = Field(default=None, description="Telefone")


class BREmitente(BaseModel):
    """Emitente (Grupo `emit`).

    Exactly one of `cnpj` / `cpf` must be provided.
    """

    cnpj: str | None = Field(default=None, description="CNPJ do emitente")
    cpf: str | None = Field(default=None, description="CPF do emitente")
    x_nome: str = Field(..., description="Razão social ou nome do emitente")
    x_fant: str | None = Field(default=None, description="Nome fantasia")
    ender_emit: BREndereco = Field(..., description="Endereço do emitente")
    ie: str = Field(..., description="Inscrição Estadual")
    ie_st: str | None = Field(default=None, description="IE do Substituto Tributário")
    im: str | None = Field(default=None, description="Inscrição Municipal")
    crt: RegimeTributario = Field(..., description="Código de Regime Tributário")

    @model_validator(mode="after")
    def check_one_document(self) -> BREmitente:
        if bool(self.cnpj) == bool(self.cpf):
            raise ValueError("Emitente deve informar exatamente um de CNPJ ou CPF.")
        return self

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, v: str | None) -> str | None:
        if v is not None and not validate_cnpj(v):
            raise ValueError(f"CNPJ do emitente inválido: {v!r}")
        return v

    @field_validator("cpf")
    @classmethod
    def check_cpf(cls, v: str | None) -> str | None:
        if v is not None and not validate_cpf(v):
            raise ValueError(f"CPF do emitente inválido: {v!r}")
        return v


class BRDestinatario(BaseModel):
    """Destinatário (Grupo `dest`). Optional at the schema level (`dest`
    has `minOccurs="0"`), but emitted whenever provided.
    """

    cnpj: str | None = Field(default=None, description="CNPJ do destinatário")
    cpf: str | None = Field(default=None, description="CPF do destinatário")
    x_nome: str | None = Field(default=None, description="Razão social ou nome do destinatário")
    ender_dest: BREndereco | None = Field(default=None, description="Endereço do destinatário")
    ind_ie_dest: str = Field(
        ..., description="Indicador da IE do destinatário: 1=contribuinte ICMS, 2=isento, 9=não contribuinte"
    )
    ie: str | None = Field(default=None, description="Inscrição Estadual do destinatário")
    email: str | None = Field(default=None, description="E-mail do destinatário")

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, v: str | None) -> str | None:
        if v is not None and not validate_cnpj(v):
            raise ValueError(f"CNPJ do destinatário inválido: {v!r}")
        return v

    @field_validator("cpf")
    @classmethod
    def check_cpf(cls, v: str | None) -> str | None:
        if v is not None and not validate_cpf(v):
            raise ValueError(f"CPF do destinatário inválido: {v!r}")
        return v


class BRPagamento(BaseModel):
    """Detalhamento da forma de pagamento (Grupo `detPag`).

    `cnpj_pag` / `uf_pag` default to the emitente's CNPJ/UF in the generator
    when not provided — `[Unverified]`: NT 2025.002-RTC appears to make these
    mandatory in PL_010d; re-verify against MOC 7.0 before relying on the
    default for production submissions.
    """

    ind_pag: str | None = Field(
        default=None, description="Indicador da forma de pagamento: 0=à vista, 1=a prazo"
    )
    t_pag: str = Field(..., description="Forma de pagamento (tPag, tabela SEFAZ)")
    x_pag: str | None = Field(default=None, description="Descrição do meio de pagamento")
    v_pag: str = Field(..., description="Valor do pagamento")
    d_pag: str | None = Field(default=None, description="Data do pagamento (YYYY-MM-DD)")
    cnpj_pag: str | None = Field(default=None, description="CNPJ da credenciadora/transacional")
    uf_pag: str | None = Field(default=None, description="UF do pagamento")


class BRInvoiceLine(InvoiceLineItem):  # type: ignore[misc]
    """NF-e/NFC-e invoice line (Grupo I — Produtos e Serviços).

    Brazil has no single VAT; ``vat_rate``/``vat_exemption_code`` from
    ``InvoiceLineItem`` are not used. ICMS, IPI, PIS, and COFINS are modeled
    as separate per-line tax fields. The IBS/CBS/Imposto Seletivo fields
    introduced by NT 2025.002-RTC (Grupo UB) are `[NEED: not yet modeled —
    field-level detail pending, see br.md "Known gaps"]`.
    """

    c_prod: str = Field(..., description="Código do produto/serviço")
    c_ean: str = Field(default="SEM GTIN", description="GTIN/EAN do produto, ou 'SEM GTIN'")
    c_ean_trib: str = Field(
        default="SEM GTIN", description="GTIN/EAN tributável, ou 'SEM GTIN'"
    )
    ncm: str = Field(
        ..., min_length=8, max_length=8, description="Código NCM (Nomenclatura Comum do Mercosul)"
    )
    cest: str | None = Field(
        default=None,
        min_length=7,
        max_length=7,
        description=(
            "Código Especificador da Substituição Tributária. "
            "[Unverified — mandatory status in PL_010d not yet confirmed against MOC 7.0]"
        ),
    )
    cfop: str = Field(
        ..., min_length=4, max_length=4, description="Código Fiscal de Operações e Prestações"
    )
    u_com: str = Field(..., description="Unidade comercial")
    q_com: str = Field(..., description="Quantidade comercial")
    v_un_com: str = Field(..., description="Valor unitário de comercialização")
    v_prod: str = Field(..., description="Valor total bruto do produto")
    u_trib: str = Field(..., description="Unidade tributável")
    q_trib: str = Field(..., description="Quantidade tributável")
    v_un_trib: str = Field(..., description="Valor unitário de tributação")
    ind_tot: str = Field(
        default="1", description="Indica se o valor do item entra no total da NF-e: 0=não, 1=sim"
    )

    icms_orig: str = Field(
        default="0", description="Origem da mercadoria (Torig): 0=nacional, 1-8=estrangeira/outros"
    )
    icms_cst: str | None = Field(
        default=None,
        description=(
            "Código de Situação Tributária do ICMS (CST, regime normal) ou "
            "Código de Situação da Operação no Simples Nacional (CSOSN). "
            "Phase 1 supports CST '00' (ICMS00) and CSOSN '102' (ICMSSN102) only; "
            "other codes raise DocumentGenerationError [NEED: extend coverage]."
        ),
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
    series, access key, operation nature/direction, and the `ide`/`emit`/
    `dest`/`total`/`transp`/`pag` groups.
    """

    modelo: NFeModelo = Field(..., description="Modelo do documento fiscal: 55 (NF-e) ou 65 (NFC-e)")
    serie: str = Field(..., max_length=3, description="Série do documento fiscal")
    nnf: str = Field(..., description="Número do documento fiscal (nNF)")
    chave_acesso: str | None = Field(
        default=None,
        max_length=44,
        description=(
            "Chave de acesso (44 caracteres). Sob PL_010d (NT 2026.004, "
            "vigente a partir de 2026-07-01) o segmento do CNPJ torna-se "
            "alfanumérico — ver br.md. Se informada, é verificada (não "
            "confiada) contra os dados do documento."
        ),
    )
    natureza_operacao: str = Field(..., description="Natureza da Operação")
    tipo_operacao: TipoOperacao = Field(..., description="Tipo de Operação: 0=entrada, 1=saída")
    protocolo_autorizacao: str | None = Field(
        default=None, description="Protocolo de autorização de uso retornado pela SEFAZ"
    )

    # Grupo ide
    c_uf: str = Field(..., min_length=2, max_length=2, description="Código IBGE da UF do emitente")
    c_nf: str | None = Field(
        default=None,
        min_length=8,
        max_length=8,
        description="Código numérico aleatório (cNF). Gerado automaticamente se omitido.",
    )
    dh_emi: str = Field(..., description="Data e hora de emissão, com fuso horário (ISO 8601)")
    id_dest: str = Field(
        ..., description="Identificador de local de destino: 1=interna, 2=interestadual, 3=exterior"
    )
    c_mun_fg: str = Field(
        ..., min_length=7, max_length=7, description="Código IBGE do município do fato gerador"
    )
    tp_imp: str = Field(default="1", description="Formato de impressão do DANFE (tpImp)")
    tp_emis: str = Field(default="1", description="Forma de emissão (tpEmis): 1=normal")
    tp_amb: TipoAmbiente = Field(..., description="Identificação do Ambiente: 1=produção, 2=homologação")
    fin_nfe: str = Field(default="1", description="Finalidade de emissão: 1=normal")
    ind_final: str = Field(..., description="Indica operação com consumidor final: 0=não, 1=sim")
    ind_pres: str = Field(..., description="Indicador de presença do comprador no estabelecimento")
    proc_emi: str = Field(default="0", description="Processo de emissão: 0=aplicativo do contribuinte")
    ver_proc: str = Field(default="mcp-nfe-br", description="Versão do processo de emissão")

    # Grupo emit / dest
    emitente: BREmitente = Field(..., description="Dados do emitente (Grupo emit)")
    destinatario: BRDestinatario | None = Field(
        default=None, description="Dados do destinatário (Grupo dest)"
    )

    # Grupo transp / pag
    mod_frete: str = Field(
        default="9", description="Modalidade do frete (modFrete): 9=sem frete"
    )
    pagamentos: list[BRPagamento] = Field(
        ..., min_length=1, description="Formas de pagamento (Grupo pag/detPag)"
    )

    lines: list[BRInvoiceLine] = Field(default_factory=list, min_length=1)  # type: ignore[assignment]

    @model_validator(mode="after")
    def check_modelo_requirements(self) -> BRInvoice:
        if self.modelo == NFeModelo.NFCE and not self.pagamentos:
            raise ValueError("NFC-e (modelo 65) requer ao menos um elemento <detPag>.")
        return self
