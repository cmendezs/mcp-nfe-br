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

IBS/CBS/Imposto Seletivo (Grupo UB/W03, NT 2025.002-RTC) item-level
(`BRGrupoImpostoSeletivo`/`BRGrupoIBSCBS`) and document-level
(`BRGrupoIBSCBSTot`) field groups are modeled as `Optional` per
`[Verified locally]` against `NT_2025.002_v1.50_RTC_NF-e_IBS_CBS_IS.pdf`.
Several monofásico/diferimento/devolução/redução/Suframa subgroups remain
`[NEED: not yet modeled, see br.md "Known gaps"]`, and the mandatory-validation
activation date (rule UB12-10) is `[NEED: still "Implementação futura" with no
concrete date as of NT 2025.002 v1.50 — do not hardcode]`.
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


class BRGrupoImpostoSeletivo(BaseModel):
    """Imposto Seletivo (Grupo UB, subgrupo IS — UB01-UB11), item-level.

    `[Verified locally]` field set against
    ``NT_2025.002_v1.50_RTC_NF-e_IBS_CBS_IS.pdf`` (table "Grupo UB", #324.01-324.11).
    Activation: `[NEED: rule UB12-10 ("Não informado grupo de imposto IBS e
    CBS") is listed in v1.50 as "Implementação futura" with no concrete date
    after multiple revisions (v1.30-v1.40) — do not hardcode a mandatory date]`.
    """

    cst_is: str | None = Field(
        default=None, description="Código de Situação Tributária do Imposto Seletivo (UB02)"
    )
    c_class_trib_is: str | None = Field(
        default=None, description="Código de Classificação Tributária do Imposto Seletivo (UB03)"
    )
    v_bc_is: str | None = Field(
        default=None, description="Valor da Base de Cálculo do Imposto Seletivo (UB05)"
    )
    p_is: str | None = Field(default=None, description="Alíquota do Imposto Seletivo, % (UB06)")
    p_is_espec: str | None = Field(
        default=None,
        description="Alíquota específica por unidade de medida apropriada, % (UB07)",
    )
    v_is: str | None = Field(default=None, description="Valor do Imposto Seletivo (UB11)")


class BRGrupoIBSUF(BaseModel):
    """IBS de competência da UF (Grupo UB, subgrupo gIBSUF — UB17-UB35).

    Only the rate/value pair is modeled; `gDif` (diferimento), `gDevTrib`
    (devolução de tributos) and `gRed` (redução de alíquota) subgroups are
    `[NEED: not modeled — out of scope for v0.3.0, see br.md "Known gaps"]`.
    """

    p_ibs_uf: str | None = Field(
        default=None, description="Alíquota do IBS de competência da UF, % (UB18)"
    )
    v_ibs_uf: str | None = Field(
        default=None, description="Valor do IBS de competência da UF (UB35)"
    )


class BRGrupoIBSMun(BaseModel):
    """IBS de competência do Município (Grupo UB, subgrupo gIBSMun — UB36-UB54).

    Only the rate/value pair is modeled; `gDif`, `gDevTrib` and `gRed`
    subgroups are `[NEED: not modeled — out of scope for v0.3.0, see br.md
    "Known gaps"]`.
    """

    p_ibs_mun: str | None = Field(
        default=None, description="Alíquota do IBS de competência do Município, % (UB37)"
    )
    v_ibs_mun: str | None = Field(
        default=None, description="Valor do IBS de competência do Município (UB54)"
    )


class BRGrupoCBS(BaseModel):
    """CBS (Grupo UB, subgrupo gCBS — UB55-UB67).

    Only the rate/value pair is modeled; `gDif`, `gDevTrib`, `gRed` and
    `gALCZFMCBS` subgroups are `[NEED: not modeled — out of scope for v0.3.0,
    see br.md "Known gaps"]`.
    """

    p_cbs: str | None = Field(default=None, description="Alíquota da CBS, % (UB56)")
    v_cbs: str | None = Field(default=None, description="Valor da CBS (UB67)")


