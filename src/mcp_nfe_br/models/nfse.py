"""Brazilian NFS-e Nacional (ADN) document model.

Models the Declaração de Prestação de Serviços (DPS), schema v1.01, namespace
``http://www.sped.fazenda.gov.br/nfse``. The contributor creates and optionally
signs a DPS and submits it to the Ambiente de Dados Nacional (ADN) via gov.br
OAuth2 authentication. ADN validates the DPS, generates the NFS-e, and returns
the signed NFSe document.

DPS structure (`TCDPS` in tiposComplexos_v1.01.xsd `[Verified locally]`):
- ``<DPS versao="1.01">`` → root element
  - ``<infDPS Id="DPS...">`` → signed element (optional ``<ds:Signature>``)
    - fields: tpAmb, dhEmi, verAplic, serie, nDPS, dCompet, tpEmit, cLocEmi,
              optional subst, prest, optional toma/interm, serv, valores,
              optional IBSCBS

DPS ID format (``TSIdDPS``, 45 chars, pattern ``DPS[0-9]{42}``)
`[Verified locally — tiposSimples_v1.01.xsd]`:
  "DPS" + cLocEmi(7) + tpInscFederal(1) + inscFederal(14, CPF padded 000 left)
  + serie(5, zero-padded) + nDPS(15, zero-padded)

Signature algorithm: RSA-SHA1 default `[Unverified — NFS-e manuals in local
bundle not yet read; assumed same as NF-e pending manual verification from
mcp-nfe-br/specs/nfse/]`.

IBS/CBS: ``BRGrupoIBSCBS`` from ``invoice.py`` is reused for ``IBSCBS`` group.
``BRGrupoIBSCBSTot`` is not emitted in DPS (document-level totals belong to
the NFS-e returned by ADN, not the DPS submitted by the contributor).

Omitted optional groups (``[NEED: not modeled for v0.5.0]``):
- ``subst`` (NFS-e substitution)
- ``interm`` (intermediary party)
- ``comExt`` (foreign trade / export)
- ``obra`` (construction works)
- ``atvEvento`` (events)
- ``infoCompl`` (complementary info)
- ``vDescCondIncond`` (conditional/unconditional discounts)
- ``vDedRed`` (deduction/reduction)
- ``tribFed`` (federal taxes on services: PIS, COFINS, IR, CSLL, INSS, INSS-PR)
- ``exigSusp`` (suspended exigibility)
- ``BM`` (municipal benefit)
"""

from __future__ import annotations

from enum import StrEnum

from mcp_einvoicing_core.models import InvoiceDocument
from pydantic import BaseModel, Field, field_validator, model_validator

from mcp_nfe_br.models.invoice import BRGrupoIBSCBS, TipoAmbiente
from mcp_nfe_br.utils.document_ids import validate_cnpj, validate_cpf


class NFSeTipoEmitente(StrEnum):
    """Emitente da DPS (`tpEmit`). Source: tiposSimples_v1.01.xsd, TSEmitenteDPS."""

    PRESTADOR = "1"
    TOMADOR = "2"
    INTERMEDIARIO = "3"


class NFSeOpSimplesNacional(StrEnum):
    """Situação perante o Simples Nacional (`opSimpNac`).

    Source: tiposComplexos_v1.01.xsd, TSOpSimpNac.
    """

    NAO_OPTANTE = "1"
    MEI = "2"
    ME_EPP = "3"


class NFSeTribISSQN(StrEnum):
    """Tributação do ISSQN (`tribISSQN`).

    Source: tiposComplexos_v1.01.xsd, TCTribMunicipal.
    """

    TRIBUTAVEL = "1"
    IMUNIDADE = "2"
    EXPORTACAO = "3"
    NAO_INCIDENCIA = "4"


class NFSeTipoRetISSQN(StrEnum):
    """Tipo de retenção do ISSQN (`tpRetISSQN`).

    Source: tiposComplexos_v1.01.xsd, TCTribMunicipal.
    """

    NAO_RETIDO = "1"
    RETIDO_TOMADOR = "2"
    RETIDO_INTERMEDIARIO = "3"


class NFSeTipoTotTrib(StrEnum):
    """Selector for the totTrib choice in TCTribTotal."""

    MONETARIO = "v"
    PERCENTUAL = "p"
    NAO_INFORMADO = "ind"
    SIMPLES_NACIONAL = "sn"


