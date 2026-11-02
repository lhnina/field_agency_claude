"""Execução, validação, pré-faturação, apuramento de remunerações e fecho mensal.

Regras (respostas ao documento de análise):
- Q1: faturação por horas CONTRATADAS; as executadas servem para apurar o custo.
- Q3: horas/mês = horas/semana × 52 ÷ 12 (Reposição). Linha que começa ou acaba a meio
  do mês é faturada em proporção dos dias de vigência nesse mês.
- Promoções [hipótese H]: o contratado é o plano de turnos da campanha, logo fatura-se
  a soma das horas planeadas no mês (a validar com o cliente).
- Q4: aceitação tácita — sem registo, a ocorrência conta com as horas planeadas, também
  para remuneração.
- Q5: supervisor e gestor podem validar.
- Q6: custo = valor/hora da ficha do colaborador, ou o custo especial da linha.
- Q8: para o PHC basta colaborador, cliente, horas trabalhadas e valor dessas horas.
"""
import csv
import io
import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Colaborador, Contrato, EstadoContrato, EstadoOcorrencia, LinhaContrato, Loja, Ocorrencia, OrigemExecucao, Perfil,
    PeriodoFechado, Tenant, TipoContrato, TipoPeriodo, TipoVinculo, User,
)
from app.services import operacao as op
from app.services.periodos import inicio_mes, motivo_bloqueio, periodo, proximo_mes, verificar_editavel

Z = Decimal("0")
PENDENTES = (EstadoOcorrencia.planeado, EstadoOcorrencia.atribuido, EstadoOcorrencia.confirmado, EstadoOcorrencia.executado)


def _q(v: Decimal) -> float:
    return float(op.q2(v))


# ------------------------------------------------------------------ execução e validação
def aplicar_aceitacao_tacita(db: Session, tenant_id: int, ate: date) -> int:
    """Ocorrências passadas, com colaborador e sem registo passam a executadas (tácita)."""
    t = db.get(Tenant, tenant_id)
    if not t or not t.aceitacao_tacita:
        return 0
    n = 0
    q = select(Ocorrencia).options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato)).where(
        Ocorrencia.tenant_id == tenant_id, Ocorrencia.data <= ate, Ocorrencia.horas_executadas.is_(None),
        Ocorrencia.estado.in_((EstadoOcorrencia.atribuido, EstadoOcorrencia.confirmado)))
    for o in db.scalars(q).unique().all():
        if o.colaborador_id is None or motivo_bloqueio(db, tenant_id, o.data, o.linha.contrato.tipo.value):
            continue
        o.horas_executadas = o.horas_planeadas
        o.origem_execucao = OrigemExecucao.tacita
        o.estado = EstadoOcorrencia.executado
        n += 1
    db.flush()
    return n


def registar_execucao(db: Session, user: User, o: Ocorrencia, horas: Decimal, observacao: str | None, hoje: date) -> Ocorrencia:
    if o.data > hoje:
        raise ValueError("Não é possível registar horas de um serviço futuro")
    if o.colaborador_id is None:
        raise ValueError("Atribua primeiro um colaborador a este serviço")
    if o.estado == EstadoOcorrencia.cancelado:
        raise ValueError("Serviço cancelado")
    if horas < 0 or horas > 24:
        raise ValueError("As horas executadas têm de estar entre 0 e 24")
    verificar_editavel(db, o)
    if o.estado == EstadoOcorrencia.validado and not observacao:
        raise ValueError("Esta ocorrência já estava validada: indique o motivo da correção")
    antes = {"horas": o.horas_executadas, "estado": o.estado.value}
    o.horas_executadas = horas
    o.origem_execucao = OrigemExecucao.manual
    o.observacao_execucao = observacao
    o.estado = EstadoOcorrencia.executado
    o.horas_aprovadas = None
    o.validado_por_id = None
    o.validado_em = None
    op.auditar(db, user, "ocorrencia", o.id, "execucao", {"antes": antes, "horas": horas, "observacao": observacao})
    db.flush()
    return o


