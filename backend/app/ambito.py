"""Âmbito de dados por perfil.

O gestor de conta tem os acessos do gestor operacional, mas só vê e altera os clientes de que é
gestor de conta (definido na ficha do cliente) e tudo o que deles depende: contratos, linhas,
ocorrências, validação, pré-faturação e apuramentos. Lojas, zonas, insígnias e colaboradores
são partilhados (são precisos para afetar e substituir).

O supervisor supervisiona uma zona (ou TODAS, quando não tem zona): só vê as lojas e os
colaboradores dessa zona, e os serviços desses colaboradores ou, por atribuir, dessas lojas.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cliente, Colaborador, Contrato, LinhaContrato, Loja, Marca, Ocorrencia, Perfil, ServicoLogistico, User


def clientes_permitidos(db: Session, user: User) -> set[int] | None:
    """None = sem restrição; caso contrário, os ids dos clientes que o utilizador pode ver."""
    if user.perfil != Perfil.gestor_conta:
        return None
    return set(db.scalars(select(Cliente.id).where(Cliente.tenant_id == user.tenant_id,
                                                   Cliente.gestor_conta_id == user.id)).all())


def zona_supervisor(user: User) -> int | None:
    """Zona a que o utilizador está limitado (só supervisores com zona); None = todas."""
    return user.zona_id if user.perfil == Perfil.supervisor else None


def equipa(db: Session, sup: User | None) -> set[int] | None:
    """Colaboradores ativos da zona do supervisor; None quando não há limitação."""
    if sup is None or sup.perfil != Perfil.supervisor or not sup.zona_id:
        return None
    return set(db.scalars(select(Colaborador.id).where(Colaborador.tenant_id == sup.tenant_id, Colaborador.ativo.is_(True),
                                                       Colaborador.zona_id == sup.zona_id)).all())


def ocorrencia_visivel(o: Ocorrencia, zona: int | None, eq: set[int] | None) -> bool:
    if zona is None:
        return True
    cid = o.colaborador_id
    return (cid in eq) if (cid is not None and eq is not None) else o.linha.loja.zona_id == zona


def servico_na_zona(s: ServicoLogistico, zona: int) -> bool:
    """Serviço logístico visível ao supervisor: loja da zona, ou motorista/ajudante da zona."""
    return (s.loja.zona_id == zona or (s.colaborador is not None and s.colaborador.zona_id == zona)
            or (s.ajudante is not None and s.ajudante.zona_id == zona))


def cliente_de(obj) -> int | None:
    if isinstance(obj, Cliente):
        return obj.id
    if isinstance(obj, (Marca, Contrato)):
        return obj.cliente_id
    if isinstance(obj, LinhaContrato):
        return obj.contrato.cliente_id
    if isinstance(obj, Ocorrencia):
        return obj.linha.contrato.cliente_id
    if isinstance(obj, ServicoLogistico):
        return obj.contrato.cliente_id
    return None


def verificar(db: Session, user: User, obj) -> None:
    """404 (como se não existisse) quando o objeto está fora do âmbito do utilizador."""
    zona = zona_supervisor(user)
    if zona is not None and isinstance(obj, (Loja, Colaborador)) and obj.zona_id != zona:
        raise HTTPException(404, "Registo não encontrado")
    if zona is not None and isinstance(obj, ServicoLogistico) and not servico_na_zona(obj, zona):
        raise HTTPException(404, "Registo não encontrado")
    permitidos = clientes_permitidos(db, user)
    if permitidos is None:
        return
    cid = cliente_de(obj)
    if cid is not None and cid not in permitidos:
        raise HTTPException(404, "Registo não encontrado")