class NFSeEndereco(BaseModel):
    """Endereço (``TCEndereco``).

    `[Verified locally — tiposComplexos_v1.01.xsd TCEndereco]`.
    Foreign-address fields (``endExt``) are `[NEED: not modeled]`.
    """

    x_lgr: str = Field(..., description="Logradouro")
    nro: str = Field(..., description="Número")
    x_cpl: str | None = Field(default=None, description="Complemento")
    x_bairro: str | None = Field(default=None, description="Bairro")
    c_mun: str = Field(..., min_length=7, max_length=7, description="Código IBGE do município")
    x_mun: str = Field(..., description="Nome do município")
    uf: str | None = Field(default=None, min_length=2, max_length=2, description="Sigla da UF")
    cep: str | None = Field(default=None, description="CEP")
    c_pais: str | None = Field(
        default=None, description="Código ISO do país (omit for Brasil, ADN infers)"
    )
    x_pais: str | None = Field(default=None, description="Nome do país")
    fone: str | None = Field(default=None, description="Telefone")


class NFSeRegimeTributacao(BaseModel):
    """Regimes de tributação do prestador (`TCRegTrib`).

    ``opSimpNac`` is mandatory; optional regime fields are `[NEED: not modeled]`:
    ``regApTribSN`` (apuração SN), ``regEspTrib`` (special regulated regimes:
    ANS/ANATEL/ANP healthcare/telecom/petroleum).
    """

    op_simp_nac: NFSeOpSimplesNacional = Field(
        ..., description="Situação perante o Simples Nacional: 1=não optante, 2=MEI, 3=ME/EPP"
    )
    reg_ap_trib_sn: str | None = Field(
        default=None,
        description=(
            "Regime de apuração SN (opcional, ME/EPP only): 1=todos pelo SN, "
            "2=tributos federais pelo SN e ISSQN por fora, 3=ISSQN pelo SN e "
            "tributos federais por fora, 4=todos por fora do SN"
        ),
    )
    reg_esp_trib: str | None = Field(
        default=None,
        description=(
            "Regime Especial de Tributação: 1=Microempreendedor Individual, "
            "2=Estimativa, 3=Sociedade de Profissionais, 4=Cooperativa, "
            "5=Microempresário Individual, 6=Microempresário e Empresa de Pequeno Porte "
            "[Unverified — code list from tiposSimples.xsd TSRegEspTrib pending manual check]"
        ),
    )


class NFSePrestador(BaseModel):
    """Informações do prestador (``TCInfoPrestador``).

    Exactly one of ``cnpj`` / ``cpf`` must be provided (``NIF``/``cNaoNIF``
    for foreign issuers are `[NEED: not modeled]`).
    ``CAEPF`` (individual economic activity registration) is `[NEED: not modeled]`.
    """

    cnpj: str | None = Field(default=None, description="CNPJ do prestador")
    cpf: str | None = Field(default=None, description="CPF do prestador")
    im: str | None = Field(default=None, description="Inscrição Municipal do prestador")
    x_nome: str | None = Field(default=None, description="Nome/razão social do prestador")
    end: NFSeEndereco | None = Field(default=None, description="Endereço do prestador")
    fone: str | None = Field(default=None, description="Telefone do prestador")
    email: str | None = Field(default=None, description="E-mail do prestador")
    reg_trib: NFSeRegimeTributacao = Field(
        ..., description="Regimes de tributação do prestador"
    )

    @model_validator(mode="after")
    def check_one_document(self) -> NFSePrestador:
        if bool(self.cnpj) == bool(self.cpf):
            raise ValueError("Prestador deve informar exatamente um de CNPJ ou CPF.")
        return self

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, v: str | None) -> str | None:
        if v is not None and not validate_cnpj(v):
            raise ValueError(f"CNPJ do prestador inválido: {v!r}")
        return v

    @field_validator("cpf")
    @classmethod
    def check_cpf(cls, v: str | None) -> str | None:
        if v is not None and not validate_cpf(v):
            raise ValueError(f"CPF do prestador inválido: {v!r}")
        return v


class NFSeTomador(BaseModel):
    """Informações de uma pessoa envolvida na NFS-e (``TCInfoPessoa``).

    Used for ``toma`` (tomador) and optionally ``interm`` (intermediário).
    At least one of ``cnpj`` / ``cpf`` / ``nif`` / ``c_nao_nif`` is required
    per schema; the model enforces exactly one of the first two for domestic
    parties. Foreign parties (``nif`` / ``c_nao_nif``) are `[NEED: not modeled]`.
    """

    cnpj: str | None = Field(default=None, description="CNPJ do tomador")
    cpf: str | None = Field(default=None, description="CPF do tomador")
    im: str | None = Field(default=None, description="Inscrição Municipal do tomador")
    x_nome: str | None = Field(default=None, description="Nome/razão social do tomador")
    end: NFSeEndereco | None = Field(default=None, description="Endereço do tomador")
    fone: str | None = Field(default=None, description="Telefone do tomador")
    email: str | None = Field(default=None, description="E-mail do tomador")

    @model_validator(mode="after")
    def check_identifier(self) -> NFSeTomador:
        if not self.cnpj and not self.cpf:
            raise ValueError("Tomador deve informar CNPJ ou CPF.")
        if self.cnpj and self.cpf:
            raise ValueError("Tomador deve informar exatamente um de CNPJ ou CPF.")
        return self

    @field_validator("cnpj")
    @classmethod
    def check_cnpj(cls, v: str | None) -> str | None:
        if v is not None and not validate_cnpj(v):
            raise ValueError(f"CNPJ do tomador inválido: {v!r}")
        return v

    @field_validator("cpf")
    @classmethod
    def check_cpf(cls, v: str | None) -> str | None:
        if v is not None and not validate_cpf(v):
            raise ValueError(f"CPF do tomador inválido: {v!r}")
        return v


