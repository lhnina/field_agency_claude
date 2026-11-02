"""Modelo de dados do MVP (incremento 1).

Unidade operacional central: Ocorrencia (um turno/visita numa data).
Contrato -> LinhaContrato (uma loja, horas por dia da semana) -> Ocorrencia.
A Afetacao liga uma linha a um colaborador de forma persistente (até ao fim);
uma Substituicao altera só o colaborador efetivo de uma ocorrência.
"""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, func, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, IdCol, TenantMixin


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(160))
    nif: Mapped[str | None] = mapped_column(String(20))
    # Parâmetros por organização
    aceitacao_tacita: Mapped[bool] = mapped_column(Boolean, default=True)
    limite_margem_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20"))
    # Encargos da agência sobre o custo/hora (TSU, seguro, proporcionais de férias e subsídios),
    # por tipo de vínculo, em %. Entram no custo das margens; não entram no apuramento salarial.
    encargos_sem_termo_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    encargos_a_termo_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    encargos_muito_curta_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    encargos_recibos_verdes_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")

    def encargos_pct(self, vinculo: "TipoVinculo") -> Decimal:
        return {
            TipoVinculo.sem_termo: self.encargos_sem_termo_pct, TipoVinculo.a_termo: self.encargos_a_termo_pct,
            TipoVinculo.muito_curta_duracao: self.encargos_muito_curta_pct,
            TipoVinculo.recibos_verdes: self.encargos_recibos_verdes_pct,
        }[vinculo] or Decimal("0")


class Perfil(str, enum.Enum):
    administrador = "administrador"
    direcao = "direcao"
    gestor = "gestor"
    supervisor = "supervisor"
    rh = "rh"
    financeiro = "financeiro"
    colaborador = "colaborador"


class User(TenantMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = IdCol()
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[Perfil] = mapped_column(Enum(Perfil, name="perfil"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- dados mestre
class Cliente(TenantMixin, Base):
    __tablename__ = "clientes"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(160))
    nif: Mapped[str | None] = mapped_column(String(20))
    codigo_phc: Mapped[int | None] = mapped_column(Integer)
    marcas: Mapped[list["Marca"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")


class Marca(TenantMixin, Base):
    __tablename__ = "marcas"
    id: Mapped[int] = IdCol()
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    cliente: Mapped[Cliente] = relationship(back_populates="marcas")


class Insignia(TenantMixin, Base):
    __tablename__ = "insignias"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))


class Zona(TenantMixin, Base):
    __tablename__ = "zonas"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))


class Loja(TenantMixin, Base):
    __tablename__ = "lojas"
    id: Mapped[int] = IdCol()
    insignia_id: Mapped[int | None] = mapped_column(ForeignKey("insignias.id"))
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id"), index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    nome: Mapped[str] = mapped_column(String(160))
    nome_credencial: Mapped[str | None] = mapped_column(String(160))
    morada: Mapped[str | None] = mapped_column(String(250))
    codigo_postal: Mapped[str | None] = mapped_column(String(10))
    localidade: Mapped[str | None] = mapped_column(String(80))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    horario_semana: Mapped[str | None] = mapped_column(String(80))
    horario_fim_semana: Mapped[str | None] = mapped_column(String(80))
    contacto_nome: Mapped[str | None] = mapped_column(String(120))
    contacto_funcao: Mapped[str | None] = mapped_column(String(80))
    contacto_email: Mapped[str | None] = mapped_column(String(160))
    contacto_telefone: Mapped[str | None] = mapped_column(String(30))
    insignia: Mapped[Insignia | None] = relationship()
    zona: Mapped[Zona | None] = relationship()


class TipoVinculo(str, enum.Enum):
    sem_termo = "sem_termo"
    a_termo = "a_termo"
    muito_curta_duracao = "muito_curta_duracao"
    recibos_verdes = "recibos_verdes"


class Colaborador(TenantMixin, Base):
    __tablename__ = "colaboradores"
    id: Mapped[int] = IdCol()
    numero: Mapped[str] = mapped_column(String(20))
    nome: Mapped[str] = mapped_column(String(160))
    funcao: Mapped[str | None] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(160))
    telefone: Mapped[str | None] = mapped_column(String(30))
    vinculo: Mapped[TipoVinculo] = mapped_column(Enum(TipoVinculo, name="tipo_vinculo"))
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim_vinculo: Mapped[date | None] = mapped_column(Date)
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id"), index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    custo_hora: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    # disponibilidade semanal: 7 caracteres '1'/'0' de segunda a domingo
    disponibilidade: Mapped[str] = mapped_column(String(7), default="1111100")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    zona: Mapped[Zona | None] = relationship()


