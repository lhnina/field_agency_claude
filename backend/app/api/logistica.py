"""Logística: viaturas e serviços logísticos (planear, atribuir, executar, validar)."""
from datetime import date
import re
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app import ambito
from app.api.base import obter
from app.db import get_db
from app.models import (
    Colaborador, Contrato, EstadoContrato, EstadoServicoLog, Loja, ServicoLogistico, Tenant, TipoContrato, TipoServicoLog,
    User, Viatura,
)
from app.security import requer
from app.services import logistica as lg
from app.services import operacao as op
from app.services.periodos import motivo_bloqueio

router = APIRouter(tags=["logística"])
HORA = r"^([01]\d|2[0-3]):[0-5]\d$"
TIPOS_COMPROVATIVO = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


# ------------------------------------------------------------------ viaturas
class ViaturaIn(BaseModel):
    matricula: str = Field(min_length=4, max_length=12)
    descricao: str | None = Field(default=None, max_length=120)
    custo_km: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    observacoes: str | None = Field(default=None, max_length=250)

    @field_validator("matricula")
    @classmethod
    def _mat(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "-")


def _viatura_json(v: Viatura, n: int = 0) -> dict:
    return {"id": v.id, "matricula": v.matricula, "descricao": v.descricao, "custo_km": float(v.custo_km),
            "observacoes": v.observacoes, "ativo": v.ativo, "servicos": n}


