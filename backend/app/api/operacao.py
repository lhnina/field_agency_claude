from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.base import obter
from app.db import get_db
from app.models import (
    Colaborador, Contrato, EstadoContrato, EstadoOcorrencia, LinhaContrato, Ocorrencia, Perfil, User,
)
from app.schemas import MoverIn, SubstituirIn
from app.security import requer
from app.services import operacao as op

router = APIRouter(tags=["operação"])


@router.get("/planeamento")
def planeamento(inicio: date | None = None, zona_id: int | None = None, cliente_id: int | None = None,
                supervisor_id: int | None = None, tipo: str | None = None,
                user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    d = inicio or date.today()
    segunda = d - timedelta(days=d.weekday())
    return op.planeamento_semana(db, user, segunda, op.FiltroPlaneamento(zona_id, cliente_id, supervisor_id, tipo))


def _oc(db: Session, oid: int, user: User) -> Ocorrencia:
    o = obter(db, Ocorrencia, oid, user)
    if user.perfil == Perfil.supervisor:
        cid = o.colaborador_id
        dono = db.get(Colaborador, cid).supervisor_id if cid else o.linha.loja.supervisor_id
        if dono != user.id:
            raise HTTPException(403, "Esta ocorrência não pertence à sua equipa")
    return o


@router.put("/ocorrencias/{oid}/colaborador")
def substituir(oid: int, body: SubstituirIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    o = _oc(db, oid, user)
    if body.colaborador_id:
        obter(db, Colaborador, body.colaborador_id, user)
    try:
        op.substituir(db, user, o, body.colaborador_id, body.motivo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"ok": True, "colaborador_id": o.colaborador_id}


@router.put("/ocorrencias/{oid}/data")
def mover(oid: int, body: MoverIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    o = _oc(db, oid, user)
    try:
        op.mover(db, user, o, body.data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"ok": True}


@router.get("/ocorrencias/{oid}/candidatos")
def candidatos(oid: int, user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    o = _oc(db, oid, user)
    res = op.candidatos(db, o)
    if user.perfil == Perfil.supervisor:
        equipa = set(db.scalars(select(Colaborador.id).where(Colaborador.supervisor_id == user.id)).all())
        res = [r for r in res if r["colaborador_id"] in equipa]
    return res


@router.get("/dashboard/operacional")
def dashboard(user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    hoje = date.today()
    seg = hoje - timedelta(days=hoje.weekday())
    sem = op.planeamento_semana(db, user, seg, op.FiltroPlaneamento())
    contratos = db.scalars(select(Contrato).where(Contrato.tenant_id == user.tenant_id,
                                                  Contrato.estado == EstadoContrato.ativo)).all()
    valor = sum((op.valor_mensal_linha(ln) for c in contratos for ln in c.linhas if ln.fim is None or ln.fim >= hoje), Decimal("0"))
    horas_mes = sum((op.horas_mes_linha(ln) for c in contratos for ln in c.linhas if ln.fim is None or ln.fim >= hoje), Decimal("0"))
    ini_mes = hoje.replace(day=1)
    prox = (ini_mes + timedelta(days=32)).replace(day=1)
    planeadas = db.scalar(select(func.coalesce(func.sum(Ocorrencia.horas_planeadas), 0)).where(
        Ocorrencia.tenant_id == user.tenant_id, Ocorrencia.data >= ini_mes, Ocorrencia.data < prox,
        Ocorrencia.estado != EstadoOcorrencia.cancelado))
    a_terminar = [c for c in contratos if c.fim and hoje <= c.fim <= hoje + timedelta(days=30)]
    return {
        "faturacao_mensal_prevista": float(valor),
        "horas_contratadas_mes": float(horas_mes),
        "horas_planeadas_mes": float(planeadas),
        "contratos_ativos": len(contratos),
        "contratos_a_terminar": [{"id": c.id, "numero": c.numero, "fim": c.fim.isoformat()} for c in a_terminar],
        "semana": sem["resumo"],
        "por_atribuir": sem["por_atribuir"][:8],
        "alertas_colaboradores": [{"id": c["id"], "nome": c["nome"], "alertas": c["alertas"]}
                                  for c in sem["colaboradores"] if c["alertas"]],
    }