class NFSeLocPrest(BaseModel):
    """Local da prestação (``TCLocPrest``).

    Either ``c_loc_prestacao`` (IBGE code, domestic) or ``c_pais_prestacao``
    (ISO country code, foreign) must be set, not both.
    `[Verified locally — tiposComplexos_v1.01.xsd TCLocPrest xs:choice]`
    """

    c_loc_prestacao: str | None = Field(
        default=None,
        min_length=7,
        max_length=7,
        description="Código IBGE do município de prestação (para prestação no Brasil)",
    )
    c_pais_prestacao: str | None = Field(
        default=None,
        description="Código ISO do país de prestação (para exportação de serviço)",
    )

    @model_validator(mode="after")
    def check_one_of(self) -> NFSeLocPrest:
        if bool(self.c_loc_prestacao) == bool(self.c_pais_prestacao):
            raise ValueError(
                "Informe exatamente um de c_loc_prestacao (município IBGE) "
                "ou c_pais_prestacao (código ISO do país)."
            )
        return self


class NFSeCServ(BaseModel):
    """Código e descrição do serviço (``TCCServ``).

    ``c_trib_nac``: 6-digit national ISS code per LC 116/2003 (2 Item + 2 Subitem
    + 2 Desdobro Nacional). Anchoring against the Anexo I table is
    `[NEED: no hardcoded table — validate online against ADN Anexo I]`.
    ``c_nbs``: NBS 2.0 code, optional per schema. Anchoring against Anexo B is
    `[NEED: no hardcoded table]`.
    """

    c_trib_nac: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Código de tributação nacional do ISSQN (6 dígitos, LC 116/2003)",
    )
    c_trib_mun: str | None = Field(
        default=None,
        description="Código de tributação municipal do ISSQN (formato livre, opcional)",
    )
    x_desc_serv: str = Field(
        ..., max_length=2000, description="Descrição completa do serviço prestado"
    )
    c_nbs: str | None = Field(
        default=None,
        description="Código NBS 2.0 (opcional, Anexo B)",
    )


class NFSeServ(BaseModel):
    """Grupo de informações do serviço (``TCServ``)."""

    loc_prest: NFSeLocPrest = Field(..., description="Local da prestação do serviço")
    c_serv: NFSeCServ = Field(..., description="Código e descrição do serviço")


class NFSeTribMunicipal(BaseModel):
    """Tributação municipal (ISSQN) do serviço (``TCTribMunicipal``).

    ``p_aliq`` (ISS rate) is optional per schema because ADN provides it when
    the municipality of incidence is registered in the national system. If the
    municipality is not registered, the contributor must supply the rate.
    Per-municipality ISS rates `[NEED: no hardcoded table — ADN-provided]`.

    Optional sub-groups not modeled: ``tpImunidade``, ``exigSusp``, ``BM``,
    ``cPaisResult`` (export). `[NEED: v0.5.0 scope limit]`
    """

    trib_issqn: NFSeTribISSQN = Field(
        ..., description="Tributação do ISSQN: 1=tributável, 2=imunidade, 3=exportação, 4=não incidência"
    )
    tp_ret_issqn: NFSeTipoRetISSQN = Field(
        ..., description="Tipo de retenção do ISSQN: 1=não retido, 2=retido pelo tomador, 3=retido pelo intermediário"
    )
    p_aliq: str | None = Field(
        default=None,
        description=(
            "Alíquota do ISSQN (%). Opcional quando o município de incidência está "
            "no Sistema Nacional NFS-e (ADN fornece automaticamente). "
            "[NEED: per-municipality ISS rate table — not hardcoded]"
        ),
    )


