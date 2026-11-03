"""Credenciais de loja: modelos Word versionados e emissão por colaborador e loja."""
import json
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, undefer

from app import ambito
from app.api.base import obter
from app.db import get_db
from app.models import (
    Cliente, Colaborador, Credencial, EstadoCredencial, LinhaContrato, ModeloCredencial, Tenant, User,
)
from app.security import requer
from app.services import credenciais as cr
from app.services import docx_campos as dx
from app.services import operacao as op

router = APIRouter(tags=["credenciais"])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_MODELO = 15 * 1024 * 1024


def _download(conteudo: bytes, nome: str) -> Response:
    return Response(conteudo, media_type=DOCX, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nome)}", "Cache-Control": "no-store"})


# ------------------------------------------------------------------ campos
@router.get("/credenciais/campos")
def campos(user: User = Depends(requer("colaboradores.ler"))):
    return [{"chave": c.chave, "descricao": c.descricao, "grupo": c.grupo, "marcador": "{{" + c.chave + "}}"} for c in cr.CAMPOS]


# ------------------------------------------------------------------ modelos
def _modelo_json(m: ModeloCredencial) -> dict:
    return {"id": m.id, "nome": m.nome, "versao": m.versao, "atual": m.atual, "ativo": m.ativo, "notas": m.notas,
            "cliente_id": m.cliente_id, "cliente": m.cliente.nome if m.cliente else None,
            "ficheiro_nome": m.ficheiro_nome, "ficheiro_tamanho": m.ficheiro_tamanho,
            "criado_em": m.created_at.isoformat() if m.created_at else None,
            "criado_por": m.criado_por.nome if m.criado_por else None}


def _analisar(conteudo: bytes) -> dict:
    """Campos encontrados no modelo e os que a plataforma não conhece."""
    _, desconhecidos, encontrados = dx.preencher(conteudo, lambda n: "x" if cr.resolver_nome(n) else None)
    return {"campos": sorted({cr.resolver_nome(n) for n in encontrados if cr.resolver_nome(n)}), "desconhecidos": desconhecidos}


