"""CT-e (Conhecimento de Transporte Eletrônico, modelo 57) models.

CT-e is a SEFAZ-cleared XML transport document, structurally a near-twin of
NF-e at the transport layer (SOAP over ICP-Brasil mTLS, 44-char access key,
enveloped XML-DSig) but with its own root (`<CTe><infCte>`), namespace, party
set, and per-modal sub-schemas. Like NF-e, CT-e predates and is unrelated to
EN 16931 — `BRCTeDocument` extends `InvoiceDocument`, not `EN16931Invoice`.

Field-level structure is `[Verified locally]` against the bundled schema
package `specs/cte/PL_CTe_400.zip` (schema 4.00, namespace
`http://www.portalfiscal.inf.br/cte`) — see
`schemas/cte/cte_v4.00.xsd`, `schemas/cte/cteTiposBasico_v4.00.xsd`,
`schemas/cte/tiposGeralCTe_v4.00.xsd`. See the package's own compliance
reference, CT-e section, for the full field-level reference and outstanding
`[NEED: verify]` markers.

Scope for this v1 model (roadmap BR-CTE-2..4, extended during BR-CTE-8/9 to
cover mandatory groups discovered while building the generator): modelo 57
only (CT-e OS, modelo 67, deferred — BR-CTE-18), `tpCTe` limited to
`0`/`1`/`3` (Normal / Complemento de Valores / Substituição — no `Anulação`
value found in the bundled XSD enum, so `infCTeAnu` is not modeled; see
br.md CT-e section). `imp/ICMS` only models CST 00 (tributação normal);
`infModal` only models rodoviário (`rntrc`) — both mirror how
`nfe_generator.py` started narrow and grew coverage across versions. Other
modais' payloads and other ICMS CSTs are `[NEED: not modeled]`.

Impedance points (per CT-e scoping plan, resolved here):
- `InvoiceDocument.buyer` has no CT-e equivalent — left unset. The paying
  party is designated by the `tomador` role instead (`BRCteTomador`).
- CT-e has no goods lines. `vPrest.comp` (freight-value components) is
  modeled as `list[BRCteVPrestComp]` on `BRCTeVPrest`, not as `lines`;
  `BRCTeDocument.lines` stays empty by design. Future audit CHECK 8 must
  exempt CT-e from the base contract's non-empty-`lines` rule.

Reforma Tributária do Consumo (RTC) — NT 2026.002, closes GitHub issue
cmendezs/mcp-nfe-br#5. `imp/IBSCBS` (full `TCIBS` tree), `emit/ISUFEmit`,
and `ide/tpPagAnt`+`gPagAntecipado` are `[Verified locally]` against
`specs/cte/CTe_Nota_Tecnica_2026_002 v1.01.pdf` (business rules) and the
`PL_CTe_400_NT2026.002 RTC_1.00.zip` schema package (structure — the NT
v1.01 only changed the Produção enforcement date, not the fields, so the
v1.00 schema stays authoritative). Self-contained NT business rules (RV
4.001, 5.001-003, 6.003, 6.004, 6.005, 7.001/002/010/011 — geographic
ZFM/ALC checks, devolução-forbidden-for-CT-e, antecipação-pagamento
self-consistency and CNPJ-Base match) are enforced as `model_validator`s on
`BRCTeDocument`. Deliberately **not** implemented:
- RV 6.001/002 (CBS rate must be 0.90% for 2026, with exceptions) —
  `[NEED: cClassTrib "indicador de tributação regular" table, not supplied,
  required to determine the exception cases]`.
- RV 7.003-009 (antecipação-pagamento cross-document checks: key exists,
  situação autorizada, not cancelled/substituído, tpPagAnt=1 on the
  referenced document) — `[NEED: requires a live SEFAZ "Acesso BD CTe"
  lookup; inherently unavailable to a stateless local validator]`.
- Suframa digit-verifier (RV 4.002) — `[NEED: check-digit algorithm not
  published in the NT]`.

Also discovered while diffing the schema package, but explicitly **out of
scope** for this change (different Notas Técnicas, not NT 2026.002):
a new `TCTeSimp` document type and a `pgtoVinc`/`TPagamentoRTC` group both
belong to NT 2026.001 ("VincPgto") and remain unimplemented.

The CT-e access-key type (`TChDFe`) also changed schema-wide (same
`PL_CTe_400_NT2026.002` package) from `[0-9]{44}` to
`[0-9]{6}[A-Z0-9]{12}[0-9]{26}` (alphanumeric-CNPJ-ready). As of BR-CTE-23
this pattern is applied to `chave_acesso`'s validator, `build_cte_access_key`,
and the `pag_antecipado` field alike, matching `TChDFe` in the bundled
schema. See the package's own compliance reference, CT-e section, for tracking.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

from mcp_einvoicing_core.models import InvoiceDocument, InvoiceParty
from pydantic import BaseModel, Field, field_validator, model_validator

from mcp_nfe_br.models.invoice import BREndereco, RegimeTributario
from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf


class CTeModelo(StrEnum):
    """Document model code (`mod` field), `TModCT`. Fixed to `"57"` — the
    XSD enum has only one value. Modelo 67 (CT-e OS) uses a separate root
    schema (`TModCTOS`) and is out of scope for this model (BR-CTE-18)."""

    CTE = "57"


class CTeTipoServico(StrEnum):
    """Tipo do Serviço (`tpServ`): 0=Normal, 1=Subcontratação,
    2=Redespacho, 3=Redespacho Intermediário, 4=Serviço Vinculado a
    Multimodal, 5=Transporte de Valores (GTV-e), 6=CT-e de Concessionária de
    Rodovias (Vale-Pedágio). `[Verified locally]` — `cteTiposBasico_v4.00.xsd`."""

    NORMAL = "0"
    SUBCONTRATACAO = "1"
    REDESPACHO = "2"
    REDESPACHO_INTERMEDIARIO = "3"
    SERVICO_VINCULADO_MULTIMODAL = "4"
    TRANSPORTE_VALORES = "5"
    CONCESSIONARIA_RODOVIAS = "6"


class CTeFinalidade(StrEnum):
    """Tipo do CT-e (`tpCTe`, `TFinCTe`): 0=Normal, 1=Complemento de
    Valores, 3=Substituição. No `Anulação` value found in the bundled XSD
    enum — `[NEED: verify — see br.md CT-e section]`."""

    NORMAL = "0"
    COMPLEMENTO_VALORES = "1"
    SUBSTITUICAO = "3"


class CTeModal(StrEnum):
    """Modal (`modal`, `TModTransp`): 01-06. `[Verified locally]` —
    `cteTiposBasico_v4.00.xsd`."""

    RODOVIARIO = "01"
    AEREO = "02"
    AQUAVIARIO = "03"
    FERROVIARIO = "04"
    DUTOVIARIO = "05"
    MULTIMODAL = "06"


class CTeTomadorPapel(StrEnum):
    """Tomador do Serviço (`toma`, used within `toma3`): 0=Remetente,
    1=Expedidor, 2=Recebedor, 3=Destinatário — reuses the data of one of the
    four party groups. `toma4` ("outros") is modeled separately as
    `BRCteTomador` with its own full party data."""

    REMETENTE = "0"
    EXPEDIDOR = "1"
    RECEBEDOR = "2"
    DESTINATARIO = "3"


class BRCteParty(BaseModel):
    """Shared shape for CT-e party groups (`emit`, `rem`, `exped`, `receb`,
    `dest`). Exactly one of `cnpj` / `cpf` must be provided, mirroring
    `BREmitente`/`BRDestinatario` in `invoice.py` — kept as a separate class
    per the scoping plan (CT-e has national-fields that do not translate,
    e.g. no `crt`)."""

    cnpj: str | None = Field(default=None, description="CNPJ da parte")
    cpf: str | None = Field(default=None, description="CPF da parte")
    x_nome: str = Field(..., description="Razão social ou nome da parte")
    ie: str | None = Field(default=None, description="Inscrição Estadual")
    endereco: BREndereco = Field(..., description="Endereço da parte")
    email: str | None = Field(default=None, description="E-mail da parte")
    fone: str | None = Field(default=None, description="Telefone da parte")

    @model_validator(mode="after")
    def check_one_document(self) -> BRCteParty:
        if bool(self.cnpj) == bool(self.cpf):
            raise ValueError("Parte do CT-e deve informar exatamente um de CNPJ ou CPF.")
        return self

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, v: str | None) -> str | None:
        """Reject alphanumeric CNPJ (BR-CTE-T1, decided).

        The bundled CT-e v4.00 schema (`tiposGeralCTe_v4.00.xsd:133`) defines
        `TCnpj` as `[0-9]{14}` (all-numeric) — unlike the NF-e schema package
        (PL_010d), which was updated for the alphanumeric CNPJ form. Accepting
        an alphanumeric CNPJ here would only defer the failure to XSD
        validation at `CTeGenerator.generate()`, after the model has already
        validated cleanly. `[NEED: verify — no CT-e-specific Nota Técnica
        confirming alphanumeric-CNPJ applicability to CT-e has been found;
        see utils/cte_access_key.py]`
        """
        if v is None:
            return v
        digits_only = v.replace(".", "").replace("/", "").replace("-", "")
        if not digits_only.isdigit():
            raise ValueError(
                "CT-e requer CNPJ numérico de 14 dígitos; CNPJ alfanumérico "
                f"ainda não suportado pelo schema PL_CTe_400 (recebido {v!r})."
            )
        if not validate_cnpj(v):
            raise ValueError(f"CNPJ inválido: {v!r}")
        return v

    @field_validator("cpf")
    @classmethod
    def check_cpf(cls, v: str | None) -> str | None:
        if v is not None and not validate_cpf(v):
            raise ValueError(f"CPF inválido: {v!r}")
        return v


class BRCteEmitente(BRCteParty):
    """Emitente (Grupo `emit`) — the transport company issuing the CT-e.

    Unlike the other CT-e party groups, `emit` has a mandatory `CRT`
    (Código de Regime Tributário) — reuses `RegimeTributario` from
    `invoice.py`, same enum values as NF-e's `emit/CRT`.
    """

    im: str | None = Field(default=None, description="Inscrição Municipal")
    crt: RegimeTributario = Field(..., description="Código de Regime Tributário")
    isuf_emit: str | None = Field(
        default=None,
        min_length=8,
        max_length=9,
        description=(
            "Inscrição do emitente na Suframa (emit/ISUFEmit). Obrigatório nas operações "
            "que se beneficiam de incentivos fiscais nas áreas sob controle da Suframa com "
            "alíquota zero da CBS (arts. 451 e 466 da LC 214/25). "
            "`[Verified locally]` — cteTiposBasico_v4.00.xsd (NT 2026.002 v1.01)."
        ),
    )


class BRCteRemetente(BRCteParty):
    """Remetente (Grupo `rem`) — the party shipping the goods."""


class BRCteExpedidor(BRCteParty):
    """Expedidor (Grupo `exped`, `minOccurs=0`) — the party that physically
    hands the goods to the carrier, when different from the remetente."""


class BRCteRecebedor(BRCteParty):
    """Recebedor (Grupo `receb`, `minOccurs=0`) — the party that physically
    receives the goods, when different from the destinatário."""


class BRCteDestinatario(BRCteParty):
    """Destinatário (Grupo `dest`, `minOccurs=0`)."""


class BRCteTomador(BaseModel):
    """Tomador do Serviço (`toma3`/`toma4` choice).

    `papel` selects one of the four existing party roles (`toma3`); when the
    tomador is a distinct fifth party ("outros", `toma4`), `outros` carries
    its own full party data instead. Exactly one of `papel` / `outros` must
    be set.
    """

    papel: CTeTomadorPapel | None = Field(
        default=None, description="Papel do tomador (toma3): reaproveita um dos 4 grupos de parte"
    )
    outros: BRCteParty | None = Field(
        default=None, description="Tomador 'outros' (toma4), com CNPJ/CPF próprio"
    )
    ind_ie_toma: str = Field(
        ...,
        description="Indicador do papel do tomador na prestação: 1=contribuinte ICMS, 2=isento, 9=não contribuinte",
    )

    @model_validator(mode="after")
    def check_one_choice(self) -> BRCteTomador:
        if bool(self.papel) == bool(self.outros):
            raise ValueError(
                "Tomador deve informar exatamente um de `papel` (toma3) ou `outros` (toma4)."
            )
        return self


class BRCteVPrestComp(BaseModel):
    """Componente do Valor da Prestação (Grupo `vPrest`, subgrupo `Comp`).

    CT-e has no goods lines; freight-value components are the closest
    analog and are modeled here rather than forced into `InvoiceDocument.lines`
    — see module docstring "Impedance points"."""

    x_nome: str = Field(..., description="Nome do componente")
    v_comp: str = Field(..., description="Valor do componente")


class BRCteVPrest(BaseModel):
    """Valores da Prestação de Serviço (Grupo `vPrest`)."""

    v_tprest: str = Field(..., description="Valor Total da Prestação do Serviço")
    v_rec: str = Field(..., description="Valor a Receber")
    comp: list[BRCteVPrestComp] = Field(
        default_factory=list, description="Componentes do valor da prestação"
    )


class BRCteInfModal(BaseModel):
    """Informações do Modal (Grupo `infModal`).

    `infModal` is `<xs:any processContents="skip">` in the main CT-e schema
    (`cteTiposBasico_v4.00.xsd` line ~3179) — the modal-specific payload is
    validated by a *separate* modal XSD, not by `cte_v4.00.xsd` itself. Only
    rodoviário (`rntrc`, the mandatory RNTRC registration number) is
    modeled for v1 — matches the "single-modal-first" scoping decision.
    Other modais' payloads are `[NEED: not modeled — see roadmap BR-CTE-18/19
    equivalents for CT-e's own modal backlog]`.
    """

    modal: CTeModal = Field(..., description="Modal do transporte")
    versao_modal: str = Field(
        default="4.00", description="Versão do leiaute específico do modal (versaoModal)"
    )
    rntrc: str | None = Field(
        default=None,
        description="Registro Nacional de Transportadores Rodoviários de Carga — mandatory for modal rodoviário.",
    )

    @model_validator(mode="after")
    def check_rodoviario_requires_rntrc(self) -> BRCteInfModal:
        if self.modal == CTeModal.RODOVIARIO and not self.rntrc:
            raise ValueError("Modal rodoviário requer RNTRC (inf_modal.rntrc).")
        return self


class BRCteICMS00(BaseModel):
    """ICMS00 (Grupo `imp/ICMS`, CST 00 — tributação normal).

    Only CST 00 is modeled for v1, mirroring how `nfe_generator.py` started
    with a single ICMS CST and grew coverage across versions. Other CT-e
    ICMS variants (ICMS20/45/60/90, ICMSOutraUF, ICMSSN) are
    `[NEED: not modeled — extend in a follow-up BR-CTE item]`.
    """

    cst: str = Field(
        default="00", description="Classificação Tributária do Serviço: 00 = tributação normal"
    )
    v_bc: str = Field(..., description="Valor da BC do ICMS")
    p_icms: str = Field(..., description="Alíquota do ICMS")
    v_icms: str = Field(..., description="Valor do ICMS")


class BRCteDif(BaseModel):
    """Diferimento (`TDif`) — used inside `gIBSUF`/`gIBSMun`/`gCBS`.

    `[Verified locally]` against `DFeTiposBasicos_v1.00.xsd` from the
    NT 2026.002 v1.00 schema package (`PL_CTe_400_NT2026.002 RTC_1.00.zip`),
    supplied 2026-08-17.
    """

    p_dif: str = Field(..., description="Percentual do diferimento (pDif)")
    v_dif: str = Field(..., description="Valor do diferimento (vDif)")


class BRCteDevTrib(BaseModel):
    """Devolução de tributos (`TDevTrib`).

    NT 2026.002 RV 5.001-003: this group is **never valid for CT-e** — it is
    only accepted on NF3e/NFCom/NFAg/NFGas. Modeled here only because the
    shared `TCIBS` type exposes it on every document kind; see
    `BRCTeDocument.check_no_devolucao_for_cte`, which rejects it if set.
    """

    p_dev_trib: str | None = Field(
        default=None, description="Percentual de devolução do tributo (pDevTrib)"
    )
    v_dev_trib: str = Field(..., description="Valor do tributo devolvido (vDevTrib)")


class BRCteRed(BaseModel):
    """Redução de alíquota (`TRed`)."""

    p_red_aliq: str = Field(
        ..., description="Percentual de redução de alíquota do cClassTrib (pRedAliq)"
    )
    p_aliq_efet: str = Field(
        ..., description="Alíquota efetiva aplicada à base de cálculo (pAliqEfet)"
    )


class BRCteALCZFMCBS(BaseModel):
    """Operações em áreas incentivadas com CBS zero (`TALCZFMCBS`, `gCBS/gALCZFMCBS`)."""

    p_aliq_efet_reg_cbs: str = Field(
        ...,
        description="Alíquota efetiva de referência da CBS fora de áreas/regimes incentivados (pAliqEfetRegCBS)",
    )
    v_trib_reg_cbs: str = Field(
        ...,
        description="Valor da CBS calculado para a operação fora de áreas/regimes incentivados (vTribRegCBS)",
    )


class BRCteEstornoCred(BaseModel):
    """Estorno de crédito (`TEstornoCred`, `imp/IBSCBS/gEstornoCred`)."""

    v_ibs_est_cred: str = Field(..., description="Valor do IBS a ser estornado (vIBSEstCred)")
    v_cbs_est_cred: str = Field(..., description="Valor da CBS a ser estornado (vCBSEstCred)")


class BRCteTribRegular(BaseModel):
    """Tributação Regular (`TTribRegular`, `imp/IBSCBS/gIBSCBS/gTribRegular`).

    Informs how the operation would be taxed if a resolutory/suspensive
    condition were not met (e.g. ZFM/ALC operations under Art. 442 §4)."""

    cst_reg: str = Field(
        ..., description="CST do IBS/CBS caso não cumprida a condição resolutória/suspensiva"
    )
    c_class_trib_reg: str = Field(
        ..., description="cClassTrib caso não cumprida a condição resolutória/suspensiva"
    )
    p_aliq_efet_reg_ibsuf: str = Field(
        ..., description="Alíquota efetiva do IBS da UF nesse cenário"
    )
    v_trib_reg_ibsuf: str = Field(..., description="Valor do IBS da UF nesse cenário")
    p_aliq_efet_reg_ibsmun: str = Field(
        ..., description="Alíquota efetiva do IBS do Município nesse cenário"
    )
    v_trib_reg_ibsmun: str = Field(..., description="Valor do IBS do Município nesse cenário")
    p_aliq_efet_reg_cbs: str = Field(..., description="Alíquota efetiva da CBS nesse cenário")
    v_trib_reg_cbs: str = Field(..., description="Valor da CBS nesse cenário")


class BRCteTribCompraGov(BaseModel):
    """Tributação em Compra Governamental (`TTribCompraGov`, `imp/IBSCBS/gIBSCBS/gTribCompraGov`)."""

    p_aliq_ibsuf: str = Field(..., description="Alíquota IBS da UF utilizada")
    v_trib_ibsuf: str = Field(
        ..., description="Valor do Tributo do IBS da UF, sem aplicação do Art. 473 da LC 214/25"
    )
    p_aliq_ibsmun: str = Field(..., description="Alíquota IBS do Município utilizada")
    v_trib_ibsmun: str = Field(
        ...,
        description="Valor do Tributo do IBS do Município, sem aplicação do Art. 473 da LC 214/25",
    )
    p_aliq_cbs: str = Field(..., description="Alíquota CBS utilizada")
    v_trib_cbs: str = Field(
        ..., description="Valor do Tributo da CBS, sem aplicação do Art. 473 da LC 214/25"
    )


class BRCteIBSUF(BaseModel):
    """Grupo do IBS de competência da UF (`imp/IBSCBS/gIBSCBS/gIBSUF`)."""

    p_ibsuf: str = Field(
        ..., description="Alíquota do IBS de competência da UF, em percentual (pIBSUF)"
    )
    g_dif: BRCteDif | None = Field(
        default=None, description="Grupo de campos do diferimento (gDif)"
    )
    g_dev_trib: BRCteDevTrib | None = Field(
        default=None,
        description="Grupo de devolução de tributos (gDevTrib) — sempre rejeitado para CT-e",
    )
    g_red: BRCteRed | None = Field(
        default=None, description="Grupo de campos da redução de alíquota (gRed)"
    )
    v_ibsuf: str = Field(..., description="Valor do IBS de competência da UF (vIBSUF)")


class BRCteIBSMun(BaseModel):
    """Grupo do IBS de competência do Município (`imp/IBSCBS/gIBSCBS/gIBSMun`)."""

    p_ibsmun: str = Field(..., description="Alíquota do IBS Municipal, em percentual (pIBSMun)")
    g_dif: BRCteDif | None = Field(
        default=None, description="Grupo de campos do diferimento (gDif)"
    )
    g_dev_trib: BRCteDevTrib | None = Field(
        default=None,
        description="Grupo de devolução de tributos (gDevTrib) — sempre rejeitado para CT-e",
    )
    g_red: BRCteRed | None = Field(
        default=None, description="Grupo de campos da redução de alíquota (gRed)"
    )
    v_ibsmun: str = Field(..., description="Valor do IBS Municipal (vIBSMun)")


class BRCteCBS(BaseModel):
    """Grupo de Tributação da CBS (`imp/IBSCBS/gIBSCBS/gCBS`)."""

    p_cbs: str = Field(..., description="Alíquota da CBS, em percentual (pCBS)")
    g_dif: BRCteDif | None = Field(
        default=None, description="Grupo de campos do diferimento (gDif)"
    )
    g_dev_trib: BRCteDevTrib | None = Field(
        default=None,
        description="Grupo de devolução de tributos (gDevTrib) — sempre rejeitado para CT-e",
    )
    g_red: BRCteRed | None = Field(
        default=None, description="Grupo de campos da redução de alíquota (gRed)"
    )
    g_alczfmcbs: BRCteALCZFMCBS | None = Field(
        default=None,
        description="Grupo de operações em áreas incentivadas (ALC/ZFM) — CBS alíquota zero (gALCZFMCBS)",
    )
    v_cbs: str = Field(..., description="Valor da CBS (vCBS)")


class BRCteIBSCBS(BaseModel):
    """Grupo completo IBS/CBS (`TCIBS`, `imp/IBSCBS/gIBSCBS`)."""

    v_bc: str = Field(..., description="Valor da base de cálculo comum a IBS/CBS (vBC)")
    g_ibsuf: BRCteIBSUF = Field(
        ..., description="Grupo de informações do IBS de competência da UF (gIBSUF)"
    )
    g_ibsmun: BRCteIBSMun = Field(
        ..., description="Grupo de informações do IBS de competência do Município (gIBSMun)"
    )
    v_ibs: str = Field(..., description="Valor do IBS — soma de vIBSUF e vIBSMun (vIBS)")
    g_cbs: BRCteCBS = Field(..., description="Grupo de informações da CBS (gCBS)")
    g_trib_regular: BRCteTribRegular | None = Field(
        default=None, description="Grupo de informações da tributação regular (gTribRegular)"
    )
    g_trib_compra_gov: BRCteTribCompraGov | None = Field(
        default=None, description="Grupo de informações de compra governamental (gTribCompraGov)"
    )


class BRCteImpIBSCBS(BaseModel):
    """Grupo de tributação IBS/CBS do CT-e (`TTribCTe`, `imp/IBSCBS`).

    NT 2026.002 — Reforma Tributária do Consumo (RTC). Field-level structure
    `[Verified locally]` against `DFeTiposBasicos_v1.00.xsd` /
    `cteTiposBasico_v4.00.xsd` from `PL_CTe_400_NT2026.002 RTC_1.00.zip`
    (supplied 2026-08-17; the NT PDF's v1.01 only changed the Produção
    enforcement date, not the field structure, so the v1.00 schema package
    remains authoritative). See br.md CT-e section for the full
    RV-rule-to-validator mapping and outstanding `[NEED]` markers.
    """

    cst: str = Field(
        ..., min_length=3, max_length=3, description="Código Situação Tributária do IBS/CBS (CST)"
    )
    c_class_trib: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Código de Classificação Tributária do IBS/CBS (cClassTrib)",
    )
    ind_doacao: str | None = Field(
        default=None, description="Indicador de doação (indDoacao): '1' quando aplicável"
    )
    g_ibscbs: BRCteIBSCBS | None = Field(
        default=None, description="Grupo de informações do IBS/CBS (gIBSCBS)"
    )
    g_estorno_cred: BRCteEstornoCred | None = Field(
        default=None,
        description="Grupo de estorno de crédito, conforme indicador no cClassTrib (gEstornoCred)",
    )


class BRCteImp(BaseModel):
    """Informações relativas aos Impostos (Grupo `imp`)."""

    icms: BRCteICMS00 = Field(..., description="Informações relativas ao ICMS (Grupo imp/ICMS)")
    v_tot_trib: str | None = Field(default=None, description="Valor Total dos Tributos (vTotTrib)")
    ibscbs: BRCteImpIBSCBS | None = Field(
        default=None,
        description="Grupo de informações do IBS e CBS (imp/IBSCBS) — Reforma Tributária do Consumo, NT 2026.002.",
    )


class BRCteInfQ(BaseModel):
    """Informações de quantidades da Carga (Grupo `infCarga/infQ`)."""

    c_unid: str = Field(
        ...,
        description="Código da Unidade de Medida: 00=M3, 01=KG, 02=TON, 03=UNIDADE, 04=LITROS, 05=MMBTU",
    )
    tp_med: str = Field(..., description="Tipo da Medida (texto livre, ex.: PESO BRUTO)")
    q_carga: str = Field(..., description="Quantidade")


class BRCteInfCarga(BaseModel):
    """Informações da Carga do CT-e (Grupo `infCTeNorm/infCarga`)."""

    v_carga: str | None = Field(
        default=None,
        description="Valor total da carga — obrigatório em todos os modais exceto dutoviário",
    )
    pro_pred: str = Field(..., max_length=60, description="Produto predominante")
    x_out_cat: str | None = Field(
        default=None, max_length=30, description="Outras características da carga"
    )
    inf_q: list[BRCteInfQ] = Field(
        ..., min_length=1, description="Informações de quantidades da carga"
    )


_ZFM_MUNICIPIOS: frozenset[str] = frozenset({"1302603", "1303569", "1301902"})
"""ZFM (Zona Franca de Manaus) — Manaus, Rio Preto da Eva, Itacoatiara (IBGE
codes). `[Verified locally]` — NT 2026.002 v1.01 §4 (p.6) and §6 (p.8)."""

_ALC_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"1304062"}),  # Tabatinga (AM)
    frozenset({"1100106"}),  # Guajará-Mirim (RO)
    frozenset({"1400100", "1400159"}),  # Boa Vista / Bonfim (RR)
    frozenset({"1600303", "1600600"}),  # Macapá / Santana (AP)
    frozenset(
        {"1200104", "1200252", "1200203"}
    ),  # Brasileia / Epitaciolândia / Cruzeiro do Sul (AC)
)
"""ALC (Área de Livre Comércio) groups — municípios within the same group are
mutually paired for the CBS zero-rate route check (RV 6.004). `[Verified
locally]` — NT 2026.002 v1.01 §6 (p.8-9)."""

_ALC_MUNICIPIOS: frozenset[str] = frozenset().union(*_ALC_GROUPS)


def _alc_group_containing(c_mun: str) -> frozenset[str] | None:
    for group in _ALC_GROUPS:
        if c_mun in group:
            return group
    return None


def _resolve_tomador_party(cte: BRCTeDocument) -> BRCteParty | None:
    """Resolve the tomador's party data, whether declared via `toma3`
    (reusing one of the four existing party groups) or `toma4` (`outros`)."""
    tomador = cte.tomador
    if tomador.outros is not None:
        return tomador.outros
    role_map: dict[CTeTomadorPapel, BRCteParty | None] = {
        CTeTomadorPapel.REMETENTE: cte.remetente,
        CTeTomadorPapel.EXPEDIDOR: cte.expedidor,
        CTeTomadorPapel.RECEBEDOR: cte.recebedor,
        CTeTomadorPapel.DESTINATARIO: cte.destinatario,
    }
    return role_map.get(tomador.papel) if tomador.papel is not None else None


class BRCTeDocument(InvoiceDocument):
    """CT-e (modelo 57) document.

    Extends `InvoiceDocument` with the fields required by the CT-e schema
    4.00 that have no EN 16931 equivalent: document model, series, access
    key, operation nature, service type/finality, modal, and the CT-e party
    set (`emit`/`rem`/`exped`/`receb`/`dest`/`tomador`).

    `lines` intentionally stays empty (see module docstring); freight-value
    components live under `v_prest.comp` instead.

    `buyer` (from `InvoiceDocument`) has no CT-e equivalent — overridden
    here as `Optional`, defaulting to `None`. `seller` keeps the base
    required constraint: the generator populates it from `emitente`. Future
    audit CHECK 8 must exempt CT-e from any `buyer`-required field-alignment
    rule that applies to the EN 16931/NF-e pathway.
    """

    buyer: InvoiceParty | None = Field(
        default=None, description="Não utilizado por CT-e — ver docstring do módulo."
    )

    mod: CTeModelo = Field(
        default=CTeModelo.CTE, description="Modelo do documento fiscal: 57 (CT-e)"
    )
    serie: str = Field(..., max_length=3, description="Série do documento fiscal")
    n_ct: str = Field(..., description="Número do CT-e (nCT)")
    chave_acesso: str | None = Field(
        default=None,
        min_length=44,
        max_length=44,
        description=(
            "Chave de acesso (44 caracteres), formato "
            "CTe[0-9]{6}[A-Z0-9]{12}[0-9]{26} no atributo Id de infCte "
            "(TChDFe, alphanumeric-CNPJ-ready)."
        ),
    )
    nat_op: str = Field(..., description="Natureza da Operação")
    tp_serv: CTeTipoServico = Field(..., description="Tipo do Serviço")
    tp_cte: CTeFinalidade = Field(
        default=CTeFinalidade.NORMAL, description="Tipo do CT-e (finalidade)"
    )
    modal: CTeModal = Field(..., description="Modal do transporte")
    dh_emi: str = Field(..., description="Data e hora de emissão, com fuso horário (ISO 8601)")
    c_uf: str = Field(..., min_length=2, max_length=2, description="Código IBGE da UF do emitente")
    cfop: str = Field(
        ..., min_length=4, max_length=4, description="Código Fiscal de Operações e Prestações"
    )
    tp_amb: str = Field(..., description="Identificação do Ambiente: 1=produção, 2=homologação")

    # Grupo ide — rota (mandatory: cMunIni/xMunIni/UFIni/cMunFim/xMunFim/UFFim/retira)
    c_mun_ini: str = Field(
        ...,
        min_length=7,
        max_length=7,
        description="Código IBGE do município de início da prestação",
    )
    x_mun_ini: str = Field(..., description="Nome do município de início da prestação")
    uf_ini: str = Field(..., min_length=2, max_length=2, description="UF de início da prestação")
    c_mun_fim: str = Field(
        ...,
        min_length=7,
        max_length=7,
        description="Código IBGE do município de término da prestação",
    )
    x_mun_fim: str = Field(..., description="Nome do município de término da prestação")
    uf_fim: str = Field(..., min_length=2, max_length=2, description="UF de término da prestação")
    retira: str = Field(
        ...,
        description="Indicador se o recebedor retira no aeroporto/filial/porto/estação: 0=sim, 1=não",
    )

    # Grupo de partes
    emitente: BRCteEmitente = Field(..., description="Dados do emitente (Grupo emit)")
    remetente: BRCteRemetente = Field(..., description="Dados do remetente (Grupo rem)")
    expedidor: BRCteExpedidor | None = Field(
        default=None, description="Dados do expedidor (Grupo exped)"
    )
    recebedor: BRCteRecebedor | None = Field(
        default=None, description="Dados do recebedor (Grupo receb)"
    )
    destinatario: BRCteDestinatario | None = Field(
        default=None, description="Dados do destinatário (Grupo dest)"
    )
    tomador: BRCteTomador = Field(..., description="Tomador do serviço (toma3/toma4)")

    v_prest: BRCteVPrest = Field(..., description="Valores da prestação de serviço (Grupo vPrest)")
    imp: BRCteImp = Field(..., description="Informações relativas aos impostos (Grupo imp)")
    inf_carga: BRCteInfCarga = Field(
        ..., description="Informações da carga (Grupo infCTeNorm/infCarga)"
    )
    inf_modal: BRCteInfModal = Field(..., description="Informações do modal (Grupo infModal)")

    # Grupo ide — Antecipação de Pagamento (NT 2026.002 §7). Only meaningful
    # when payment occurs before the service and this CT-e is the supply
    # document associated with those advance payments.
    tp_pag_ant: str | None = Field(
        default=None,
        description=(
            "Tipo Pagamento ou Pagamento Antecipado (ide/tpPagAnt): "
            "1=Pagamento Antecipado, 3=Fornecimento com pagamento realizado anteriormente."
        ),
    )
    pag_antecipado: list[str] = Field(
        default_factory=list,
        description=(
            "Chaves de acesso dos CT-e de antecipação de pagamento "
            "(ide/gPagAntecipado/chCTePagAnt) — só preenchido quando tpPagAnt=3."
        ),
    )

    lines: list = Field(
        default_factory=list, description="Não utilizado por CT-e — ver docstring do módulo."
    )

    @field_validator("chave_acesso", mode="after")
    @classmethod
    def check_chave_acesso_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$", v):
            raise ValueError(
                "Chave de acesso do CT-e fora do formato esperado "
                f"(TChDFe, 44 caracteres [0-9]{{6}}[A-Z0-9]{{12}}[0-9]{{26}}): {v!r}"
            )
        return v

    @model_validator(mode="after")
    def check_modal_consistency(self) -> BRCTeDocument:
        if self.inf_modal.modal != self.modal:
            raise ValueError("`inf_modal.modal` deve coincidir com `modal` no grupo `ide`.")
        return self

    @field_validator("pag_antecipado", mode="after")
    @classmethod
    def check_pag_antecipado_format(cls, v: list[str]) -> list[str]:
        """`chCTePagAnt` uses the alphanumeric-ready `TChDFe` type
        (`[0-9]{6}[A-Z0-9]{12}[0-9]{26}`), the same pattern now enforced on
        this document's own `chave_acesso` as of BR-CTE-23 (see
        `check_chave_acesso_format`)."""
        for key in v:
            if not re.match(r"^[0-9]{6}[A-Z0-9]{12}[0-9]{26}$", key):
                raise ValueError(
                    "Chave de acesso de antecipação de pagamento (ide/gPagAntecipado/"
                    f"chCTePagAnt) fora do formato esperado (44 caracteres): {key!r}."
                )
        return v

    @model_validator(mode="after")
    def check_tp_pag_ant_consistency(self) -> BRCTeDocument:
        """NT 2026.002 RV 7.001/002."""
        if self.tp_pag_ant in (None, "1") and self.pag_antecipado:
            raise ValueError(
                "ide/gPagAntecipado não deve ser informado quando tpPagAnt não for '3' "
                "(NT 2026.002 RV 7.001)."
            )
        if self.tp_pag_ant == "3" and not self.pag_antecipado:
            raise ValueError(
                "ide/gPagAntecipado deve ser informado quando tpPagAnt='3' (NT 2026.002 RV 7.002)."
            )
        return self

    @model_validator(mode="after")
    def check_pag_antecipado_no_duplicates(self) -> BRCTeDocument:
        """NT 2026.002 RV 7.011."""
        if len(self.pag_antecipado) != len(set(self.pag_antecipado)):
            raise ValueError(
                "Chaves de acesso repetidas em ide/gPagAntecipado (NT 2026.002 RV 7.011)."
            )
        return self

    @model_validator(mode="after")
    def check_pag_antecipado_cnpj_base(self) -> BRCTeDocument:
        """NT 2026.002 RV 7.010. Self-contained: the CNPJ-Base is embedded
        in `chCTePagAnt` itself (chars 6:14, per the verified `TChDFe`
        layout), so no external lookup is needed to compare it against the
        emitente's own CNPJ-Base."""
        if not self.pag_antecipado:
            return self
        emit_cnpj = self.emitente.cnpj
        if emit_cnpj is None:
            return self
        emit_base = emit_cnpj[:8]
        for key in self.pag_antecipado:
            key_base = key[6:14]
            if key_base.upper() != emit_base.upper():
                raise ValueError(
                    f"CNPJ-Base da chave de acesso de antecipação de pagamento ({key_base!r}) "
                    f"difere do CNPJ-Base do emitente ({emit_base!r}) — NT 2026.002 RV 7.010."
                )
        return self

    @model_validator(mode="after")
    def check_no_devolucao_for_cte(self) -> BRCTeDocument:
        """NT 2026.002 RV 5.001-003: `gDevTrib` is only valid for NF3e/
        NFCom/NFAg/NFGas, never for CT-e — reject if set anywhere in the
        shared `TCIBS` tree."""
        ibscbs = self.imp.ibscbs
        if ibscbs is None or ibscbs.g_ibscbs is None:
            return self
        g = ibscbs.g_ibscbs
        if (
            g.g_ibsuf.g_dev_trib is not None
            or g.g_ibsmun.g_dev_trib is not None
            or g.g_cbs.g_dev_trib is not None
        ):
            raise ValueError(
                "Grupo de devolução de tributos (gDevTrib) não é permitido para CT-e — só é "
                "aceito em NF3e/NFCom/NFAg/NFGas (NT 2026.002 RV 5.001-003)."
            )
        return self

    @model_validator(mode="after")
    def check_suframa_required_for_alczfmcbs(self) -> BRCTeDocument:
        """NT 2026.002 RV 6.003."""
        ibscbs = self.imp.ibscbs
        if ibscbs is None or ibscbs.g_ibscbs is None or ibscbs.g_ibscbs.g_cbs.g_alczfmcbs is None:
            return self
        if not self.emitente.isuf_emit:
            raise ValueError(
                "emit/ISUFEmit deve ser informado quando imp/IBSCBS/gIBSCBS/gCBS/gALCZFMCBS "
                "estiver preenchido (NT 2026.002 RV 6.003)."
            )
        return self

    @model_validator(mode="after")
    def check_emit_municipio_in_incentivized_area(self) -> BRCTeDocument:
        """NT 2026.002 RV 4.001."""
        if not self.emitente.isuf_emit:
            return self
        c_mun = self.emitente.endereco.c_mun
        if c_mun not in _ZFM_MUNICIPIOS and c_mun not in _ALC_MUNICIPIOS:
            raise ValueError(
                f"Município do emitente ({c_mun!r}) não pertence a uma área incentivada "
                "(ZFM/ALC), mas emit/ISUFEmit foi informado (NT 2026.002 RV 4.001)."
            )
        return self

    @model_validator(mode="after")
    def check_alczfmcbs_route_in_incentivized_area(self) -> BRCTeDocument:
        """NT 2026.002 RV 6.004. Either início/fim/emitente/tomador(PJ) all
        fall within ZFM, or início/fim fall within the same ALC group and
        emitente/tomador(PJ) also fall within that same group."""
        ibscbs = self.imp.ibscbs
        if ibscbs is None or ibscbs.g_ibscbs is None or ibscbs.g_ibscbs.g_cbs.g_alczfmcbs is None:
            return self

        tomador_party = _resolve_tomador_party(self)
        tomador_is_pj = tomador_party is not None and tomador_party.cnpj is not None
        tomador_mun = (
            tomador_party.endereco.c_mun if tomador_is_pj and tomador_party is not None else None
        )

        parties_mun = [self.c_mun_ini, self.c_mun_fim, self.emitente.endereco.c_mun]
        if tomador_mun is not None:
            parties_mun.append(tomador_mun)

        if all(m in _ZFM_MUNICIPIOS for m in parties_mun):
            return self

        start_group = _alc_group_containing(self.c_mun_ini)
        end_group = _alc_group_containing(self.c_mun_fim)
        if (
            start_group is not None
            and start_group == end_group
            and self.emitente.endereco.c_mun in start_group
            and (tomador_mun is None or tomador_mun in start_group)
        ):
            return self

        raise ValueError(
            "gALCZFMCBS preenchido, mas início/fim da prestação, emitente e tomador (se PJ) "
            "não pertencem à mesma área incentivada (ZFM, ou a mesma ALC) — NT 2026.002 RV 6.004."
        )

    @model_validator(mode="after")
    def check_v_trib_reg_cbs_arithmetic(self) -> BRCTeDocument:
        """NT 2026.002 RV 6.005: `vTribRegCBS = gIBSCBS/vBC x
        (gALCZFMCBS/pAliqEfetRegCBS / 100)`. `[Unverified: SEFAZ's rounding
        mode for this check is not stated in the NT — using standard
        round-half-up to 2 decimals, matching the field's `TDec1302RTC`
        precision]`."""
        ibscbs = self.imp.ibscbs
        if ibscbs is None or ibscbs.g_ibscbs is None:
            return self
        alc = ibscbs.g_ibscbs.g_cbs.g_alczfmcbs
        if alc is None:
            return self
        try:
            v_bc = Decimal(ibscbs.g_ibscbs.v_bc)
            p_aliq = Decimal(alc.p_aliq_efet_reg_cbs)
            v_trib_declared = Decimal(alc.v_trib_reg_cbs)
        except InvalidOperation:
            return self
        expected = (v_bc * p_aliq / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if expected != v_trib_declared:
            raise ValueError(
                f"vTribRegCBS ({v_trib_declared}) não corresponde a vBC x pAliqEfetRegCBS / 100 "
                f"(esperado {expected}) — NT 2026.002 RV 6.005."
            )
        return self
