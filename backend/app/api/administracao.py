"""Gestão de utilizadores e de feriados da organização."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.base import obter
from app.db import get_db
from app.models import Feriado, Perfil, User, Zona
from app.security import current_user, hash_password, verify_password
from app.services import feriados as fer
from app.services import operacao as op

router = APIRouter()
GESTAO = (Perfil.administrador, Perfil.direcao)


def _gestor_utilizadores(user: User = Depends(current_user)) -> User:
    if user.perfil not in GESTAO:
        raise HTTPException(403, "Só a Direção ou o Administrador gerem utilizadores")
    return user


def _senha(v: str) -> str:
    if len(v) < 8 or v.isalpha() or v.isdigit():
        raise ValueError("A palavra-passe tem de ter pelo menos 8 caracteres, com letras e números")
    return v


# ------------------------------------------------------------------ utilizadores
class UtilizadorIn(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=200)
    perfil: Perfil
    ativo: bool = True

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Email inválido")
        return v


class NovoUtilizadorIn(UtilizadorIn):
    password: str

    _p = field_validator("password")(classmethod(lambda cls, v: _senha(v)))


class PasswordIn(BaseModel):
    password: str
    _p = field_validator("password")(classmethod(lambda cls, v: _senha(v)))


class MinhaPasswordIn(BaseModel):
    atual: str
    nova: str
    _p = field_validator("nova")(classmethod(lambda cls, v: _senha(v)))


def _out(u: User) -> dict:
    return {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil.value, "ativo": u.ativo}


def _admins_ativos(db: Session, tenant_id: int, exceto: int | None = None) -> int:
    q = select(func.count(User.id)).where(User.tenant_id == tenant_id, User.perfil == Perfil.administrador, User.ativo.is_(True))
    if exceto:
        q = q.where(User.id != exceto)
    return db.scalar(q) or 0


@router.get("/utilizadores", tags=["utilizadores"])
def listar(user: User = Depends(_gestor_utilizadores), db: Session = Depends(get_db)):
    return [_out(u) for u in db.scalars(select(User).where(User.tenant_id == user.tenant_id).order_by(User.ativo.desc(), User.nome)).all()]


@router.post("/utilizadores", status_code=201, tags=["utilizadores"])
def criar(body: NovoUtilizadorIn, user: User = Depends(_gestor_utilizadores), db: Session = Depends(get_db)):
    if body.perfil == Perfil.administrador and user.perfil != Perfil.administrador:
        raise HTTPException(403, "Só um Administrador pode criar administradores")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Já existe um utilizador com este email")
    u = User(tenant_id=user.tenant_id, nome=body.nome, email=body.email, perfil=body.perfil, ativo=body.ativo,
             password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    op.auditar(db, user, "utilizador", u.id, "criar", {"email": u.email, "perfil": u.perfil.value})
    db.commit()
    return _out(u)


@router.put("/utilizadores/{uid}", tags=["utilizadores"])
def editar(uid: int, body: UtilizadorIn, user: User = Depends(_gestor_utilizadores), db: Session = Depends(get_db)):
    u = obter(db, User, uid, user)
    if Perfil.administrador in (u.perfil, body.perfil) and user.perfil != Perfil.administrador:
        raise HTTPException(403, "Só um Administrador altera administradores")
    if u.id == user.id and (not body.ativo or body.perfil != u.perfil):
        raise HTTPException(422, "Não pode desativar nem alterar o perfil do seu próprio utilizador")
    perde_admin = u.perfil == Perfil.administrador and u.ativo and (body.perfil != Perfil.administrador or not body.ativo)
    if perde_admin and _admins_ativos(db, user.tenant_id, exceto=u.id) == 0:
        raise HTTPException(422, "Tem de existir pelo menos um Administrador ativo")
    if body.email != u.email and db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "Já existe um utilizador com este email")
    antes = _out(u)
    u.nome, u.email, u.perfil, u.ativo = body.nome, body.email, body.perfil, body.ativo
    op.auditar(db, user, "utilizador", u.id, "editar", {"antes": antes, "depois": _out(u)})
    db.commit()
    return _out(u)


@router.post("/utilizadores/{uid}/password", tags=["utilizadores"])
def repor_password(uid: int, body: PasswordIn, user: User = Depends(_gestor_utilizadores), db: Session = Depends(get_db)):
    u = obter(db, User, uid, user)
    if u.perfil == Perfil.administrador and user.perfil != Perfil.administrador:
        raise HTTPException(403, "Só um Administrador repõe a palavra-passe de administradores")
    u.password_hash = hash_password(body.password)
    op.auditar(db, user, "utilizador", u.id, "repor_password", None)
    db.commit()
    return {"ok": True}


@router.put("/auth/password", tags=["auth"])
def minha_password(body: MinhaPasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.atual, user.password_hash):
        raise HTTPException(422, "A palavra-passe atual não está correta")
    user.password_hash = hash_password(body.nova)
    op.auditar(db, user, "utilizador", user.id, "alterar_password", None)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ feriados
class FeriadoIn(BaseModel):
    data: date
    nome: str = Field(min_length=1, max_length=80)
    zona_id: int | None = None


def _gestor_feriados(user: User = Depends(current_user)) -> User:
    if user.perfil not in (Perfil.administrador, Perfil.direcao, Perfil.gestor):
        raise HTTPException(403, "Sem permissão para gerir feriados")
    return user


@router.get("/feriados", tags=["feriados"])
def feriados(ano: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return fer.listar(db, user.tenant_id, ano or date.today().year)


@router.post("/feriados", status_code=201, tags=["feriados"])
def criar_feriado(body: FeriadoIn, user: User = Depends(_gestor_feriados), db: Session = Depends(get_db)):
    if body.zona_id:
        obter(db, Zona, body.zona_id, user)
    if body.data in fer.nacionais(body.data.year):
        raise HTTPException(422, "Esta data já é feriado nacional")
    dup = db.scalar(select(Feriado).where(Feriado.tenant_id == user.tenant_id, Feriado.data == body.data,
                                          Feriado.zona_id.is_(None) if body.zona_id is None else Feriado.zona_id == body.zona_id))
    if dup:
        raise HTTPException(409, "Este feriado já existe")
    f = Feriado(tenant_id=user.tenant_id, **body.model_dump())
    db.add(f)
    db.flush()
    n = fer.reagendar_para_feriado(db, user, f)
    op.auditar(db, user, "feriado", f.id, "criar", {**body.model_dump(), "servicos_reagendados": n})
    db.commit()
    return {"id": f.id, "servicos_reagendados": n}


@router.delete("/feriados/{fid}", tags=["feriados"])
def apagar_feriado(fid: int, user: User = Depends(_gestor_feriados), db: Session = Depends(get_db)):
    f = db.get(Feriado, fid)
    if not f or f.tenant_id != user.tenant_id:
        raise HTTPException(404, "Feriado não encontrado (os feriados nacionais não podem ser apagados)")
    op.auditar(db, user, "feriado", f.id, "apagar", {"data": f.data, "nome": f.nome, "zona_id": f.zona_id})
    db.delete(f)
    db.commit()
    return {"ok": True}
