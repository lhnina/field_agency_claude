from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.base import obter
from app.db import get_db
from app.models import Afetacao, Ausencia, Colaborador, EstadoOcorrencia, Ocorrencia, Perfil, User
from app.schemas import AusenciaIn, AusenciaOut, ColaboradorIn, ColaboradorOut, EstadoAtivoIn
from app.security import requer
from app.services import operacao as op

router = APIRouter(tags=["colaboradores"])


def _scope(s, user: User):
    if user.perfil == Perfil.supervisor:
        s = s.where(Colaborador.supervisor_id == user.id)
    return s


@router.get("/colaboradores", response_model=list[ColaboradorOut])
def listar(q: str | None = None, vinculo: str | None = None, zona_id: int | None = None, inativos: bool = False,
           user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    s = _scope(select(Colaborador).where(Colaborador.tenant_id == user.tenant_id), user)
    if not inativos:
        s = s.where(Colaborador.ativo.is_(True))
    if q:
        s = s.where(or_(Colaborador.nome.ilike(f"%{q}%"), Colaborador.numero.ilike(f"%{q}%")))
    if vinculo:
        s = s.where(Colaborador.vinculo == vinculo)
    if zona_id:
        s = s.where(Colaborador.zona_id == zona_id)
    return db.scalars(s.order_by(Colaborador.ativo.desc(), Colaborador.nome)).all()


@router.get("/colaboradores/{cid}", response_model=ColaboradorOut)
def detalhe(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    if user.perfil == Perfil.supervisor and c.supervisor_id != user.id:
        raise HTTPException(404, "Registo não encontrado")
    return c


@router.post("/colaboradores", response_model=ColaboradorOut, status_code=201)
def criar(body: ColaboradorIn, user: User = Depends(requer("colaboradores.editar")), db: Session = Depends(get_db)):
    if db.scalar(select(Colaborador).where(Colaborador.tenant_id == user.tenant_id, Colaborador.numero == body.numero)):
        raise HTTPException(409, f"Já existe um colaborador com o n.º {body.numero}")
    c = Colaborador(tenant_id=user.tenant_id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/colaboradores/{cid}", response_model=ColaboradorOut)
def editar(cid: int, body: ColaboradorIn, user: User = Depends(requer("colaboradores.editar")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    antes = {k: getattr(c, k) for k in body.model_dump()}
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    op.auditar(db, user, "colaborador", c.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    db.refresh(c)
    return c


@router.post("/colaboradores/{cid}/estado", response_model=ColaboradorOut)
def estado(cid: int, body: EstadoAtivoIn, user: User = Depends(requer("colaboradores.editar")), db: Session = Depends(get_db)):
    """Desativar não apaga: o colaborador sai das listas e o histórico mantém-se."""
    c = obter(db, Colaborador, cid, user)
    if not body.ativo:
        hoje = date.today()
        afet = db.scalar(select(func.count(Afetacao.id)).where(
            Afetacao.colaborador_id == c.id, or_(Afetacao.ate.is_(None), Afetacao.ate >= hoje))) or 0
        futuras = db.scalar(select(func.count(Ocorrencia.id)).where(
            Ocorrencia.colaborador_efetivo_id == c.id, Ocorrencia.data >= hoje,
            Ocorrencia.estado.in_((EstadoOcorrencia.atribuido, EstadoOcorrencia.confirmado)))) or 0
        if afet or futuras:
            raise HTTPException(422, f"O colaborador está afeto a {afet} loja(s) e tem {futuras} substituição(ões) futura(s): "
                                     "reafete-as antes de o desativar")
    if c.ativo != body.ativo:
        c.ativo = body.ativo
        op.auditar(db, user, "colaborador", c.id, "reativar" if body.ativo else "desativar", None)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------- ausências
def _aus_out(db: Session, a: Ausencia) -> AusenciaOut:
    por_sub = op.ocorrencias_afetadas(db, a)
    total = db.scalar(select(func.count(Ocorrencia.id)).where(
        Ocorrencia.tenant_id == a.tenant_id, Ocorrencia.data.between(a.inicio, a.fim),
        Ocorrencia.colaborador_previsto_id == a.colaborador_id, Ocorrencia.estado != EstadoOcorrencia.cancelado))
    return AusenciaOut(id=a.id, colaborador_id=a.colaborador_id, colaborador_nome=a.colaborador.nome, tipo=a.tipo,
                       inicio=a.inicio, fim=a.fim, observacoes=a.observacoes,
                       ocorrencias_afetadas=max(total or 0, len(por_sub)), por_substituir=len(por_sub))


@router.get("/ausencias", response_model=list[AusenciaOut], tags=["ausências"])
def ausencias(desde: date | None = None, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    s = select(Ausencia).join(Colaborador).where(Ausencia.tenant_id == user.tenant_id)
    if user.perfil == Perfil.supervisor:
        s = s.where(Colaborador.supervisor_id == user.id)
    if desde:
        s = s.where(Ausencia.fim >= desde)
    return [_aus_out(db, a) for a in db.scalars(s.order_by(Ausencia.inicio)).all()]


@router.post("/ausencias", response_model=AusenciaOut, status_code=201, tags=["ausências"])
def criar_ausencia(body: AusenciaIn, user: User = Depends(requer("ausencias.editar")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, body.colaborador_id, user)
    if user.perfil == Perfil.supervisor and c.supervisor_id != user.id:
        raise HTTPException(403, "Só pode registar ausências da sua equipa")
    a = Ausencia(tenant_id=user.tenant_id, **body.model_dump())
    db.add(a)
    db.flush()
    op.auditar(db, user, "ausencia", a.id, "criar", body.model_dump())
    db.commit()
    db.refresh(a)
    return _aus_out(db, a)


@router.get("/ausencias/{aid}/ocorrencias", tags=["ausências"])
def ausencia_ocorrencias(aid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    a = obter(db, Ausencia, aid, user)
    return [{"id": o.id, "data": o.data, "horas": float(o.horas_planeadas), "loja": o.linha.loja.nome,
             "substituicao": o.colaborador_efetivo_id is not None} for o in op.ocorrencias_afetadas(db, a)]
