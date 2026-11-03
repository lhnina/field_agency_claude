from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import EstadoContrato, TipoAusencia, TipoContrato, TipoVinculo


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(ORM):
    id: int
    nome: str
    email: str
    perfil: str


# ---------------------------------------------------------------- dados mestre
class Nome(BaseModel):
    nome: str = Field(min_length=1, max_length=160)


class IdNome(ORM):
    id: int
    nome: str


class IdNomeAtivo(ORM):
    id: int
    nome: str
    ativo: bool


class MarcaOut(ORM):
    id: int
    nome: str
    ativo: bool = True


class EstadoAtivoIn(BaseModel):
    ativo: bool


class ClienteIn(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    nif: str | None = None
    codigo_erp: int | None = None
    morada: str | None = None
    codigo_postal: str | None = None
    localidade: str | None = None
    telefone: str | None = None
    email: str | None = None
    url: str | None = None
    contacto_nome: str | None = None
    gestor_conta: str | None = None
    observacoes: str | None = None
    marcas: list[str] = []


class ClienteOut(ORM):
    id: int
    nome: str
    nif: str | None
    codigo_erp: int | None
    morada: str | None
    codigo_postal: str | None
    localidade: str | None
    telefone: str | None
    email: str | None
    url: str | None
    contacto_nome: str | None
    gestor_conta: str | None
    observacoes: str | None
    ativo: bool
    marcas: list[MarcaOut]


class LojaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    insignia_id: int | None = None
    zona_id: int | None = None
    supervisor_id: int | None = None
    nome_credencial: str | None = None
    morada: str | None = None
    codigo_postal: str | None = None
    localidade: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    horario_semana: str | None = None
    horario_fim_semana: str | None = None
    contacto_nome: str | None = None
    contacto_funcao: str | None = None
    contacto_email: str | None = None
    contacto_telefone: str | None = None


class LojaOut(LojaIn, ORM):
    id: int
    ativo: bool
    insignia: IdNome | None = None
    zona: IdNome | None = None


# ---------------------------------------------------------------- colaboradores
class ColaboradorIn(BaseModel):
    numero: str = Field(min_length=1, max_length=20)
    nome: str = Field(min_length=1, max_length=160)
    funcao: str | None = None
    email: str | None = None
    telefone: str | None = None
    vinculo: TipoVinculo
    data_inicio: date | None = None
    data_fim_vinculo: date | None = None
    zona_id: int | None = None
    supervisor_id: int | None = None
    custo_hora: Decimal = Decimal("0")
    disponibilidade: str = "1111100"
    ativo: bool = True

    @field_validator("disponibilidade")
    @classmethod
    def _disp(cls, v: str) -> str:
        if len(v) != 7 or set(v) - {"0", "1"}:
            raise ValueError("A disponibilidade tem 7 dígitos 0/1 (segunda a domingo)")
        return v


class ColaboradorOut(ColaboradorIn, ORM):
    id: int
    zona: IdNome | None = None
    horas_afetadas: Decimal = Decimal("0")  # soma das horas/semana das lojas em que está afeto hoje


# ---------------------------------------------------------------- contratos
class LinhaIn(BaseModel):
    loja_id: int
    inicio: date
    fim: date | None = None
    h_seg: Decimal = Decimal("0")
    h_ter: Decimal = Decimal("0")
    h_qua: Decimal = Decimal("0")
    h_qui: Decimal = Decimal("0")
    h_sex: Decimal = Decimal("0")
    h_sab: Decimal = Decimal("0")
    h_dom: Decimal = Decimal("0")
    hora_inicio: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    preco_hora: Decimal = Field(ge=0)
    preco_hora_extra: Decimal | None = None
    custo_hora_especial: Decimal | None = None
    mecanica: str | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def _valida(self):
        horas = [self.h_seg, self.h_ter, self.h_qua, self.h_qui, self.h_sex, self.h_sab, self.h_dom]
        if any(h < 0 or h > 24 for h in horas):
            raise ValueError("As horas por dia têm de estar entre 0 e 24")
        if sum(horas) == 0:
            raise ValueError("Indique as horas em pelo menos um dia da semana")
        if self.fim and self.fim < self.inicio:
            raise ValueError("A data de fim da linha é anterior à data de início")
        return self


class AfetacaoOut(ORM):
    id: int
    colaborador_id: int
    colaborador_nome: str
    desde: date
    ate: date | None


class LinhaOut(ORM):
    id: int
    loja_id: int
    loja_nome: str
    loja_insignia: str | None
    loja_zona: str | None
    inicio: date
    fim: date | None
    h_seg: Decimal
    h_ter: Decimal
    h_qua: Decimal
    h_qui: Decimal
    h_sex: Decimal
    h_sab: Decimal
    h_dom: Decimal
    hora_inicio: str | None
    preco_hora: Decimal
    preco_hora_extra: Decimal | None
    custo_hora_especial: Decimal | None
    mecanica: str | None
    observacoes: str | None
    horas_semana: Decimal
    horas_mes: Decimal
    valor_mensal: Decimal
    afetacao_atual: AfetacaoOut | None
    afetacoes: list[AfetacaoOut]


class ContratoIn(BaseModel):
    tipo: TipoContrato
    cliente_id: int
    marca_id: int | None = None
    data: date
    inicio: date
    fim: date | None = None
    descricao: str | None = None
    evento: str | None = None
    observacoes: str | None = None

    @model_validator(mode="after")
    def _datas(self):
        if self.fim and self.fim < self.inicio:
            raise ValueError("A data de fim é anterior à data de início")
        return self


class ContratoResumo(ORM):
    id: int
    numero: str
    tipo: TipoContrato
    estado: EstadoContrato
    cliente_id: int
    cliente_nome: str
    marca_nome: str | None
    descricao: str | None
    evento: str | None
    data: date
    inicio: date
    fim: date | None
    versao: int
    n_linhas: int
    horas_semana: Decimal
    horas_mes: Decimal
    valor_mensal: Decimal
    linhas_por_atribuir: int


class ContratoOut(ContratoResumo):
    marca_id: int | None
    observacoes: str | None
    linhas: list[LinhaOut]


class EstadoIn(BaseModel):
    estado: EstadoContrato


class AfetarIn(BaseModel):
    colaborador_id: int
    desde: date
    ate: date | None = None


class GerarIn(BaseModel):
    ate: date | None = None


# ---------------------------------------------------------------- operação
class SubstituirIn(BaseModel):
    colaborador_id: int | None
    motivo: str | None = None


class MoverIn(BaseModel):
    data: date


class AusenciaIn(BaseModel):
    colaborador_id: int
    tipo: TipoAusencia
    inicio: date
    fim: date
    observacoes: str | None = None

    @model_validator(mode="after")
    def _datas(self):
        if self.fim < self.inicio:
            raise ValueError("A data de fim é anterior à data de início")
        return self


class AusenciaOut(ORM):
    id: int
    colaborador_id: int
    colaborador_nome: str
    tipo: TipoAusencia
    inicio: date
    fim: date
    observacoes: str | None
    ocorrencias_afetadas: int
    por_substituir: int


TokenOut.model_rebuild()
