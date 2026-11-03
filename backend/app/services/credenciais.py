"""Credenciais de loja: campos disponíveis nos modelos Word e valores para um colaborador numa loja."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Colaborador, Credencial, DocumentoColaborador, LinhaContrato, Tenant, TipoDocumento

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
ATIVIDADE = {"REP": "Reposição", "PRO": "Promoção", "LOG": "Logística", "EQF": "Equipas fixas"}


@dataclass(frozen=True)
class Campo:
    chave: str
    descricao: str
    grupo: str
    aliases: tuple[str, ...] = ()


# Os aliases cobrem os nomes usados no modelo de credencial original (MERGEFIELD do ERP e marcadores <<...>>).
CAMPOS: list[Campo] = [
    Campo("nome", "Nome do colaborador", "Colaborador"),
    Campo("numero_colaborador", "N.º interno do colaborador", "Colaborador", ("ncolaborador",)),
    Campo("funcao", "Função", "Colaborador"),
    Campo("data_nascimento", "Data de nascimento (dd/mm/aaaa)", "Colaborador", ("nasc", "datanasc", "datadenascimento")),
    Campo("numero_identificacao", "N.º do Doc. de Identificação", "Colaborador",
          ("pe2bino", "bino", "numero", "cc", "bi", "numerocc", "nidentificacao")),
    Campo("niss", "N.º de beneficiário da Segurança Social", "Colaborador",
          ("nbenef", "numerobenef", "numerobeneficiario", "numerosegurancasocial")),
    Campo("data_exame_medico", "Data do exame médico (ficha de aptidão)", "Colaborador", ("data", "datamed", "examemedico")),
    Campo("cliente", "Cliente (firma)", "Serviço", ("ucrecli", "firma", "nomedocliente")),
    Campo("loja", "Loja (nome para credencial)", "Serviço", ("ucreloj", "estabelecimento")),
    Campo("loja_morada", "Morada da loja", "Serviço"),
    Campo("loja_localidade", "Localidade da loja", "Serviço"),
    Campo("atividade", "Atividade exercida (tipo de contrato)", "Serviço", ("reposicao", "atividadeexercida", "tipodecontrato")),
    Campo("carga_horaria", "Horas semanais na loja", "Serviço", ("cargahoraria", "horassemanais")),
    Campo("contrato", "N.º do contrato", "Serviço"),
    Campo("validade", "Validade da credencial (dd/mm/aaaa)", "Credencial", ("ucreval", "datadevalidade", "validadedacredencial")),
    Campo("validade_extenso", "Validade da credencial por extenso", "Credencial"),
    Campo("numero_credencial", "N.º da credencial", "Credencial"),
    Campo("substitui", "N.º da credencial que esta substitui", "Credencial"),
    Campo("data_emissao", "Data de emissão (dd/mm/aaaa)", "Credencial"),
    Campo("data_emissao_extenso", "Data de emissão por extenso (segunda-feira, 3 de novembro de 2026)", "Credencial"),
    Campo("empresa", "Nome da empresa (Parâmetros)", "Empresa", ("nomedaempresadefinidoemparametros", "empregador", "nomedaempresa")),
    Campo("empresa_nif", "NIF da empresa", "Empresa", ("nif",)),
    Campo("empresa_morada", "Sede social / morada", "Empresa", ("morada", "sedesocial")),
    Campo("empresa_codigo_postal", "Código postal da empresa", "Empresa", ("codpostal", "codigopostal")),
    Campo("empresa_localidade", "Localidade da empresa", "Empresa", ("localidade",)),
    Campo("empresa_registo", "Registo comercial (conservatória)", "Empresa", ("registocomercial", "conservatoria")),
    Campo("seguradora", "Seguradora de acidentes de trabalho", "Empresa", ("companhiadeseguros",)),
    Campo("apolice", "N.º da apólice", "Empresa", ("apolicen", "napolice")),
    Campo("apolice_validade", "Validade da apólice por extenso", "Empresa", ("dddemesdeano", "ddemesdeano", "validadedaapolice")),
]


def chave(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


INDICE: dict[str, str] = {}
for _c in CAMPOS:
    INDICE[chave(_c.chave)] = _c.chave
    for _a in _c.aliases:
        INDICE[chave(_a)] = _c.chave


def resolver_nome(nome: str) -> str | None:
    return INDICE.get(chave(nome))


def curta(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def extenso(d: date | None, dia_semana: bool = False) -> str:
    if not d:
        return ""
    s = f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    return f"{DIAS_SEMANA[d.weekday()]}, {s}" if dia_semana else s


def _num(v) -> str:
    s = f"{float(v):g}"
    return s.replace(".", ",")


def documento_atual(db: Session, colaborador_id: int, *nomes: str) -> DocumentoColaborador | None:
    """Documento atual do colaborador cujo tipo tem um destes nomes (sem acentos/maiúsculas)."""
    alvo = {chave(n) for n in nomes}
    for d in db.scalars(select(DocumentoColaborador).join(TipoDocumento).where(
            DocumentoColaborador.colaborador_id == colaborador_id, DocumentoColaborador.atual.is_(True))).all():
        if chave(d.tipo.nome) in alvo:
            return d
    return None


def exame_medico(db: Session, colaborador_id: int) -> date | None:
    d = documento_atual(db, colaborador_id, "Exame médico", "Ficha de aptidão", "Ficha de aptidão médica", "Exame médico (ficha de aptidão)")
    return d.emissao if d else None


def valores(db: Session, tenant: Tenant, colab: Colaborador, linha: LinhaContrato, *, validade: date | None,
            data_exame: date | None, emissao: date, numero: str, substitui: str | None) -> dict[str, str]:
    loja, contrato = linha.loja, linha.contrato
    cc = documento_atual(db, colab.id, "Doc. de Identificação", "Documento de identificação", "Cartão de Cidadão",
                         "Bilhete de identidade", "Título de residência")
    return {
        "nome": colab.nome,
        "numero_colaborador": colab.numero,
        "funcao": colab.funcao or "",
        "data_nascimento": curta(colab.data_nascimento),
        "numero_identificacao": colab.numero_identificacao or (cc.numero if cc and cc.numero else ""),
        "niss": colab.niss or "",
        "data_exame_medico": curta(data_exame),
        "cliente": contrato.cliente.nome,
        "loja": loja.nome_credencial or loja.nome,
        "loja_morada": loja.morada or "",
        "loja_localidade": loja.localidade or "",
        "atividade": ATIVIDADE.get(contrato.tipo.value, contrato.tipo.value),
        "carga_horaria": _num(linha.horas_semana),
        "contrato": contrato.numero,
        "validade": curta(validade),
        "validade_extenso": extenso(validade),
        "numero_credencial": numero,
        "substitui": substitui or "",
        "data_emissao": curta(emissao),
        "data_emissao_extenso": extenso(emissao, dia_semana=True),
        "empresa": tenant.nome,
        "empresa_nif": tenant.nif or "",
        "empresa_morada": tenant.morada or "",
        "empresa_codigo_postal": tenant.codigo_postal or "",
        "empresa_localidade": tenant.localidade or "",
        "empresa_registo": tenant.registo_comercial or "",
        "seguradora": tenant.seguradora or "",
        "apolice": tenant.apolice or "",
        "apolice_validade": extenso(tenant.apolice_validade),
    }


# Dados que, se faltarem, deixam a credencial incompleta (aviso, não bloqueio)
OBRIGATORIOS = {
    "data_nascimento": "data de nascimento do colaborador", "numero_identificacao": "n.º do Doc. de Identificação do colaborador",
    "niss": "n.º de Segurança Social do colaborador", "data_exame_medico": "data do exame médico",
    "empresa_morada": "morada da empresa (Parâmetros)", "seguradora": "seguradora (Parâmetros)", "apolice": "n.º da apólice (Parâmetros)",
}


def em_falta(v: dict[str, str], usados: set[str] | None = None) -> list[str]:
    return [txt for k, txt in OBRIGATORIOS.items() if not v.get(k) and (usados is None or k in usados)]


def proximo_numero(db: Session, tenant_id: int, ano: int) -> str:
    prefixo = f"CR-{ano}/"
    n = db.scalar(select(func.count(Credencial.id)).where(Credencial.tenant_id == tenant_id, Credencial.numero.like(prefixo + "%"))) or 0
    return f"{prefixo}{n + 1:04d}"