class NFSeTotTrib(BaseModel):
    """Total aproximado de tributos (`TCTribTotal`).

    Exatamente um dos campos deve ser informado:
    - ``v_tot_trib_fed`` + ``v_tot_trib_est`` + ``v_tot_trib_mun`` (monetary)
    - ``p_tot_trib`` (percentage)
    - ``ind_tot_trib`` = "0" (não informado, Decreto 8.264/2014)
    - ``p_tot_trib_sn`` (Simples Nacional percentage)

    `[Verified locally — tiposComplexos_v1.01.xsd TCTribTotal xs:choice]`
    """

    v_tot_trib_fed: str | None = Field(
        default=None, description="Valor total aproximado dos tributos federais (R$)"
    )
    v_tot_trib_est: str | None = Field(
        default=None, description="Valor total aproximado dos tributos estaduais (R$)"
    )
    v_tot_trib_mun: str | None = Field(
        default=None, description="Valor total aproximado dos tributos municipais (R$)"
    )
    p_tot_trib: str | None = Field(
        default=None, description="Percentual total aproximado dos tributos (%)"
    )
    ind_tot_trib: str | None = Field(
        default=None,
        description="Indicador de não-informação: '0' = não informar tributos (Decreto 8.264/2014)",
    )
    p_tot_trib_sn: str | None = Field(
        default=None, description="Percentual aproximado Simples Nacional (%)"
    )

    @model_validator(mode="after")
    def check_exactly_one_mode(self) -> NFSeTotTrib:
        has_monetary = any(
            v is not None for v in (self.v_tot_trib_fed, self.v_tot_trib_est, self.v_tot_trib_mun)
        )
        filled = [
            x
            for x in (
                has_monetary,
                self.p_tot_trib is not None,
                self.ind_tot_trib is not None,
                self.p_tot_trib_sn is not None,
            )
            if x
        ]
        if len(filled) != 1:
            raise ValueError(
                "Informe exatamente um modo de totTrib: monetário "
                "(v_tot_trib_fed/est/mun), percentual (p_tot_trib), "
                "não informado (ind_tot_trib='0'), ou Simples Nacional (p_tot_trib_sn)."
            )
        if has_monetary and not all(
            v is not None for v in (self.v_tot_trib_fed, self.v_tot_trib_est, self.v_tot_trib_mun)
        ):
            raise ValueError(
                "Modo monetário requer v_tot_trib_fed, v_tot_trib_est e v_tot_trib_mun."
            )
        return self


class NFSeValores(BaseModel):
    """Grupo de valores do serviço prestado (`TCInfoValores`).

    ``v_serv`` is mandatory; discounts, deductions, and federal tax info are
    `[NEED: not modeled for v0.5.0]`.
    """

    v_serv: str = Field(..., description="Valor dos serviços (R$)")
    trib_mun: NFSeTribMunicipal = Field(
        ..., description="Tributação municipal (ISSQN)"
    )
    tot_trib: NFSeTotTrib = Field(
        ..., description="Total aproximado de tributos (obrigatório)"
    )


class NFSeDocument(InvoiceDocument):
    """NFS-e Nacional DPS document model.

    Extends ``InvoiceDocument`` for the Declaração de Prestação de Serviços (DPS)
    submitted to the ADN. The contributor creates and optionally signs this document;
    ADN returns the corresponding signed NFS-e.

    DPS field order follows ``TCInfDPS`` in ``tiposComplexos_v1.01.xsd``
    `[Verified locally]`.
    """

    tp_amb: TipoAmbiente = Field(
        ..., description="Identificação do Ambiente: 1=produção, 2=homologação"
    )
    ver_aplic: str = Field(
        default="mcp-nfe-br",
        description="Versão do aplicativo que gerou o DPS",
    )
    serie: str = Field(
        ...,
        max_length=5,
        description="Série do DPS (até 5 caracteres)",
    )
    n_dps: str = Field(
        ...,
        max_length=15,
        description="Número do DPS (até 15 dígitos)",
    )
    d_compet: str = Field(
        ...,
        description="Data de competência — início da prestação (AAAAMMDD)",
    )
    tp_emit: NFSeTipoEmitente = Field(
        default=NFSeTipoEmitente.PRESTADOR,
        description="Emitente da DPS: 1=prestador, 2=tomador, 3=intermediário",
    )
    c_loc_emi: str = Field(
        ...,
        min_length=7,
        max_length=7,
        description="Código IBGE do município emissor (7 dígitos)",
    )
    prest: NFSePrestador = Field(..., description="Informações do prestador")
    toma: NFSeTomador | None = Field(
        default=None, description="Informações do tomador (opcional)"
    )
    serv: NFSeServ = Field(..., description="Informações do serviço")
    valores: NFSeValores = Field(..., description="Valores do serviço e tributação")
    ibscbs: BRGrupoIBSCBS | None = Field(
        default=None,
        description="IBS/CBS (NT 2025.002-RTC, opcional em DPS)",
    )
