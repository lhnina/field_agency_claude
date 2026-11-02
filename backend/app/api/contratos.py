from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.base import obter
from app.config import settings
from app.db import get_db
from app.models import (
    Afetacao, Cliente, Colaborador, Contrato, EstadoContrato, LinhaContrato, Loja, Marca, Perfil, User,
)
from app.schemas import (
    AfetacaoOut, AfetarIn, ContratoIn, ContratoOut, ContratoResumo, EstadoIn, GerarIn, LinhaIn, LinhaOut,
)
from app.security import requer
from app.services import operacao as op

router = APIRouter(tags=["contratos"])


def _af_out(a: Afetacao) -> AfetacaoOut:
    return AfetacaoOut(id=a.id, colaborador_id=a.colaborador_id, colaborador_nome=a.colaborador.nome, desde=a.desde, ate=a.ate)


def _linha_out(ln: LinhaContrato, hoje: date) -> LinhaOut:
    atual = op.afetacao_em(ln, max(hoje, ln.inicio))
    return LinhaOut(
        id=ln.id, loja_id=ln.loja_id, loja_nome=ln.loja.nome,
        loja_insignia=ln.loja.insignia.nome if ln.loja.insignia else None,
        loja_zona=ln.loja.zona.nome if ln.loja.zona else None,
        inicio=ln.inicio, fim=ln.fim, h_seg=ln.h_seg, h_ter=ln.h_ter, h_qua=ln.h_qua, h_qui=ln.h_qui, h_sex=ln.h_sex,
        h_sab=ln.h_sab, h_dom=ln.h_dom, hora_inicio=ln.hora_inicio, preco_hora=ln.preco_hora,
        preco_hora_extra=ln.preco_hora_extra, custo_hora_especial=ln.custo_hora_especial, mecanica=ln.mecanica,
        observacoes=ln.observacoes, horas_semana=ln.horas_semana, horas_mes=op.horas_mes_linha(ln),
        valor_mensal=op.valor_mensal_linha(ln), afetacao_atual=_af_out(atual) if atual else None,
        afetacoes=[_af_out(a) for a in ln.afetacoes],
    )


def _ativas(c: Contrato, hoje: date) -> list[LinhaContrato]:
    return [ln for ln in c.linhas if ln.fim is None or ln.fim >= hoje]


def _resumo(c: Contrato, hoje: date) -> dict:
    ativas = _ativas(c, hoje)
    hs = sum((ln.horas_semana for ln in ativas), Decimal("0"))
    return dict(
        id=c.id, numero=c.numero, tipo=c.tipo, estado=c.estado, cliente_id=c.cliente_id, cliente_nome=c.cliente.nome,
        marca_nome=c.marca.nome if c.marca else None, descricao=c.descricao, evento=c.evento, data=c.data,
        inicio=c.inicio, fim=c.fim, versao=c.versao, n_linhas=len(ativas), horas_semana=hs,
        horas_mes=op.q2(hs * op.SEMANAS_POR_MES),
        valor_mensal=sum((op.valor_mensal_linha(ln) for ln in ativas), Decimal("0")),
        linhas_por_atribuir=sum(1 for ln in ativas if op.afetacao_em(ln, max(hoje, ln.inicio)) is None),
    )


def _carregar(db: Session, cid: int, user: User) -> Contrato:
    c = db.scalar(select(Contrato).options(
        selectinload(Contrato.linhas).selectinload(LinhaContrato.afetacoes).selectinload(Afetacao.colaborador),
        selectinload(Contrato.linhas).selectinload(LinhaContrato.loja).selectinload(Loja.insignia),
        selectinload(Contrato.linhas).selectinload(LinhaContrato.loja).selectinload(Loja.zona),
    ).where(Contrato.id == cid, Contrato.tenant_id == user.tenant_id))
    if not c:
        raise HTTPException(404, "Contrato não encontrado")
    return c


def _out(c: Contrato) -> ContratoOut:
    hoje = date.today()
    return ContratoOut(**_resumo(c, hoje), marca_id=c.marca_id, observacoes=c.observacoes,
                       linhas=[_linha_out(ln, hoje) for ln in c.linhas])


def _horizonte() -> date:
    return date.today() + timedelta(days=settings.horizonte_planeamento_dias)


@router.get("/contratos", response_model=list[ContratoResumo])
def listar(tipo: str | None = None, estado: str | None = None, cliente_id: int | None = None, q: str | None = None,
           user: User = Depends(requer("contratos.ler")), db: Session = Depends(get_db)):
    s = select(Contrato).options(selectinload(Contrato.linhas).selectinload(LinhaContrato.afetacoes)).where(
        Contrato.tenant_id == user.tenant_id)
    if tipo:
        s = s.where(Contrato.tipo == tipo)
    if estado:
        s = s.where(Contrato.estado == estado)
    if cliente_id:
        s = s.where(Contrato.cliente_id == cliente_id)
    hoje = date.today()
    out = [ContratoResumo(**_resumo(c, hoje)) for c in db.scalars(s.order_by(Contrato.numero.desc())).all()]
    if q:
        ql = q.lower()
        out = [c for c in out if ql in c.numero.lower() or ql in c.cliente_nome.lower() or ql in (c.marca_nome or "").lower()]
    return sorted(out, key=lambda c: -c.valor_mensal)


