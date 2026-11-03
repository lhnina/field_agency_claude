"""Documentação dos colaboradores (tipos, requisitos, documentos e anexos)."""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, undefer

from app import ambito
from app.api.base import garantir_funcao, obter
from app.db import get_db
from app.models import Cliente, Colaborador, DocumentoColaborador, Insignia, RequisitoDocumental, TipoDocumento, User
from app.security import requer
from app.services import documentos as dc
from app.services import operacao as op

router = APIRouter(tags=["documentação"])

MAX_ANEXO = 10 * 1024 * 1024
TIPOS_ANEXO = {"application/pdf", "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


# ------------------------------------------------------------------ tipos de documento
class TipoIn(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    tem_validade: bool = True
    dias_aviso: int = Field(default=30, ge=0, le=365)


class AtivoIn(BaseModel):
    ativo: bool


def _tipo_json(t: TipoDocumento, n_req: int = 0, n_docs: int = 0) -> dict:
    return {"id": t.id, "nome": t.nome, "tem_validade": t.tem_validade, "dias_aviso": t.dias_aviso, "ativo": t.ativo,
            "requisitos": n_req, "documentos": n_docs}


@router.get("/tipos-documento")
def tipos(inativos: bool = False, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    q = select(TipoDocumento).where(TipoDocumento.tenant_id == user.tenant_id)
    if not inativos:
        q = q.where(TipoDocumento.ativo.is_(True))
    nreq = dict(db.execute(select(RequisitoDocumental.tipo_documento_id, func.count()).where(
        RequisitoDocumental.tenant_id == user.tenant_id, RequisitoDocumental.ativo.is_(True))
        .group_by(RequisitoDocumental.tipo_documento_id)).all())
    ndoc = dict(db.execute(select(DocumentoColaborador.tipo_documento_id, func.count()).where(
        DocumentoColaborador.tenant_id == user.tenant_id, DocumentoColaborador.atual.is_(True))
        .group_by(DocumentoColaborador.tipo_documento_id)).all())
    return [_tipo_json(t, nreq.get(t.id, 0), ndoc.get(t.id, 0))
            for t in db.scalars(q.order_by(TipoDocumento.ativo.desc(), TipoDocumento.nome)).all()]


@router.post("/tipos-documento", status_code=201)
def criar_tipo(body: TipoIn, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    if db.scalar(select(TipoDocumento).where(TipoDocumento.tenant_id == user.tenant_id,
                                             func.lower(TipoDocumento.nome) == body.nome.strip().lower())):
        raise HTTPException(409, "Já existe um tipo de documento com este nome")
    t = TipoDocumento(tenant_id=user.tenant_id, nome=body.nome.strip(), tem_validade=body.tem_validade, dias_aviso=body.dias_aviso)
    db.add(t)
    db.flush()
    op.auditar(db, user, "tipo_documento", t.id, "criar", body.model_dump())
    db.commit()
    return _tipo_json(t)


@router.put("/tipos-documento/{tid}")
def editar_tipo(tid: int, body: TipoIn, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    t = obter(db, TipoDocumento, tid, user)
    t.nome, t.tem_validade, t.dias_aviso = body.nome.strip(), body.tem_validade, body.dias_aviso
    op.auditar(db, user, "tipo_documento", t.id, "editar", body.model_dump())
    db.commit()
    return _tipo_json(t)


@router.post("/tipos-documento/{tid}/estado")
def estado_tipo(tid: int, body: AtivoIn, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    t = obter(db, TipoDocumento, tid, user)
    if t.ativo != body.ativo:
        t.ativo = body.ativo
        op.auditar(db, user, "tipo_documento", t.id, "reativar" if body.ativo else "desativar", None)
    db.commit()
    return _tipo_json(t)


# ------------------------------------------------------------------ requisitos
class RequisitoIn(BaseModel):
    tipo_documento_id: int
    funcao: str | None = None
    cliente_id: int | None = None
    insignia_id: int | None = None


def _req_json(r: RequisitoDocumental) -> dict:
    return {"id": r.id, "tipo_documento_id": r.tipo_documento_id, "tipo": r.tipo.nome, "funcao": r.funcao,
            "cliente_id": r.cliente_id, "cliente": r.cliente.nome if r.cliente else None,
            "insignia_id": r.insignia_id, "insignia": r.insignia.nome if r.insignia else None,
            "aplica_se": dc.motivo_requisito(r), "ativo": r.ativo}


@router.get("/requisitos-documentais")
def requisitos(user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    q = select(RequisitoDocumental).options(joinedload(RequisitoDocumental.tipo), joinedload(RequisitoDocumental.cliente),
                                            joinedload(RequisitoDocumental.insignia)).where(
        RequisitoDocumental.tenant_id == user.tenant_id, RequisitoDocumental.ativo.is_(True))
    return sorted((_req_json(r) for r in db.scalars(q).all()), key=lambda r: (r["tipo"], r["aplica_se"]))


@router.post("/requisitos-documentais", status_code=201)
def criar_requisito(body: RequisitoIn, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    obter(db, TipoDocumento, body.tipo_documento_id, user)
    if body.cliente_id:
        db_cli = db.get(Cliente, body.cliente_id)
        if not db_cli or db_cli.tenant_id != user.tenant_id:
            raise HTTPException(404, "Cliente não encontrado")
    if body.insignia_id:
        obter(db, Insignia, body.insignia_id, user)
    funcao = garantir_funcao(db, user.tenant_id, body.funcao)
    existe = db.scalar(select(RequisitoDocumental).where(
        RequisitoDocumental.tenant_id == user.tenant_id, RequisitoDocumental.ativo.is_(True),
        RequisitoDocumental.tipo_documento_id == body.tipo_documento_id,
        (RequisitoDocumental.funcao == funcao) if funcao else RequisitoDocumental.funcao.is_(None),
        (RequisitoDocumental.cliente_id == body.cliente_id) if body.cliente_id else RequisitoDocumental.cliente_id.is_(None),
        (RequisitoDocumental.insignia_id == body.insignia_id) if body.insignia_id else RequisitoDocumental.insignia_id.is_(None)))
    if existe:
        raise HTTPException(409, "Este requisito já existe")
    r = RequisitoDocumental(tenant_id=user.tenant_id, tipo_documento_id=body.tipo_documento_id, funcao=funcao,
                            cliente_id=body.cliente_id, insignia_id=body.insignia_id)
    db.add(r)
    db.flush()
    op.auditar(db, user, "requisito_documental", r.id, "criar", body.model_dump())
    db.commit()
    db.refresh(r)
    return _req_json(r)


@router.delete("/requisitos-documentais/{rid}")
def remover_requisito(rid: int, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    r = obter(db, RequisitoDocumental, rid, user)
    r.ativo = False  # fica no histórico
    op.auditar(db, user, "requisito_documental", r.id, "desativar", None)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ situação documental
def _colabs_ambito(db: Session, user: User, ids: list[int] | None = None) -> list[Colaborador]:
    q = select(Colaborador).options(joinedload(Colaborador.zona)).where(Colaborador.tenant_id == user.tenant_id,
                                                                        Colaborador.ativo.is_(True))
    zona = ambito.zona_supervisor(user)
    if zona is not None:
        q = q.where(Colaborador.zona_id == zona)
    if ids is not None:
        q = q.where(Colaborador.id.in_(ids))
    return list(db.scalars(q).all())


@router.get("/documentos")
def documentos(user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    """Situação documental de todos os colaboradores ativos no âmbito do utilizador."""
    hoje = date.today()
    colabs = _colabs_ambito(db, user)
    ctx = dc.contexto(db, user.tenant_id, [c.id for c in colabs])
    linhas = dc.situacao(db, ctx, colabs, hoje)
    return {"linhas": linhas, "resumo": dc.resumo(linhas)}


@router.get("/colaboradores/{cid}/documentos")
def documentos_colaborador(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    c = obter(db, Colaborador, cid, user)
    ctx = dc.contexto(db, user.tenant_id, [c.id])
    linhas = dc.situacao(db, ctx, [c], date.today())
    hist = db.scalars(select(DocumentoColaborador).options(joinedload(DocumentoColaborador.tipo)).where(
        DocumentoColaborador.colaborador_id == c.id, DocumentoColaborador.atual.is_(False))
        .order_by(DocumentoColaborador.created_at.desc())).all()
    return {"linhas": linhas, "resumo": dc.resumo(linhas),
            "historico": [{**dc.documento_json(d), "tipo": d.tipo.nome} for d in hist]}


def _data(v: str | None, nome: str) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise HTTPException(422, f"{nome}: data inválida")


async def _anexo(ficheiro: UploadFile | None) -> tuple[bytes, str, str] | None:
    if ficheiro is None or not ficheiro.filename:
        return None
    conteudo = await ficheiro.read()
    if len(conteudo) > MAX_ANEXO:
        raise HTTPException(422, "O anexo não pode ter mais de 10 MB")
    tipo = (ficheiro.content_type or "").lower()
    if tipo not in TIPOS_ANEXO:
        raise HTTPException(422, "O anexo tem de ser PDF ou imagem (JPG, PNG, WEBP, HEIC)")
    return conteudo, ficheiro.filename[:200], tipo


def _validar(tipo: TipoDocumento, emissao: date | None, validade: date | None) -> None:
    if tipo.tem_validade and not validade:
        raise HTTPException(422, f"Indique a validade: o {tipo.nome} tem validade")
    if emissao and validade and validade < emissao:
        raise HTTPException(422, "A validade não pode ser anterior à data de emissão")
    if emissao and emissao > date.today():
        raise HTTPException(422, "A data de emissão não pode ser no futuro")


@router.post("/colaboradores/{cid}/documentos", status_code=201)
async def registar(cid: int, tipo_documento_id: int = Form(...), numero: str | None = Form(None),
                   emissao: str | None = Form(None), validade: str | None = Form(None),
                   observacoes: str | None = Form(None), ficheiro: UploadFile | None = File(None),
                   user: User = Depends(requer("documentos.editar")), db: Session = Depends(get_db)):
    """Regista um documento entregue. Se já havia um do mesmo tipo, esse passa ao histórico (renovação)."""
    c = obter(db, Colaborador, cid, user)
    tipo = obter(db, TipoDocumento, tipo_documento_id, user)
    em, val = _data(emissao, "Emissão"), _data(validade, "Validade")
    _validar(tipo, em, val)
    anexo = await _anexo(ficheiro)
    anteriores = db.scalars(select(DocumentoColaborador).where(
        DocumentoColaborador.colaborador_id == c.id, DocumentoColaborador.tipo_documento_id == tipo.id,
        DocumentoColaborador.atual.is_(True))).all()
    for a in anteriores:
        a.atual = False
    d = DocumentoColaborador(tenant_id=user.tenant_id, colaborador_id=c.id, tipo_documento_id=tipo.id,
                             numero=(numero or "").strip() or None, emissao=em, validade=val if tipo.tem_validade else None,
                             observacoes=(observacoes or "").strip() or None, criado_por_id=user.id)
    if anexo:
        d.ficheiro, d.ficheiro_nome, d.ficheiro_tipo = anexo
        d.ficheiro_tamanho = len(anexo[0])
    db.add(d)
    db.flush()
    op.auditar(db, user, "documento_colaborador", d.id, "renovar" if anteriores else "registar",
               {"colaborador_id": c.id, "tipo": tipo.nome, "validade": validade, "anexo": d.ficheiro_nome})
    db.commit()
    return dc.documento_json(d)


@router.put("/documentos/{did}")
async def corrigir(did: int, numero: str | None = Form(None), emissao: str | None = Form(None),
                   validade: str | None = Form(None), observacoes: str | None = Form(None),
                   ficheiro: UploadFile | None = File(None),
                   user: User = Depends(requer("documentos.editar")), db: Session = Depends(get_db)):
    """Corrige os dados do documento atual (e, opcionalmente, substitui o anexo)."""
    d = obter(db, DocumentoColaborador, did, user)
    obter(db, Colaborador, d.colaborador_id, user)
    tipo = d.tipo
    em, val = _data(emissao, "Emissão"), _data(validade, "Validade")
    _validar(tipo, em, val)
    anexo = await _anexo(ficheiro)
    antes = dc.documento_json(d)
    d.numero, d.emissao = (numero or "").strip() or None, em
    d.validade = val if tipo.tem_validade else None
    d.observacoes = (observacoes or "").strip() or None
    if anexo:
        d.ficheiro, d.ficheiro_nome, d.ficheiro_tipo = anexo
        d.ficheiro_tamanho = len(anexo[0])
    db.flush()
    op.auditar(db, user, "documento_colaborador", d.id, "corrigir", {"antes": antes, "depois": dc.documento_json(d)})
    db.commit()
    return dc.documento_json(d)


@router.get("/documentos/{did}/ficheiro")
def descarregar(did: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    d = db.scalar(select(DocumentoColaborador).options(undefer(DocumentoColaborador.ficheiro)).where(
        DocumentoColaborador.id == did, DocumentoColaborador.tenant_id == user.tenant_id))
    if not d or d.ficheiro is None:
        raise HTTPException(404, "Anexo não encontrado")
    obter(db, Colaborador, d.colaborador_id, user)  # âmbito (supervisor: só a sua zona)
    op.auditar(db, user, "documento_colaborador", d.id, "descarregar", {"ficheiro": d.ficheiro_nome})  # RGPD
    db.commit()
    nome = d.ficheiro_nome or "documento"
    return Response(d.ficheiro, media_type=d.ficheiro_tipo or "application/octet-stream",
                    headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(nome)}",
                             "Cache-Control": "no-store"})
