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
    Boolean, CheckConstraint, Date, DateTime, Enum, func, ForeignKey, Integer, LargeBinary, Numeric, String, Text,
    UniqueConstraint,
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
    # Dados da empresa usados nas credenciais
    morada: Mapped[str | None] = mapped_column(String(250))
    codigo_postal: Mapped[str | None] = mapped_column(String(10))
    localidade: Mapped[str | None] = mapped_column(String(80))
    registo_comercial: Mapped[str | None] = mapped_column(String(250))
    seguradora: Mapped[str | None] = mapped_column(String(160))
    apolice: Mapped[str | None] = mapped_column(String(60))
    apolice_validade: Mapped[date | None] = mapped_column(Date)

    def encargos_pct(self, vinculo: "TipoVinculo", muito_curta: bool = False) -> Decimal:
        if muito_curta and vinculo != TipoVinculo.recibos_verdes:
            return self.encargos_muito_curta_pct or Decimal("0")
        return {
            TipoVinculo.sem_termo: self.encargos_sem_termo_pct, TipoVinculo.a_termo: self.encargos_a_termo_pct,
            TipoVinculo.recibos_verdes: self.encargos_recibos_verdes_pct,
        }[vinculo] or Decimal("0")

    def encargos_colaborador(self, c: "Colaborador") -> Decimal:
        return self.encargos_pct(c.vinculo, c.muito_curta_duracao)


class Perfil(str, enum.Enum):
    administrador = "administrador"
    direcao = "direcao"
    gestor = "gestor"
    gestor_conta = "gestor_conta"  # como o gestor, mas só nos clientes de que é gestor de conta
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
    # Supervisor: zona que supervisiona (vazio = TODAS as zonas)
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id"))
    zona: Mapped["Zona | None"] = relationship()


# ---------------------------------------------------------------- dados mestre
class Cliente(TenantMixin, Base):
    __tablename__ = "clientes"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(160))
    nif: Mapped[str | None] = mapped_column(String(20))
    codigo_erp: Mapped[int | None] = mapped_column(Integer)
    morada: Mapped[str | None] = mapped_column(String(250))
    codigo_postal: Mapped[str | None] = mapped_column(String(10))
    localidade: Mapped[str | None] = mapped_column(String(80))
    telefone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(160))
    url: Mapped[str | None] = mapped_column(String(250))
    contacto_nome: Mapped[str | None] = mapped_column(String(120))
    gestor_conta_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    marcas: Mapped[list["Marca"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")
    gestor_conta: Mapped["User | None"] = relationship(foreign_keys=[gestor_conta_id])


class Marca(TenantMixin, Base):
    __tablename__ = "marcas"
    id: Mapped[int] = IdCol()
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(160))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cliente: Mapped[Cliente] = relationship(back_populates="marcas")


class Insignia(TenantMixin, Base):
    __tablename__ = "insignias"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Logótipo da cadeia (miniatura nas grelhas de lojas). logo_v muda a cada novo logótipo (cache do browser).
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    logo_tipo: Mapped[str | None] = mapped_column(String(60))
    logo_v: Mapped[int | None] = mapped_column(Integer)


class Funcao(TenantMixin, Base):
    """Funções dos colaboradores (Repositor(a), Promotor(a)…). Tabela única para não haver variantes do mesmo nome."""
    __tablename__ = "funcoes"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Zona(TenantMixin, Base):
    __tablename__ = "zonas"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Loja(TenantMixin, Base):
    __tablename__ = "lojas"
    id: Mapped[int] = IdCol()
    insignia_id: Mapped[int | None] = mapped_column(ForeignKey("insignias.id"))
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id"), index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    nome: Mapped[str] = mapped_column(String(160))
    codigo_erp: Mapped[str | None] = mapped_column(String(30), index=True)
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
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    insignia: Mapped[Insignia | None] = relationship()
    zona: Mapped[Zona | None] = relationship()


class TipoVinculo(str, enum.Enum):
    sem_termo = "sem_termo"
    a_termo = "a_termo"
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
    # Tipo de contrato de trabalho (não é um vínculo): contrato de muito curta duração.
    muito_curta_duracao: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Datas laborais (não se aplicam a recibos verdes)
    data_admissao: Mapped[date | None] = mapped_column(Date)
    data_saida: Mapped[date | None] = mapped_column(Date)
    data_inicio: Mapped[date | None] = mapped_column(Date)  # início do contrato atual
    data_fim_vinculo: Mapped[date | None] = mapped_column(Date)  # fim do contrato atual
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id"), index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    custo_hora: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0"))
    # disponibilidade semanal: 7 caracteres '1'/'0' de segunda a domingo
    disponibilidade: Mapped[str] = mapped_column(String(7), default="1111100")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Identificação (credenciais). Dados pessoais: acesso restrito (RGPD).
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    numero_identificacao: Mapped[str | None] = mapped_column(String(30))
    niss: Mapped[str | None] = mapped_column(String(20))
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
    # Equipas Fixas: valor de gestão mensal por colaborador (por omissão) e acréscimo nas despesas refaturadas
    valor_gestao: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    acrescimo_despesas_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
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