def validar(db: Session, user: User, ocorrencias: list[Ocorrencia], aprovar: bool, motivo: str | None, hoje: date) -> dict:
    ok, erros = 0, []
    for o in ocorrencias:
        try:
            if o.data > hoje:
                raise ValueError("serviço futuro")
            if o.colaborador_id is None:
                raise ValueError("sem colaborador")
            if o.estado == EstadoOcorrencia.cancelado:
                raise ValueError("cancelado")
            verificar_editavel(db, o)
        except ValueError as e:
            erros.append({"id": o.id, "erro": str(e)})
            continue
        if aprovar:
            if o.horas_executadas is None:  # validar sem registo = confirma as horas planeadas
                o.horas_executadas = o.horas_planeadas
                o.origem_execucao = OrigemExecucao.manual
            o.horas_aprovadas = o.horas_executadas
            o.estado = EstadoOcorrencia.validado
        else:
            o.horas_aprovadas = Z
            o.estado = EstadoOcorrencia.rejeitado
            o.observacao_execucao = motivo or o.observacao_execucao
        o.validado_por_id = user.id
        o.validado_em = datetime.now(timezone.utc)
        op.auditar(db, user, "ocorrencia", o.id, "validar" if aprovar else "rejeitar",
                   {"horas_aprovadas": o.horas_aprovadas, "motivo": motivo})
        ok += 1
    db.flush()
    return {"processadas": ok, "erros": erros}


# ------------------------------------------------------------------ custo
def custo_hora(o: Ocorrencia, colabs: dict[int, Colaborador]) -> Decimal:
    if o.linha.custo_hora_especial is not None:
        return o.linha.custo_hora_especial
    c = colabs.get(o.colaborador_id) if o.colaborador_id else None
    return c.custo_hora if c else Z


def horas_custo(o: Ocorrencia) -> Decimal:
    """Horas que geram custo: aprovadas; senão executadas; rejeitadas/canceladas = 0."""
    if o.estado in (EstadoOcorrencia.rejeitado, EstadoOcorrencia.cancelado):
        return Z
    if o.horas_aprovadas is not None:
        return o.horas_aprovadas
    return o.horas_executadas or Z


def _ocorrencias_mes(db: Session, tenant_id: int, mes: date, area: str | None = None):
    q = (select(Ocorrencia).join(LinhaContrato).join(Contrato)
         .options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato).joinedload(Contrato.cliente),
                  joinedload(Ocorrencia.linha).joinedload(LinhaContrato.loja))
         .where(Ocorrencia.tenant_id == tenant_id, Ocorrencia.data >= mes, Ocorrencia.data < proximo_mes(mes)))
    if area:
        q = q.where(Contrato.tipo == area)
    return db.scalars(q).unique().all()


def _colabs(db: Session, tenant_id: int) -> dict[int, Colaborador]:
    return {c.id: c for c in db.scalars(select(Colaborador).where(Colaborador.tenant_id == tenant_id)).all()}


