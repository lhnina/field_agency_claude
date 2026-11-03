from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cliente, Contrato, EstadoContrato, Funcao, Insignia, LinhaContrato, Loja, Marca, Perfil, User, Zona
from app.schemas import ClienteIn, ClienteOut, EstadoAtivoIn, IdNome, IdNomeAtivo, LojaIn, LojaOut, Nome, TokenOut, UserOut
from app.security import create_token, current_user, requer, verify_password
from app.services import operacao as op
from app import ambito

router = APIRouter()


def obter(db: Session, model, id_: int, user: User):
    obj = db.get(model, id_)
    if obj is None or getattr(obj, "tenant_id", user.tenant_id) != user.tenant_id:
        raise HTTPException(404, "Registo não encontrado")
    ambito.verificar(db, user, obj)
    return obj


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower().strip()))
    if not user or not user.ativo or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Email ou palavra-passe incorretos")
    return TokenOut(access_token=create_token(user), user=UserOut(id=user.id, nome=user.nome, email=user.email, perfil=user.perfil.value, zona=user.zona.nome if user.zona else None))


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, nome=user.nome, email=user.email, perfil=user.perfil.value, zona=user.zona.nome if user.zona else None)


@router.get("/utilizadores/gestores-conta", response_model=list[IdNome], tags=["auth"])
def gestores_conta(user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.tenant_id == user.tenant_id, User.perfil == Perfil.gestor_conta,
                                         User.ativo.is_(True)).order_by(User.nome)).all()


@router.get("/utilizadores/supervisores", response_model=list[IdNome], tags=["auth"])
def supervisores(user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.tenant_id == user.tenant_id, User.perfil == Perfil.supervisor,
                                         User.ativo.is_(True)).order_by(User.nome)).all()


# ---------------------------------------------------------------- ativo / inativo
# Nenhum registo de negócio é apagado: fica inativo, deixa de aparecer nas listas e
# seleções, e mantém todo o histórico. Reativar repõe-no.
def _estado(db: Session, user: User, obj, ativo: bool, entidade: str, bloqueio: str | None = None):
    if not ativo and bloqueio:
        raise HTTPException(422, bloqueio)
    if obj.ativo != ativo:
        obj.ativo = ativo
        op.auditar(db, user, entidade, obj.id, "reativar" if ativo else "desativar", None)
    db.commit()
    return obj


def _contratos_vivos(db: Session, *cond) -> int:
    return db.scalar(select(func.count(func.distinct(Contrato.id))).select_from(Contrato).outerjoin(LinhaContrato)
                     .where(Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.proposta)), *cond)) or 0