# ---------------------------------------------------------------- documentação
class TipoDocumento(TenantMixin, Base):
    """Tipo de documento controlado pela agência (cartão de cidadão, formação HACCP, registo criminal…)."""
    __tablename__ = "tipos_documento"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))
    tem_validade: Mapped[bool] = mapped_column(Boolean, default=True)
    dias_aviso: Mapped[int] = mapped_column(Integer, default=30)  # avisa X dias antes de expirar
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class RequisitoDocumental(TenantMixin, Base):
    """Documento obrigatório. Campos vazios = qualquer: sem função, cliente nem insígnia aplica-se a todos.
    Com cliente/insígnia aplica-se a quem presta serviço nesse cliente/cadeia."""
    __tablename__ = "requisitos_documentais"
    id: Mapped[int] = IdCol()
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"), index=True)
    funcao: Mapped[str | None] = mapped_column(String(80))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"))
    insignia_id: Mapped[int | None] = mapped_column(ForeignKey("insignias.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    tipo: Mapped[TipoDocumento] = relationship()
    cliente: Mapped["Cliente | None"] = relationship()
    insignia: Mapped["Insignia | None"] = relationship()


class DocumentoColaborador(TenantMixin, Base):
    """Documento entregue por um colaborador. Ao renovar, o anterior fica no histórico (atual=False)."""
    __tablename__ = "documentos_colaborador"
    id: Mapped[int] = IdCol()
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"), index=True)
    numero: Mapped[str | None] = mapped_column(String(80))
    emissao: Mapped[date | None] = mapped_column(Date)
    validade: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(String(250))
    atual: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ficheiro_nome: Mapped[str | None] = mapped_column(String(200))
    ficheiro_tipo: Mapped[str | None] = mapped_column(String(100))
    ficheiro_tamanho: Mapped[int | None] = mapped_column(Integer)
    # Conteúdo do anexo: carregado só quando é descarregado (deferred)
    ficheiro: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    colaborador: Mapped[Colaborador] = relationship()
    tipo: Mapped[TipoDocumento] = relationship()


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
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"))  # null = nacional (legado; hoje calculados)
    zona_id: Mapped[int | None] = mapped_column(ForeignKey("zonas.id", ondelete="CASCADE"))  # feriado municipal
    data: Mapped[date] = mapped_column(Date, index=True)
    nome: Mapped[str] = mapped_column(String(80))
    zona: Mapped[Zona | None] = relationship()


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


# ---------------------------------------------------------------- credenciais
class ModeloCredencial(TenantMixin, Base):
    """Modelo Word (.docx) da credencial. Cada novo carregamento com o mesmo nome é uma nova versão;
    as versões anteriores ficam guardadas (as credenciais emitidas apontam para a versão usada)."""
    __tablename__ = "modelos_credencial"
    id: Mapped[int] = IdCol()
    nome: Mapped[str] = mapped_column(String(120))
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"))  # vazio = modelo geral
    versao: Mapped[int] = mapped_column(Integer, default=1)
    atual: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notas: Mapped[str | None] = mapped_column(String(250))
    ficheiro_nome: Mapped[str] = mapped_column(String(200))
    ficheiro_tamanho: Mapped[int] = mapped_column(Integer, default=0)
    ficheiro: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cliente: Mapped[Cliente | None] = relationship()
    criado_por: Mapped[User | None] = relationship()


class EstadoCredencial(str, enum.Enum):
    emitida = "emitida"
    substituida = "substituida"
    anulada = "anulada"


class Credencial(TenantMixin, Base):
    """Credencial emitida para um colaborador numa loja (a partir de uma versão de modelo)."""
    __tablename__ = "credenciais"
    id: Mapped[int] = IdCol()
    numero: Mapped[str] = mapped_column(String(20), index=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    linha_id: Mapped[int | None] = mapped_column(ForeignKey("linhas_contrato.id"))
    loja_id: Mapped[int] = mapped_column(ForeignKey("lojas.id"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), index=True)
    modelo_id: Mapped[int] = mapped_column(ForeignKey("modelos_credencial.id"))
    emitida_em: Mapped[date] = mapped_column(Date)
    valida_ate: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[EstadoCredencial] = mapped_column(Enum(EstadoCredencial, name="estado_credencial"), default=EstadoCredencial.emitida)
    substitui_id: Mapped[int | None] = mapped_column(ForeignKey("credenciais.id"))
    motivo: Mapped[str | None] = mapped_column(String(250))
    dados: Mapped[str | None] = mapped_column(Text)  # JSON dos valores usados
    ficheiro_nome: Mapped[str] = mapped_column(String(200))
    ficheiro: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    colaborador: Mapped[Colaborador] = relationship()
    loja: Mapped[Loja] = relationship()
    cliente: Mapped[Cliente] = relationship()
    modelo: Mapped[ModeloCredencial] = relationship()
    substitui: Mapped["Credencial | None"] = relationship(remote_side="Credencial.id")


# ---------------------------------------------------------------- logística
class Viatura(TenantMixin, Base):
    """Viatura da agência. Uma viatura faz serviços para vários clientes e lojas."""
    __tablename__ = "viaturas"
    id: Mapped[int] = IdCol()
    matricula: Mapped[str] = mapped_column(String(12))
    descricao: Mapped[str | None] = mapped_column(String(120))  # marca/modelo, tipo de caixa
    custo_km: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))  # €/km (combustível, desgaste)
    observacoes: Mapped[str | None] = mapped_column(String(250))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TipoServicoLog(str, enum.Enum):
    entrega = "entrega"
    recolha = "recolha"
    implementacao = "implementacao"
    entrega_implementacao = "entrega_implementacao"
    desmontagem = "desmontagem"


class EstadoServicoLog(str, enum.Enum):
    planeado = "planeado"      # sem viatura/motorista
    atribuido = "atribuido"    # com viatura e motorista
    executado = "executado"    # registo de execução feito
    validado = "validado"      # validado pelo gestor: conta para faturação e custos
    cancelado = "cancelado"


class ServicoLogistico(TenantMixin, Base):
    """Linha de um contrato de Logística: um serviço pontual numa loja, numa data (entrega, recolha, implementação…)."""
    __tablename__ = "servicos_logisticos"
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    loja_id: Mapped[int] = mapped_column(ForeignKey("lojas.id"), index=True)
    tipo: Mapped[TipoServicoLog] = mapped_column(Enum(TipoServicoLog, name="tipo_servico_log"))
    data: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[str | None] = mapped_column(String(5))  # janela horária
    hora_fim: Mapped[str | None] = mapped_column(String(5))
    origem: Mapped[str | None] = mapped_column(String(200))     # armazém / morada de origem
    materiais: Mapped[str | None] = mapped_column(Text)
    preco: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))  # valor de faturação do serviço
    referencia_erp: Mapped[str | None] = mapped_column(String(40), index=True)    # pedido/guia no ERP
    observacoes: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[EstadoServicoLog] = mapped_column(Enum(EstadoServicoLog, name="estado_servico_log"), default=EstadoServicoLog.planeado)
    # atribuição
    viatura_id: Mapped[int | None] = mapped_column(ForeignKey("viaturas.id"), index=True)
    colaborador_id: Mapped[int | None] = mapped_column(ForeignKey("colaboradores.id"), index=True)  # motorista
    ajudante_id: Mapped[int | None] = mapped_column(ForeignKey("colaboradores.id"))
    # execução
    km_partida: Mapped[int | None] = mapped_column(Integer)
    km_chegada: Mapped[int | None] = mapped_column(Integer)
    portagens: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    outros_custos: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    outros_custos_desc: Mapped[str | None] = mapped_column(String(200))
    inicio_real: Mapped[str | None] = mapped_column(String(5))
    fim_real: Mapped[str | None] = mapped_column(String(5))
    observacao_execucao: Mapped[str | None] = mapped_column(String(250))
    comprovativo_nome: Mapped[str | None] = mapped_column(String(200))
    comprovativo_tipo: Mapped[str | None] = mapped_column(String(100))
    comprovativo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    executado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    motivo: Mapped[str | None] = mapped_column(String(250))  # cancelamento / rejeição
    contrato: Mapped[Contrato] = relationship()
    loja: Mapped[Loja] = relationship()
    viatura: Mapped[Viatura | None] = relationship()
    colaborador: Mapped[Colaborador | None] = relationship(foreign_keys=[colaborador_id])
    ajudante: Mapped[Colaborador | None] = relationship(foreign_keys=[ajudante_id])