@router.get("/viaturas")
def viaturas(inativos: bool = False, user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    q = select(Viatura).where(Viatura.tenant_id == user.tenant_id)
    if not inativos:
        q = q.where(Viatura.ativo.is_(True))
    n = dict(db.execute(select(ServicoLogistico.viatura_id, func.count()).where(
        ServicoLogistico.tenant_id == user.tenant_id, ServicoLogistico.viatura_id.is_not(None))
        .group_by(ServicoLogistico.viatura_id)).all())
    return [_viatura_json(v, n.get(v.id, 0)) for v in db.scalars(q.order_by(Viatura.ativo.desc(), Viatura.matricula)).all()]


def _matricula_livre(db: Session, user: User, mat: str, exceto: int | None = None) -> None:
    q = select(Viatura).where(Viatura.tenant_id == user.tenant_id, Viatura.matricula == mat)
    if exceto:
        q = q.where(Viatura.id != exceto)
    if db.scalar(q):
        raise HTTPException(409, f"Já existe uma viatura com a matrícula {mat}")


@router.post("/viaturas", status_code=201)
def criar_viatura(body: ViaturaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    _matricula_livre(db, user, body.matricula)
    v = Viatura(tenant_id=user.tenant_id, **body.model_dump())
    db.add(v)
    db.flush()
    op.auditar(db, user, "viatura", v.id, "criar", body.model_dump())
    db.commit()
    return _viatura_json(v)


@router.put("/viaturas/{vid}")
def editar_viatura(vid: int, body: ViaturaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    v = obter(db, Viatura, vid, user)
    _matricula_livre(db, user, body.matricula, v.id)
    antes = _viatura_json(v)
    for k, x in body.model_dump().items():
        setattr(v, k, x)
    op.auditar(db, user, "viatura", v.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return _viatura_json(v)


@router.post("/viaturas/{vid}/estado")
def estado_viatura(vid: int, body: dict, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    v = obter(db, Viatura, vid, user)
    ativo = bool(body.get("ativo"))
    if not ativo:
        n = db.scalar(select(func.count(ServicoLogistico.id)).where(
            ServicoLogistico.viatura_id == v.id, ServicoLogistico.data >= date.today(),
            ServicoLogistico.estado.in_((EstadoServicoLog.planeado, EstadoServicoLog.atribuido)))) or 0
        if n:
            raise HTTPException(422, f"A viatura tem {n} serviço(s) por fazer: atribua-os a outra viatura antes de a desativar")
    v.ativo = ativo
    op.auditar(db, user, "viatura", v.id, "reativar" if ativo else "desativar", None)
    db.commit()
    return _viatura_json(v)


# ------------------------------------------------------------------ serviços: consulta
def _carregar(db: Session, user: User, sid: int) -> ServicoLogistico:
    s = db.scalar(select(ServicoLogistico).options(*lg.opcoes_carregar()).where(
        ServicoLogistico.id == sid, ServicoLogistico.tenant_id == user.tenant_id))
    if not s:
        raise HTTPException(404, "Serviço não encontrado")
    ambito.verificar(db, user, s)
    return s


def _lista(db: Session, user: User, q) -> list[dict]:
    servs = list(db.scalars(q.options(*lg.opcoes_carregar()).order_by(
        ServicoLogistico.data, ServicoLogistico.hora_inicio.nulls_last(), ServicoLogistico.id)).unique().all())
    permitidos = ambito.clientes_permitidos(db, user)
    zona = ambito.zona_supervisor(user)
    servs = [s for s in servs if (permitidos is None or s.contrato.cliente_id in permitidos)
             and (zona is None or ambito.servico_na_zona(s, zona))]
    tenant = db.get(Tenant, user.tenant_id)
    ctx = lg.Contexto(db, user.tenant_id, servs)
    return [lg.servico_json(s, tenant, ctx) for s in servs]


@router.get("/logistica/servicos")
def servicos(inicio: date, fim: date, estado: str | None = None, viatura_id: int | None = None,
             cliente_id: int | None = None, colaborador_id: int | None = None,
             user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    """Serviços de contratos de Logística em curso entre duas datas (os restantes veem-se no próprio contrato)."""
    q = select(ServicoLogistico).join(Contrato, ServicoLogistico.contrato_id == Contrato.id).where(
        ServicoLogistico.tenant_id == user.tenant_id, ServicoLogistico.data.between(inicio, fim),
        Contrato.estado == EstadoContrato.ativo)
    if estado == "pendentes":
        q = q.where(ServicoLogistico.estado.in_((EstadoServicoLog.planeado, EstadoServicoLog.atribuido)))
    elif estado:
        q = q.where(ServicoLogistico.estado == estado)
    if viatura_id:
        q = q.where(ServicoLogistico.viatura_id == viatura_id)
    if cliente_id:
        q = q.where(Contrato.cliente_id == cliente_id)
    if colaborador_id:
        q = q.where((ServicoLogistico.colaborador_id == colaborador_id) | (ServicoLogistico.ajudante_id == colaborador_id))
    itens = _lista(db, user, q)
    vivos = [s for s in itens if s["estado"] != "cancelado"]
    exec_ = [s for s in vivos if s["custos"]]
    return {"itens": itens, "resumo": {
        "total": len(vivos), "por_atribuir": sum(1 for s in vivos if s["estado"] == "planeado"),
        "por_executar": sum(1 for s in vivos if s["estado"] in ("planeado", "atribuido")),
        "por_validar": sum(1 for s in vivos if s["estado"] == "executado"),
        "com_alertas": sum(1 for s in vivos if s["alertas"]),
        "valor": sum(s["preco"] for s in vivos), "custo": sum(s["custos"]["total"] for s in exec_),
        "km": sum(s["custos"]["km"] for s in exec_),
    }}


@router.get("/contratos/{cid}/servicos")
def servicos_contrato(cid: int, user: User = Depends(requer("contratos.ler")), db: Session = Depends(get_db)):
    c = obter(db, Contrato, cid, user)
    return _lista(db, user, select(ServicoLogistico).where(ServicoLogistico.contrato_id == c.id))


# ------------------------------------------------------------------ serviços: planear
class ServicoIn(BaseModel):
    loja_id: int
    tipo: TipoServicoLog
    data: date
    hora_inicio: str | None = Field(default=None, pattern=HORA)
    hora_fim: str | None = Field(default=None, pattern=HORA)
    origem: str | None = Field(default=None, max_length=200)
    materiais: str | None = None
    preco: Decimal = Field(default=Decimal("0"), ge=0)
    referencia_erp: str | None = Field(default=None, max_length=40)
    observacoes: str | None = None


def _validar_servico(db: Session, user: User, c: Contrato, body: ServicoIn) -> None:
    if c.tipo != TipoContrato.LOG:
        raise HTTPException(422, "Só os contratos de Logística têm serviços logísticos")
    obter(db, Loja, body.loja_id, user)
    if body.data < c.inicio or (c.fim and body.data > c.fim):
        raise HTTPException(422, "A data do serviço tem de estar dentro da vigência do contrato")
    if body.hora_inicio and body.hora_fim and body.hora_fim <= body.hora_inicio:
        raise HTTPException(422, "A janela horária tem de terminar depois de começar")
    if (m := motivo_bloqueio(db, user.tenant_id, body.data, TipoContrato.LOG.value)):
        raise HTTPException(422, m)


def _limpo(body: ServicoIn) -> dict:
    d = body.model_dump()
    for k in ("origem", "materiais", "referencia_erp", "observacoes"):
        d[k] = (d[k] or "").strip() or None
    return d


@router.post("/contratos/{cid}/servicos", status_code=201)
def criar_servico(cid: int, body: ServicoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = obter(db, Contrato, cid, user)
    _validar_servico(db, user, c, body)
    s = ServicoLogistico(tenant_id=user.tenant_id, contrato_id=c.id, **_limpo(body))
    db.add(s)
    db.flush()
    op.auditar(db, user, "servico_logistico", s.id, "criar", body.model_dump())
    db.commit()
    return lg.servico_json(_carregar(db, user, s.id), db.get(Tenant, user.tenant_id))


@router.put("/servicos-logisticos/{sid}")
def editar_servico(sid: int, body: ServicoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    s = _carregar(db, user, sid)
    if s.estado in (EstadoServicoLog.validado, EstadoServicoLog.cancelado):
        raise HTTPException(422, "Um serviço validado ou cancelado já não pode ser alterado")
    if (m := motivo_bloqueio(db, user.tenant_id, s.data, TipoContrato.LOG.value)):
        raise HTTPException(422, m)
    _validar_servico(db, user, s.contrato, body)
    antes = lg.servico_json(s, None)
    for k, v in _limpo(body).items():
        setattr(s, k, v)
    op.auditar(db, user, "servico_logistico", s.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return lg.servico_json(_carregar(db, user, s.id), db.get(Tenant, user.tenant_id))


class AtribuirIn(BaseModel):
    viatura_id: int | None = None
    colaborador_id: int | None = None
    ajudante_id: int | None = None


@router.put("/servicos-logisticos/{sid}/atribuicao")
def atribuir(sid: int, body: AtribuirIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    """Viatura, motorista e ajudante. Com viatura e motorista o serviço fica «atribuído». Os conflitos geram alertas, não bloqueiam."""
    s = _carregar(db, user, sid)
    if s.estado not in (EstadoServicoLog.planeado, EstadoServicoLog.atribuido):
        raise HTTPException(422, "Só se altera a atribuição de serviços por executar")
    if body.viatura_id:
        v = obter(db, Viatura, body.viatura_id, user)
        if not v.ativo:
            raise HTTPException(422, "A viatura está inativa")
    for cid in (body.colaborador_id, body.ajudante_id):
        if cid:
            col = obter(db, Colaborador, cid, user)
            if op.saiu(col, s.data):
                raise HTTPException(422, f"{col.nome} sai a {col.data_saida.strftime('%d/%m/%Y')}: não pode fazer serviços depois dessa data")
    if body.ajudante_id and body.ajudante_id == body.colaborador_id:
        raise HTTPException(422, "O ajudante não pode ser o próprio motorista")
    antes = {"viatura_id": s.viatura_id, "colaborador_id": s.colaborador_id, "ajudante_id": s.ajudante_id}
    s.viatura_id, s.colaborador_id, s.ajudante_id = body.viatura_id, body.colaborador_id, body.ajudante_id
    s.estado = EstadoServicoLog.atribuido if (s.viatura_id and s.colaborador_id) else EstadoServicoLog.planeado
    op.auditar(db, user, "servico_logistico", s.id, "atribuir", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    db.expire_all()
    s = _carregar(db, user, sid)
    return lg.servico_json(s, db.get(Tenant, user.tenant_id), lg.Contexto(db, user.tenant_id, [s]))


@router.get("/servicos-logisticos/{sid}/candidatos")
def candidatos(sid: int, user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    """Viaturas e colaboradores com a ocupação do dia, para a escolha na atribuição."""
    s = _carregar(db, user, sid)
    ctx = lg.Contexto(db, user.tenant_id, [s])
    no_dia = [x for x in ctx.por_dia.get(s.data, []) if x.id != s.id]
    vs = db.scalars(select(Viatura).where(Viatura.tenant_id == user.tenant_id, Viatura.ativo.is_(True)).order_by(Viatura.matricula)).all()
    viaturas = [{"id": v.id, "matricula": v.matricula, "descricao": v.descricao, "servicos_dia": sum(1 for x in no_dia if x.viatura_id == v.id),
                 "conflito": any(x.viatura_id == v.id and lg._sobrepoe(s, x) for x in no_dia)} for v in vs]
    zona = ambito.zona_supervisor(user)
    qc = select(Colaborador).where(Colaborador.tenant_id == user.tenant_id, Colaborador.ativo.is_(True))
    if zona is not None:
        qc = qc.where(Colaborador.zona_id == zona)
    colabs = []
    for c in db.scalars(qc.order_by(Colaborador.nome)).all():
        if op.saiu(c, s.data):
            continue
        alert = []
        if ctx.ausente(c.id, s.data):
            alert.append("Ausente")
        if any(c.id in (x.colaborador_id, x.ajudante_id) and lg._sobrepoe(s, x) for x in no_dia):
            alert.append("Outro serviço à mesma hora")
        if c.disponibilidade[s.data.weekday()] != "1":
            alert.append("Indisponível neste dia")
        colabs.append({"id": c.id, "nome": c.nome, "funcao": c.funcao, "zona": c.zona.nome if c.zona else None,
                       "servicos_dia": sum(1 for x in no_dia if c.id in (x.colaborador_id, x.ajudante_id)), "alertas": alert})
    colabs.sort(key=lambda c: (bool(c["alertas"]), c["zona"] != (s.loja.zona.nome if s.loja.zona else None), c["nome"]))
    return {"viaturas": viaturas, "colaboradores": colabs}


# ------------------------------------------------------------------ execução e validação
def _num(v: str | None, nome: str, tipo=Decimal):
    if v is None or str(v).strip() == "":
        return None
    try:
        x = tipo(str(v).replace(",", "."))
    except Exception:
        raise HTTPException(422, f"{nome}: valor inválido")
    if x < 0:
        raise HTTPException(422, f"{nome}: não pode ser negativo")
    return x


@router.post("/servicos-logisticos/{sid}/execucao")
async def registar_execucao(sid: int, km_partida: str | None = Form(None), km_chegada: str | None = Form(None),
                            portagens: str | None = Form(None), outros_custos: str | None = Form(None),
                            outros_custos_desc: str | None = Form(None), inicio_real: str | None = Form(None),
                            fim_real: str | None = Form(None), observacao: str | None = Form(None),
                            comprovativo: UploadFile | None = File(None),
                            user: User = Depends(requer("validacao.editar")), db: Session = Depends(get_db)):
    """Registo do que foi feito: km, portagens, outros custos, horas e comprovativo (guia assinada, foto)."""
    s = _carregar(db, user, sid)
    if s.estado in (EstadoServicoLog.validado, EstadoServicoLog.cancelado):
        raise HTTPException(422, "Este serviço já está validado ou cancelado")
    if not s.viatura_id or not s.colaborador_id:
        raise HTTPException(422, "Atribua a viatura e o motorista antes de registar a execução")
    if s.data > date.today():
        raise HTTPException(422, "Só se regista a execução de serviços de hoje ou de dias anteriores")
    if (m := motivo_bloqueio(db, user.tenant_id, s.data, TipoContrato.LOG.value)):
        raise HTTPException(422, m)
    kp, kc = _num(km_partida, "Km de partida", int), _num(km_chegada, "Km de chegada", int)
    if kp is not None and kc is not None and kc < kp:
        raise HTTPException(422, "Os km de chegada não podem ser inferiores aos de partida")
    for h, nome in ((inicio_real, "Hora de início"), (fim_real, "Hora de fim")):
        if h and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", h):
            raise HTTPException(422, f"{nome}: use HH:MM")
    s.km_partida, s.km_chegada = kp, kc
    s.portagens, s.outros_custos = _num(portagens, "Portagens"), _num(outros_custos, "Outros custos")
    s.outros_custos_desc = (outros_custos_desc or "").strip() or None
    s.inicio_real, s.fim_real = inicio_real or None, fim_real or None
    s.observacao_execucao = (observacao or "").strip() or None
    if comprovativo is not None and comprovativo.filename:
        conteudo = await comprovativo.read()
        tipo = (comprovativo.content_type or "").lower()
        if tipo not in TIPOS_COMPROVATIVO:
            raise HTTPException(422, "O comprovativo tem de ser PDF ou imagem")
        if len(conteudo) > 10 * 1024 * 1024:
            raise HTTPException(422, "O comprovativo não pode ter mais de 10 MB")
        s.comprovativo, s.comprovativo_nome, s.comprovativo_tipo = conteudo, comprovativo.filename[:200], tipo
    s.estado = EstadoServicoLog.executado
    s.executado_por_id = user.id
    op.auditar(db, user, "servico_logistico", s.id, "executar", {"km": lg.km(s), "portagens": portagens, "horas": float(lg.horas_execucao(s))})
    db.commit()
    db.expire_all()
    s = _carregar(db, user, sid)
    return lg.servico_json(s, db.get(Tenant, user.tenant_id))


class ValidarIn(BaseModel):
    ids: list[int]
    aprovar: bool = True
    motivo: str | None = None


@router.post("/servicos-logisticos/validar")
def validar(body: ValidarIn, user: User = Depends(requer("validacao.editar")), db: Session = Depends(get_db)):
    """Aprovar: o serviço passa a validado (conta para faturação e custos). Rejeitar: volta a «atribuído» para novo registo."""
    if not body.aprovar and not (body.motivo or "").strip():
        raise HTTPException(422, "Indique o motivo da rejeição")
    n = 0
    for sid in body.ids:
        s = _carregar(db, user, sid)
        if s.estado != EstadoServicoLog.executado:
            continue
        if (m := motivo_bloqueio(db, user.tenant_id, s.data, TipoContrato.LOG.value)):
            raise HTTPException(422, m)
        if body.aprovar:
            s.estado, s.validado_por_id = EstadoServicoLog.validado, user.id
        else:
            s.estado, s.motivo = EstadoServicoLog.atribuido, body.motivo.strip()
        op.auditar(db, user, "servico_logistico", s.id, "validar" if body.aprovar else "rejeitar", {"motivo": body.motivo})
        n += 1
    db.commit()
    return {"processados": n}


class CancelarIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=250)


@router.post("/servicos-logisticos/{sid}/cancelar")
def cancelar(sid: int, body: CancelarIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    s = _carregar(db, user, sid)
    if s.estado == EstadoServicoLog.validado:
        raise HTTPException(422, "Um serviço validado não pode ser cancelado")
    if (m := motivo_bloqueio(db, user.tenant_id, s.data, TipoContrato.LOG.value)):
        raise HTTPException(422, m)
    s.estado, s.motivo = EstadoServicoLog.cancelado, body.motivo.strip()
    op.auditar(db, user, "servico_logistico", s.id, "cancelar", {"motivo": s.motivo})
    db.commit()
    return {"ok": True}


@router.get("/servicos-logisticos/{sid}/comprovativo")
def comprovativo(sid: int, user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    s = _carregar(db, user, sid)
    s = db.scalar(select(ServicoLogistico).options(undefer(ServicoLogistico.comprovativo)).where(ServicoLogistico.id == s.id))
    if not s.comprovativo:
        raise HTTPException(404, "Sem comprovativo")
    op.auditar(db, user, "servico_logistico", s.id, "ver_comprovativo", None)
    db.commit()
    return Response(s.comprovativo, media_type=s.comprovativo_tipo or "application/octet-stream",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(s.comprovativo_nome or 'comprovativo')}",
                             "Cache-Control": "no-store"})


@router.get("/dashboard/logistica")
def dashboard(user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    hoje = date.today()
    q = select(ServicoLogistico).join(Contrato, ServicoLogistico.contrato_id == Contrato.id).where(
        ServicoLogistico.tenant_id == user.tenant_id, Contrato.estado == EstadoContrato.ativo,
        ServicoLogistico.estado != EstadoServicoLog.cancelado, ServicoLogistico.data.between(hoje, date.fromordinal(hoje.toordinal() + 6)))
    itens = _lista(db, user, q)
    return {"proximos_7_dias": len(itens), "hoje": sum(1 for s in itens if s["data"] == hoje.isoformat()),
            "por_atribuir": sum(1 for s in itens if s["estado"] == "planeado"),
            "com_alertas": sum(1 for s in itens if s["alertas"])}

