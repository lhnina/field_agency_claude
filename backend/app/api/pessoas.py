from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.base import garantir_funcao, obter
from app.db import get_db
from app.models import (
    Afetacao, Ausencia, Colaborador, Contrato, EstadoContrato, EstadoOcorrencia, LinhaContrato, Ocorrencia, Perfil, User,
)
from app.schemas import AusenciaIn, AusenciaOut, ColaboradorIn, ColaboradorOut, EstadoAtivoIn
from app import ambito
from app.security import requer
from app.services import operacao as op

router = APIRouter(tags=["colaboradores"])


def _scope(s, user: User):
    zona = ambito.zona_supervisor(user)
    if zona is not None:
        s = s.where(Colaborador.zona_id == zona)
    return s


@router.get("/colaboradores", response_model=list[ColaboradorOut])
def listar(q: str | None = None, vinculo: str | None = None, zona_id: int | None = None, inativos: bool = False,
           limite: int | None = None, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    s = _scope(select(Colaborador).where(Colaborador.tenant_id == user.tenant_id), user)
    if not inativos:
        s = s.where(Colaborador.ativo.is_(True))
    if q:
        for termo in q.split():
            s = s.where(or_(Colaborador.nome.ilike(f"%{termo}%"), Colaborador.numero.ilike(f"%{termo}%"),
                            Colaborador.funcao.ilike(f"%{termo}%")))
    if vinculo == "muito_curta_duracao":
        s = s.where(Colaborador.muito_curta_duracao.is_(True))
    elif vinculo:
        s = s.where(Colaborador.vinculo == vinculo)
    if zona_id:
        s = s.where(Colaborador.zona_id == zona_id)
    s = s.order_by(Colaborador.ativo.desc(), Colaborador.nome)
    if limite:
        s = s.limit(min(limite, 200))
    out = [ColaboradorOut.model_validate(c) for c in db.scalars(s).all()]
    carga = _carga(db, [c.id for c in out])
    for c in out:
        c.horas_afetadas = carga.get(c.id, Decimal("0"))
    return out


def _afetacoes_vigentes(db: Session, ids: list[int]) -> list[Afetacao]:
    hoje = date.today()
    if not ids:
        return []
    return db.scalars(select(Afetacao).join(LinhaContrato).join(Contrato).options(
        joinedload(Afetacao.linha).joinedload(LinhaContrato.loja),
        joinedload(Afetacao.linha).joinedload(LinhaContrato.contrato).joinedload(Contrato.cliente)).where(
        Afetacao.colaborador_id.in_(ids), Afetacao.desde <= hoje, or_(Afetacao.ate.is_(None), Afetacao.ate >= hoje),
        Contrato.estado == EstadoContrato.ativo, LinhaContrato.inicio <= hoje,
        or_(LinhaContrato.fim.is_(None), LinhaContrato.fim >= hoje),
        or_(Contrato.fim.is_(None), Contrato.fim >= hoje))).unique().all()


def _carga(db: Session, ids: list[int]) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    for a in _afetacoes_vigentes(db, ids):
        out[a.colaborador_id] = out.get(a.colaborador_id, Decimal("0")) + a.linha.horas_semana
    return out


@router.get("/colaboradores/{cid}/afetacoes")
def afetacoes(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    """Lojas em que o colaborador está afeto hoje, com as horas de cada dia."""
    c = obter(db, Colaborador, cid, user)
    dias = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")
    res = []
    permitidos = ambito.clientes_permitidos(db, user)
    for a in _afetacoes_vigentes(db, [c.id]):
        ln = a.linha
        if permitidos is not None and ln.contrato.cliente_id not in permitidos:
            continue
        res.append({"linha_id": ln.id, "loja": ln.loja.nome, "cliente": ln.contrato.cliente.nome, "contrato_id": ln.contrato_id,
                    "contrato_numero": ln.contrato.numero, "tipo": ln.contrato.tipo.value, "horas_semana": float(ln.horas_semana),
                    "dias": [f"{d} {float(ln.horas_dia(i)):g}h".replace(".", ",") for i, d in enumerate(dias) if ln.horas_dia(i) > 0],
                    "desde": a.desde.isoformat(), "ate": a.ate.isoformat() if a.ate else None})
    return sorted(res, key=lambda x: (x["cliente"], x["loja"]))


@router.get("/colaboradores/{cid}", response_model=ColaboradorOut)
def detalhe(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    out = ColaboradorOut.model_validate(c)
    out.horas_afetadas = _carga(db, [c.id]).get(c.id, Decimal("0"))
    return out


def _validar(body: ColaboradorIn) -> None:
    try:
        body.validar_datas()
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/colaboradores", response_model=ColaboradorOut, status_code=201)
def criar(body: ColaboradorIn, user: User = Depends(requer("colaboradores.editar")), db: Session = Depends(get_db)):
    if db.scalar(select(Colaborador).where(Colaborador.tenant_id == user.tenant_id, Colaborador.numero == body.numero)):
        raise HTTPException(409, f"Já existe um colaborador com o n.º {body.numero}")
    _validar(body)
    body.funcao = garantir_funcao(db, user.tenant_id, body.funcao)
    c = Colaborador(tenant_id=user.tenant_id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/colaboradores/{cid}", response_model=ColaboradorOut)
def editar(cid: int, body: ColaboradorIn, user: User = Depends(requer("colaboradores.editar")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    _validar(body)
    body.funcao = garantir_funcao(db, user.tenant_id, body.funcao)
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
    zona = ambito.zona_supervisor(user)
    if zona is not None:
        s = s.where(Colaborador.zona_id == zona)
    if desde:
        s = s.where(Ausencia.fim >= desde)
    return [_aus_out(db, a) for a in db.scalars(s.order_by(Ausencia.inicio)).all()]


@router.post("/ausencias", response_model=AusenciaOut, status_code=201, tags=["ausências"])
def criar_ausencia(body: AusenciaIn, user: User = Depends(requer("ausencias.editar")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, body.colaborador_id, user)
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
