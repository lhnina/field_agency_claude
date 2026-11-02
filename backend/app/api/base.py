from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cliente, Insignia, Loja, Marca, Perfil, User, Zona
from app.schemas import ClienteIn, ClienteOut, IdNome, LojaIn, LojaOut, Nome, TokenOut, UserOut
from app.security import create_token, current_user, requer, verify_password

router = APIRouter()


def obter(db: Session, model, id_: int, user: User):
    obj = db.get(model, id_)
    if obj is None or getattr(obj, "tenant_id", user.tenant_id) != user.tenant_id:
        raise HTTPException(404, "Registo não encontrado")
    return obj


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower().strip()))
    if not user or not user.ativo or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Email ou palavra-passe incorretos")
    return TokenOut(access_token=create_token(user), user=UserOut(id=user.id, nome=user.nome, email=user.email, perfil=user.perfil.value))


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, nome=user.nome, email=user.email, perfil=user.perfil.value)


@router.get("/utilizadores/supervisores", response_model=list[IdNome], tags=["auth"])
def supervisores(user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.tenant_id == user.tenant_id, User.perfil == Perfil.supervisor,
                                         User.ativo.is_(True)).order_by(User.nome)).all()


# ---------------------------------------------------------------- listas simples
def _simple(model, path: str, tag: str):
    @router.get(f"/{path}", response_model=list[IdNome], tags=[tag])
    def listar(user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
        return db.scalars(select(model).where(model.tenant_id == user.tenant_id).order_by(model.nome)).all()

    @router.post(f"/{path}", response_model=IdNome, status_code=201, tags=[tag])
    def criar(body: Nome, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
        obj = model(tenant_id=user.tenant_id, nome=body.nome)
        db.add(obj)
        db.commit()
        return obj


_simple(Zona, "zonas", "dados mestre")
_simple(Insignia, "insignias", "dados mestre")


# ---------------------------------------------------------------- clientes
@router.get("/clientes", response_model=list[ClienteOut], tags=["dados mestre"])
def clientes(user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return db.scalars(select(Cliente).where(Cliente.tenant_id == user.tenant_id).order_by(Cliente.nome)).all()


@router.post("/clientes", response_model=ClienteOut, status_code=201, tags=["dados mestre"])
def criar_cliente(body: ClienteIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    c = Cliente(tenant_id=user.tenant_id, nome=body.nome, nif=body.nif, codigo_phc=body.codigo_phc,
                marcas=[Marca(tenant_id=user.tenant_id, nome=m) for m in body.marcas if m.strip()])
    db.add(c)
    db.commit()
    return c


@router.put("/clientes/{cid}", response_model=ClienteOut, tags=["dados mestre"])
def editar_cliente(cid: int, body: ClienteIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    c = obter(db, Cliente, cid, user)
    c.nome, c.nif, c.codigo_phc = body.nome, body.nif, body.codigo_phc
    atuais = {m.nome: m for m in c.marcas}
    for nome in body.marcas:
        if nome.strip() and nome not in atuais:
            c.marcas.append(Marca(tenant_id=user.tenant_id, nome=nome))
    db.commit()
    return c


# ---------------------------------------------------------------- lojas
@router.get("/lojas", response_model=list[LojaOut], tags=["dados mestre"])
def lojas(q: str | None = None, zona_id: int | None = None, user: User = Depends(requer("dados_mestre.ler")),
          db: Session = Depends(get_db)):
    s = select(Loja).where(Loja.tenant_id == user.tenant_id)
    if q:
        s = s.where(Loja.nome.ilike(f"%{q}%"))
    if zona_id:
        s = s.where(Loja.zona_id == zona_id)
    return db.scalars(s.order_by(Loja.nome)).all()


@router.post("/lojas", response_model=LojaOut, status_code=201, tags=["dados mestre"])
def criar_loja(body: LojaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    lj = Loja(tenant_id=user.tenant_id, **body.model_dump())
    db.add(lj)
    db.commit()
    db.refresh(lj)
    return lj


@router.put("/lojas/{lid}", response_model=LojaOut, tags=["dados mestre"])
def editar_loja(lid: int, body: LojaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    lj = obter(db, Loja, lid, user)
    for k, v in body.model_dump().items():
        setattr(lj, k, v)
    db.commit()
    db.refresh(lj)
    return lj