# ------------------------------------------------------------------ pré-faturação
def prefaturacao(db: Session, tenant_id: int, mes: date, area: str, hoje: date) -> dict:
    mes = inicio_mes(mes)
    fim = proximo_mes(mes)
    dias_mes = monthrange(mes.year, mes.month)[1]
    colabs = _colabs(db, tenant_id)
    ocs = _ocorrencias_mes(db, tenant_id, mes, area)
    por_linha: dict[int, list[Ocorrencia]] = defaultdict(list)
    for o in ocs:
        por_linha[o.linha_id].append(o)

    contratos = db.scalars(select(Contrato).options(
        joinedload(Contrato.cliente), joinedload(Contrato.linhas).joinedload(LinhaContrato.loja)).where(
        Contrato.tenant_id == tenant_id, Contrato.tipo == area,
        Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.terminado)),
        Contrato.inicio < fim, or_(Contrato.fim.is_(None), Contrato.fim >= mes))).unique().all()

    clientes: dict[int, dict] = {}
    tot = defaultdict(lambda: Z)
    for c in sorted(contratos, key=lambda c: (c.cliente.nome, c.numero)):
        cdict = {"id": c.id, "numero": c.numero, "evento": c.evento, "descricao": c.descricao, "linhas": []}
        ctot = defaultdict(lambda: Z)
        for ln in c.linhas:
            ini = max(ln.inicio, c.inicio, mes)
            ultimo = date.fromordinal(fim.toordinal() - 1)
            fim_ln = min(x for x in (ln.fim, c.fim, ultimo) if x is not None)
            if fim_ln < ini:
                continue
            dias = (fim_ln - ini).days + 1
            lo = por_linha.get(ln.id, [])
            if area == TipoContrato.REP.value:
                fator = Decimal(dias) / Decimal(dias_mes)
                h_contr = op.q2(ln.horas_semana * op.SEMANAS_POR_MES * fator)
                valor = op.q2(ln.horas_semana * op.SEMANAS_POR_MES * ln.preco_hora * fator)
            else:
                h_contr = sum((o.horas_planeadas for o in lo if o.estado != EstadoOcorrencia.cancelado), Z)
                valor = op.q2(h_contr * ln.preco_hora)
            h_exec = sum((horas_custo(o) for o in lo), Z)
            custo = op.q2(sum((horas_custo(o) * custo_hora(o, colabs) for o in lo), Z))
            pend = sum(1 for o in lo if o.estado in PENDENTES and o.data <= hoje)
            linha = {
                "linha_id": ln.id, "loja": ln.loja.nome, "dias_vigencia": dias, "dias_mes": dias_mes,
                "horas_semana": float(ln.horas_semana), "preco_hora": float(ln.preco_hora),
                "horas_contratadas": float(h_contr), "valor": float(valor),
                "horas_executadas": float(h_exec), "custo": float(custo), "margem": float(valor - custo),
                "pendentes_validacao": pend,
            }
            cdict["linhas"].append(linha)
            for k in ("horas_contratadas", "valor", "horas_executadas", "custo"):
                ctot[k] += Decimal(str(linha[k]))
            ctot["pendentes"] += pend
        if not cdict["linhas"]:
            continue
        cdict["totais"] = {k: float(v) for k, v in ctot.items()}
        cl = clientes.setdefault(c.cliente_id, {"cliente_id": c.cliente_id, "cliente": c.cliente.nome,
                                                "codigo_phc": c.cliente.codigo_phc, "contratos": [],
                                                "totais": defaultdict(lambda: Z)})
        cl["contratos"].append(cdict)
        for k, v in ctot.items():
            cl["totais"][k] += v
            tot[k] += v
    lista = []
    for cl in sorted(clientes.values(), key=lambda x: -x["totais"]["valor"]):
        cl["totais"] = {k: float(v) for k, v in cl["totais"].items()}
        lista.append(cl)
    p = periodo(db, tenant_id, TipoPeriodo.faturacao, mes, area)
    totais = {k: float(v) for k, v in tot.items()}
    totais["margem"] = float(tot["valor"] - tot["custo"])
    totais["margem_pct"] = float((tot["valor"] - tot["custo"]) / tot["valor"] * 100) if tot["valor"] else 0.0
    return {"mes": mes.isoformat(), "area": area, "fechado": p is not None,
            "fechado_em": p.created_at.isoformat() if p else None, "clientes": lista, "totais": totais}


