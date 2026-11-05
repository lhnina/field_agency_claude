"""Equipas Fixas: colaboradores dedicados a um cliente, que fazem rotas de lojas segundo uma escala semanal.

Faturação mensal, por elemento da equipa:
    custo real (horas validadas × custo/hora com encargos)
  + valor de gestão (mensal, em proporção dos dias do elemento na equipa nesse mês)
  + despesas refaturadas (viatura, combustível, portagens, telemóvel…) × (1 + acréscimo %)
A margem da agência é o valor de gestão mais o acréscimo das despesas.
Os dias de trabalho geram-se a partir da escala (rota e horário por dia da semana); faltas e
substituições registam-se no próprio dia. Um mês só fecha com todos os dias validados.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Ausencia, Colaborador, Contrato, DespesaEquipa, ElementoEquipa, EscalaEquipa, EstadoContrato, EstadoServicoEquipa,
    Loja, RotaEquipa, RotaLoja, ServicoEquipa, Tenant, TipoContrato,
)
from app.services import operacao as op

Z = Decimal("0")
TIPOS_DESPESA = {"viatura": "Viatura", "combustivel": "Combustível", "portagens": "Portagens",
                 "telemovel": "Telemóvel", "alojamento": "Alojamento/refeições", "outra": "Outra"}
ATIVOS = (EstadoServicoEquipa.planeado, EstadoServicoEquipa.validado)


def _min(h: str) -> int:
    hh, mm = h.split(":")
    return int(hh) * 60 + int(mm)


def horas(hora_inicio: str, hora_fim: str, pausa_min: int) -> Decimal:
    m = _min(hora_fim) - _min(hora_inicio)
    if m <= 0:
        m += 24 * 60
    m = max(0, m - (pausa_min or 0))
    return (Decimal(m) / Decimal(60)).quantize(Decimal("0.01"))


def horas_servico(s: ServicoEquipa) -> Decimal:
    """Horas que contam: as validadas (ou as planeadas enquanto não há validação); falta/cancelado = 0."""
    if s.estado not in ATIVOS:
        return Z
    return s.horas_reais if s.horas_reais is not None else s.horas_planeadas


def valor_gestao(el: ElementoEquipa, c: Contrato) -> Decimal:
    return el.valor_gestao if el.valor_gestao is not None else (c.valor_gestao or Z)


def horas_semana(el: ElementoEquipa) -> Decimal:
    return sum((horas(e.hora_inicio, e.hora_fim, e.pausa_min) for e in el.escala), Z)


def vigente(el: ElementoEquipa, d: date) -> bool:
    return el.desde <= d and (el.ate is None or el.ate >= d)


def _fim_elemento(el: ElementoEquipa, c: Contrato) -> date | None:
    fins = [x for x in (el.ate, c.fim, el.colaborador.data_saida if el.colaborador else None) if x is not None]
    return min(fins) if fins else None


def carregar_contrato(db: Session, cid: int) -> Contrato:
    return db.scalar(select(Contrato).where(Contrato.id == cid))


def elementos(db: Session, contrato_id: int) -> list[ElementoEquipa]:
    return list(db.scalars(select(ElementoEquipa).options(
        selectinload(ElementoEquipa.escala).joinedload(EscalaEquipa.rota), joinedload(ElementoEquipa.colaborador))
        .where(ElementoEquipa.contrato_id == contrato_id).order_by(ElementoEquipa.desde, ElementoEquipa.id)).unique().all())


def rotas(db: Session, contrato_id: int) -> list[RotaEquipa]:
    return list(db.scalars(select(RotaEquipa).options(selectinload(RotaEquipa.lojas).joinedload(RotaLoja.loja))
                           .where(RotaEquipa.contrato_id == contrato_id).order_by(RotaEquipa.ativo.desc(), RotaEquipa.nome)).unique().all())


# ------------------------------------------------------------------ geração dos dias
def gerar(db: Session, c: Contrato, desde: date, ate: date) -> int:
    """Cria (de forma idempotente) os dias de trabalho da escala entre duas datas. Só contratos em curso."""
    if c.tipo != TipoContrato.EQF or c.estado != EstadoContrato.ativo:
        return 0
    criados = 0
    for el in elementos(db, c.id):
        if not el.escala:
            continue
        ini = max(desde, el.desde, c.inicio)
        fim = min(x for x in (ate, _fim_elemento(el, c)) if x is not None)
        if fim < ini:
            continue
        por_dia = {e.dia: e for e in el.escala}
        existentes = set(db.scalars(select(ServicoEquipa.data).where(
            ServicoEquipa.elemento_id == el.id, ServicoEquipa.data.between(ini, fim))).all())
        feriados = op.feriados_entre(db, c.tenant_id, ini, fim, el.colaborador.zona_id)
        d = ini
        while d <= fim:
            e = por_dia.get(d.weekday())
            if e and d not in existentes and d not in feriados:
                db.add(ServicoEquipa(tenant_id=c.tenant_id, contrato_id=c.id, elemento_id=el.id, colaborador_id=el.colaborador_id,
                                     rota_id=e.rota_id, data=d, hora_inicio=e.hora_inicio, hora_fim=e.hora_fim,
                                     pausa_min=e.pausa_min, horas_planeadas=horas(e.hora_inicio, e.hora_fim, e.pausa_min)))
                criados += 1
            d += timedelta(days=1)
    db.flush()
    return criados


def regenerar(db: Session, c: Contrato, desde: date, ate: date, elemento_id: int | None = None) -> None:
    """Depois de mudar a escala: refaz os dias futuros ainda planeados e não mexidos à mão."""
    q = select(ServicoEquipa).where(ServicoEquipa.contrato_id == c.id, ServicoEquipa.data >= desde,
                                    ServicoEquipa.estado == EstadoServicoEquipa.planeado, ServicoEquipa.alterado.is_(False))
    if elemento_id:
        q = q.where(ServicoEquipa.elemento_id == elemento_id)
    for s in db.scalars(q).all():
        db.delete(s)
    db.flush()
    gerar(db, c, desde, ate)


def garantir(db: Session, tenant_id: int, ate: date) -> None:
    """Estende a geração dos contratos em curso até `ate` (a escala não tem fim)."""
    hoje = date.today()
    for c in db.scalars(select(Contrato).where(Contrato.tenant_id == tenant_id, Contrato.tipo == TipoContrato.EQF,
                                               Contrato.estado == EstadoContrato.ativo)).all():
        gerar(db, c, max(hoje - timedelta(days=7), c.inicio), ate)


def sair(db: Session, user, c: Colaborador) -> int:
    """Data de saída do colaborador: termina-o nas equipas e retira os dias seguintes por validar."""
    n = 0
    depois = c.data_saida + timedelta(days=1)
    for el in db.scalars(select(ElementoEquipa).where(ElementoEquipa.colaborador_id == c.id)).all():
        if el.ate is None or el.ate > c.data_saida:
            el.ate = max(el.desde, c.data_saida)
            n += 1
    for s in db.scalars(select(ServicoEquipa).options(joinedload(ServicoEquipa.elemento)).where(
            ServicoEquipa.colaborador_id == c.id, ServicoEquipa.data >= depois,
            ServicoEquipa.estado == EstadoServicoEquipa.planeado)).all():
        if s.elemento.colaborador_id == c.id:
            db.delete(s)
        else:  # era substituto: volta ao titular
            s.colaborador_id = s.elemento.colaborador_id
        n += 1
    db.flush()
    return n


# ------------------------------------------------------------------ alertas e JSON
class Contexto:
    def __init__(self, db: Session, tenant_id: int, servicos: list[ServicoEquipa]):
        datas = {s.data for s in servicos}
        self.ausencias: dict[int, list[Ausencia]] = defaultdict(list)
        self.outros: dict[tuple[int, date], Decimal] = defaultdict(lambda: Z)
        if datas:
            ini, fim = min(datas), max(datas)
            for a in db.scalars(select(Ausencia).where(Ausencia.tenant_id == tenant_id, Ausencia.inicio <= fim,
                                                       Ausencia.fim >= ini)).all():
                self.ausencias[a.colaborador_id].append(a)
            # horas do colaborador noutros serviços (reposição/promoções e outras equipas) no mesmo dia
            for (cid, d), h in op.horas_colaborador_dia(db, tenant_id, ini, fim).items():
                self.outros[(cid, d)] += h
        from app.services import documentos as dc  # import local: evita ciclo
        self.doc = dc.contexto(db, tenant_id)

    def ausente(self, cid: int, d: date) -> bool:
        return any(a.inicio <= d <= a.fim for a in self.ausencias.get(cid, []))

    def alertas(self, s: ServicoEquipa) -> list[str]:
        if s.estado != EstadoServicoEquipa.planeado:
            return []
        out = []
        if self.ausente(s.colaborador_id, s.data):
            out.append("Ausente neste dia: registe a falta ou um substituto")
        total = self.outros.get((s.colaborador_id, s.data), Z)
        if total > Decimal("8"):
            out.append(f"{total:g} h no dia, contando com outros serviços (limite 8 h)")
        if s.colaborador and op.saiu(s.colaborador, s.data):
            out.append("O colaborador já saiu nesta data")
        if s.rota and s.colaborador:
            falhas = set()
            for rl in s.rota.lojas:
                falhas.update(self.doc.falhas(s.colaborador, s.contrato.cliente_id, rl.loja.insignia_id, s.data))
            out += [f"Documentação: {f}" for f in sorted(falhas)]
        if s.data < date.today():
            out.append("Dia passado por validar")
        return out


def opcoes():
    return (joinedload(ServicoEquipa.contrato).joinedload(Contrato.cliente),
            joinedload(ServicoEquipa.elemento).joinedload(ElementoEquipa.colaborador),
            joinedload(ServicoEquipa.colaborador),
            joinedload(ServicoEquipa.rota).selectinload(RotaEquipa.lojas).joinedload(RotaLoja.loja))


def servico_json(s: ServicoEquipa, ctx: Contexto | None = None) -> dict:
    titular = s.elemento.colaborador
    return {
        "id": s.id, "contrato_id": s.contrato_id, "contrato_numero": s.contrato.numero, "cliente": s.contrato.cliente.nome,
        "elemento_id": s.elemento_id, "titular_id": titular.id, "titular": titular.nome,
        "colaborador_id": s.colaborador_id, "colaborador": s.colaborador.nome, "substituicao": s.colaborador_id != titular.id,
        "rota_id": s.rota_id, "rota": s.rota.nome if s.rota else None,
        "lojas": [rl.loja.nome for rl in s.rota.lojas] if s.rota else [],
        "data": s.data.isoformat(), "hora_inicio": s.hora_inicio, "hora_fim": s.hora_fim, "pausa_min": s.pausa_min,
        "horas_planeadas": float(s.horas_planeadas), "horas_reais": float(s.horas_reais) if s.horas_reais is not None else None,
        "estado": s.estado.value, "alterado": s.alterado, "observacao": s.observacao,
        "alertas": ctx.alertas(s) if ctx else [],
    }


def rota_json(r: RotaEquipa) -> dict:
    return {"id": r.id, "nome": r.nome, "observacoes": r.observacoes, "ativo": r.ativo,
            "lojas": [{"id": rl.loja.id, "nome": rl.loja.nome, "localidade": rl.loja.localidade} for rl in r.lojas]}


def elemento_json(el: ElementoEquipa, c: Contrato, hoje: date) -> dict:
    return {
        "id": el.id, "colaborador_id": el.colaborador_id, "colaborador": el.colaborador.nome, "numero": el.colaborador.numero,
        "funcao": el.colaborador.funcao, "desde": el.desde.isoformat(), "ate": el.ate.isoformat() if el.ate else None,
        "valor_gestao": float(el.valor_gestao) if el.valor_gestao is not None else None,
        "valor_gestao_efetivo": float(valor_gestao(el, c)), "observacoes": el.observacoes, "ativo": vigente(el, hoje) or el.desde > hoje,
        "horas_semana": float(horas_semana(el)), "custo_hora": float(el.colaborador.custo_hora or Z),
        "escala": [{"dia": e.dia, "rota_id": e.rota_id, "rota": e.rota.nome, "hora_inicio": e.hora_inicio, "hora_fim": e.hora_fim,
                    "pausa_min": e.pausa_min, "horas": float(horas(e.hora_inicio, e.hora_fim, e.pausa_min))} for e in el.escala],
    }


def resumo_contrato(db: Session, c: Contrato, hoje: date) -> dict:
    els = [el for el in elementos(db, c.id) if vigente(el, hoje) or el.desde > hoje]
    hs = sum((horas_semana(el) for el in els), Z)
    tenant = db.get(Tenant, c.tenant_id)
    from app.services import logistica as lg
    gestao = sum((valor_gestao(el, c) for el in els), Z)
    custo = sum((horas_semana(el) * op.SEMANAS_POR_MES * lg.custo_hora(el.colaborador, tenant) for el in els), Z)
    return {"n": len(els), "horas_semana": hs, "gestao": gestao, "custo_previsto": op.q2(custo),
            "previsto": op.q2(custo + gestao), "sem_escala": sum(1 for el in els if not el.escala)}


# ------------------------------------------------------------------ pré-faturação
def prefaturacao(db: Session, tenant_id: int, mes: date, fim: date, hoje: date, clientes: set[int] | None = None) -> list[dict]:
    tenant = db.get(Tenant, tenant_id)
    dias_mes = monthrange(mes.year, mes.month)[1]
    ultimo = fim - timedelta(days=1)
    q = select(Contrato).options(joinedload(Contrato.cliente)).where(
        Contrato.tenant_id == tenant_id, Contrato.tipo == TipoContrato.EQF,
        Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.terminado, EstadoContrato.suspenso)),
        Contrato.inicio < fim, (Contrato.fim.is_(None)) | (Contrato.fim >= mes))
    if clientes is not None:
        q = q.where(Contrato.cliente_id.in_(clientes))
    por_cliente: dict[int, dict] = {}
    for c in db.scalars(q.order_by(Contrato.numero)).unique().all():
        servs = db.scalars(select(ServicoEquipa).options(joinedload(ServicoEquipa.colaborador)).where(
            ServicoEquipa.contrato_id == c.id, ServicoEquipa.data >= mes, ServicoEquipa.data < fim)).all()
        por_el: dict[int, list[ServicoEquipa]] = defaultdict(list)
        for s in servs:
            por_el[s.elemento_id].append(s)
        linhas = []
        for el in elementos(db, c.id):
            ini = max(el.desde, c.inicio, mes)
            f = min(x for x in (_fim_elemento(el, c), ultimo) if x is not None)
            lo = por_el.get(el.id, [])
            if f < ini and not lo:
                continue
            dias = max(0, (f - ini).days + 1)
            gestao = op.q2(valor_gestao(el, c) * Decimal(dias) / Decimal(dias_mes))
            validados = [s for s in lo if s.estado == EstadoServicoEquipa.validado]
            h = sum((s.horas_reais or Z for s in validados), Z)
            from app.services import logistica as lg
            custo = op.q2(sum(((s.horas_reais or Z) * lg.custo_hora(s.colaborador, tenant) for s in validados), Z))
            pend = sum(1 for s in lo if s.estado == EstadoServicoEquipa.planeado and s.data <= min(hoje, ultimo))
            por_fazer = sum(1 for s in lo if s.estado == EstadoServicoEquipa.planeado and s.data > hoje)
            previsto = op.q2(sum((s.horas_planeadas * lg.custo_hora(s.colaborador, tenant)
                                  for s in lo if s.estado == EstadoServicoEquipa.planeado), Z))
            valor = custo + gestao
            linhas.append({
                "linha_id": el.id, "tipo": "elemento", "loja": el.colaborador.nome, "numero": el.colaborador.numero,
                "dias_vigencia": dias, "dias_mes": dias_mes, "dias_trabalho": sum(1 for s in lo if s.estado in ATIVOS),
                "faltas": sum(1 for s in lo if s.estado == EstadoServicoEquipa.falta),
                "horas_executadas": float(h), "custo": float(custo), "gestao": float(gestao), "valor": float(valor),
                "margem": float(gestao), "pendentes_validacao": pend, "por_executar": por_fazer, "custo_previsto": float(previsto),
            })
        desp = db.scalars(select(DespesaEquipa).where(DespesaEquipa.contrato_id == c.id, DespesaEquipa.data >= mes,
                                                      DespesaEquipa.data < fim)).all()
        if desp:
            custo_d = sum((d.valor for d in desp), Z)
            refat = sum((d.valor for d in desp if d.refaturar), Z)
            valor_d = op.q2(refat * (1 + (c.acrescimo_despesas_pct or Z) / 100))
            linhas.append({"linha_id": -c.id, "tipo": "despesas", "loja": f"Despesas ({len(desp)})", "numero": None,
                           "dias_vigencia": 0, "dias_mes": dias_mes, "dias_trabalho": 0, "faltas": 0, "horas_executadas": 0.0,
                           "custo": float(custo_d), "gestao": 0.0, "valor": float(valor_d), "margem": float(valor_d - custo_d),
                           "pendentes_validacao": 0, "por_executar": 0, "custo_previsto": 0.0,
                           "detalhe": {t: float(sum((d.valor for d in desp if d.tipo == t), Z)) for t in {d.tipo for d in desp}}})
        if not linhas:
            continue
        t = defaultdict(float)
        for ln in linhas:
            for k in ("valor", "custo", "gestao", "horas_executadas", "custo_previsto"):
                t[k] += ln[k]
            t["pendentes"] += ln["pendentes_validacao"]
            t["por_executar"] += ln["por_executar"]
        cl = por_cliente.setdefault(c.cliente_id, {"cliente_id": c.cliente_id, "cliente": c.cliente.nome,
                                                  "codigo_erp": c.cliente.codigo_erp, "contratos": [], "totais": defaultdict(float)})
        cl["contratos"].append({"id": c.id, "numero": c.numero, "evento": c.evento, "descricao": c.descricao,
                                "linhas": linhas, "totais": dict(t)})
        for k, v in t.items():
            cl["totais"][k] += v
    out = [{**cl, "totais": dict(cl["totais"])} for cl in por_cliente.values()]
    return sorted(out, key=lambda x: -x["totais"].get("valor", 0))
