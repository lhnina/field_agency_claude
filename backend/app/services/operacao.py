"""Regras de negócio do núcleo operacional: geração de ocorrências, afetação
persistente, substituições, ausências e vista semanal de planeamento."""
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.services.periodos import verificar_editavel
from app.models import (
    Afetacao, Auditoria, Ausencia, Colaborador, Contrato, EstadoContrato, EstadoOcorrencia, Feriado, LinhaContrato,
    Loja, Ocorrencia, Perfil, TipoVinculo, User,
)

SEMANAS_POR_MES = Decimal(52) / Decimal(12)
EDITAVEIS = (EstadoOcorrencia.planeado, EstadoOcorrencia.atribuido, EstadoOcorrencia.confirmado)


def q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ valores
def horas_mes_linha(linha: LinhaContrato) -> Decimal:
    """Horas contratadas por mês = horas/semana × 52 ÷ 12 (resposta Q3)."""
    return q2(linha.horas_semana * SEMANAS_POR_MES)


def valor_mensal_linha(linha: LinhaContrato) -> Decimal:
    return q2(linha.horas_semana * SEMANAS_POR_MES * linha.preco_hora)


def linha_ativa(linha: LinhaContrato, d: date) -> bool:
    c = linha.contrato
    return (
        linha.inicio <= d
        and (linha.fim is None or d <= linha.fim)
        and c.inicio <= d
        and (c.fim is None or d <= c.fim)
    )


def proximo_numero(db: Session, tenant_id: int, tipo: str, ano: int) -> str:
    prefixo = f"CT-{tipo}-{ano}/"
    existentes = db.scalars(
        select(Contrato.numero).where(Contrato.tenant_id == tenant_id, Contrato.numero.like(prefixo + "%"))
    ).all()
    seq = max((int(n.split("/")[1]) for n in existentes), default=0) + 1
    return f"{prefixo}{seq:04d}"


def auditar(db: Session, user: User | None, entidade: str, entidade_id: int, acao: str, detalhe: dict | None = None,
            tenant_id: int | None = None) -> None:
    db.add(Auditoria(
        tenant_id=tenant_id or user.tenant_id, user_id=user.id if user else None, entidade=entidade,
        entidade_id=entidade_id, acao=acao, detalhe=json.dumps(detalhe, default=str, ensure_ascii=False) if detalhe else None,
    ))


# ------------------------------------------------------------------ afetação
def afetacao_em(linha: LinhaContrato, d: date) -> Afetacao | None:
    for a in linha.afetacoes:
        if a.desde <= d and (a.ate is None or d <= a.ate):
            return a
    return None


def feriados_entre(db: Session, tenant_id: int, ini: date, fim: date, zona_id: int | None = None) -> set[date]:
    from app.services.feriados import feriados_entre as _f  # import local: evita ciclo
    return _f(db, tenant_id, ini, fim, zona_id)


def _dia_reagendado(linha: LinhaContrato, d: date, feriados: set[date], fim: date) -> date | None:
    """Feriado ou loja fechada: o serviço passa para outro dia (resposta Q9).
    Preferência: próximo dia útil (seg–sáb) da mesma semana sem horas na linha;
    depois qualquer dia útil seguinte; por fim o dia útil anterior."""
    candidatos = [d + timedelta(days=i) for i in range(1, 7)]
    candidatos = [c for c in candidatos if c <= fim and c.weekday() < 6 and c not in feriados]
    mesma_semana = [c for c in candidatos if c.isocalendar()[1] == d.isocalendar()[1]]
    for lista in (
        [c for c in mesma_semana if linha.horas_dia(c.weekday()) == 0],
        [c for c in candidatos if linha.horas_dia(c.weekday()) == 0],
        candidatos,
    ):
        if lista:
            return lista[0]
    for i in range(1, 7):
        c = d - timedelta(days=i)
        if c.weekday() < 6 and c not in feriados and c >= linha.inicio:
            return c
    return None


