"""Equipas Fixas: rotas, elementos com escala semanal, dias de trabalho (faltas, substituições, validação) e despesas."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ambito
from app.api.base import obter
from app.config import settings
from app.db import get_db
from app.models import (
    Colaborador, Contrato, DespesaEquipa, ElementoEquipa, EscalaEquipa, EstadoContrato, EstadoServicoEquipa, Loja,
    RotaEquipa, RotaLoja, ServicoEquipa, TipoContrato, TipoVinculo, User,
)
from app.security import requer
from app.services import equipas as eq
from app.services import operacao as op
from app.services.periodos import motivo_bloqueio

router = APIRouter(tags=["equipas fixas"])
HORA = r"^([01]\d|2[0-3]):[0-5]\d$"
AREA = TipoContrato.EQF.value


def _horizonte() -> date:
    return date.today() + timedelta(days=settings.horizonte_planeamento_dias)


def _contrato(db: Session, cid: int, user: User) -> Contrato:
    c = obter(db, Contrato, cid, user)
    if c.tipo != TipoContrato.EQF:
        raise HTTPException(422, "Este contrato não é de Equipas Fixas")
    return c


def _dm(d: date) -> str:
    return d.strftime("%d/%m/%Y")


# ------------------------------------------------------------------ consulta do contrato
@router.get("/contratos/{cid}/equipa")
def equipa(cid: int, user: User = Depends(requer("contratos.ler")), db: Session = Depends(get_db)):
    c = _contrato(db, cid, user)
    hoje = date.today()
    r = eq.resumo_contrato(db, c, hoje)
    return {
        "rotas": [eq.rota_json(x) for x in eq.rotas(db, c.id)],
        "elementos": [eq.elemento_json(el, c, hoje) for el in eq.elementos(db, c.id)],
        "valor_gestao": float(c.valor_gestao) if c.valor_gestao is not None else None,
        "acrescimo_despesas_pct": float(c.acrescimo_despesas_pct or 0),
        "resumo": {"elementos": r["n"], "horas_semana": float(r["horas_semana"]),
                   "horas_mes": float(op.q2(r["horas_semana"] * op.SEMANAS_POR_MES)), "gestao_mensal": float(r["gestao"]),
                   "sem_escala": r["sem_escala"]},
    }


def _regenerar(db: Session, c: Contrato, elemento_id: int | None = None) -> None:
    if c.estado == EstadoContrato.ativo:
        eq.regenerar(db, c, max(date.today(), c.inicio), _horizonte(), elemento_id)


# ------------------------------------------------------------------ rotas
class RotaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    observacoes: str | None = None
    lojas: list[int] = Field(min_length=1)


def _gravar_rota(db: Session, user: User, r: RotaEquipa, body: RotaIn) -> None:
    if len(set(body.lojas)) != len(body.lojas):
        raise HTTPException(422, "A rota tem lojas repetidas")
    for lid in body.lojas:
        obter(db, Loja, lid, user)
    r.nome, r.observacoes = body.nome.strip(), (body.observacoes or "").strip() or None
    r.lojas.clear()
    db.flush()
    for i, lid in enumerate(body.lojas):
        r.lojas.append(RotaLoja(loja_id=lid, ordem=i))


@router.post("/contratos/{cid}/rotas", status_code=201)
def criar_rota(cid: int, body: RotaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _contrato(db, cid, user)
    if db.scalar(select(RotaEquipa).where(RotaEquipa.contrato_id == c.id, RotaEquipa.nome.ilike(body.nome.strip()))):
        raise HTTPException(409, f"Já existe a rota {body.nome.strip()} neste contrato")
    r = RotaEquipa(tenant_id=user.tenant_id, contrato_id=c.id, nome=body.nome.strip())
    db.add(r)
    _gravar_rota(db, user, r, body)
    db.flush()
    op.auditar(db, user, "rota_equipa", r.id, "criar", body.model_dump())
    db.commit()
    return eq.rota_json(next(x for x in eq.rotas(db, c.id) if x.id == r.id))


@router.put("/rotas-equipa/{rid}")
def editar_rota(rid: int, body: RotaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    r = obter(db, RotaEquipa, rid, user)
    c = _contrato(db, r.contrato_id, user)
    if db.scalar(select(RotaEquipa).where(RotaEquipa.contrato_id == c.id, RotaEquipa.id != r.id,
                                          RotaEquipa.nome.ilike(body.nome.strip()))):
        raise HTTPException(409, f"Já existe a rota {body.nome.strip()} neste contrato")
    _gravar_rota(db, user, r, body)
    op.auditar(db, user, "rota_equipa", r.id, "editar", body.model_dump())
    db.commit()
    return eq.rota_json(next(x for x in eq.rotas(db, c.id) if x.id == r.id))


@router.post("/rotas-equipa/{rid}/estado")
def estado_rota(rid: int, body: dict, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    r = obter(db, RotaEquipa, rid, user)
    _contrato(db, r.contrato_id, user)
    ativo = bool(body.get("ativo"))
    if not ativo:
        em_uso = db.scalars(select(ElementoEquipa).join(EscalaEquipa).where(
            EscalaEquipa.rota_id == r.id, (ElementoEquipa.ate.is_(None)) | (ElementoEquipa.ate >= date.today()))).unique().all()
        if em_uso:
            raise HTTPException(422, "A rota está na escala de " + ", ".join(el.colaborador.nome for el in em_uso)
                                + ": retire-a da escala antes de a desativar")
    r.ativo = ativo
    op.auditar(db, user, "rota_equipa", r.id, "reativar" if ativo else "desativar", None)
    db.commit()
    return eq.rota_json(r)


# ------------------------------------------------------------------ elementos e escala
class DiaEscala(BaseModel):
    dia: int = Field(ge=0, le=6)
    rota_id: int
    hora_inicio: str = Field(pattern=HORA)
    hora_fim: str = Field(pattern=HORA)
    pausa_min: int = Field(default=60, ge=0, le=240)


class ElementoIn(BaseModel):
    colaborador_id: int
    desde: date
    ate: date | None = None
    valor_gestao: Decimal | None = Field(default=None, ge=0)
    observacoes: str | None = None
    escala: list[DiaEscala] = []

    @model_validator(mode="after")
    def _v(self):
        if self.ate and self.ate < self.desde:
            raise ValueError("A data de fim é anterior à data de início")
        if len({d.dia for d in self.escala}) != len(self.escala):
            raise ValueError("A escala tem dias repetidos")
        for d in self.escala:
            if eq.horas(d.hora_inicio, d.hora_fim, d.pausa_min) <= 0:
                raise ValueError("O horário de um dia não tem horas (verifique a pausa)")
        return self


def _validar_elemento(db: Session, user: User, c: Contrato, body: ElementoIn, exceto: int | None = None) -> Colaborador:
    col = obter(db, Colaborador, body.colaborador_id, user)
    if not col.ativo:
        raise HTTPException(422, f"{col.nome} está inativo")
    if col.vinculo == TipoVinculo.recibos_verdes:
        raise HTTPException(422, "Um prestador (recibos verdes) não pode fazer parte de uma equipa fixa")
    if body.desde < c.inicio or (c.fim and body.desde > c.fim):
        raise HTTPException(422, f"O início tem de estar dentro da vigência do contrato ({_dm(c.inicio)} – "
                                 f"{_dm(c.fim) if c.fim else 'sem termo'})")
    if c.fim and body.ate and body.ate > c.fim:
        raise HTTPException(422, f"O fim não pode ser depois do fim do contrato ({_dm(c.fim)})")
    if col.data_saida and body.desde > col.data_saida:
        raise HTTPException(422, f"{col.nome} sai a {_dm(col.data_saida)}")
    rotas_ok = {r.id for r in eq.rotas(db, c.id) if r.ativo}
    if any(d.rota_id not in rotas_ok for d in body.escala):
        raise HTTPException(422, "A escala usa uma rota que não é deste contrato ou está inativa")
    for el in db.scalars(select(ElementoEquipa).where(ElementoEquipa.contrato_id == c.id,
                                                      ElementoEquipa.colaborador_id == col.id)).all():
        if el.id == exceto:
            continue
        if (el.ate is None or el.ate >= body.desde) and (body.ate is None or body.ate >= el.desde):
            raise HTTPException(409, f"{col.nome} já faz parte desta equipa nesse período")
    return col


def _gravar_escala(db: Session, el: ElementoEquipa, body: ElementoIn) -> None:
    el.escala.clear()
    db.flush()  # apaga antes de inserir (dia único por colaborador)
    for d in sorted(body.escala, key=lambda x: x.dia):
        el.escala.append(EscalaEquipa(**d.model_dump()))


def _elemento_out(db: Session, el_id: int, c: Contrato) -> dict:
    return eq.elemento_json(next(x for x in eq.elementos(db, c.id) if x.id == el_id), c, date.today())


@router.post("/contratos/{cid}/elementos", status_code=201)
def criar_elemento(cid: int, body: ElementoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _contrato(db, cid, user)
    col = _validar_elemento(db, user, c, body)
    ate = body.ate
    if col.data_saida and (ate is None or ate > col.data_saida):
        ate = col.data_saida
    el = ElementoEquipa(tenant_id=user.tenant_id, contrato_id=c.id, colaborador_id=col.id, desde=body.desde, ate=ate,
                        valor_gestao=body.valor_gestao, observacoes=(body.observacoes or "").strip() or None)
    db.add(el)
    _gravar_escala(db, el, body)
    db.flush()
    op.auditar(db, user, "elemento_equipa", el.id, "criar", body.model_dump())
    _regenerar(db, c, el.id)
    db.commit()
    return _elemento_out(db, el.id, c)


@router.put("/elementos-equipa/{eid}")
def editar_elemento(eid: int, body: ElementoIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    el = obter(db, ElementoEquipa, eid, user)
    c = _contrato(db, el.contrato_id, user)
    if body.colaborador_id != el.colaborador_id:
        raise HTTPException(422, "Para mudar de colaborador, termine este e acrescente outro à equipa")
    col = _validar_elemento(db, user, c, body, exceto=el.id)
    antes = eq.elemento_json(el, c, date.today())
    el.desde, el.ate = body.desde, (min(body.ate, col.data_saida) if body.ate and col.data_saida else body.ate or col.data_saida)
    el.valor_gestao, el.observacoes = body.valor_gestao, (body.observacoes or "").strip() or None
    _gravar_escala(db, el, body)
    db.flush()
    # dias planeados fora do novo período saem
    for s in db.scalars(select(ServicoEquipa).where(ServicoEquipa.elemento_id == el.id,
                                                    ServicoEquipa.estado == EstadoServicoEquipa.planeado)).all():
        if s.data < el.desde or (el.ate and s.data > el.ate):
            db.delete(s)
    op.auditar(db, user, "elemento_equipa", el.id, "editar", {"antes": antes, "depois": body.model_dump()})
    _regenerar(db, c, el.id)
    db.commit()
    return _elemento_out(db, el.id, c)


# ------------------------------------------------------------------ semana
def _visivel(db: Session, user: User, s: ServicoEquipa, permitidos: set[int] | None, zona: int | None) -> bool:
    if permitidos is not None and s.contrato.cliente_id not in permitidos:
        return False
    return zona is None or ambito.servico_equipa_na_zona(s, zona)


@router.get("/equipas/semana")
def semana(inicio: date | None = None, contrato_id: int | None = None, cliente_id: int | None = None,
           user: User = Depends(requer("planeamento.ler")), db: Session = Depends(get_db)):
    d = inicio or date.today()
    seg = d - timedelta(days=d.weekday())
    dom = seg + timedelta(days=6)
    eq.garantir(db, user.tenant_id, max(dom, _horizonte()))
    db.commit()
    q = (select(ServicoEquipa).options(*eq.opcoes()).join(Contrato, ServicoEquipa.contrato_id == Contrato.id)
         .where(ServicoEquipa.tenant_id == user.tenant_id, ServicoEquipa.data.between(seg, dom),
                ServicoEquipa.estado != EstadoServicoEquipa.cancelado, Contrato.estado == EstadoContrato.ativo))
    if contrato_id:
        q = q.where(ServicoEquipa.contrato_id == contrato_id)
    if cliente_id:
        q = q.where(Contrato.cliente_id == cliente_id)
    permitidos, zona = ambito.clientes_permitidos(db, user), ambito.zona_supervisor(user)
    servs = [s for s in db.scalars(q.order_by(ServicoEquipa.data)).unique().all() if _visivel(db, user, s, permitidos, zona)]
    ctx = eq.Contexto(db, user.tenant_id, servs)
    linhas: dict[int, dict] = {}
    for s in servs:
        el = s.elemento
        ln = linhas.setdefault(el.id, {"elemento_id": el.id, "colaborador_id": el.colaborador_id, "colaborador": el.colaborador.nome,
                                       "funcao": el.colaborador.funcao, "contrato_id": s.contrato_id,
                                       "contrato_numero": s.contrato.numero, "cliente": s.contrato.cliente.nome,
                                       "dias": {}, "horas": 0.0})
        j = eq.servico_json(s, ctx)
        ln["dias"][j["data"]] = j
        ln["horas"] += float(eq.horas_servico(s))
    itens = sorted(linhas.values(), key=lambda x: (x["cliente"], x["contrato_numero"], x["colaborador"]))
    todos = [j for ln in itens for j in ln["dias"].values()]
    return {"inicio": seg.isoformat(), "fim": dom.isoformat(),
            "dias": [(seg + timedelta(days=i)).isoformat() for i in range(7)], "linhas": itens,
            "resumo": {"dias": len(todos), "por_validar": sum(1 for j in todos if j["estado"] == "planeado" and j["data"] <= date.today().isoformat()),
                       "validados": sum(1 for j in todos if j["estado"] == "validado"),
                       "faltas": sum(1 for j in todos if j["estado"] == "falta"),
                       "substituicoes": sum(1 for j in todos if j["substituicao"]),
                       "com_alertas": sum(1 for j in todos if j["alertas"]),
                       "horas": sum(ln["horas"] for ln in itens), "elementos": len(itens)}}


# ------------------------------------------------------------------ dia de trabalho
def _servico(db: Session, user: User, sid: int) -> ServicoEquipa:
    s = db.scalar(select(ServicoEquipa).options(*eq.opcoes()).where(ServicoEquipa.id == sid,
                                                                    ServicoEquipa.tenant_id == user.tenant_id))
    if not s:
        raise HTTPException(404, "Registo não encontrado")
    ambito.verificar(db, user, s)
    return s


def _editavel(db: Session, user: User, s: ServicoEquipa) -> None:
    if (m := motivo_bloqueio(db, user.tenant_id, s.data, AREA)):
        raise HTTPException(422, m)


class DiaIn(BaseModel):
    colaborador_id: int
    rota_id: int | None = None
    hora_inicio: str = Field(pattern=HORA)
    hora_fim: str = Field(pattern=HORA)
    pausa_min: int = Field(default=60, ge=0, le=240)
    observacao: str | None = Field(default=None, max_length=250)


@router.put("/servicos-equipa/{sid}")
def editar_dia(sid: int, body: DiaIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    """Substituto, rota ou horário de um só dia. A escala de base mantém-se."""
    s = _servico(db, user, sid)
    _editavel(db, user, s)
    if s.estado == EstadoServicoEquipa.validado:
        raise HTTPException(422, "Este dia já está validado: reabra-o antes de o alterar")
    col = obter(db, Colaborador, body.colaborador_id, user)
    if op.saiu(col, s.data):
        raise HTTPException(422, f"{col.nome} sai a {_dm(col.data_saida)}: não pode trabalhar depois dessa data")
    if body.rota_id and body.rota_id not in {r.id for r in eq.rotas(db, s.contrato_id)}:
        raise HTTPException(422, "A rota não é deste contrato")
    h = eq.horas(body.hora_inicio, body.hora_fim, body.pausa_min)
    if h <= 0:
        raise HTTPException(422, "O horário não tem horas (verifique a pausa)")
    antes = eq.servico_json(s)
    s.colaborador_id, s.rota_id = col.id, body.rota_id or s.rota_id
    s.hora_inicio, s.hora_fim, s.pausa_min, s.horas_planeadas = body.hora_inicio, body.hora_fim, body.pausa_min, h
    s.observacao = (body.observacao or "").strip() or None
    s.alterado = True
    op.auditar(db, user, "servico_equipa", s.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    return eq.servico_json(_servico(db, user, s.id))


class FaltaIn(BaseModel):
    motivo: str = Field(min_length=2, max_length=250)


@router.post("/servicos-equipa/{sid}/falta")
def falta(sid: int, body: FaltaIn, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    s = _servico(db, user, sid)
    _editavel(db, user, s)
    s.estado, s.observacao, s.horas_reais, s.alterado = EstadoServicoEquipa.falta, body.motivo.strip(), None, True
    op.auditar(db, user, "servico_equipa", s.id, "falta", {"motivo": s.observacao})
    db.commit()
    return eq.servico_json(_servico(db, user, s.id))


@router.post("/servicos-equipa/{sid}/repor")
def repor(sid: int, user: User = Depends(requer("planeamento.editar")), db: Session = Depends(get_db)):
    """Volta a «planeado» (anula uma falta ou reabre um dia validado para correção)."""
    s = _servico(db, user, sid)
    _editavel(db, user, s)
    antes = s.estado.value
    s.estado, s.horas_reais, s.validado_por_id = EstadoServicoEquipa.planeado, None, None
    op.auditar(db, user, "servico_equipa", s.id, "repor", {"antes": antes})
    db.commit()
    return eq.servico_json(_servico(db, user, s.id))


class ValidarIn(BaseModel):
    ids: list[int] = Field(min_length=1)
    horas: Decimal | None = Field(default=None, ge=0, le=24)  # só para um dia; vazio = horas planeadas


@router.post("/servicos-equipa/validar")
def validar(body: ValidarIn, user: User = Depends(requer("validacao.editar")), db: Session = Depends(get_db)):
    if body.horas is not None and len(body.ids) != 1:
        raise HTTPException(422, "As horas reais indicam-se dia a dia")
    hoje, n, ignorados = date.today(), 0, 0
    for sid in body.ids:
        s = _servico(db, user, sid)
        if s.estado != EstadoServicoEquipa.planeado or s.data > hoje:
            ignorados += 1
            continue
        _editavel(db, user, s)
        s.horas_reais = body.horas if body.horas is not None else s.horas_planeadas
        s.estado, s.validado_por_id = EstadoServicoEquipa.validado, user.id
        op.auditar(db, user, "servico_equipa", s.id, "validar", {"horas": s.horas_reais})
        n += 1
    db.commit()
    return {"validados": n, "ignorados": ignorados}


# ------------------------------------------------------------------ despesas
class DespesaIn(BaseModel):
    data: date
    tipo: str
    descricao: str | None = Field(default=None, max_length=200)
    valor: Decimal = Field(gt=0, le=Decimal("999999"))
    elemento_id: int | None = None
    refaturar: bool = True

    @model_validator(mode="after")
    def _t(self):
        if self.tipo not in eq.TIPOS_DESPESA:
            raise ValueError("Tipo de despesa inválido")
        return self


def _despesa_json(d: DespesaEquipa) -> dict:
    return {"id": d.id, "data": d.data.isoformat(), "tipo": d.tipo, "tipo_label": eq.TIPOS_DESPESA.get(d.tipo, d.tipo),
            "descricao": d.descricao, "valor": float(d.valor), "elemento_id": d.elemento_id,
            "colaborador": d.elemento.colaborador.nome if d.elemento else None, "refaturar": d.refaturar}


def _validar_despesa(db: Session, user: User, c: Contrato, body: DespesaIn) -> None:
    if body.data < c.inicio or (c.fim and body.data > c.fim):
        raise HTTPException(422, "A data da despesa tem de estar dentro da vigência do contrato")
    if (m := motivo_bloqueio(db, user.tenant_id, body.data, AREA)):
        raise HTTPException(422, m)
    if body.elemento_id:
        el = obter(db, ElementoEquipa, body.elemento_id, user)
        if el.contrato_id != c.id:
            raise HTTPException(422, "O colaborador não é desta equipa")


@router.get("/contratos/{cid}/despesas")
def despesas(cid: int, mes: date | None = None, user: User = Depends(requer("contratos.ler")), db: Session = Depends(get_db)):
    c = _contrato(db, cid, user)
    m = (mes or date.today()).replace(day=1)
    prox = (m + timedelta(days=32)).replace(day=1)
    itens = db.scalars(select(DespesaEquipa).where(DespesaEquipa.contrato_id == c.id, DespesaEquipa.data >= m,
                                                   DespesaEquipa.data < prox).order_by(DespesaEquipa.data, DespesaEquipa.id)).all()
    total = sum((d.valor for d in itens), Decimal("0"))
    refat = sum((d.valor for d in itens if d.refaturar), Decimal("0"))
    return {"mes": m.isoformat(), "itens": [_despesa_json(d) for d in itens], "tipos": eq.TIPOS_DESPESA,
            "totais": {"custo": float(total), "refaturado": float(op.q2(refat * (1 + (c.acrescimo_despesas_pct or 0) / 100)))},
            "bloqueio": motivo_bloqueio(db, user.tenant_id, m, AREA)}


@router.post("/contratos/{cid}/despesas", status_code=201)
def criar_despesa(cid: int, body: DespesaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    c = _contrato(db, cid, user)
    _validar_despesa(db, user, c, body)
    d = DespesaEquipa(tenant_id=user.tenant_id, contrato_id=c.id, registado_por_id=user.id,
                      **{**body.model_dump(), "descricao": (body.descricao or "").strip() or None})
    db.add(d)
    db.flush()
    op.auditar(db, user, "despesa_equipa", d.id, "criar", body.model_dump())
    db.commit()
    db.refresh(d)
    return _despesa_json(d)


@router.put("/despesas-equipa/{did}")
def editar_despesa(did: int, body: DespesaIn, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    d = obter(db, DespesaEquipa, did, user)
    c = _contrato(db, d.contrato_id, user)
    if (m := motivo_bloqueio(db, user.tenant_id, d.data, AREA)):
        raise HTTPException(422, m)
    _validar_despesa(db, user, c, body)
    antes = _despesa_json(d)
    for k, v in {**body.model_dump(), "descricao": (body.descricao or "").strip() or None}.items():
        setattr(d, k, v)
    op.auditar(db, user, "despesa_equipa", d.id, "editar", {"antes": antes, "depois": body.model_dump()})
    db.commit()
    db.refresh(d)
    return _despesa_json(d)


@router.delete("/despesas-equipa/{did}")
def apagar_despesa(did: int, user: User = Depends(requer("contratos.editar")), db: Session = Depends(get_db)):
    d = obter(db, DespesaEquipa, did, user)
    _contrato(db, d.contrato_id, user)
    if (m := motivo_bloqueio(db, user.tenant_id, d.data, AREA)):
        raise HTTPException(422, m)
    op.auditar(db, user, "despesa_equipa", d.id, "apagar", _despesa_json(d))
    db.delete(d)
    db.commit()
    return {"ok": True}