# ------------------------------------------------------------------ apuramento de remunerações
def apuramento(db: Session, tenant_id: int, mes: date, hoje: date, supervisor_id: int | None = None) -> dict:
    mes = inicio_mes(mes)
    colabs = _colabs(db, tenant_id)
    linhas: dict[tuple[int, int], dict] = {}
    pend_por_colab: dict[int, int] = defaultdict(int)
    for o in _ocorrencias_mes(db, tenant_id, mes):
        cid = o.colaborador_id
        if cid is None or o.estado == EstadoOcorrencia.cancelado:
            continue
        if supervisor_id and colabs[cid].supervisor_id != supervisor_id:
            continue
        if o.estado in PENDENTES:
            if o.data <= hoje:
                pend_por_colab[cid] += 1
            continue
        if o.estado != EstadoOcorrencia.validado:
            continue
        cli = o.linha.contrato.cliente
        vh = custo_hora(o, colabs)
        k = (cid, cli.id, vh)
        r = linhas.setdefault(k, {"cliente_id": cli.id, "cliente": cli.nome, "codigo_phc": cli.codigo_phc,
                                  "valor_hora": vh, "horas": Z, "tacitas": 0, "servicos": 0})
        r["horas"] += o.horas_aprovadas or Z
        r["servicos"] += 1
        if o.origem_execucao == OrigemExecucao.tacita:
            r["tacitas"] += 1
    por_colab: dict[int, dict] = {}
    for (cid, _, _), r in linhas.items():
        c = colabs[cid]
        d = por_colab.setdefault(cid, {"colaborador_id": cid, "numero": c.numero, "nome": c.nome,
                                       "vinculo": c.vinculo.value, "prestador": c.vinculo == TipoVinculo.recibos_verdes,
                                       "linhas": [], "horas": Z, "valor": Z})
        valor = op.q2(r["horas"] * r["valor_hora"])
        d["linhas"].append({**r, "horas": float(r["horas"]), "valor_hora": float(r["valor_hora"]), "valor": float(valor)})
        d["horas"] += r["horas"]
        d["valor"] += valor
    for cid, n in pend_por_colab.items():
        if cid not in por_colab:
            c = colabs[cid]
            por_colab[cid] = {"colaborador_id": cid, "numero": c.numero, "nome": c.nome, "vinculo": c.vinculo.value,
                              "prestador": c.vinculo == TipoVinculo.recibos_verdes, "linhas": [], "horas": Z, "valor": Z}
    lista = []
    for d in sorted(por_colab.values(), key=lambda x: x["nome"]):
        d["pendentes"] = pend_por_colab.get(d["colaborador_id"], 0)
        d["horas"], d["valor"] = float(d["horas"]), float(d["valor"])
        d["linhas"].sort(key=lambda x: x["cliente"])
        lista.append(d)
    p = periodo(db, tenant_id, TipoPeriodo.remuneracao, mes)
    trab = [d for d in lista if not d["prestador"]]
    prest = [d for d in lista if d["prestador"]]
    return {
        "mes": mes.isoformat(), "fechado": p is not None, "fechado_em": p.created_at.isoformat() if p else None,
        "colaboradores": lista,
        "totais": {
            "horas": sum(d["horas"] for d in lista), "valor": sum(d["valor"] for d in lista),
            "valor_trabalhadores": sum(d["valor"] for d in trab), "valor_prestadores": sum(d["valor"] for d in prest),
            "colaboradores": len(trab), "prestadores": len(prest), "pendentes": sum(pend_por_colab.values()),
        },
    }