class BRGrupoIBSCBS(BaseModel):
    """IBS/CBS (Grupo UB, subgrupo IBSCBS — UB12-UB67), item-level.

    `[Verified locally]` field set against
    ``NT_2025.002_v1.50_RTC_NF-e_IBS_CBS_IS.pdf`` (table "Grupo UB", #324.12-324.67).
    The `gTribRegular`, `gCompraGov`, `gMonoAdValorem`/monofásico, and
    `gEstornoCred` subgroups are `[NEED: not modeled — out of scope for
    v0.3.0, see br.md "Known gaps"]`.
    """

    cst: str | None = Field(
        default=None, description="Código de Situação Tributária do IBS e CBS (UB13)"
    )
    c_class_trib: str | None = Field(
        default=None, description="Código de Classificação Tributária do IBS e CBS (UB14)"
    )
    ind_doacao: str | None = Field(
        default=None,
        description="Indicador de natureza de operação de doação: '1' quando doação (UB14a)",
    )
    v_bc: str | None = Field(default=None, description="Base de cálculo do IBS e CBS (UB16)")
    ibs_uf: BRGrupoIBSUF | None = Field(
        default=None, description="Grupo de informações do IBS para a UF (UB17)"
    )
    ibs_mun: BRGrupoIBSMun | None = Field(
        default=None, description="Grupo de informações do IBS para o município (UB36)"
    )
    v_ibs: str | None = Field(
        default=None,
        description="Valor do IBS, soma de vIBSUF e vIBSMun (UB54a)",
    )
    cbs: BRGrupoCBS | None = Field(
        default=None, description="Grupo de informações da CBS (UB55)"
    )


class BRGrupoIBSUFTot(BaseModel):
    """Totais do IBS da UF (Grupo W03, subgrupo gIBSUF — W37-W41), document-level."""

    v_dif: str | None = Field(
        default=None, description="Valor total do diferimento do IBS UF (W38)"
    )
    v_dev_trib: str | None = Field(
        default=None, description="Valor total de devolução de tributos do IBS UF (W39)"
    )
    v_ibs_uf: str | None = Field(default=None, description="Valor total do IBS da UF (W41)")


class BRGrupoIBSMunTot(BaseModel):
    """Totais do IBS do Município (Grupo W03, subgrupo gIBSMun — W42-W46), document-level."""

    v_dif: str | None = Field(
        default=None, description="Valor total do diferimento do IBS Municipal (W43)"
    )
    v_dev_trib: str | None = Field(
        default=None, description="Valor total de devolução de tributos do IBS Municipal (W44)"
    )
    v_ibs_mun: str | None = Field(
        default=None, description="Valor total do IBS do Município (W46)"
    )


class BRGrupoIBSTot(BaseModel):
    """Totais do IBS (Grupo W03, subgrupo gIBS — W36-W49), document-level.

    `gMono` (monofasia) and `gEstornoCred` totals subgroups are `[NEED: not
    modeled — out of scope for v0.3.0, see br.md "Known gaps"]`.
    """

    ibs_uf: BRGrupoIBSUFTot | None = Field(
        default=None, description="Grupo total do IBS da UF (W37)"
    )
    ibs_mun: BRGrupoIBSMunTot | None = Field(
        default=None, description="Grupo total do IBS do Município (W42)"
    )
    v_ibs: str | None = Field(default=None, description="Valor total do IBS (W47)")
    v_cred_pres: str | None = Field(
        default=None, description="Valor total do crédito presumido do IBS (W48)"
    )
    v_cred_pres_cond_sus: str | None = Field(
        default=None,
        description="Valor total do crédito presumido do IBS em condição suspensiva (W49)",
    )


