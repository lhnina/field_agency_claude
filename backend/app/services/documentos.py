"""Documentação dos colaboradores: requisitos, estado e verificação no planeamento.

Um requisito diz que um tipo de documento é obrigatório. Os campos vazios valem "qualquer":
- sem função, cliente nem insígnia: obrigatório para todos;
- com função: para os colaboradores dessa função;
- com cliente e/ou insígnia: para quem presta serviço nesse cliente e/ou nessa cadeia.

A falta de documentação nunca impede a afetação: só gera alertas (decisão de 03/11).
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Afetacao, Colaborador, Contrato, DocumentoColaborador, EstadoContrato, LinhaContrato, Loja, RequisitoDocumental,
    TipoDocumento,
)

VALIDO, A_EXPIRAR, EXPIRADO, EM_FALTA = "valido", "a_expirar", "expirado", "em_falta"


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def estado_documento(doc: DocumentoColaborador | None, tipo: TipoDocumento, em: date) -> str:
    if doc is None:
        return EM_FALTA
    if not tipo.tem_validade or doc.validade is None:
        return VALIDO
    if doc.validade < em:
        return EXPIRADO
    if doc.validade <= em + timedelta(days=tipo.dias_aviso or 0):
        return A_EXPIRAR
    return VALIDO


def motivo_requisito(r: RequisitoDocumental) -> str:
    partes = []
    if r.funcao:
        partes.append(f"função {r.funcao}")
    if r.cliente_id:
        partes.append(f"cliente {r.cliente.nome}")
    if r.insignia_id:
        partes.append(f"cadeia {r.insignia.nome}")
    return " · ".join(partes) or "todos os colaboradores"


@dataclass
class Contexto:
    """Requisitos e documentos atuais carregados uma vez, para avaliar muitos colaboradores/serviços."""
    requisitos: list[RequisitoDocumental]
    tipos: dict[int, TipoDocumento]
    docs: dict[tuple[int, int], DocumentoColaborador] = field(default_factory=dict)  # (colaborador, tipo) → atual

    def aplicaveis(self, c: Colaborador, cliente_id: int | None = None, insignia_id: int | None = None,
                   servico: bool = True) -> list[RequisitoDocumental]:
        """Requisitos que se aplicam ao colaborador; com servico=True, num serviço do cliente/insígnia indicados."""
        out = []
        for r in self.requisitos:
            if r.funcao and norm(r.funcao) != norm(c.funcao):
                continue
            if r.cliente_id and (not servico or r.cliente_id != cliente_id):
                continue
            if r.insignia_id and (not servico or r.insignia_id != insignia_id):
                continue
            out.append(r)
        return out

    def falhas(self, c: Colaborador, cliente_id: int | None, insignia_id: int | None, em: date) -> list[str]:
        """Documentos obrigatórios em falta ou expirados na data de um serviço (texto para o alerta)."""
        res, vistos = [], set()
        for r in self.aplicaveis(c, cliente_id, insignia_id):
            if r.tipo_documento_id in vistos:
                continue
            vistos.add(r.tipo_documento_id)
            tipo = self.tipos[r.tipo_documento_id]
            doc = self.docs.get((c.id, tipo.id))
            e = estado_documento(doc, tipo, em)
            if e == EM_FALTA:
                res.append(f"{tipo.nome} em falta")
            elif e == EXPIRADO:
                res.append(f"{tipo.nome} expirado a {doc.validade:%d/%m/%Y}")
        return res


def contexto(db: Session, tenant_id: int, colaboradores: list[int] | None = None) -> Contexto:
    reqs = db.scalars(select(RequisitoDocumental).options(
        joinedload(RequisitoDocumental.cliente), joinedload(RequisitoDocumental.insignia)).join(TipoDocumento).where(
        RequisitoDocumental.tenant_id == tenant_id, RequisitoDocumental.ativo.is_(True), TipoDocumento.ativo.is_(True))).all()
    tipos = {t.id: t for t in db.scalars(select(TipoDocumento).where(TipoDocumento.tenant_id == tenant_id)).all()}
    q = select(DocumentoColaborador).where(DocumentoColaborador.tenant_id == tenant_id, DocumentoColaborador.atual.is_(True))
    if colaboradores is not None:
        q = q.where(DocumentoColaborador.colaborador_id.in_(colaboradores or [0]))
    docs = {(d.colaborador_id, d.tipo_documento_id): d for d in db.scalars(q).all()}
    return Contexto(list(reqs), tipos, docs)


def servicos_vigentes(db: Session, ids: list[int], hoje: date) -> dict[int, set[tuple[int, int | None]]]:
    """(cliente, insígnia) dos serviços em que cada colaborador está afeto hoje ou no futuro."""
    out: dict[int, set[tuple[int, int | None]]] = {}
    if not ids:
        return out
    rows = db.execute(select(Afetacao.colaborador_id, Contrato.cliente_id, Loja.insignia_id)
                      .join(LinhaContrato, Afetacao.linha_id == LinhaContrato.id)
                      .join(Contrato, LinhaContrato.contrato_id == Contrato.id)
                      .join(Loja, LinhaContrato.loja_id == Loja.id)
                      .where(Afetacao.colaborador_id.in_(ids), or_(Afetacao.ate.is_(None), Afetacao.ate >= hoje),
                             Contrato.estado.in_((EstadoContrato.ativo, EstadoContrato.proposta)),
                             or_(LinhaContrato.fim.is_(None), LinhaContrato.fim >= hoje))).all()
    for cid, cli, ins in rows:
        out.setdefault(cid, set()).add((cli, ins))
    return out


def situacao(db: Session, ctx: Contexto, colabs: list[Colaborador], hoje: date) -> list[dict]:
    """Uma linha por colaborador e tipo de documento relevante: obrigatório (pela função ou pelos serviços
    em que está afeto) ou já entregue."""
    servicos = servicos_vigentes(db, [c.id for c in colabs], hoje)
    linhas = []
    for c in colabs:
        porque: dict[int, list[str]] = {}
        for r in ctx.aplicaveis(c, servico=False):
            porque.setdefault(r.tipo_documento_id, []).append(motivo_requisito(r))
        for cli, ins in servicos.get(c.id, set()):
            for r in ctx.aplicaveis(c, cli, ins):
                if r.cliente_id or r.insignia_id:
                    porque.setdefault(r.tipo_documento_id, []).append(motivo_requisito(r))
        tipos = set(porque) | {t for (cid, t) in ctx.docs if cid == c.id}
        for tid in tipos:
            tipo = ctx.tipos[tid]
            if not tipo.ativo and tid not in porque and (c.id, tid) not in ctx.docs:
                continue
            doc = ctx.docs.get((c.id, tid))
            linhas.append({
                "colaborador_id": c.id, "colaborador": c.nome, "numero_colaborador": c.numero, "funcao": c.funcao,
                "zona": c.zona.nome if c.zona else None, "tipo_documento_id": tid, "tipo": tipo.nome,
                "tem_validade": tipo.tem_validade, "obrigatorio": tid in porque,
                "motivo": " / ".join(dict.fromkeys(porque.get(tid, []))) or None,
                "estado": estado_documento(doc, tipo, hoje),
                "documento": documento_json(doc) if doc else None,
            })
    ordem = {EXPIRADO: 0, EM_FALTA: 1, A_EXPIRAR: 2, VALIDO: 3}
    linhas.sort(key=lambda x: (ordem[x["estado"]], x["colaborador"], x["tipo"]))
    return linhas


def documento_json(d: DocumentoColaborador) -> dict:
    return {
        "id": d.id, "colaborador_id": d.colaborador_id, "tipo_documento_id": d.tipo_documento_id,
        "numero": d.numero, "emissao": d.emissao.isoformat() if d.emissao else None,
        "validade": d.validade.isoformat() if d.validade else None, "observacoes": d.observacoes, "atual": d.atual,
        "ficheiro_nome": d.ficheiro_nome, "ficheiro_tamanho": d.ficheiro_tamanho,
        "registado_em": d.created_at.isoformat() if d.created_at else None,
    }


def resumo(linhas: list[dict]) -> dict:
    """Contagens para os indicadores (só documentos obrigatórios contam como problema)."""
    obrig = [x for x in linhas if x["obrigatorio"]]
    return {
        "expirados": sum(1 for x in obrig if x["estado"] == EXPIRADO),
        "em_falta": sum(1 for x in obrig if x["estado"] == EM_FALTA),
        "a_expirar": sum(1 for x in linhas if x["estado"] == A_EXPIRAR),
        "validos": sum(1 for x in linhas if x["estado"] == VALIDO),
        "colaboradores_com_problemas": len({x["colaborador_id"] for x in obrig if x["estado"] in (EXPIRADO, EM_FALTA)}),
    }