# ---------------------------------------------------------------- contratos
class TipoContrato(str, enum.Enum):
    REP = "REP"
    PRO = "PRO"
    LOG = "LOG"
    EQF = "EQF"


class EstadoContrato(str, enum.Enum):
    proposta = "proposta"
    ativo = "ativo"
    suspenso = "suspenso"
    terminado = "terminado"


class Contrato(TenantMixin, Base):
    __tablename__ = "contratos"
    __table_args__ = (UniqueConstraint("tenant_id", "numero"),)
    id: Mapped[int] = IdCol()
    numero: Mapped[str] = mapped_column(String(30))
    tipo: Mapped[TipoContrato] = mapped_column(Enum(TipoContrato, name="tipo_contrato"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    marca_id: Mapped[int | None] = mapped_column(ForeignKey("marcas.id"))
    data: Mapped[date] = mapped_column(Date)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[EstadoContrato] = mapped_column(Enum(EstadoContrato, name="estado_contrato"), default=EstadoContrato.proposta)
    descricao: Mapped[str | None] = mapped_column(String(200))
    evento: Mapped[str | None] = mapped_column(String(160))  # promoções: ex. "Campanha de Natal"
    observacoes: Mapped[str | None] = mapped_column(Text)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    cliente: Mapped[Cliente] = relationship()
    marca: Mapped[Marca | None] = relationship()
    linhas: Mapped[list["LinhaContrato"]] = relationship(back_populates="contrato", cascade="all, delete-orphan", order_by="LinhaContrato.id")


DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")


class LinhaContrato(TenantMixin, Base):
    __tablename__ = "linhas_contrato"
    __table_args__ = tuple(CheckConstraint(f"h_{d} >= 0 AND h_{d} <= 24", name=f"ck_linha_h_{d}") for d in DIAS)
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    loja_id: Mapped[int] = mapped_column(ForeignKey("lojas.id"), index=True)
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    # Horas por dia da semana, definidas pelo colaborador/gestor (resposta Q2)
    h_seg: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_ter: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_qua: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_qui: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_sex: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_sab: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    h_dom: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))
    hora_inicio: Mapped[str | None] = mapped_column(String(5))  # promoções: "09:00"
    preco_hora: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    preco_hora_extra: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    custo_hora_especial: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # resposta Q6
    mecanica: Mapped[str | None] = mapped_column(String(80))  # promoções: degustação, amostra...
    observacoes: Mapped[str | None] = mapped_column(Text)
    contrato: Mapped[Contrato] = relationship(back_populates="linhas")
    loja: Mapped[Loja] = relationship()
    afetacoes: Mapped[list["Afetacao"]] = relationship(back_populates="linha", cascade="all, delete-orphan", order_by="Afetacao.desde")

    def horas_dia(self, weekday: int) -> Decimal:
        return getattr(self, f"h_{DIAS[weekday]}") or Decimal("0")

    @property
    def horas_semana(self) -> Decimal:
        return sum((self.horas_dia(i) for i in range(7)), Decimal("0"))