# ---------------------------------------------------------------- listas simples (zonas, insígnias)
def _simple(model, path: str, tag: str, entidade: str, renomear=None):
    @router.get(f"/{path}", response_model=list[IdNomeAtivo], tags=[tag], name=f"listar_{path}")
    def listar(inativos: bool = False, user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
        q = select(model).where(model.tenant_id == user.tenant_id)
        if not inativos:
            q = q.where(model.ativo.is_(True))
        return db.scalars(q.order_by(model.ativo.desc(), model.nome)).all()

    @router.post(f"/{path}", response_model=IdNomeAtivo, status_code=201, tags=[tag], name=f"criar_{path}")
    def criar(body: Nome, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
        if db.scalar(select(model).where(model.tenant_id == user.tenant_id, func.lower(model.nome) == body.nome.strip().lower())):
            raise HTTPException(409, "Já existe um registo com este nome")
        obj = model(tenant_id=user.tenant_id, nome=body.nome.strip())
        db.add(obj)
        db.commit()
        return obj

    @router.put(f"/{path}/{{oid}}", response_model=IdNomeAtivo, tags=[tag], name=f"editar_{path}")
    def editar(oid: int, body: Nome, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
        obj = obter(db, model, oid, user)
        novo = body.nome.strip()
        if db.scalar(select(model).where(model.tenant_id == user.tenant_id, model.id != obj.id, func.lower(model.nome) == novo.lower())):
            raise HTTPException(409, "Já existe um registo com este nome")
        antigo, obj.nome = obj.nome, novo
        if renomear and antigo != novo:
            renomear(db, user, antigo, novo)
        db.commit()
        return obj

    @router.post(f"/{path}/{{oid}}/estado", response_model=IdNomeAtivo, tags=[tag], name=f"estado_{path}")
    def estado(oid: int, body: EstadoAtivoIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
        return _estado(db, user, obter(db, model, oid, user), body.ativo, entidade)


_simple(Zona, "zonas", "dados mestre", "zona")
_simple(Insignia, "insignias", "dados mestre", "insignia")


def _renomear_funcao(db: Session, user: User, antigo: str, novo: str) -> None:
    """A função é guardada por nome nos colaboradores e nos requisitos: acompanha a mudança de nome."""
    from sqlalchemy import update
    from app.models import Colaborador, RequisitoDocumental
    db.execute(update(Colaborador).where(Colaborador.tenant_id == user.tenant_id, Colaborador.funcao == antigo).values(funcao=novo))
    db.execute(update(RequisitoDocumental).where(RequisitoDocumental.tenant_id == user.tenant_id,
                                                 RequisitoDocumental.funcao == antigo).values(funcao=novo))


_simple(Funcao, "funcoes", "dados mestre", "funcao", _renomear_funcao)


def garantir_funcao(db: Session, tenant_id: int, nome: str | None) -> str | None:
    """Devolve o nome da função tal como está na tabela (sem distinguir maiúsculas); cria-a se não existir."""
    nome = (nome or "").strip()
    if not nome:
        return None
    f = db.scalar(select(Funcao).where(Funcao.tenant_id == tenant_id, func.lower(Funcao.nome) == nome.lower()))
    if not f:
        f = Funcao(tenant_id=tenant_id, nome=nome)
        db.add(f)
        db.flush()
    return f.nome


# ---------------------------------------------------------------- clientes
CAMPOS_CLIENTE = ("nome", "nif", "codigo_erp", "morada", "codigo_postal", "localidade", "telefone", "email", "url",
                  "contacto_nome", "gestor_conta_id", "observacoes")


@router.get("/clientes", response_model=list[ClienteOut], tags=["dados mestre"])
def clientes(inativos: bool = False, q: str | None = None, user: User = Depends(requer("dados_mestre.ler")),
             db: Session = Depends(get_db)):
    s = select(Cliente).where(Cliente.tenant_id == user.tenant_id)
    if not inativos:
        s = s.where(Cliente.ativo.is_(True))
    if q:
        s = s.where(Cliente.nome.ilike(f"%{q}%") | Cliente.nif.ilike(f"%{q}%"))
    permitidos = ambito.clientes_permitidos(db, user)
    if permitidos is not None:
        s = s.where(Cliente.id.in_(permitidos))
    out = db.scalars(s.order_by(Cliente.ativo.desc(), Cliente.nome)).all()
    for c in out:  # marcas inativas só aparecem na ficha
        c.marcas.sort(key=lambda m: (not m.ativo, m.nome))
    return out


@router.get("/clientes/{cid}", response_model=ClienteOut, tags=["dados mestre"])
def cliente(cid: int, user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return obter(db, Cliente, cid, user)


def _gestor_conta(db: Session, user: User, body: ClienteIn) -> None:
    """Valida o gestor de conta escolhido; o gestor de conta fica sempre como gestor dos clientes que cria ou edita."""
    if user.perfil == Perfil.gestor_conta:
        body.gestor_conta_id = user.id
    elif body.gestor_conta_id is not None:
        g = db.get(User, body.gestor_conta_id)
        if not g or g.tenant_id != user.tenant_id or g.perfil != Perfil.gestor_conta:
            raise HTTPException(422, "O gestor de conta tem de ser um utilizador com o perfil Gestor de conta")


def _marcas(c: Cliente, nomes: list[str], tenant_id: int) -> None:
    atuais = {m.nome.strip().lower(): m for m in c.marcas}
    for nome in nomes:
        k = nome.strip().lower()
        if k and k not in atuais:
            m = Marca(tenant_id=tenant_id, nome=nome.strip())
            c.marcas.append(m)
            atuais[k] = m
        elif k and not atuais[k].ativo:
            atuais[k].ativo = True


@router.post("/clientes", response_model=ClienteOut, status_code=201, tags=["dados mestre"])
def criar_cliente(body: ClienteIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    if db.scalar(select(Cliente).where(Cliente.tenant_id == user.tenant_id, func.lower(Cliente.nome) == body.nome.strip().lower())):
        raise HTTPException(409, "Já existe um cliente com este nome")
    _gestor_conta(db, user, body)
    c = Cliente(tenant_id=user.tenant_id, **{k: getattr(body, k) for k in CAMPOS_CLIENTE})
    _marcas(c, body.marcas, user.tenant_id)
    db.add(c)
    db.flush()
    op.auditar(db, user, "cliente", c.id, "criar", body.model_dump())
    db.commit()
    return c


@router.put("/clientes/{cid}", response_model=ClienteOut, tags=["dados mestre"])
def editar_cliente(cid: int, body: ClienteIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    c = obter(db, Cliente, cid, user)
    _gestor_conta(db, user, body)
    antes = {k: getattr(c, k) for k in CAMPOS_CLIENTE}
    for k in CAMPOS_CLIENTE:
        setattr(c, k, getattr(body, k))
    _marcas(c, body.marcas, user.tenant_id)
    op.auditar(db, user, "cliente", c.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return c


@router.post("/clientes/{cid}/estado", response_model=ClienteOut, tags=["dados mestre"])
def estado_cliente(cid: int, body: EstadoAtivoIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    c = obter(db, Cliente, cid, user)
    n = _contratos_vivos(db, Contrato.cliente_id == c.id)
    return _estado(db, user, c, body.ativo, "cliente",
                   f"O cliente tem {n} contrato(s) ativo(s) ou em proposta: termine-os antes de o desativar" if n else None)


@router.post("/marcas/{mid}/estado", tags=["dados mestre"])
def estado_marca(mid: int, body: EstadoAtivoIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    m = obter(db, Marca, mid, user)
    n = _contratos_vivos(db, Contrato.marca_id == m.id)
    _estado(db, user, m, body.ativo, "marca",
            f"A marca tem {n} contrato(s) ativo(s) ou em proposta" if n else None)
    return {"id": m.id, "ativo": m.ativo}


# ---------------------------------------------------------------- lojas
@router.get("/lojas", response_model=list[LojaOut], tags=["dados mestre"])
def lojas(q: str | None = None, zona_id: int | None = None, inativos: bool = False, limite: int | None = None,
          user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    s = select(Loja).where(Loja.tenant_id == user.tenant_id)
    if not inativos:
        s = s.where(Loja.ativo.is_(True))
    if q:
        for termo in q.split():
            t = f"%{termo}%"
            s = s.where(Loja.nome.ilike(t) | Loja.localidade.ilike(t) | Loja.codigo_postal.ilike(t) | Loja.morada.ilike(t))
    if zona_id:
        s = s.where(Loja.zona_id == zona_id)
    zona = ambito.zona_supervisor(user)
    if zona is not None:
        s = s.where(Loja.zona_id == zona)
    s = s.order_by(Loja.ativo.desc(), Loja.nome)
    if limite:
        s = s.limit(min(limite, 200))
    return db.scalars(s).all()


@router.get("/lojas/{lid}", response_model=LojaOut, tags=["dados mestre"])
def loja(lid: int, user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    return obter(db, Loja, lid, user)


@router.get("/lojas/{lid}/servicos", tags=["dados mestre"])
def loja_servicos(lid: int, user: User = Depends(requer("dados_mestre.ler")), db: Session = Depends(get_db)):
    """Linhas de contrato em vigor nesta loja, com o colaborador afeto."""
    lj = obter(db, Loja, lid, user)
    hoje = date.today()
    linhas = db.scalars(select(LinhaContrato).join(Contrato).where(
        LinhaContrato.loja_id == lj.id, Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.proposta)),
        or_(LinhaContrato.fim.is_(None), LinhaContrato.fim >= hoje))).all()
    permitidos = ambito.clientes_permitidos(db, user)
    if permitidos is not None:
        linhas = [ln for ln in linhas if ln.contrato.cliente_id in permitidos]
    out = []
    for ln in linhas:
        af = op.afetacao_em(ln, max(hoje, ln.inicio))
        out.append({"linha_id": ln.id, "contrato_id": ln.contrato_id, "contrato_numero": ln.contrato.numero,
                    "tipo": ln.contrato.tipo.value, "estado": ln.contrato.estado.value, "cliente": ln.contrato.cliente.nome,
                    "horas_semana": float(ln.horas_semana), "dias": [d for d, i in zip(("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"), range(7)) if ln.horas_dia(i) > 0],
                    "colaborador": af.colaborador.nome if af else None})
    return sorted(out, key=lambda x: x["cliente"])


@router.post("/lojas", response_model=LojaOut, status_code=201, tags=["dados mestre"])
def criar_loja(body: LojaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    if db.scalar(select(Loja).where(Loja.tenant_id == user.tenant_id, func.lower(Loja.nome) == body.nome.strip().lower())):
        raise HTTPException(409, "Já existe uma loja com este nome")
    lj = Loja(tenant_id=user.tenant_id, **body.model_dump())
    db.add(lj)
    db.flush()
    op.auditar(db, user, "loja", lj.id, "criar", body.model_dump())
    db.commit()
    db.refresh(lj)
    return lj


@router.put("/lojas/{lid}", response_model=LojaOut, tags=["dados mestre"])
def editar_loja(lid: int, body: LojaIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    lj = obter(db, Loja, lid, user)
    antes = {k: getattr(lj, k) for k in body.model_dump()}
    for k, v in body.model_dump().items():
        setattr(lj, k, v)
    op.auditar(db, user, "loja", lj.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    db.refresh(lj)
    return lj


@router.post("/lojas/{lid}/estado", response_model=LojaOut, tags=["dados mestre"])
def estado_loja(lid: int, body: EstadoAtivoIn, user: User = Depends(requer("dados_mestre.editar")), db: Session = Depends(get_db)):
    lj = obter(db, Loja, lid, user)
    n = db.scalar(select(func.count(LinhaContrato.id)).join(Contrato).where(
        LinhaContrato.loja_id == lj.id, Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.proposta)),
        or_(LinhaContrato.fim.is_(None), LinhaContrato.fim >= date.today()))) or 0
    _estado(db, user, lj, body.ativo, "loja",
            f"A loja tem {n} linha(s) de contrato em vigor: termine-as antes de a desativar" if n else None)
    db.refresh(lj)
    return lj
