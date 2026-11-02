"""Períodos mensais fechados: depois do fecho, nada do mês abrangido muda (R10/R11)."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ocorrencia, PeriodoFechado, TipoPeriodo


class PeriodoFechadoErro(ValueError):
    pass


def inicio_mes(d: date) -> date:
    return d.replace(day=1)


def proximo_mes(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def periodo(db: Session, tenant_id: int, tipo: TipoPeriodo, mes: date, area: str = "*") -> PeriodoFechado | None:
    return db.scalar(select(PeriodoFechado).where(
        PeriodoFechado.tenant_id == tenant_id, PeriodoFechado.tipo == tipo,
        PeriodoFechado.mes == inicio_mes(mes), PeriodoFechado.area == area))


def motivo_bloqueio(db: Session, tenant_id: int, d: date, area: str) -> str | None:
    if periodo(db, tenant_id, TipoPeriodo.remuneracao, d):
        return f"O apuramento de remunerações de {d:%m/%Y} já foi fechado"
    if periodo(db, tenant_id, TipoPeriodo.faturacao, d, area):
        return f"A pré-faturação de {d:%m/%Y} desta área já foi fechada"
    return None


def verificar_editavel(db: Session, o: Ocorrencia, nova_data: date | None = None) -> None:
    area = o.linha.contrato.tipo.value
    for d in {o.data, nova_data} - {None}:
        m = motivo_bloqueio(db, o.tenant_id, d, area)
        if m:
            raise PeriodoFechadoErro(m + ": as alterações são feitas como ajuste no período seguinte")