@router.get("/modelos-credencial")
def modelos(user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    ms = db.scalars(select(ModeloCredencial).options(joinedload(ModeloCredencial.cliente), joinedload(ModeloCredencial.criado_por))
                    .where(ModeloCredencial.tenant_id == user.tenant_id)
                    .order_by(ModeloCredencial.nome, ModeloCredencial.versao.desc())).all()
    return [_modelo_json(m) for m in ms]


@router.post("/modelos-credencial", status_code=201)
async def carregar_modelo(nome: str = Form(...), cliente_id: int | None = Form(None), notas: str | None = Form(None),
                          ficheiro: UploadFile = File(...),
                          user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    """Carrega um modelo Word. Se já existe um modelo com o mesmo nome (e cliente), fica como nova versão."""
    nome = nome.strip()
    if not nome:
        raise HTTPException(422, "Indique o nome do modelo")
    if not (ficheiro.filename or "").lower().endswith(".docx"):
        raise HTTPException(422, "O modelo tem de ser um documento Word (.docx)")
    conteudo = await ficheiro.read()
    if len(conteudo) > MAX_MODELO:
        raise HTTPException(422, "O modelo não pode ter mais de 15 MB")
    try:
        dx.validar_docx(conteudo)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if cliente_id:
        obter(db, Cliente, cliente_id, user)
    anteriores = db.scalars(select(ModeloCredencial).where(
        ModeloCredencial.tenant_id == user.tenant_id, ModeloCredencial.nome.ilike(nome),
        ModeloCredencial.cliente_id.is_(None) if not cliente_id else ModeloCredencial.cliente_id == cliente_id)).all()
    versao = max((a.versao for a in anteriores), default=0) + 1
    for a in anteriores:
        a.atual = False
    m = ModeloCredencial(tenant_id=user.tenant_id, nome=anteriores[0].nome if anteriores else nome, cliente_id=cliente_id or None,
                         versao=versao, atual=True, ativo=True, notas=(notas or "").strip() or None,
                         ficheiro_nome=(ficheiro.filename or "modelo.docx")[:200], ficheiro_tamanho=len(conteudo),
                         ficheiro=conteudo, criado_por_id=user.id)
    db.add(m)
    db.flush()
    op.auditar(db, user, "modelo_credencial", m.id, "nova_versao" if anteriores else "criar",
               {"nome": m.nome, "versao": versao, "ficheiro": m.ficheiro_nome})
    db.commit()
    db.refresh(m)
    return {**_modelo_json(m), **_analisar(conteudo)}


@router.get("/modelos-credencial/{mid}/analise")
def analisar_modelo(mid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    m = db.scalar(select(ModeloCredencial).options(undefer(ModeloCredencial.ficheiro)).where(
        ModeloCredencial.id == mid, ModeloCredencial.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Modelo não encontrado")
    return _analisar(m.ficheiro)


@router.get("/modelos-credencial/{mid}/ficheiro")
def descarregar_modelo(mid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    m = db.scalar(select(ModeloCredencial).options(undefer(ModeloCredencial.ficheiro)).where(
        ModeloCredencial.id == mid, ModeloCredencial.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Modelo não encontrado")
    base = m.ficheiro_nome.rsplit(".", 1)[0]
    return _download(m.ficheiro, f"{base} (v{m.versao}).docx")


@router.post("/modelos-credencial/{mid}/estado")
def estado_modelo(mid: int, body: dict, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    """Ativa/desativa um modelo (todas as versões com o mesmo nome e cliente)."""
    m = obter(db, ModeloCredencial, mid, user)
    ativo = bool(body.get("ativo"))
    for x in db.scalars(select(ModeloCredencial).where(
            ModeloCredencial.tenant_id == user.tenant_id, ModeloCredencial.nome == m.nome,
            ModeloCredencial.cliente_id.is_(None) if m.cliente_id is None else ModeloCredencial.cliente_id == m.cliente_id)).all():
        x.ativo = ativo
    op.auditar(db, user, "modelo_credencial", m.id, "reativar" if ativo else "desativar", {"nome": m.nome})
    db.commit()
    return {"ok": True}


@router.post("/modelos-credencial/{mid}/repor")
def repor_versao(mid: int, user: User = Depends(requer("documentos.configurar")), db: Session = Depends(get_db)):
    """Volta a usar uma versão anterior: é copiada como nova versão (o histórico não se reescreve)."""
    m = db.scalar(select(ModeloCredencial).options(undefer(ModeloCredencial.ficheiro)).where(
        ModeloCredencial.id == mid, ModeloCredencial.tenant_id == user.tenant_id))
    if not m:
        raise HTTPException(404, "Modelo não encontrado")
    irmaos = db.scalars(select(ModeloCredencial).where(
        ModeloCredencial.tenant_id == user.tenant_id, ModeloCredencial.nome == m.nome,
        ModeloCredencial.cliente_id.is_(None) if m.cliente_id is None else ModeloCredencial.cliente_id == m.cliente_id)).all()
    for x in irmaos:
        x.atual = False
    novo = ModeloCredencial(tenant_id=user.tenant_id, nome=m.nome, cliente_id=m.cliente_id, versao=max(x.versao for x in irmaos) + 1,
                            atual=True, ativo=True, notas=f"Reposição da versão {m.versao}", ficheiro_nome=m.ficheiro_nome,
                            ficheiro_tamanho=m.ficheiro_tamanho, ficheiro=m.ficheiro, criado_por_id=user.id)
    db.add(novo)
    db.flush()
    op.auditar(db, user, "modelo_credencial", novo.id, "repor_versao", {"de": m.versao, "para": novo.versao})
    db.commit()
    return {"id": novo.id, "versao": novo.versao}


# ------------------------------------------------------------------ emissão
def _cred_json(c: Credencial) -> dict:
    return {"id": c.id, "numero": c.numero, "colaborador_id": c.colaborador_id, "colaborador": c.colaborador.nome,
            "colaborador_numero": c.colaborador.numero, "loja_id": c.loja_id, "loja": c.loja.nome, "cliente_id": c.cliente_id,
            "cliente": c.cliente.nome, "linha_id": c.linha_id, "emitida_em": c.emitida_em.isoformat(),
            "valida_ate": c.valida_ate.isoformat() if c.valida_ate else None, "estado": c.estado.value,
            "substitui": c.substitui.numero if c.substitui else None, "motivo": c.motivo,
            "modelo": f"{c.modelo.nome} v{c.modelo.versao}", "ficheiro_nome": c.ficheiro_nome}


def _q_cred(user: User):
    return select(Credencial).options(
        joinedload(Credencial.colaborador), joinedload(Credencial.loja), joinedload(Credencial.cliente),
        joinedload(Credencial.modelo), joinedload(Credencial.substitui)).where(Credencial.tenant_id == user.tenant_id)


def _no_ambito(db: Session, user: User, creds: list[Credencial]) -> list[Credencial]:
    zona = ambito.zona_supervisor(user)
    permitidos = ambito.clientes_permitidos(db, user)
    return [c for c in creds if (zona is None or c.colaborador.zona_id == zona)
            and (permitidos is None or c.cliente_id in permitidos)]


@router.get("/credenciais")
def listar(estado: str | None = None, colaborador_id: int | None = None, loja_id: int | None = None,
           user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    s = _q_cred(user)
    if estado:
        s = s.where(Credencial.estado == estado)
    if colaborador_id:
        s = s.where(Credencial.colaborador_id == colaborador_id)
    if loja_id:
        s = s.where(Credencial.loja_id == loja_id)
    creds = _no_ambito(db, user, list(db.scalars(s.order_by(Credencial.id.desc())).unique().all()))
    return [_cred_json(c) for c in creds]


def _modelo_para(db: Session, user: User, cliente_id: int, modelo_id: int | None) -> ModeloCredencial:
    if modelo_id:
        m = db.scalar(select(ModeloCredencial).options(undefer(ModeloCredencial.ficheiro)).where(
            ModeloCredencial.id == modelo_id, ModeloCredencial.tenant_id == user.tenant_id))
        if not m:
            raise HTTPException(404, "Modelo não encontrado")
        return m
    base = select(ModeloCredencial).options(undefer(ModeloCredencial.ficheiro)).where(
        ModeloCredencial.tenant_id == user.tenant_id, ModeloCredencial.atual.is_(True), ModeloCredencial.ativo.is_(True))
    m = db.scalar(base.where(ModeloCredencial.cliente_id == cliente_id)) or \
        db.scalar(base.where(ModeloCredencial.cliente_id.is_(None)).order_by(ModeloCredencial.id))
    if not m:
        raise HTTPException(422, "Não há nenhum modelo de credencial ativo: carregue um em Documentação › Credenciais")
    return m


def _linha(db: Session, user: User, linha_id: int) -> LinhaContrato:
    ln = obter(db, LinhaContrato, linha_id, user)
    return ln


def _validade_sugerida(ln: LinhaContrato, hoje: date) -> date:
    """Fim da linha ou do contrato; sem termo, 1 ano; nunca no passado."""
    fim = ln.fim or ln.contrato.fim
    return fim if fim and fim >= hoje else hoje.replace(year=hoje.year + 1) - timedelta(days=1)


def _substituiveis(db: Session, user: User, ln: LinhaContrato, colaborador_id: int) -> list[Credencial]:
    """Credenciais emitidas na mesma loja e cliente (de quem estava antes ou do próprio)."""
    creds = db.scalars(_q_cred(user).where(
        Credencial.loja_id == ln.loja_id, Credencial.cliente_id == ln.contrato.cliente_id,
        Credencial.estado == EstadoCredencial.emitida).order_by(Credencial.id.desc())).unique().all()
    # primeiro as de outros colaboradores (é o caso da afetação de alguém novo), depois as do próprio
    return sorted(creds, key=lambda c: (c.colaborador_id == colaborador_id, -c.id))


@router.get("/credenciais/preparar")
def preparar(colaborador_id: int, linha_id: int, user: User = Depends(requer("documentos.editar")), db: Session = Depends(get_db)):
    """Dados para o diálogo de emissão: modelo, validade sugerida, exame médico e credenciais a substituir."""
    col = obter(db, Colaborador, colaborador_id, user)
    ln = _linha(db, user, linha_id)
    hoje = date.today()
    try:
        m = _modelo_para(db, user, ln.contrato.cliente_id, None)
        modelo = {"id": m.id, "nome": m.nome, "versao": m.versao}
        usados = set(_analisar(m.ficheiro)["campos"])
    except HTTPException as e:
        modelo, usados = None, set()
        aviso_modelo = e.detail
    else:
        aviso_modelo = None
    exame = cr.exame_medico(db, col.id)
    validade = _validade_sugerida(ln, hoje)
    v = cr.valores(db, db.get(Tenant, user.tenant_id), col, ln, validade=validade, data_exame=exame, emissao=hoje, numero="", substitui=None)
    modelos = db.scalars(select(ModeloCredencial).where(
        ModeloCredencial.tenant_id == user.tenant_id, ModeloCredencial.atual.is_(True), ModeloCredencial.ativo.is_(True),
        or_(ModeloCredencial.cliente_id.is_(None), ModeloCredencial.cliente_id == ln.contrato.cliente_id))
        .order_by(ModeloCredencial.nome)).all()
    return {
        "colaborador": col.nome, "loja": ln.loja.nome, "cliente": ln.contrato.cliente.nome, "contrato": ln.contrato.numero,
        "modelo": modelo, "modelos": [{"id": x.id, "nome": x.nome, "versao": x.versao, "cliente": x.cliente_id is not None} for x in modelos],
        "aviso_modelo": aviso_modelo, "validade": validade.isoformat(),
        "data_exame_medico": exame.isoformat() if exame else None,
        "em_falta": [t for t in cr.em_falta(v, usados or None) if t != "data do exame médico"],
        "substituiveis": [_cred_json(c) for c in _substituiveis(db, user, ln, col.id)],
    }


class EmitirIn(BaseModel):
    colaborador_id: int
    linha_id: int
    modelo_id: int | None = None
    valida_ate: date | None = None
    data_exame_medico: date | None = None
    substitui_id: int | None = None
    motivo: str | None = Field(default=None, max_length=250)


@router.post("/credenciais", status_code=201)
def emitir(body: EmitirIn, user: User = Depends(requer("documentos.editar")), db: Session = Depends(get_db)):
    col = obter(db, Colaborador, body.colaborador_id, user)
    ln = _linha(db, user, body.linha_id)
    hoje = date.today()
    if body.valida_ate and body.valida_ate < hoje:
        raise HTTPException(422, "A validade da credencial não pode ser no passado")
    m = _modelo_para(db, user, ln.contrato.cliente_id, body.modelo_id)
    anterior = None
    if body.substitui_id:
        anterior = obter(db, Credencial, body.substitui_id, user)
        if anterior.loja_id != ln.loja_id or anterior.estado != EstadoCredencial.emitida:
            raise HTTPException(422, "Só pode substituir uma credencial em vigor da mesma loja")
    numero = cr.proximo_numero(db, user.tenant_id, hoje.year)
    tenant = db.get(Tenant, user.tenant_id)
    v = cr.valores(db, tenant, col, ln, validade=body.valida_ate, data_exame=body.data_exame_medico or cr.exame_medico(db, col.id),
                   emissao=hoje, numero=numero, substitui=anterior.numero if anterior else None)
    conteudo, desconhecidos, _ = dx.preencher(m.ficheiro, lambda n: v.get(cr.resolver_nome(n) or "", None)
                                                if cr.resolver_nome(n) else None, v["data_emissao_extenso"])
    nome_fich = f"Credencial {numero.replace('/', '-')} - {col.nome} - {ln.loja.nome}.docx"
    c = Credencial(tenant_id=user.tenant_id, numero=numero, colaborador_id=col.id, linha_id=ln.id, loja_id=ln.loja_id,
                   cliente_id=ln.contrato.cliente_id, modelo_id=m.id, emitida_em=hoje, valida_ate=body.valida_ate,
                   estado=EstadoCredencial.emitida, substitui_id=anterior.id if anterior else None,
                   motivo=(body.motivo or "").strip() or None, dados=json.dumps(v, ensure_ascii=False),
                   ficheiro_nome=nome_fich, ficheiro=conteudo, criado_por_id=user.id)
    db.add(c)
    if anterior:
        anterior.estado = EstadoCredencial.substituida
    db.flush()
    op.auditar(db, user, "credencial", c.id, "emitir", {"numero": numero, "colaborador": col.nome, "loja": ln.loja.nome,
                                                        "modelo": f"{m.nome} v{m.versao}",
                                                        "substitui": anterior.numero if anterior else None})
    db.commit()
    c = db.scalar(_q_cred(user).where(Credencial.id == c.id))
    return {**_cred_json(c), "desconhecidos": desconhecidos}


@router.get("/credenciais/{cid}/ficheiro")
def descarregar(cid: int, user: User = Depends(requer("colaboradores.ler")), db: Session = Depends(get_db)):
    c = db.scalar(select(Credencial).options(undefer(Credencial.ficheiro), joinedload(Credencial.colaborador)).where(
        Credencial.id == cid, Credencial.tenant_id == user.tenant_id))
    if not c or not _no_ambito(db, user, [c]):
        raise HTTPException(404, "Credencial não encontrada")
    op.auditar(db, user, "credencial", c.id, "descarregar", {"numero": c.numero})  # RGPD: tem dados pessoais
    db.commit()
    return _download(c.ficheiro, c.ficheiro_nome)


class AnularIn(BaseModel):
    motivo: str = Field(min_length=3, max_length=250)


@router.post("/credenciais/{cid}/anular")
def anular(cid: int, body: AnularIn, user: User = Depends(requer("documentos.editar")), db: Session = Depends(get_db)):
    c = db.scalar(_q_cred(user).where(Credencial.id == cid))
    if not c or not _no_ambito(db, user, [c]):
        raise HTTPException(404, "Credencial não encontrada")
    if c.estado != EstadoCredencial.emitida:
        raise HTTPException(422, "Só se anulam credenciais em vigor")
    c.estado = EstadoCredencial.anulada
    c.motivo = body.motivo.strip()
    op.auditar(db, user, "credencial", c.id, "anular", {"motivo": c.motivo})
    db.commit()
    return _cred_json(c)