def apuramento_csv(dados: dict) -> str:
    """Ficheiro para o PHC: separador ';', decimais com vírgula, UTF-8 com BOM (abre bem no Excel)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(["Mes", "Numero", "Colaborador", "Tipo", "Cliente", "Cliente PHC", "Servicos", "Horas", "Valor hora", "Valor"])
    fmt = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
    for d in dados["colaboradores"]:
        for ln in d["linhas"]:
            w.writerow([dados["mes"][:7], d["numero"], d["nome"], "Prestador" if d["prestador"] else "Trabalhador",
                        ln["cliente"], ln["codigo_phc"] or "", ln["servicos"], fmt(ln["horas"]), fmt(ln["valor_hora"]), fmt(ln["valor"])])
    return "﻿" + buf.getvalue()


# ------------------------------------------------------------------ fecho
def fechar(db: Session, user: User, tipo: TipoPeriodo, mes: date, area: str, hoje: date) -> PeriodoFechado:
    mes = inicio_mes(mes)
    if mes >= inicio_mes(hoje):
        raise ValueError("Só é possível fechar meses já terminados")
    if periodo(db, user.tenant_id, tipo, mes, area):
        raise ValueError("Este período já está fechado")
    if tipo == TipoPeriodo.remuneracao:
        dados = apuramento(db, user.tenant_id, mes, hoje)
        if dados["totais"]["pendentes"]:
            raise ValueError(f"Existem {dados['totais']['pendentes']} serviços por validar neste mês")
        resumo = dados["totais"]
    else:
        dados = prefaturacao(db, user.tenant_id, mes, area, hoje)
        resumo = dados["totais"]
    p = PeriodoFechado(tenant_id=user.tenant_id, tipo=tipo, area=area, mes=mes, fechado_por_id=user.id,
                       resumo=json.dumps(resumo, default=str))
    db.add(p)
    db.flush()
    op.auditar(db, user, "periodo", p.id, "fechar", {"tipo": tipo.value, "area": area, "mes": mes, "totais": resumo})
    return p


def reabrir(db: Session, user: User, tipo: TipoPeriodo, mes: date, area: str) -> None:
    if user.perfil not in (Perfil.administrador, Perfil.direcao):
        raise PermissionError("Só a Direção ou o Administrador podem reabrir um período")
    p = periodo(db, user.tenant_id, tipo, mes, area)
    if not p:
        raise ValueError("Este período não está fechado")
    op.auditar(db, user, "periodo", p.id, "reabrir", {"tipo": tipo.value, "area": area, "mes": inicio_mes(mes)})
    db.delete(p)
    db.flush()


# ------------------------------------------------------------------ muito curta duração
def indicadores_colaborador(db: Session, c: Colaborador, hoje: date) -> dict:
    ini_ano, fim_ano = date(hoje.year, 1, 1), date(hoje.year, 12, 31)
    datas = db.scalars(select(func.distinct(Ocorrencia.data)).where(
        Ocorrencia.tenant_id == c.tenant_id, Ocorrencia.data.between(ini_ano, fim_ano),
        Ocorrencia.estado.notin_((EstadoOcorrencia.cancelado, EstadoOcorrencia.rejeitado)),
        or_(Ocorrencia.colaborador_efetivo_id == c.id,
            and_(Ocorrencia.colaborador_efetivo_id.is_(None), Ocorrencia.colaborador_previsto_id == c.id)))).all()
    trabalhados = sum(1 for d in datas if d <= hoje)
    planeados = sum(1 for d in datas if d > hoje)
    res = {"dias_trabalhados_ano": trabalhados, "dias_planeados_ano": planeados, "alertas": []}
    if c.vinculo == TipoVinculo.muito_curta_duracao:
        res["limite_dias_ano"] = 70
        res["limite_dias_contrato"] = 35
        dc = (hoje - c.data_inicio).days + 1 if c.data_inicio and c.data_inicio <= hoje else 0
        res["dias_contrato_atual"] = dc
        total = trabalhados + planeados
        if total > 70:
            res["alertas"].append({"nivel": "erro", "texto": f"{total} dias no ano (trabalhados e planeados) excedem 70: o contrato converte-se em contrato a termo"})
        elif total >= 56:
            res["alertas"].append({"nivel": "aviso", "texto": f"{total} de 70 dias no ano (trabalhados e planeados)"})
        if dc > 35:
            res["alertas"].append({"nivel": "erro", "texto": f"Contrato atual com {dc} dias seguidos (máximo 35)"})
        elif dc >= 28:
            res["alertas"].append({"nivel": "aviso", "texto": f"Contrato atual com {dc} de 35 dias seguidos"})
    return res
