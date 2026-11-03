"""Logística: serviços pontuais (entrega, recolha, implementação, desmontagem) com viatura e motorista.

Faturação: preço por serviço, para os serviços validados (ou executados) com data no mês.
Custo: km (chegada − partida) × custo/km da viatura + portagens + outros custos
       + horas de execução × custo/hora (com encargos) do motorista e do ajudante.
A gestão física de stock dos materiais fica para uma fase posterior: aqui os materiais são texto.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Ausencia, Colaborador, Contrato, EstadoServicoLog, Loja, ServicoLogistico, Tenant, TipoServicoLog,
)

Z = Decimal("0")
TIPO_LABEL = {
    TipoServicoLog.entrega: "Entrega", TipoServicoLog.recolha: "Recolha", TipoServicoLog.implementacao: "Implementação",
    TipoServicoLog.entrega_implementacao: "Entrega + Implementação", TipoServicoLog.desmontagem: "Desmontagem",
}
FATURAVEIS = (EstadoServicoLog.executado, EstadoServicoLog.validado)


def minutos(h: str | None) -> int | None:
    if not h:
        return None
    hh, mm = h.split(":")
    return int(hh) * 60 + int(mm)


def horas_execucao(s: ServicoLogistico) -> Decimal:
    a, b = minutos(s.inicio_real), minutos(s.fim_real)
    if a is None or b is None:
        return Z
    if b < a:  # passou a meia-noite
        b += 24 * 60
    return (Decimal(b - a) / Decimal(60)).quantize(Decimal("0.01"))


def km(s: ServicoLogistico) -> int:
    if s.km_partida is None or s.km_chegada is None:
        return 0
    return max(0, s.km_chegada - s.km_partida)


def custo_hora(c: Colaborador | None, tenant: Tenant | None) -> Decimal:
    if c is None:
        return Z
    base = c.custo_hora or Z
    return base * (1 + (tenant.encargos_pct(c.vinculo) if tenant else Z) / 100)


def custos(s: ServicoLogistico, tenant: Tenant | None) -> dict:
    """Custo do serviço (só faz sentido depois de executado)."""
    h = horas_execucao(s)
    k = km(s)
    c_km = (Decimal(k) * (s.viatura.custo_km if s.viatura else Z)).quantize(Decimal("0.01"))
    mao = (h * (custo_hora(s.colaborador, tenant) + custo_hora(s.ajudante, tenant))).quantize(Decimal("0.01"))
    port, outros = s.portagens or Z, s.outros_custos or Z
    total = c_km + mao + port + outros
    return {"km": k, "custo_km": float(c_km), "horas": float(h), "mao_obra": float(mao), "portagens": float(port),
            "outros": float(outros), "total": float(total)}


def _sobrepoe(a: ServicoLogistico, b: ServicoLogistico) -> bool:
    ai, af, bi, bf = minutos(a.hora_inicio), minutos(a.hora_fim), minutos(b.hora_inicio), minutos(b.hora_fim)
    if None in (ai, af, bi, bf):
        return False
    return ai < bf and bi < af


class Contexto:
    """Dados carregados uma vez para calcular alertas de muitos serviços."""

    def __init__(self, db: Session, tenant_id: int, servicos: list[ServicoLogistico]):
        datas = {s.data for s in servicos}
        self.por_dia: dict[date, list[ServicoLogistico]] = defaultdict(list)
        if datas:
            for s in db.scalars(select(ServicoLogistico).where(
                    ServicoLogistico.tenant_id == tenant_id, ServicoLogistico.data.in_(datas),
                    ServicoLogistico.estado != EstadoServicoLog.cancelado)).all():
                self.por_dia[s.data].append(s)
        self.ausencias: dict[int, list[Ausencia]] = defaultdict(list)
        if datas:
            for a in db.scalars(select(Ausencia).where(Ausencia.tenant_id == tenant_id, Ausencia.inicio <= max(datas),
                                                       Ausencia.fim >= min(datas))).all():
                self.ausencias[a.colaborador_id].append(a)
        from app.services import documentos as dc  # import local: evita ciclo
        self.doc = dc.contexto(db, tenant_id)

    def ausente(self, cid: int | None, d: date) -> bool:
        return bool(cid) and any(a.inicio <= d <= a.fim for a in self.ausencias.get(cid, []))

    def alertas(self, s: ServicoLogistico) -> list[str]:
        if s.estado not in (EstadoServicoLog.planeado, EstadoServicoLog.atribuido):
            return []  # depois de executado, os avisos de planeamento já não interessam
        out = []
        if s.estado == EstadoServicoLog.planeado:
            if not s.viatura_id:
                out.append("Sem viatura")
            if not s.colaborador_id:
                out.append("Sem motorista")
        outros = [x for x in self.por_dia.get(s.data, []) if x.id != s.id]
        if s.viatura_id and any(x.viatura_id == s.viatura_id and _sobrepoe(s, x) for x in outros):
            out.append("Viatura com outro serviço à mesma hora")
        for cid, papel in ((s.colaborador_id, "Motorista"), (s.ajudante_id, "Ajudante")):
            if not cid:
                continue
            if self.ausente(cid, s.data):
                out.append(f"{papel} ausente nesta data")
            if any(cid in (x.colaborador_id, x.ajudante_id) and _sobrepoe(s, x) for x in outros):
                out.append(f"{papel} com outro serviço à mesma hora")
            c = s.colaborador if cid == s.colaborador_id else s.ajudante
            if c is not None:
                out += [f"{papel}: documentação — {f}" for f in self.doc.falhas(c, s.contrato.cliente_id, s.loja.insignia_id, s.data)]
        if s.estado in (EstadoServicoLog.planeado, EstadoServicoLog.atribuido) and s.data < date.today():
            out.append("Data passada sem registo de execução")
        return out


def servico_json(s: ServicoLogistico, tenant: Tenant | None, ctx: Contexto | None = None) -> dict:
    executado = s.estado in FATURAVEIS
    c = custos(s, tenant) if executado else None
    return {
        "id": s.id, "contrato_id": s.contrato_id, "contrato_numero": s.contrato.numero, "cliente_id": s.contrato.cliente_id,
        "cliente": s.contrato.cliente.nome, "marca": s.contrato.marca.nome if s.contrato.marca else None,
        "loja_id": s.loja_id, "loja": s.loja.nome, "loja_morada": ", ".join(x for x in (s.loja.morada, s.loja.localidade) if x),
        "loja_zona": s.loja.zona.nome if s.loja.zona else None,
        "insignia_id": s.loja.insignia_id, "insignia": s.loja.insignia.nome if s.loja.insignia else None,
        "insignia_logo_v": s.loja.insignia.logo_v if s.loja.insignia else None,
        "tipo": s.tipo.value, "tipo_label": TIPO_LABEL[s.tipo], "data": s.data.isoformat(), "hora_inicio": s.hora_inicio,
        "hora_fim": s.hora_fim, "origem": s.origem, "materiais": s.materiais, "preco": float(s.preco),
        "referencia_erp": s.referencia_erp, "observacoes": s.observacoes, "estado": s.estado.value,
        "viatura_id": s.viatura_id, "viatura": f"{s.viatura.matricula}" + (f" · {s.viatura.descricao}" if s.viatura and s.viatura.descricao else "") if s.viatura else None,
        "colaborador_id": s.colaborador_id, "colaborador": s.colaborador.nome if s.colaborador else None,
        "ajudante_id": s.ajudante_id, "ajudante": s.ajudante.nome if s.ajudante else None,
        "km_partida": s.km_partida, "km_chegada": s.km_chegada, "portagens": float(s.portagens) if s.portagens is not None else None,
        "outros_custos": float(s.outros_custos) if s.outros_custos is not None else None, "outros_custos_desc": s.outros_custos_desc,
        "inicio_real": s.inicio_real, "fim_real": s.fim_real, "observacao_execucao": s.observacao_execucao,
        "comprovativo_nome": s.comprovativo_nome, "motivo": s.motivo,
        "custos": c, "margem": float(s.preco - Decimal(str(c["total"]))) if c else None,
        "alertas": ctx.alertas(s) if ctx else [],
    }


def opcoes_carregar():
    from app.models import Viatura
    return (joinedload(ServicoLogistico.contrato).joinedload(Contrato.cliente),
            joinedload(ServicoLogistico.contrato).joinedload(Contrato.marca),
            joinedload(ServicoLogistico.loja).joinedload(Loja.insignia), joinedload(ServicoLogistico.loja).joinedload(Loja.zona),
            joinedload(ServicoLogistico.viatura), joinedload(ServicoLogistico.colaborador), joinedload(ServicoLogistico.ajudante))


# ------------------------------------------------------------------ pré-faturação
def prefaturacao(db: Session, tenant_id: int, mes: date, fim: date, hoje: date, clientes: set[int] | None = None) -> list[dict]:
    """Serviços com data no mês, por cliente e contrato. Faturam-se os executados/validados (preço por serviço);
    os por executar aparecem para controlo, sem valor."""
    q = select(ServicoLogistico).options(*opcoes_carregar()).join(Contrato, ServicoLogistico.contrato_id == Contrato.id).where(
        ServicoLogistico.tenant_id == tenant_id, ServicoLogistico.data >= mes, ServicoLogistico.data < fim,
        ServicoLogistico.estado != EstadoServicoLog.cancelado)
    if clientes is not None:
        q = q.where(Contrato.cliente_id.in_(clientes))
    tenant = db.get(Tenant, tenant_id)
    por_cliente: dict[int, dict] = {}
    for s in db.scalars(q.order_by(ServicoLogistico.data, ServicoLogistico.id)).unique().all():
        c = s.contrato
        fatura = s.estado in FATURAVEIS
        cst = custos(s, tenant) if fatura else None
        valor = float(s.preco) if fatura else 0.0
        custo = cst["total"] if cst else 0.0
        linha = {"linha_id": s.id, "loja": s.loja.nome, "data": s.data.isoformat(), "tipo": TIPO_LABEL[s.tipo], "estado": s.estado.value,
                 "referencia_erp": s.referencia_erp, "preco": float(s.preco), "valor": valor, "custo": custo,
                 "margem": valor - custo, "km": cst["km"] if cst else 0,
                 "pendentes_validacao": 1 if s.estado == EstadoServicoLog.executado else 0,
                 "por_executar": 1 if s.estado in (EstadoServicoLog.planeado, EstadoServicoLog.atribuido) else 0}
        cl = por_cliente.setdefault(c.cliente_id, {"cliente_id": c.cliente_id, "cliente": c.cliente.nome,
                                                  "codigo_erp": c.cliente.codigo_erp, "contratos": {}})
        cd = cl["contratos"].setdefault(c.id, {"id": c.id, "numero": c.numero, "evento": c.evento, "descricao": c.descricao, "linhas": []})
        cd["linhas"].append(linha)
    out = []
    for cl in por_cliente.values():
        contratos = []
        for cd in cl["contratos"].values():
            t = defaultdict(float)
            for ln in cd["linhas"]:
                for k in ("valor", "custo", "km"):
                    t[k] += ln[k]
                t["pendentes"] += ln["pendentes_validacao"]
                t["por_executar"] += ln["por_executar"]
            cd["totais"] = dict(t)
            contratos.append(cd)
        tt = defaultdict(float)
        for cd in contratos:
            for k, v in cd["totais"].items():
                tt[k] += v
        out.append({**cl, "contratos": contratos, "totais": dict(tt)})
    return sorted(out, key=lambda x: -x["totais"].get("valor", 0))
