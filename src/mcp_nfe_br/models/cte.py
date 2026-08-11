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
`schemas/cte/tiposGeralCTe_v4.00.xsd`. See context-library/countries/br.md
CT-e section for the full field-level reference and outstanding
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
"""

from __future__ import annotations

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
        ..., description="Indicador do papel do tomador na prestação: 1=contribuinte ICMS, 2=isento, 9=não contribuinte"
    )

    @model_validator(mode="after")
    def check_one_choice(self) -> BRCteTomador:
        if bool(self.papel) == bool(self.outros):
            raise ValueError("Tomador deve informar exatamente um de `papel` (toma3) ou `outros` (toma4).")
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
    comp: list[BRCteVPrestComp] = Field(default_factory=list, description="Componentes do valor da prestação")


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
    versao_modal: str = Field(default="4.00", description="Versão do leiaute específico do modal (versaoModal)")
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

    cst: str = Field(default="00", description="Classificação Tributária do Serviço: 00 = tributação normal")
    v_bc: str = Field(..., description="Valor da BC do ICMS")
    p_icms: str = Field(..., description="Alíquota do ICMS")
    v_icms: str = Field(..., description="Valor do ICMS")


class BRCteImp(BaseModel):
    """Informações relativas aos Impostos (Grupo `imp`)."""

    icms: BRCteICMS00 = Field(..., description="Informações relativas ao ICMS (Grupo imp/ICMS)")
    v_tot_trib: str | None = Field(default=None, description="Valor Total dos Tributos (vTotTrib)")


class BRCteInfQ(BaseModel):
    """Informações de quantidades da Carga (Grupo `infCarga/infQ`)."""

    c_unid: str = Field(..., description="Código da Unidade de Medida: 00=M3, 01=KG, 02=TON, 03=UNIDADE, 04=LITROS, 05=MMBTU")
    tp_med: str = Field(..., description="Tipo da Medida (texto livre, ex.: PESO BRUTO)")
    q_carga: str = Field(..., description="Quantidade")


class BRCteInfCarga(BaseModel):
    """Informações da Carga do CT-e (Grupo `infCTeNorm/infCarga`)."""

    v_carga: str | None = Field(
        default=None, description="Valor total da carga — obrigatório em todos os modais exceto dutoviário"
    )
    pro_pred: str = Field(..., max_length=60, description="Produto predominante")
    x_out_cat: str | None = Field(default=None, max_length=30, description="Outras características da carga")
    inf_q: list[BRCteInfQ] = Field(..., min_length=1, description="Informações de quantidades da carga")


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

    buyer: InvoiceParty | None = Field(default=None, description="Não utilizado por CT-e — ver docstring do módulo.")

    mod: CTeModelo = Field(default=CTeModelo.CTE, description="Modelo do documento fiscal: 57 (CT-e)")
    serie: str = Field(..., max_length=3, description="Série do documento fiscal")
    n_ct: str = Field(..., description="Número do CT-e (nCT)")
    chave_acesso: str | None = Field(
        default=None,
        min_length=44,
        max_length=44,
        description="Chave de acesso (44 caracteres), formato CTe[0-9]{44} no atributo Id de infCte.",
    )
    nat_op: str = Field(..., description="Natureza da Operação")
    tp_serv: CTeTipoServico = Field(..., description="Tipo do Serviço")
    tp_cte: CTeFinalidade = Field(default=CTeFinalidade.NORMAL, description="Tipo do CT-e (finalidade)")
    modal: CTeModal = Field(..., description="Modal do transporte")
    dh_emi: str = Field(..., description="Data e hora de emissão, com fuso horário (ISO 8601)")
    c_uf: str = Field(..., min_length=2, max_length=2, description="Código IBGE da UF do emitente")
    cfop: str = Field(..., min_length=4, max_length=4, description="Código Fiscal de Operações e Prestações")
    tp_amb: str = Field(..., description="Identificação do Ambiente: 1=produção, 2=homologação")

    # Grupo ide — rota (mandatory: cMunIni/xMunIni/UFIni/cMunFim/xMunFim/UFFim/retira)
    c_mun_ini: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município de início da prestação")
    x_mun_ini: str = Field(..., description="Nome do município de início da prestação")
    uf_ini: str = Field(..., min_length=2, max_length=2, description="UF de início da prestação")
    c_mun_fim: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município de término da prestação")
    x_mun_fim: str = Field(..., description="Nome do município de término da prestação")
    uf_fim: str = Field(..., min_length=2, max_length=2, description="UF de término da prestação")
    retira: str = Field(..., description="Indicador se o recebedor retira no aeroporto/filial/porto/estação: 0=sim, 1=não")

    # Grupo de partes
    emitente: BRCteEmitente = Field(..., description="Dados do emitente (Grupo emit)")
    remetente: BRCteRemetente = Field(..., description="Dados do remetente (Grupo rem)")
    expedidor: BRCteExpedidor | None = Field(default=None, description="Dados do expedidor (Grupo exped)")
    recebedor: BRCteRecebedor | None = Field(default=None, description="Dados do recebedor (Grupo receb)")
    destinatario: BRCteDestinatario | None = Field(default=None, description="Dados do destinatário (Grupo dest)")
    tomador: BRCteTomador = Field(..., description="Tomador do serviço (toma3/toma4)")

    v_prest: BRCteVPrest = Field(..., description="Valores da prestação de serviço (Grupo vPrest)")
    imp: BRCteImp = Field(..., description="Informações relativas aos impostos (Grupo imp)")
    inf_carga: BRCteInfCarga = Field(..., description="Informações da carga (Grupo infCTeNorm/infCarga)")
    inf_modal: BRCteInfModal = Field(..., description="Informações do modal (Grupo infModal)")

    lines: list = Field(default_factory=list, description="Não utilizado por CT-e — ver docstring do módulo.")

    @field_validator("chave_acesso", mode="after")
    @classmethod
    def check_chave_acesso_format(cls, v: str | None) -> str | None:
        import re

        if v is None:
            return v
        if not re.match(r"^[0-9]{44}$", v):
            raise ValueError(f"Chave de acesso do CT-e fora do formato esperado (44 dígitos): {v!r}")
        return v

    @model_validator(mode="after")
    def check_modal_consistency(self) -> BRCTeDocument:
        if self.inf_modal.modal != self.modal:
            raise ValueError("`inf_modal.modal` deve coincidir com `modal` no grupo `ide`.")
        return self