def gerar_ocorrencias(db: Session, linha: LinhaContrato, ate: date, desde: date | None = None) -> int:
    """Gera (de forma idempotente) as ocorrências de uma linha até `ate`."""
    c = linha.contrato
    if c.estado != EstadoContrato.ativo:
        return 0
    ini = max(linha.inicio, c.inicio, desde or linha.inicio)
    fim = min(x for x in (ate, linha.fim, c.fim) if x is not None)
    if fim < ini:
        return 0
    feriados = feriados_entre(db, linha.tenant_id, ini, fim + timedelta(days=7), linha.loja.zona_id if linha.loja else None)
    existentes = set(db.scalars(select(Ocorrencia.data_original).where(
        Ocorrencia.linha_id == linha.id, Ocorrencia.data_original.between(ini, fim))).all())
    criadas = 0
    d = ini
    while d <= fim:
        h = linha.horas_dia(d.weekday())
        if h > 0 and d not in existentes:
            alvo, reag = d, False
            if d in feriados:
                alvo, reag = _dia_reagendado(linha, d, feriados, fim + timedelta(days=6)), True
            if alvo is not None:
                af = afetacao_em(linha, alvo)
                db.add(Ocorrencia(
                    tenant_id=linha.tenant_id, linha_id=linha.id, data=alvo, data_original=d, hora_inicio=linha.hora_inicio,
                    horas_planeadas=h, reagendada_feriado=reag,
                    colaborador_previsto_id=af.colaborador_id if af else None,
                    estado=EstadoOcorrencia.atribuido if af else EstadoOcorrencia.planeado,
                ))
                criadas += 1
        d += timedelta(days=1)
    db.flush()
    return criadas


def regenerar_futuras(db: Session, linha: LinhaContrato, desde: date, ate: date) -> int:
    """Depois de alterar horas/datas de uma linha: apaga ocorrências futuras ainda
    não executadas e volta a gerar. Substituições futuras nessas datas perdem-se."""
    for o in db.scalars(select(Ocorrencia).where(
            Ocorrencia.linha_id == linha.id, Ocorrencia.data_original >= desde, Ocorrencia.estado.in_(EDITAVEIS))).all():
        db.delete(o)
    db.flush()
    return gerar_ocorrencias(db, linha, ate=ate, desde=desde)


def afetar(db: Session, user: User, linha: LinhaContrato, colaborador: Colaborador, desde: date, ate: date | None = None) -> Afetacao:
    """Afetação persistente: o colaborador fica na linha desde `desde` até `ate`
    (por defeito até ao fim). Fecha a afetação anterior e atualiza as ocorrências."""
    if ate is not None and ate < desde:
        raise ValueError("A data de fim é anterior à data de início")
    if colaborador.data_saida is not None:
        if desde > colaborador.data_saida:
            raise ValueError(f"{colaborador.nome} sai a {_dm(colaborador.data_saida)}: não pode ser afeto depois dessa data")
        if ate is None or ate > colaborador.data_saida:
            ate = colaborador.data_saida  # a afetação termina na data de saída
    for a in list(linha.afetacoes):
        if a.desde >= desde and (ate is None or a.desde <= ate):
            linha.afetacoes.remove(a)
            db.delete(a)
        elif a.desde < desde and (a.ate is None or a.ate >= desde):
            if ate is not None and (a.ate is None or a.ate > ate):
                # afetação temporária no meio de outra: a anterior retoma depois
                linha.afetacoes.append(Afetacao(tenant_id=linha.tenant_id, colaborador_id=a.colaborador_id,
                                                desde=ate + timedelta(days=1), ate=a.ate))
            a.ate = desde - timedelta(days=1)
    nova = Afetacao(tenant_id=linha.tenant_id, colaborador_id=colaborador.id, desde=desde, ate=ate)
    linha.afetacoes.append(nova)
    linha.afetacoes.sort(key=lambda x: x.desde)
    db.flush()

    cond = [Ocorrencia.linha_id == linha.id, Ocorrencia.data >= desde, Ocorrencia.estado.in_(EDITAVEIS)]
    if ate is not None:
        cond.append(Ocorrencia.data <= ate)
    for o in db.scalars(select(Ocorrencia).where(*cond)).all():
        o.colaborador_previsto_id = colaborador.id
        if o.colaborador_efetivo_id == colaborador.id:
            o.colaborador_efetivo_id = None
            o.motivo_alteracao = None
        o.estado = EstadoOcorrencia.atribuido
    # Se havia uma afetação temporária a terminar, as datas seguintes voltam ao titular
    if ate is not None:
        for o in db.scalars(select(Ocorrencia).where(
                Ocorrencia.linha_id == linha.id, Ocorrencia.data > ate, Ocorrencia.estado.in_(EDITAVEIS))).all():
            af = afetacao_em(linha, o.data)
            o.colaborador_previsto_id = af.colaborador_id if af else None
            o.estado = EstadoOcorrencia.atribuido if af else EstadoOcorrencia.planeado
    auditar(db, user, "linha_contrato", linha.id, "afetacao",
            {"colaborador_id": colaborador.id, "desde": desde, "ate": ate})
    db.flush()
    return nova