class BRGrupoCBSTot(BaseModel):
    """Totais da CBS (Grupo W03, subgrupo gCBS — W50-W56b), document-level."""

    v_dif: str | None = Field(default=None, description="Valor total do diferimento da CBS (W53)")
    v_dev_trib: str | None = Field(
        default=None, description="Valor total de devolução de tributos da CBS (W54)"
    )
    v_cbs: str | None = Field(default=None, description="Valor total da CBS (W56)")
    v_cred_pres: str | None = Field(
        default=None, description="Valor total do crédito presumido da CBS (W56a)"
    )
    v_cred_pres_cond_sus: str | None = Field(
        default=None,
        description="Valor total do crédito presumido da CBS em condição suspensiva (W56b)",
    )


class BRGrupoIBSCBSTot(BaseModel):
    """Totais da NF-e com IBS e CBS (Grupo W03, subgrupo IBSCBSTot — W34-W49), document-level.

    `[Verified locally]` field set against
    ``NT_2025.002_v1.50_RTC_NF-e_IBS_CBS_IS.pdf`` (table "Grupo W03", #355.4-355.19).
    """

    v_bc_ibscbs: str | None = Field(
        default=None, description="Valor total da BC do IBS e da CBS (W35)"
    )
    ibs: BRGrupoIBSTot | None = Field(default=None, description="Grupo total do IBS (W36)")
    cbs: BRGrupoCBSTot | None = Field(default=None, description="Grupo total da CBS (W50)")


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
            "v0.3.0 supports CST '00'/'10'/'20'/'30'/'40'/'41'/'50'/'51'/'60'/'70'/'90' "
            "and CSOSN '101'/'102'/'103'/'201'/'202'/'203'/'300'/'500'/'900'; other "
            "codes raise DocumentGenerationError [NEED: extend coverage]."
        ),
    )
    icms_rate: str | None = Field(default=None, description="Alíquota do ICMS (%)")
    icms_amount: str | None = Field(default=None, description="Valor do ICMS")
    icms_mod_bc: str | None = Field(
        default=None,
        description=(
            "Modalidade de determinação da BC do ICMS (modBC): 0=MVA, 1=Pauta, "
            "2=Preço Tabelado, 3=Valor da Operação. Padrão '3' quando omitido."
        ),
    )
    icms_p_red_bc: str | None = Field(
        default=None,
        description="Percentual de redução da BC do ICMS (pRedBC) — CST 20/51/70.",
    )
    icms_mod_bc_st: str | None = Field(
        default=None,
        description=(
            "Modalidade de determinação da BC do ICMS ST (modBCST): 0=Preço "
            "tabelado, 1-3=Lista, 4=MVA, 5=Pauta, 6=Valor da operação. "
            "Padrão '4' (MVA) quando omitido `[Unverified]`."
        ),
    )
    icms_p_mva_st: str | None = Field(
        default=None,
        description="Percentual da Margem de Valor Agregado do ICMS ST (pMVAST).",
    )
    icms_p_red_bc_st: str | None = Field(
        default=None,
        description="Percentual de redução da BC do ICMS ST (pRedBCST).",
    )
    icms_v_bc_st: str | None = Field(
        default=None, description="Valor da BC do ICMS ST (vBCST)."
    )
    icms_p_icms_st: str | None = Field(
        default=None, description="Alíquota do ICMS ST (pICMSST)."
    )
    icms_v_icms_st: str | None = Field(
        default=None, description="Valor do ICMS ST (vICMSST)."
    )
    icms_v_bc_st_ret: str | None = Field(
        default=None,
        description=(
            "Valor da BC do ICMS ST retido anteriormente (vBCSTRet) — "
            "CST 60 / CSOSN 500."
        ),
    )
    icms_p_st: str | None = Field(
        default=None,
        description=(
            "Alíquota suportada pelo consumidor final (pST) — CST 60 / CSOSN 500."
        ),
    )
    icms_v_icms_subst: str | None = Field(
        default=None,
        description=(
            "Valor do ICMS próprio do substituto cobrado em operação anterior "
            "(vICMSSubstituto) — CST 60 / CSOSN 500."
        ),
    )
    icms_v_icms_st_ret: str | None = Field(
        default=None,
        description=(
            "Valor do ICMS ST retido anteriormente (vICMSSTRet) — CST 60 / CSOSN 500."
        ),
    )
    icms_p_cred_sn: str | None = Field(
        default=None,
        description=(
            "Alíquota aplicável de cálculo do crédito do Simples Nacional "
            "(pCredSN) — CSOSN 101/201."
        ),
    )
    icms_v_cred_icms_sn: str | None = Field(
        default=None,
        description=(
            "Valor do crédito do ICMS do Simples Nacional (vCredICMSSN) — "
            "CSOSN 101/201."
        ),
    )
    ipi_cst: str | None = Field(default=None, description="Código de Situação Tributária do IPI")
    ipi_rate: str | None = Field(default=None, description="Alíquota do IPI (%)")
    ipi_amount: str | None = Field(default=None, description="Valor do IPI")
    pis_cst: str | None = Field(default=None, description="Código de Situação Tributária do PIS")
    pis_amount: str | None = Field(default=None, description="Valor do PIS")
    cofins_cst: str | None = Field(
        default=None, description="Código de Situação Tributária do COFINS"
    )
    cofins_amount: str | None = Field(default=None, description="Valor do COFINS")

    imposto_seletivo: BRGrupoImpostoSeletivo | None = Field(
        default=None, description="Informações do Imposto Seletivo (Grupo UB, subgrupo IS)"
    )
    ibs_cbs: BRGrupoIBSCBS | None = Field(
        default=None,
        description="Informações do IBS e da CBS (Grupo UB, subgrupo IBSCBS)",
    )


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
        min_length=44,
        max_length=44,
        description=(
            "Chave de acesso (44 caracteres). Sob PL_010d (NT 2026.004, "
            "vigente a partir de 2026-07-01) o segmento do CNPJ torna-se "
            "alfanumérico — ver br.md. Se informada, é verificada (não "
            "confiada) contra os dados do documento."
        ),
    )

    @field_validator("chave_acesso", mode="after")
    @classmethod
    def check_chave_acesso_format(cls, v: str | None) -> str | None:
        import re

        if v is None:
            return v
        # PL_010d structure: 6 digits (cUF+AAMM) + 14 alphanumeric uppercase (CNPJ) +
        # 24 digits (mod+serie+nNF+tpEmis+cNF+cDV).
        # [Unverified — element names per NT 2026.004 v1.01; verify before 2026-07-01 cutover]
        chave_re = re.compile(r"^[0-9]{6}[0-9A-Z]{14}[0-9]{24}$")
        if not chave_re.match(v):
            raise ValueError(
                f"Chave de acesso fora do formato PL_010d (6 dígitos + 14 CNPJ alfanumérico "
                f"+ 24 dígitos): {v!r}"
            )
        return v
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

    # Grupo W03 — Total da NF-e com IBS / CBS / IS (NT 2025.002-RTC)
    v_is_tot: str | None = Field(
        default=None, description="Total do Imposto Seletivo, soma dos vIS dos itens (W33)"
    )
    ibscbs_tot: BRGrupoIBSCBSTot | None = Field(
        default=None, description="Totais da NF-e com IBS e CBS (W34)"
    )
    v_nf_tot: str | None = Field(
        default=None,
        description=(
            "Valor total da NF-e considerando os impostos por fora IBS, CBS e "
            "IS (W60). `[NEED: rule W60-05/W60-10 listed as 'Implementação "
            "futura' in NT 2025.002 v1.50 — do not treat as mandatory]`."
        ),
    )

    @model_validator(mode="after")
    def check_modelo_requirements(self) -> BRInvoice:
        if self.modelo == NFeModelo.NFCE and not self.pagamentos:
            raise ValueError("NFC-e (modelo 65) requer ao menos um elemento <detPag>.")
        return self