# ---------------------------------------------------------------- equipas fixas
class RotaEquipa(TenantMixin, Base):
    """Rota de uma equipa fixa: um conjunto ordenado de lojas visitadas num dia."""
    __tablename__ = "rotas_equipa"
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    lojas: Mapped[list["RotaLoja"]] = relationship(cascade="all, delete-orphan", order_by="RotaLoja.ordem")


class RotaLoja(Base):
    __tablename__ = "rotas_lojas"
    id: Mapped[int] = IdCol()
    rota_id: Mapped[int] = mapped_column(ForeignKey("rotas_equipa.id", ondelete="CASCADE"), index=True)
    loja_id: Mapped[int] = mapped_column(ForeignKey("lojas.id"), index=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    loja: Mapped[Loja] = relationship()


class ElementoEquipa(TenantMixin, Base):
    """Colaborador de uma equipa fixa, com a escala semanal (rota e horário por dia)."""
    __tablename__ = "elementos_equipa"
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)
    desde: Mapped[date] = mapped_column(Date)
    ate: Mapped[date | None] = mapped_column(Date)
    valor_gestao: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # vazio = o do contrato
    observacoes: Mapped[str | None] = mapped_column(Text)
    colaborador: Mapped[Colaborador] = relationship()
    escala: Mapped[list["EscalaEquipa"]] = relationship(cascade="all, delete-orphan", order_by="EscalaEquipa.dia")