# ------------------------------------------------------------------ saída do colaborador
def saiu(c: Colaborador, d: date) -> bool:
    """Depois da data de saída o colaborador já não trabalha (o próprio dia ainda conta)."""
    return c.data_saida is not None and d > c.data_saida


def _dm(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def aplicar_saida(db: Session, user: User | None, c: Colaborador) -> dict:
    """Com data de saída: termina as afetações nessa data, retira-o das substituições e dos
    serviços de logística por executar depois dela e, passada a data, desativa-o.
    Nada é apagado: as ocorrências ficam por atribuir no planeamento."""
    from app.models import EstadoServicoLog, ServicoLogistico  # import local: evita ciclo
    res = {"afetacoes": 0, "servicos": 0, "desativado": False}
    if c.data_saida is None:
        return res
    depois = c.data_saida + timedelta(days=1)
    linhas = db.scalars(select(LinhaContrato).join(Afetacao).where(
        Afetacao.colaborador_id == c.id, or_(Afetacao.ate.is_(None), Afetacao.ate > c.data_saida))).unique().all()
    for ln in linhas:
        for a in list(ln.afetacoes):
            if a.colaborador_id != c.id:
                continue
            if a.desde > c.data_saida:
                ln.afetacoes.remove(a)
                db.delete(a)
                res["afetacoes"] += 1
            elif a.ate is None or a.ate > c.data_saida:
                a.ate = c.data_saida
                res["afetacoes"] += 1
        db.flush()
        for o in db.scalars(select(Ocorrencia).where(
                Ocorrencia.linha_id == ln.id, Ocorrencia.data >= depois, Ocorrencia.estado.in_(EDITAVEIS),
                Ocorrencia.colaborador_previsto_id == c.id)).all():
            o.colaborador_previsto_id = None
            o.estado = EstadoOcorrencia.planeado if o.colaborador_efetivo_id is None else o.estado
            res["servicos"] += 1
    for o in db.scalars(select(Ocorrencia).where(
            Ocorrencia.colaborador_efetivo_id == c.id, Ocorrencia.data >= depois, Ocorrencia.estado.in_(EDITAVEIS))).all():
        o.colaborador_efetivo_id = None
        o.motivo_alteracao = None
        o.estado = EstadoOcorrencia.atribuido if o.colaborador_previsto_id else EstadoOcorrencia.planeado
        res["servicos"] += 1
    pend = (EstadoServicoLog.planeado, EstadoServicoLog.atribuido)
    for s in db.scalars(select(ServicoLogistico).where(
            ServicoLogistico.data >= depois, ServicoLogistico.estado.in_(pend),
            or_(ServicoLogistico.colaborador_id == c.id, ServicoLogistico.ajudante_id == c.id))).all():
        if s.colaborador_id == c.id:
            s.colaborador_id = None
            s.estado = EstadoServicoLog.planeado
        if s.ajudante_id == c.id:
            s.ajudante_id = None
        res["servicos"] += 1
    from app.services import equipas as eq  # import local: evita ciclo
    res["servicos"] += eq.sair(db, user, c)
    if c.ativo and c.data_saida < date.today():
        c.ativo = False
        res["desativado"] = True
    if res["afetacoes"] or res["servicos"] or res["desativado"]:
        auditar(db, user, "colaborador", c.id, "saida", {"data_saida": c.data_saida, **res}, tenant_id=c.tenant_id)
    db.flush()
    return res


def aplicar_saidas(db: Session, tenant_id: int) -> None:
    """Desativa quem já saiu (corre ao abrir colaboradores e planeamento)."""
    db.flush()
    for c in db.scalars(select(Colaborador).where(
            Colaborador.tenant_id == tenant_id, Colaborador.ativo.is_(True),
            Colaborador.data_saida.is_not(None), Colaborador.data_saida < date.today())).all():
        aplicar_saida(db, None, c)


def remover_afetacao(db: Session, user: User, linha: LinhaContrato, desde: date) -> None:
    """Termina a afetação em vigor a partir de `desde`: as ocorrências ficam por atribuir."""
    for a in list(linha.afetacoes):
        if a.desde >= desde:
            linha.afetacoes.remove(a)
            db.delete(a)
        elif a.ate is None or a.ate >= desde:
            a.ate = desde - timedelta(days=1)
    for o in db.scalars(select(Ocorrencia).where(
            Ocorrencia.linha_id == linha.id, Ocorrencia.data >= desde, Ocorrencia.estado.in_(EDITAVEIS))).all():
        o.colaborador_previsto_id = None
        o.estado = EstadoOcorrencia.planeado if o.colaborador_efetivo_id is None else o.estado
    auditar(db, user, "linha_contrato", linha.id, "remover_afetacao", {"desde": desde})
    db.flush()


def substituir(db: Session, user: User, o: Ocorrencia, colaborador_id: int | None, motivo: str | None) -> Ocorrencia:
    """Altera só esta ocorrência; a afetação de base mantém-se."""
    if o.estado not in EDITAVEIS:
        raise ValueError("Esta ocorrência já foi executada ou validada e não pode ser alterada")
    verificar_editavel(db, o)
    antes = o.colaborador_id
    if colaborador_id:
        novo = db.get(Colaborador, colaborador_id)
        if novo and saiu(novo, o.data):
            raise ValueError(f"{novo.nome} sai a {_dm(novo.data_saida)}: não pode fazer serviços depois dessa data")
    if colaborador_id is None or colaborador_id == o.colaborador_previsto_id:
        o.colaborador_efetivo_id = None
        o.motivo_alteracao = None
    else:
        o.colaborador_efetivo_id = colaborador_id
        o.motivo_alteracao = motivo or "Substituição"
    o.estado = EstadoOcorrencia.atribuido if o.colaborador_id else EstadoOcorrencia.planeado
    auditar(db, user, "ocorrencia", o.id, "substituicao", {"de": antes, "para": o.colaborador_id, "motivo": motivo})
    db.flush()
    return o


def mover(db: Session, user: User, o: Ocorrencia, nova_data: date) -> Ocorrencia:
    if o.estado not in EDITAVEIS:
        raise ValueError("Esta ocorrência já foi executada ou validada e não pode ser alterada")
    verificar_editavel(db, o, nova_data)
    if not linha_ativa(o.linha, nova_data):
        raise ValueError("A nova data está fora da vigência da linha de contrato")
    antes = o.data
    o.data = nova_data
    auditar(db, user, "ocorrencia", o.id, "mover", {"de": antes, "para": nova_data})
    db.flush()
    return o


def ocorrencias_afetadas(db: Session, aus: Ausencia) -> list[Ocorrencia]:
    return db.scalars(select(Ocorrencia).options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.loja))
                      .join(LinhaContrato, Ocorrencia.linha_id == LinhaContrato.id).join(Contrato, LinhaContrato.contrato_id == Contrato.id).where(
        Ocorrencia.tenant_id == aus.tenant_id, Contrato.estado == EstadoContrato.ativo,
        Ocorrencia.data.between(aus.inicio, aus.fim),
        Ocorrencia.estado.in_(EDITAVEIS),
        or_(Ocorrencia.colaborador_efetivo_id == aus.colaborador_id,
            and_(Ocorrencia.colaborador_efetivo_id.is_(None), Ocorrencia.colaborador_previsto_id == aus.colaborador_id)),
    ).order_by(Ocorrencia.data)).unique().all()