class Afetacao(TenantMixin, Base):
    """Colaborador afeto a uma linha a partir de uma data, por defeito até ao fim."""

    __tablename__ = "afetacoes"
    id: Mapped[int] = IdCol()
    linha_id: Mapped[int] = mapped_column(ForeignKey("linhas_contrato.id", ondelete="CASCADE"), index=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    desde: Mapped[date] = mapped_column(Date)
    ate: Mapped[date | None] = mapped_column(Date)
    linha: Mapped[LinhaContrato] = relationship(back_populates="afetacoes")
    colaborador: Mapped[Colaborador] = relationship()


class EstadoOcorrencia(str, enum.Enum):
    planeado = "planeado"      # sem colaborador
    atribuido = "atribuido"
    confirmado = "confirmado"
    executado = "executado"
    validado = "validado"
    rejeitado = "rejeitado"    # não realizado: 0 horas faturáveis/remuneráveis
    cancelado = "cancelado"


class OrigemExecucao(str, enum.Enum):
    registo = "registo"   # registado pelo colaborador (app, fase 3)
    manual = "manual"     # registado/corrigido no backoffice
    tacita = "tacita"     # aceitação tácita: sem registo = horas planeadas (Q4)


class Ocorrencia(TenantMixin, Base):
    __tablename__ = "ocorrencias"
    __table_args__ = (UniqueConstraint("linha_id", "data_original", name="uq_ocorrencia_linha_data"),)
    id: Mapped[int] = IdCol()
    linha_id: Mapped[int] = mapped_column(ForeignKey("linhas_contrato.id", ondelete="CASCADE"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    data_original: Mapped[date] = mapped_column(Date)  # difere de data quando foi reagendada (feriado)
    hora_inicio: Mapped[str | None] = mapped_column(String(5))
    horas_planeadas: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    horas_executadas: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    horas_aprovadas: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    colaborador_previsto_id: Mapped[int | None] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    colaborador_efetivo_id: Mapped[int | None] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    motivo_alteracao: Mapped[str | None] = mapped_column(String(200))
    reagendada_feriado: Mapped[bool] = mapped_column(Boolean, default=False)
    estado: Mapped[EstadoOcorrencia] = mapped_column(Enum(EstadoOcorrencia, name="estado_ocorrencia"), default=EstadoOcorrencia.planeado)
    origem_execucao: Mapped[OrigemExecucao | None] = mapped_column(Enum(OrigemExecucao, name="origem_execucao"))
    observacao_execucao: Mapped[str | None] = mapped_column(String(250))
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    validado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    linha: Mapped[LinhaContrato] = relationship()
    colaborador_previsto: Mapped[Colaborador | None] = relationship(foreign_keys=[colaborador_previsto_id])
    colaborador_efetivo: Mapped[Colaborador | None] = relationship(foreign_keys=[colaborador_efetivo_id])

    @property
    def colaborador_id(self) -> int | None:
        return self.colaborador_efetivo_id or self.colaborador_previsto_id


class TipoAusencia(str, enum.Enum):
    ferias = "ferias"
    falta = "falta"
    baixa = "baixa"
    indisponivel = "indisponivel"


class Ausencia(TenantMixin, Base):
    __tablename__ = "ausencias"
    id: Mapped[int] = IdCol()
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    tipo: Mapped[TipoAusencia] = mapped_column(Enum(TipoAusencia, name="tipo_ausencia"))
    inicio: Mapped[date] = mapped_column(Date)
    fim: Mapped[date] = mapped_column(Date)
    aprovada: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(String(200))
    colaborador: Mapped[Colaborador] = relationship()


class TipoPeriodo(str, enum.Enum):
    faturacao = "faturacao"
    remuneracao = "remuneracao"


class PeriodoFechado(TenantMixin, Base):
    """Fecho mensal. Faturação fecha por área; remuneração fecha o mês inteiro.
    Depois do fecho, as ocorrências abrangidas ficam imutáveis (R10/R11)."""

    __tablename__ = "periodos_fechados"
    __table_args__ = (UniqueConstraint("tenant_id", "tipo", "area", "mes", name="uq_periodo"),)
    id: Mapped[int] = IdCol()
    tipo: Mapped[TipoPeriodo] = mapped_column(Enum(TipoPeriodo, name="tipo_periodo"))
    area: Mapped[str] = mapped_column(String(3), default="*")  # REP/PRO/LOG/EQF ou * (remuneração)
    mes: Mapped[date] = mapped_column(Date)  # primeiro dia do mês
    fechado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resumo: Mapped[str | None] = mapped_column(Text)  # snapshot JSON dos totais no momento do fecho


class Feriado(Base):
    __tablename__ = "feriados"
    id: Mapped[int] = IdCol()
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"))  # null = nacional
    data: Mapped[date] = mapped_column(Date, index=True)
    nome: Mapped[str] = mapped_column(String(80))


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = IdCol()
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    entidade: Mapped[str] = mapped_column(String(60))
    entidade_id: Mapped[int] = mapped_column(Integer)
    acao: Mapped[str] = mapped_column(String(40))
    detalhe: Mapped[str | None] = mapped_column(Text)  # JSON antes/depois
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
