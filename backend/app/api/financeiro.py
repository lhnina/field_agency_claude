from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.base import obter
from app.db import get_db
from app.models import (
    Colaborador, Contrato, EstadoOcorrencia, LinhaContrato, Ocorrencia, Perfil, TipoContrato, TipoPeriodo, User,
)
from app.security import requer
from app.services import fecho
from app.services.periodos import PeriodoFechadoErro, motivo_bloqueio

router = APIRouter()


def hoje() -> date:
    return date.today()


def _mes(s: str) -> date:
    try:
        y, m = s.split("-")[:2]
        return date(int(y), int(m), 1)
    except Exception:
        raise HTTPException(422, "Mês inválido (formato AAAA-MM)")


# ------------------------------------------------------------------ validação de horas
class ExecucaoIn(BaseModel):
    horas: Decimal = Field(ge=0, le=24)
    observacao: str | None = Field(default=None, max_length=250)


class ValidarIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=2000)
    aprovar: bool = True
    motivo: str | None = Field(default=None, max_length=250)


ESTADOS_FILTRO = {
    "por_validar": (EstadoOcorrencia.atribuido, EstadoOcorrencia.confirmado, EstadoOcorrencia.executado),
    "validadas": (EstadoOcorrencia.validado,),
    "rejeitadas": (EstadoOcorrencia.rejeitado,),
}


def _equipa(db: Session, user: User) -> set[int] | None:
    if user.perfil != Perfil.supervisor:
        return None
    return set(db.scalars(select(Colaborador.id).where(Colaborador.supervisor_id == user.id)).all())


@router.get("/validacao", tags=["validação"])
def listar_validacao(inicio: date | None = None, fim: date | None = None, estado: str = "por_validar",
                     colaborador_id: int | None = None, cliente_id: int | None = None,
                     user: User = Depends(requer("validacao.ler")), db: Session = Depends(get_db)):
    h = hoje()
    # aceitação tácita aplicada até ontem antes de mostrar a lista (idempotente)
    if fecho.aplicar_aceitacao_tacita(db, user.tenant_id, h - timedelta(days=1)):
        db.commit()
    fim = min(fim or h, h)
    inicio = inicio or fim.replace(day=1)
    q = (select(Ocorrencia).join(LinhaContrato).join(Contrato)
         .options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.loja),
                  joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato).joinedload(Contrato.cliente))
         .where(Ocorrencia.tenant_id == user.tenant_id, Ocorrencia.data.between(inicio, fim),
                Ocorrencia.estado.in_(ESTADOS_FILTRO.get(estado, ESTADOS_FILTRO["por_validar"])),
                or_(Ocorrencia.colaborador_previsto_id.is_not(None), Ocorrencia.colaborador_efetivo_id.is_not(None))))
    if cliente_id:
        q = q.where(Contrato.cliente_id == cliente_id)
    ocs = db.scalars(q.order_by(Ocorrencia.data, Ocorrencia.id)).unique().all()
    equipa = _equipa(db, user)
    nomes = {c.id: c for c in db.scalars(select(Colaborador).where(Colaborador.tenant_id == user.tenant_id)).all()}
    out = []
    for o in ocs:
        cid = o.colaborador_id
        if equipa is not None and cid not in equipa:
            continue
        if colaborador_id and cid != colaborador_id:
            continue
        diff = None if o.horas_executadas is None else float(o.horas_executadas - o.horas_planeadas)
        bloqueio = motivo_bloqueio(db, user.tenant_id, o.data, o.linha.contrato.tipo.value)
        out.append({
            "id": o.id, "data": o.data.isoformat(), "colaborador_id": cid, "colaborador": nomes[cid].nome,
            "loja": o.linha.loja.nome, "cliente": o.linha.contrato.cliente.nome, "tipo": o.linha.contrato.tipo.value,
            "contrato_numero": o.linha.contrato.numero, "horas_planeadas": float(o.horas_planeadas),
            "horas_executadas": None if o.horas_executadas is None else float(o.horas_executadas),
            "horas_aprovadas": None if o.horas_aprovadas is None else float(o.horas_aprovadas),
            "diferenca": diff, "origem": o.origem_execucao.value if o.origem_execucao else None,
            "estado": o.estado.value, "observacao": o.observacao_execucao, "substituicao": o.colaborador_efetivo_id is not None,
            "bloqueado": bloqueio,
        })
    resumo = {
        "total": len(out),
        "tacitas": sum(1 for x in out if x["origem"] == "tacita"),
        "com_diferenca": sum(1 for x in out if x["diferenca"]),
        "horas_planeadas": sum(x["horas_planeadas"] for x in out),
        "horas_executadas": sum(x["horas_executadas"] or 0 for x in out),
    }
    return {"inicio": inicio.isoformat(), "fim": fim.isoformat(), "itens": out, "resumo": resumo}