# ------------------------------------------------------------------ carga e candidatos
def _horas_por_colaborador(db: Session, tenant_id: int, ini: date, fim: date) -> dict[tuple[int, date], Decimal]:
    rows = db.execute(select(Ocorrencia.colaborador_efetivo_id, Ocorrencia.colaborador_previsto_id, Ocorrencia.data,
                             Ocorrencia.horas_planeadas)
        .join(LinhaContrato, Ocorrencia.linha_id == LinhaContrato.id).join(Contrato, LinhaContrato.contrato_id == Contrato.id)
        .where(Ocorrencia.tenant_id == tenant_id, Ocorrencia.data.between(ini, fim),
               Ocorrencia.estado != EstadoOcorrencia.cancelado, Contrato.estado == EstadoContrato.ativo)).all()
    out: dict[tuple[int, date], Decimal] = {}
    for ef, pr, d, h in rows:
        cid = ef or pr
        if cid:
            out[(cid, d)] = out.get((cid, d), Decimal("0")) + h
    for k, h in _horas_equipas(db, tenant_id, ini, fim).items():
        out[k] = out.get(k, Decimal("0")) + h
    return out


def _horas_equipas(db: Session, tenant_id: int, ini: date, fim: date, ids: set[int] | None = None) -> dict[tuple[int, date], Decimal]:
    """Horas dos dias de Equipas Fixas (contratos em curso, não faltas nem cancelados)."""
    from app.models import EstadoServicoEquipa, ServicoEquipa  # import local: evita ciclo
    q = (select(ServicoEquipa.colaborador_id, ServicoEquipa.data, ServicoEquipa.horas_planeadas, ServicoEquipa.horas_reais)
         .join(Contrato, ServicoEquipa.contrato_id == Contrato.id)
         .where(ServicoEquipa.tenant_id == tenant_id, ServicoEquipa.data.between(ini, fim), Contrato.estado == EstadoContrato.ativo,
                ServicoEquipa.estado.in_((EstadoServicoEquipa.planeado, EstadoServicoEquipa.validado))))
    if ids is not None:
        q = q.where(ServicoEquipa.colaborador_id.in_(ids))
    out: dict[tuple[int, date], Decimal] = {}
    for cid, d, hp, hr in db.execute(q).all():
        out[(cid, d)] = out.get((cid, d), Decimal("0")) + (hr if hr is not None else hp)
    return out


