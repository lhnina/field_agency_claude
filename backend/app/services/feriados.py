"""Feriados: nacionais calculados para qualquer ano; municipais e da agência guardados por organização,
opcionalmente limitados a uma zona (as lojas dessa zona)."""
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Feriado, LinhaContrato, Loja, Ocorrencia, User


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo gregoriano anónimo / Meeus)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def nacionais(ano: int) -> dict[date, str]:
    """Feriados obrigatórios do Código do Trabalho (art. 234.º)."""
    p = pascoa(ano)
    return {
        date(ano, 1, 1): "Ano Novo", p - timedelta(days=2): "Sexta-feira Santa", p: "Páscoa",
        date(ano, 4, 25): "Dia da Liberdade", date(ano, 5, 1): "Dia do Trabalhador",
        p + timedelta(days=60): "Corpo de Deus", date(ano, 6, 10): "Dia de Portugal",
        date(ano, 8, 15): "Assunção de Nossa Senhora", date(ano, 10, 5): "Implantação da República",
        date(ano, 11, 1): "Dia de Todos os Santos", date(ano, 12, 1): "Restauração da Independência",
        date(ano, 12, 8): "Imaculada Conceição", date(ano, 12, 25): "Natal",
    }


def feriados_entre(db: Session, tenant_id: int, ini: date, fim: date, zona_id: int | None = None) -> set[date]:
    out = {d for ano in range(ini.year, fim.year + 1) for d in nacionais(ano) if ini <= d <= fim}
    cond = [Feriado.data.between(ini, fim),
            or_(Feriado.tenant_id.is_(None), and_(Feriado.tenant_id == tenant_id,
                                                   or_(Feriado.zona_id.is_(None), Feriado.zona_id == zona_id)))]
    out |= set(db.scalars(select(Feriado.data).where(*cond)).all())
    return out


def listar(db: Session, tenant_id: int, ano: int) -> list[dict]:
    res = [{"id": None, "data": d.isoformat(), "nome": n, "ambito": "nacional", "zona_id": None, "zona": None}
           for d, n in sorted(nacionais(ano).items())]
    for f in db.scalars(select(Feriado).options(joinedload(Feriado.zona)).where(
            Feriado.tenant_id == tenant_id, Feriado.data.between(date(ano, 1, 1), date(ano, 12, 31)))).all():
        res.append({"id": f.id, "data": f.data.isoformat(), "nome": f.nome,
                    "ambito": "zona" if f.zona_id else "agencia", "zona_id": f.zona_id, "zona": f.zona.nome if f.zona else None})
    return sorted(res, key=lambda x: x["data"])


def reagendar_para_feriado(db: Session, user: User, f: Feriado) -> int:
    """Um feriado novo passa para outro dia os serviços já gerados nessa data (Q9)."""
    from app.services import operacao as op  # import local: evita ciclo
    from app.services.periodos import motivo_bloqueio

    q = (select(Ocorrencia).join(LinhaContrato).join(Loja)
         .options(joinedload(Ocorrencia.linha).joinedload(LinhaContrato.contrato),
                  joinedload(Ocorrencia.linha).joinedload(LinhaContrato.loja))
         .where(Ocorrencia.tenant_id == f.tenant_id, Ocorrencia.data == f.data,
                Ocorrencia.estado.in_(op.EDITAVEIS), Ocorrencia.horas_executadas.is_(None)))
    if f.zona_id:
        q = q.where(Loja.zona_id == f.zona_id)
    n = 0
    for o in db.scalars(q).unique().all():
        if motivo_bloqueio(db, f.tenant_id, o.data, o.linha.contrato.tipo.value):
            continue
        feriados = feriados_entre(db, f.tenant_id, f.data - timedelta(days=7), f.data + timedelta(days=14), o.linha.loja.zona_id)
        alvo = op._dia_reagendado(o.linha, o.data, feriados, f.data + timedelta(days=13))
        if alvo is None:
            continue
        op.auditar(db, user, "ocorrencia", o.id, "reagendar_feriado", {"de": o.data, "para": alvo, "feriado": f.nome})
        o.data = alvo
        o.reagendada_feriado = True
        n += 1
    db.flush()
    return n