def _carregar(db: Session, user: User, ids: list[int]) -> list[Ocorrencia]:
    ocs = db.scalars(select(Ocorrencia).options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato))
                     .where(Ocorrencia.tenant_id == user.tenant_id, Ocorrencia.id.in_(ids))).unique().all()
    equipa = _equipa(db, user)
    if equipa is not None and any(o.colaborador_id not in equipa for o in ocs):
        raise HTTPException(403, "Só pode validar serviços da sua equipa")
    return ocs


@router.put("/ocorrencias/{oid}/execucao", tags=["validação"])
def registar(oid: int, body: ExecucaoIn, user: User = Depends(requer("validacao.editar")), db: Session = Depends(get_db)):
    o = _carregar(db, user, [oid])
    if not o:
        raise HTTPException(404, "Registo não encontrado")
    try:
        fecho.registar_execucao(db, user, o[0], body.horas, body.observacao, hoje())
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"ok": True}


@router.post("/validacao", tags=["validação"])
def validar(body: ValidarIn, user: User = Depends(requer("validacao.editar")), db: Session = Depends(get_db)):
    if not body.aprovar and not body.motivo:
        raise HTTPException(422, "Indique o motivo da rejeição")
    res = fecho.validar(db, user, _carregar(db, user, body.ids), body.aprovar, body.motivo, hoje())
    db.commit()
    return res


# ------------------------------------------------------------------ pré-faturação
@router.get("/prefaturacao", tags=["financeiro"])
def prefaturacao(mes: str, area: TipoContrato = TipoContrato.REP, user: User = Depends(requer("financeiro.ler")),
                 db: Session = Depends(get_db)):
    return fecho.prefaturacao(db, user.tenant_id, _mes(mes), area.value, hoje())


# ------------------------------------------------------------------ apuramento
@router.get("/apuramento", tags=["financeiro"])
def apuramento(mes: str, user: User = Depends(requer("remuneracoes.ler")), db: Session = Depends(get_db)):
    return fecho.apuramento(db, user.tenant_id, _mes(mes), hoje())


@router.get("/apuramento/export.csv", tags=["financeiro"])
def apuramento_csv(mes: str, user: User = Depends(requer("remuneracoes.ler")), db: Session = Depends(get_db)):
    dados = fecho.apuramento(db, user.tenant_id, _mes(mes), hoje())
    nome = f"apuramento-{dados['mes'][:7]}.csv"
    return Response(fecho.apuramento_csv(dados), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


# ------------------------------------------------------------------ fecho de períodos
class FechoIn(BaseModel):
    tipo: TipoPeriodo
    mes: str
    area: str = "*"


def _area(body: FechoIn) -> str:
    if body.tipo == TipoPeriodo.remuneracao:
        return "*"
    if body.area not in {t.value for t in TipoContrato}:
        raise HTTPException(422, "Indique a área a fechar")
    return body.area


@router.post("/periodos/fechar", tags=["financeiro"])
def fechar(body: FechoIn, user: User = Depends(requer("periodo.fechar")), db: Session = Depends(get_db)):
    try:
        fecho.fechar(db, user, body.tipo, _mes(body.mes), _area(body), hoje())
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"ok": True}


@router.post("/periodos/reabrir", tags=["financeiro"])
def reabrir(body: FechoIn, user: User = Depends(requer("periodo.fechar")), db: Session = Depends(get_db)):
    try:
        fecho.reabrir(db, user, body.tipo, _mes(body.mes), _area(body))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ indicadores do colaborador
@router.get("/colaboradores/{cid}/indicadores", tags=["colaboradores"])
def indicadores(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    if user.perfil == Perfil.supervisor and c.supervisor_id != user.id:
        raise HTTPException(404, "Registo não encontrado")
    return fecho.indicadores_colaborador(db, c, hoje())


__all__ = ["router", "PeriodoFechadoErro"]