def horas_colaborador_dia(db: Session, tenant_id: int, ini: date, fim: date) -> dict[tuple[int, date], Decimal]:
    """Horas por colaborador e dia em todos os serviços (reposição, promoções e equipas fixas)."""
    return _horas_por_colaborador(db, tenant_id, ini, fim)


def _ausentes(db: Session, tenant_id: int, ini: date, fim: date) -> dict[int, list[Ausencia]]:
    out: dict[int, list[Ausencia]] = {}
    for a in db.scalars(select(Ausencia).where(Ausencia.tenant_id == tenant_id, Ausencia.aprovada.is_(True),
                                               Ausencia.inicio <= fim, Ausencia.fim >= ini)).all():
        out.setdefault(a.colaborador_id, []).append(a)
    return out


def candidatos(db: Session, o: Ocorrencia, limite: int = 8) -> list[dict]:
    """Sugestão explicável de substitutos. Nunca impede a escolha manual."""
    loja = o.linha.loja
    seg = o.data - timedelta(days=o.data.weekday())
    horas = _horas_por_colaborador(db, o.tenant_id, seg, seg + timedelta(days=6))
    ausentes = _ausentes(db, o.tenant_id, o.data, o.data)
    from app.services import documentos as dc  # import local: evita ciclo
    ctx_doc = dc.contexto(db, o.tenant_id)
    res = []
    for c in db.scalars(select(Colaborador).where(Colaborador.tenant_id == o.tenant_id, Colaborador.ativo.is_(True))).all():
        if c.id == o.colaborador_id or saiu(c, o.data):
            continue
        motivos, pontos, bloqueios = [], 0, []
        if c.id in ausentes:
            bloqueios.append("Ausente nesta data")
        if c.disponibilidade[o.data.weekday()] == "1":
            pontos += 3
            motivos.append("Disponível neste dia da semana")
        else:
            bloqueios.append("Indisponível neste dia da semana")
        if loja.zona_id and c.zona_id == loja.zona_id:
            pontos += 2
            motivos.append("Mesma zona da loja")
        dia = horas.get((c.id, o.data), Decimal("0"))
        semana = sum((v for (cid, _), v in horas.items() if cid == c.id), Decimal("0"))
        if c.vinculo != TipoVinculo.recibos_verdes:
            if dia + o.horas_planeadas > Decimal(str(settings.limite_horas_dia)):
                bloqueios.append(f"Excederia {settings.limite_horas_dia:g} h no dia ({dia + o.horas_planeadas} h)")
            if semana + o.horas_planeadas > Decimal(str(settings.limite_horas_semana)):
                bloqueios.append(f"Excederia {settings.limite_horas_semana:g} h na semana")
        for falta in ctx_doc.falhas(c, o.linha.contrato.cliente_id, loja.insignia_id, o.data):
            bloqueios.append(f"Documentação: {falta}")
        pontos += 1 if semana < 20 else 0
        res.append({"colaborador_id": c.id, "nome": c.nome, "vinculo": c.vinculo.value, "muito_curta_duracao": c.muito_curta_duracao, "horas_dia": float(dia),
                    "horas_semana": float(semana), "pontos": pontos - 10 * len(bloqueios), "motivos": motivos,
                    "alertas": bloqueios})
    res.sort(key=lambda r: (-r["pontos"], r["horas_semana"]))
    return res[:limite]