@router.get("/contratos/{cid}", response_model=ContratoOut)
def detalhe(cid: int, user: User = Depends(requer("contratos.ler")), db: Session = Depends(get_db)):
    return _out(_carregar(db, cid, user))


@router.post("/contratos", response_model=ContratoOut, status_code=201)
def criar(body: ContratoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    obter(db, Cliente, body.cliente_id, user)
    if body.marca_id:
        m = obter(db, Marca, body.marca_id, user)
        if m.cliente_id != body.cliente_id:
            raise HTTPException(422, "A marca não pertence ao cliente indicado")
    c = Contrato(tenant_id=user.tenant_id, numero=op.proximo_numero(db, user.tenant_id, body.tipo.value, body.data.year),
                 **body.model_dump())
    db.add(c)
    db.flush()
    op.auditar(db, user, "contrato", c.id, "criar", body.model_dump())
    db.commit()
    return _out(_carregar(db, c.id, user))


@router.put("/contratos/{cid}", response_model=ContratoOut)
def editar(cid: int, body: ContratoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _carregar(db, cid, user)
    if body.tipo != c.tipo:
        raise HTTPException(422, "O tipo de contrato não pode ser alterado")
    antes = {k: getattr(c, k) for k in body.model_dump()}
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    c.versao += 1
    op.auditar(db, user, "contrato", c.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.flush()
    if c.estado == EstadoContrato.ativo:
        for ln in c.linhas:
            op.regenerar_futuras(db, ln, max(date.today(), ln.inicio), _horizonte())
    db.commit()
    return _out(_carregar(db, cid, user))


@router.post("/contratos/{cid}/estado", response_model=ContratoOut)
def mudar_estado(cid: int, body: EstadoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _carregar(db, cid, user)
    if body.estado == EstadoContrato.ativo and not c.linhas:
        raise HTTPException(422, "Um contrato sem linhas não pode ser ativado")
    op.auditar(db, user, "contrato", c.id, "estado", {"de": c.estado, "para": body.estado})
    c.estado = body.estado
    db.flush()
    if c.estado == EstadoContrato.ativo:
        for ln in c.linhas:
            op.gerar_ocorrencias(db, ln, ate=_horizonte())
    db.commit()
    return _out(_carregar(db, cid, user))


# ---------------------------------------------------------------- linhas
@router.post("/contratos/{cid}/linhas", response_model=ContratoOut, status_code=201)
def criar_linha(cid: int, body: LinhaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _carregar(db, cid, user)
    obter(db, Loja, body.loja_id, user)
    if body.inicio < c.inicio or (c.fim and body.inicio > c.fim):
        raise HTTPException(422, "O início da linha tem de estar dentro da vigência do contrato")
    ln = LinhaContrato(tenant_id=user.tenant_id, **body.model_dump())
    c.linhas.append(ln)
    db.flush()
    op.auditar(db, user, "linha_contrato", ln.id, "criar", body.model_dump())
    db.refresh(ln)
    op.gerar_ocorrencias(db, ln, ate=_horizonte())
    db.commit()
    return _out(_carregar(db, cid, user))


@router.put("/linhas/{lid}", response_model=ContratoOut)
def editar_linha(lid: int, body: LinhaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    ln = obter(db, LinhaContrato, lid, user)
    antes = {k: getattr(ln, k) for k in body.model_dump()}
    for k, v in body.model_dump().items():
        setattr(ln, k, v)
    ln.contrato.versao += 1
    op.auditar(db, user, "linha_contrato", ln.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.flush()
    op.regenerar_futuras(db, ln, max(date.today(), ln.inicio), _horizonte())
    db.commit()
    return _out(_carregar(db, ln.contrato_id, user))


@router.post("/linhas/{lid}/afetacao", response_model=ContratoOut)
def afetar(lid: int, body: AfetarIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    ln = obter(db, LinhaContrato, lid, user)
    col = obter(db, Colaborador, body.colaborador_id, user)
    if user.perfil == Perfil.supervisor and col.supervisor_id != user.id:
        raise HTTPException(403, "Só pode afetar colaboradores da sua equipa")
    try:
        op.afetar(db, user, ln, col, body.desde, body.ate)
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return _out(_carregar(db, ln.contrato_id, user))


@router.delete("/linhas/{lid}/afetacao", response_model=ContratoOut)
def remover_afetacao(lid: int, desde: date, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    ln = obter(db, LinhaContrato, lid, user)
    op.remover_afetacao(db, user, ln, desde)
    db.commit()
    return _out(_carregar(db, ln.contrato_id, user))


@router.post("/contratos/{cid}/gerar")
def gerar(cid: int, body: GerarIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _carregar(db, cid, user)
    if c.estado != EstadoContrato.ativo:
        raise HTTPException(422, "Só contratos ativos geram ocorrências")
    n = sum(op.gerar_ocorrencias(db, ln, ate=body.ate or _horizonte()) for ln in c.linhas)
    db.commit()
    return {"criadas": n}
