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


class ConfigOut(ConfigIn):
    nome: str
    pode_editar: bool


def _out(t: Tenant, user: User) -> ConfigOut:
    return ConfigOut(nome=t.nome, pode_editar=user.perfil in (Perfil.administrador, Perfil.direcao),
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