# ------------------------------------------------------------------ vista semanal
@dataclass
class FiltroPlaneamento:
    zona_id: int | None = None
    cliente_id: int | None = None
    supervisor_id: int | None = None
    tipo: str | None = None
    colaborador_ids: list[int] = field(default_factory=list)


def planeamento_semana(db: Session, user: User, segunda: date, f: FiltroPlaneamento) -> dict:
    dom = segunda + timedelta(days=6)
    q = (select(Ocorrencia)
         .join(LinhaContrato, Ocorrencia.linha_id == LinhaContrato.id)
         .join(Contrato, LinhaContrato.contrato_id == Contrato.id)
         .join(Loja, LinhaContrato.loja_id == Loja.id)
         .options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.loja),
                  joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato).joinedload(Contrato.cliente))
         .where(Ocorrencia.tenant_id == user.tenant_id, Ocorrencia.data.between(segunda, dom),
                Ocorrencia.estado != EstadoOcorrencia.cancelado,
                # Só contratos "Em curso": em orçamento, suspensos e terminados não aparecem.
                Contrato.estado == EstadoContrato.ativo))
    # Todos os filtros combinam-se (E). Na vista de um colaborador, a zona só filtra
    # os serviços por atribuir: os serviços dele aparecem em qualquer zona.
    alvo = set(f.colaborador_ids)
    if f.zona_id and not alvo:
        q = q.where(Loja.zona_id == f.zona_id)
    if f.cliente_id:
        q = q.where(Contrato.cliente_id == f.cliente_id)
    if f.tipo:
        q = q.where(Contrato.tipo == f.tipo)
    from app.ambito import clientes_permitidos
    permitidos = clientes_permitidos(db, user)
    if permitidos is not None:
        q = q.where(Contrato.cliente_id.in_(permitidos))
    ocorrencias = db.scalars(q.order_by(Ocorrencia.data, Ocorrencia.hora_inicio)).unique().all()

    # Âmbito do supervisor (o próprio, ou o escolhido no filtro): a zona que supervisiona.
    from app.ambito import equipa as equipa_de
    sup_user = user if user.perfil == Perfil.supervisor else (db.get(User, f.supervisor_id) if f.supervisor_id else None)
    zona_sup = sup_user.zona_id if sup_user is not None else None
    sup = zona_sup is not None
    equipa: set[int] | None = equipa_de(db, sup_user)

    def visivel(o: Ocorrencia) -> bool:
        cid = o.colaborador_id
        if cid is None:  # por atribuir: lojas do supervisor e, na vista de colaborador, da zona escolhida
            if sup and o.linha.loja.zona_id != zona_sup:
                return False
            return not (alvo and f.zona_id and o.linha.loja.zona_id != f.zona_id)
        if equipa is not None and cid not in equipa:
            return False
        return not alvo or cid in alvo

    ocorrencias = [o for o in ocorrencias if visivel(o)]
    ids = {o.colaborador_id for o in ocorrencias if o.colaborador_id}
    if alvo:  # o colaborador aparece mesmo sem serviços nesta semana
        ids |= alvo if equipa is None else (alvo & equipa)
    elif equipa is not None and not (f.cliente_id or f.zona_id or f.tipo):
        ids |= equipa  # só o supervisor filtrado: mostra a equipa toda, para poder afetar
    colabs = {c.id: c for c in db.scalars(select(Colaborador).where(Colaborador.id.in_(ids))).all()} if ids else {}
    ausencias = _ausentes(db, user.tenant_id, segunda, dom)
    from app.services import documentos as dc  # import local: evita ciclo
    ctx_doc = dc.contexto(db, user.tenant_id, list(colabs))
    falhas_doc: dict[int, set[str]] = {}

    horas: dict[tuple[int, date], Decimal] = {}
    for o in ocorrencias:
        if o.colaborador_id:
            k = (o.colaborador_id, o.data)
            horas[k] = horas.get(k, Decimal("0")) + o.horas_planeadas
    if colabs:  # os dias de Equipas Fixas contam para os limites de horas
        for k, h in _horas_equipas(db, user.tenant_id, segunda, dom, set(colabs)).items():
            horas[k] = horas.get(k, Decimal("0")) + h

    def aus_em(cid: int, d: date) -> Ausencia | None:
        return next((a for a in ausencias.get(cid, []) if a.inicio <= d <= a.fim), None)

    def oc_json(o: Ocorrencia) -> dict:
        alertas = []
        cid = o.colaborador_id
        if cid is None:
            alertas.append("sem_colaborador")
        else:
            if aus_em(cid, o.data):
                alertas.append("colaborador_ausente")
            c = colabs.get(cid)
            if c and c.vinculo != TipoVinculo.recibos_verdes and horas.get((cid, o.data), 0) > Decimal(str(settings.limite_horas_dia)):
                alertas.append("excede_horas_dia")
        ln = o.linha
        docs = ctx_doc.falhas(colabs[cid], ln.contrato.cliente_id, ln.loja.insignia_id, o.data) if cid in colabs else []
        if docs:  # só aviso: não impede a afetação
            alertas.append("documentacao")
            falhas_doc.setdefault(cid, set()).update(docs)
        return {
            "id": o.id, "data": o.data.isoformat(), "data_original": o.data_original.isoformat(),
            "reagendada_feriado": o.reagendada_feriado, "hora_inicio": o.hora_inicio,
            "horas": float(o.horas_planeadas), "estado": o.estado.value,
            "colaborador_id": cid, "colaborador_previsto_id": o.colaborador_previsto_id,
            "substituicao": o.colaborador_efetivo_id is not None, "motivo": o.motivo_alteracao,
            "linha_id": ln.id, "contrato_id": ln.contrato_id, "contrato_numero": ln.contrato.numero,
            "tipo": ln.contrato.tipo.value, "cliente": ln.contrato.cliente.nome, "loja": ln.loja.nome,
            "loja_id": ln.loja_id, "mecanica": ln.mecanica, "alertas": alertas, "documentacao": docs,
        }

    oc = [oc_json(o) for o in ocorrencias]
    linhas_colab = []
    for cid, c in sorted(colabs.items(), key=lambda kv: kv[1].nome):
        tot = sum((v for (k, _), v in horas.items() if k == cid), Decimal("0"))
        alertas = []
        if c.vinculo != TipoVinculo.recibos_verdes:
            if tot > Decimal(str(settings.limite_horas_semana)):
                alertas.append(f"Excede {settings.limite_horas_semana:g} h na semana ({tot} h)")
            for (k, d), v in horas.items():
                if k == cid and v > Decimal(str(settings.limite_horas_dia)):
                    alertas.append(f"{v} h em {d.strftime('%d/%m')} (limite {settings.limite_horas_dia:g} h)")
            dias_trab = sorted({d for (k, d), _ in horas.items() if k == cid})
            if len(dias_trab) >= 7:
                alertas.append("Sem dia de descanso semanal")
            if c.muito_curta_duracao:
                from app.services.fecho import indicadores_colaborador  # import local: evita ciclo
                alertas += [a["texto"] for a in indicadores_colaborador(db, c, date.today())["alertas"]]
        if falhas_doc.get(cid):
            alertas.append("Documentação: " + ", ".join(sorted(falhas_doc[cid])))
        aus = [{"tipo": a.tipo.value, "inicio": a.inicio.isoformat(), "fim": a.fim.isoformat()} for a in ausencias.get(cid, [])]
        linhas_colab.append({
            "id": cid, "nome": c.nome, "numero": c.numero, "vinculo": c.vinculo.value, "muito_curta_duracao": c.muito_curta_duracao, "funcao": c.funcao,
            "horas_semana": float(tot), "limite_semana": None if c.vinculo == TipoVinculo.recibos_verdes else settings.limite_horas_semana,
            "alertas": alertas, "ausencias": aus, "disponibilidade": c.disponibilidade,
        })

    return {
        "inicio": segunda.isoformat(), "fim": dom.isoformat(),
        "dias": [(segunda + timedelta(days=i)).isoformat() for i in range(7)],
        "colaboradores": linhas_colab,
        "ocorrencias": [o for o in oc if o["colaborador_id"] is not None],
        "por_atribuir": [o for o in oc if o["colaborador_id"] is None],
        "resumo": {
            "total": len(oc),
            "por_atribuir": sum(1 for o in oc if o["colaborador_id"] is None),
            "conflitos": sum(1 for o in oc if {"colaborador_ausente", "excede_horas_dia"} & set(o["alertas"])),
            "ausencias": sum(len(v) for k, v in ausencias.items() if k in colabs),
            "documentacao": sum(1 for o in oc if "documentacao" in o["alertas"]),
            "horas": float(sum((o.horas_planeadas for o in ocorrencias), Decimal("0"))),
        },
    }
