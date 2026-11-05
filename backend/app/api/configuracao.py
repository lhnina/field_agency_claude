from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Perfil, Tenant, User
from app.security import current_user
from app.services import operacao as op

router = APIRouter(prefix="/configuracao", tags=["configuração"])

Pct = Field(ge=0, le=200)


class ConfigIn(BaseModel):
    aceitacao_tacita: bool
    limite_margem_pct: Decimal = Field(ge=0, le=100)
    encargos_sem_termo_pct: Decimal = Pct
    encargos_a_termo_pct: Decimal = Pct
    encargos_muito_curta_pct: Decimal = Pct
    encargos_recibos_verdes_pct: Decimal = Pct


class EmpresaIn(BaseModel):
    """Dados da empresa usados nas credenciais."""
    nome: str = Field(min_length=1, max_length=160)
    nif: str | None = Field(default=None, max_length=20)
    morada: str | None = Field(default=None, max_length=250)
    codigo_postal: str | None = Field(default=None, max_length=10)
    localidade: str | None = Field(default=None, max_length=80)
    registo_comercial: str | None = Field(default=None, max_length=250)
    seguradora: str | None = Field(default=None, max_length=160)
    apolice: str | None = Field(default=None, max_length=60)
    apolice_validade: date | None = None


class ConfigOut(ConfigIn):
    nome: str
    pode_editar: bool
    empresa: EmpresaIn


def _out(t: Tenant, user: User) -> ConfigOut:
    return ConfigOut(nome=t.nome, pode_editar=user.perfil in (Perfil.administrador, Perfil.direcao),
                     empresa=EmpresaIn(**{k: getattr(t, k) for k in EmpresaIn.model_fields}),
                     **{k: getattr(t, k) for k in ConfigIn.model_fields})


@router.get("", response_model=ConfigOut)
def ler(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.perfil == Perfil.colaborador:
        raise HTTPException(403, "Sem permissão")
    return _out(db.get(Tenant, user.tenant_id), user)


@router.put("", response_model=ConfigOut)
def gravar(body: ConfigIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.perfil not in (Perfil.administrador, Perfil.direcao):
        raise HTTPException(403, "Só a Direção ou o Administrador alteram a configuração")
    t = db.get(Tenant, user.tenant_id)
    antes = {k: getattr(t, k) for k in ConfigIn.model_fields}
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    op.auditar(db, user, "configuracao", t.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return _out(t, user)


@router.put("/empresa", response_model=ConfigOut)
def gravar_empresa(body: EmpresaIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.perfil not in (Perfil.administrador, Perfil.direcao):
        raise HTTPException(403, "Só a Direção ou o Administrador alteram a configuração")
    t = db.get(Tenant, user.tenant_id)
    antes = {k: getattr(t, k) for k in EmpresaIn.model_fields}
    for k, v in body.model_dump().items():
        setattr(t, k, v.strip() if isinstance(v, str) else v)
    t.nome = body.nome.strip()
    op.auditar(db, user, "configuracao", t.id, "empresa", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return _out(t, user)