class EscalaEquipa(Base):
    __tablename__ = "escalas_equipa"
    __table_args__ = (UniqueConstraint("elemento_id", "dia"), CheckConstraint("dia >= 0 AND dia <= 6", name="ck_escala_dia"))
    id: Mapped[int] = IdCol()
    elemento_id: Mapped[int] = mapped_column(ForeignKey("elementos_equipa.id", ondelete="CASCADE"), index=True)
    dia: Mapped[int] = mapped_column(Integer)  # 0 = segunda
    rota_id: Mapped[int] = mapped_column(ForeignKey("rotas_equipa.id"))
    hora_inicio: Mapped[str] = mapped_column(String(5))
    hora_fim: Mapped[str] = mapped_column(String(5))
    pausa_min: Mapped[int] = mapped_column(Integer, default=60)
    rota: Mapped[RotaEquipa] = relationship()


class EstadoServicoEquipa(str, enum.Enum):
    planeado = "planeado"
    validado = "validado"   # horas confirmadas: contam para custo, faturação e remuneração
    falta = "falta"         # não trabalhou (ausência): 0 horas
    cancelado = "cancelado"


class ServicoEquipa(TenantMixin, Base):
    """Dia de trabalho de um elemento da equipa fixa (gerado a partir da escala)."""
    __tablename__ = "servicos_equipa"
    __table_args__ = (UniqueConstraint("elemento_id", "data"),)
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    elemento_id: Mapped[int] = mapped_column(ForeignKey("elementos_equipa.id", ondelete="CASCADE"), index=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("colaboradores.id"), index=True)  # quem faz (pode ser substituto)
    rota_id: Mapped[int | None] = mapped_column(ForeignKey("rotas_equipa.id"))
    data: Mapped[date] = mapped_column(Date, index=True)
    hora_inicio: Mapped[str] = mapped_column(String(5))
    hora_fim: Mapped[str] = mapped_column(String(5))
    pausa_min: Mapped[int] = mapped_column(Integer, default=60)
    horas_planeadas: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    horas_reais: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estado: Mapped[EstadoServicoEquipa] = mapped_column(Enum(EstadoServicoEquipa, name="estado_servico_equipa"),
                                                        default=EstadoServicoEquipa.planeado)
    alterado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # mexido à mão: a escala não o regenera
    observacao: Mapped[str | None] = mapped_column(String(250))
    validado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    contrato: Mapped[Contrato] = relationship()
    elemento: Mapped[ElementoEquipa] = relationship()
    colaborador: Mapped[Colaborador] = relationship()
    rota: Mapped[RotaEquipa | None] = relationship()


class DespesaEquipa(TenantMixin, Base):
    """Despesa de uma equipa fixa (viatura, combustível, portagens, telemóvel…), refaturada ao cliente."""
    __tablename__ = "despesas_equipa"
    id: Mapped[int] = IdCol()
    contrato_id: Mapped[int] = mapped_column(ForeignKey("contratos.id", ondelete="CASCADE"), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    descricao: Mapped[str | None] = mapped_column(String(200))
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    elemento_id: Mapped[int | None] = mapped_column(ForeignKey("elementos_equipa.id", ondelete="SET NULL"))
    refaturar: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    registado_por_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    elemento: Mapped[ElementoEquipa | None] = relationship()
