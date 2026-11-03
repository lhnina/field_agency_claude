"""Importação inicial por Excel (B03): clientes, lojas, colaboradores e contratos.

Fluxo: descarregar o modelo → preencher → carregar → pré-visualizar (erros por linha)
→ confirmar. A confirmação só grava se não houver erros, tudo numa transação.
Clientes, lojas e colaboradores são atualizados quando já existem (chave: nome,
nome ou n.º). Contratos são sempre novos: uma linha do Excel por loja, agrupadas
pela coluna "Referência".
"""
import io
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Cliente, Colaborador, Contrato, EstadoContrato, Insignia, LinhaContrato, Loja, Marca, Perfil, ServicoLogistico, TipoContrato,
    TipoVinculo, User, Zona,
)
from app.services import operacao as op

MAX_LINHAS = 5000


# ------------------------------------------------------------------ conversões
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _txt(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _dec(v: Any, campo: str) -> Decimal | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return Decimal(str(v).replace("€", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"{campo}: '{v}' não é um número")


def _data(v: Any, campo: str) -> date | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"{campo}: '{s}' não é uma data (use dd/mm/aaaa)")


VINCULOS = {
    "sem termo": TipoVinculo.sem_termo, "efetivo": TipoVinculo.sem_termo, "a termo": TipoVinculo.a_termo,
    "muito curta duracao": TipoVinculo.muito_curta_duracao, "curta duracao": TipoVinculo.muito_curta_duracao,
    "recibos verdes": TipoVinculo.recibos_verdes, "prestador": TipoVinculo.recibos_verdes,
}
TIPOS = {"reposicao": TipoContrato.REP, "rep": TipoContrato.REP, "promocao": TipoContrato.PRO,
         "promocoes": TipoContrato.PRO, "pro": TipoContrato.PRO}
DIAS_PT = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def _disponibilidade(v: Any) -> str | None:
    s = _txt(v)
    if not s:
        return None
    if re.fullmatch(r"[01]{7}", s):
        return s
    dias = {_norm(x)[:3] for x in re.split(r"[,;/ ]+", s) if x.strip()}
    if not dias <= set(DIAS_PT):
        raise ValueError(f"Disponibilidade: '{s}' (use Seg,Ter,Qua… ou 1111100)")
    return "".join("1" if d in dias else "0" for d in DIAS_PT)


# ------------------------------------------------------------------ definição das folhas
@dataclass
class Coluna:
    nome: str
    obrigatoria: bool = False
    exemplo: Any = None
    ajuda: str = ""
    lista: list[str] | None = None


@dataclass
class Modelo:
    titulo: str
    colunas: list[Coluna]
    notas: list[str] = field(default_factory=list)


MODELOS: dict[str, Modelo] = {
    "clientes": Modelo("Clientes", [
        Coluna("Nome", True, "Bom Grão Cafés"), Coluna("NIF", False, "509123456"),
        Coluna("Código ERP", False, 1201, "N.º de cliente no ERP"),
        Coluna("Marcas", False, "Bom Grão; Grão Gourmet", "Separadas por ponto e vírgula"),
        Coluna("Morada", False, "Rua do Café, 10"), Coluna("Código postal", False, "1000-100"),
        Coluna("Localidade", False, "Lisboa"), Coluna("Telefone", False, "210000000"),
        Coluna("Email", False, "geral@bomgrao.pt"), Coluna("Site", False, "https://bomgrao.pt"),
        Coluna("Contacto", False, "Paulo Reis"), Coluna("Gestor de conta", False, "Joana Pires"),
        Coluna("Observações", False, None),
    ], ["Se o cliente já existir (mesmo nome), é atualizado e as marcas novas são acrescentadas."]),
    "lojas": Modelo("Lojas", [
        Coluna("Nome", True, "Continente Amadora"), Coluna("Código ERP", False, "L0457"), Coluna("Insígnia", False, "Continente"),
        Coluna("Zona", False, "Amadora", "Criada se não existir"), Coluna("Nome para credencial", False, "CONTINENTE AMADORA"),
        Coluna("Morada", False, "Av. Conde Castro Guimarães"), Coluna("Código postal", False, "2720-100"),
        Coluna("Localidade", False, "Amadora"), Coluna("Horário semana", False, "08:00–22:00"),
        Coluna("Horário fim de semana", False, "09:00–21:00"), Coluna("Contacto", False, "Ana Silva"),
        Coluna("Função do contacto", False, "Chefe de secção"), Coluna("Telefone", False, "214000000"),
        Coluna("Email", False, "loja@exemplo.pt"),
        Coluna("Supervisor", False, "rui@promovida.pt", "Email ou nome do utilizador supervisor"),
    ], ["Se a loja já existir (mesmo nome), é atualizada.", "Insígnias e zonas novas são criadas automaticamente."]),
    "colaboradores": Modelo("Colaboradores", [
        Coluna("N.º", True, "0412"), Coluna("Nome", True, "Inês Carvalho"), Coluna("Função", False, "Repositor(a)"),
        Coluna("Vínculo", True, "A termo", lista=["Sem termo", "A termo", "Muito curta duração", "Recibos verdes"]),
        Coluna("Data de início", False, "03/02/2025", "dd/mm/aaaa (na muito curta duração: início do contrato atual)"),
        Coluna("Data de fim do vínculo", False, None, "dd/mm/aaaa"),
        Coluna("Zona", False, "Amadora"), Coluna("Supervisor", False, "rui@promovida.pt", "Email ou nome"),
        Coluna("Custo por hora", False, 11.40, "€"), Coluna("Telemóvel", False, "912345118"),
        Coluna("Email", False, "ines@exemplo.pt"),
        Coluna("Disponibilidade", False, "Seg,Ter,Qua,Qui,Sex", "Dias separados por vírgula, ou 1111100"),
    ], ["Se o colaborador já existir (mesmo n.º), é atualizado."]),
    "contratos": Modelo("Contratos", [
        Coluna("Referência", True, "BG-2026", "Agrupa as linhas do mesmo contrato"),
        Coluna("Tipo", True, "Reposição", lista=["Reposição", "Promoção"]),
        Coluna("Cliente", True, "Bom Grão Cafés", "Tem de existir (importe primeiro os clientes)"),
        Coluna("Marca", False, "Bom Grão"), Coluna("Data do contrato", False, "01/12/2025"),
        Coluna("Início", True, "01/01/2026"), Coluna("Fim", False, None, "Vazio = sem termo"),
        Coluna("Descrição ou evento", False, "Reposição Grande Lisboa"),
        Coluna("Loja", True, "Continente Amadora", "Tem de existir (importe primeiro as lojas)"),
        *[Coluna(d, False, h, "Horas") for d, h in zip(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"], [1.5, 0, 1.5, 0, 0, 0, 0])],
        Coluna("Preço por hora", True, 18.00, "€"), Coluna("Hora de início", False, None, "Promoções: hh:mm"),
        Coluna("Mecânica", False, None, "Promoções: Degustação, Amostras…"),
        Coluna("Colaborador (N.º)", False, "0412", "Afeto desde o início da linha"),
        Coluna("Início da linha", False, None, "Vazio = início do contrato"),
        Coluna("Fim da linha", False, None, "Vazio = fim do contrato"),
        Coluna("Estado", False, "Ativo", lista=["Ativo", "Proposta"]),
    ], ["Uma linha por loja; as linhas com a mesma Referência formam um contrato.",
        "Os contratos são sempre criados de novo, com numeração automática. Contratos ativos geram logo o planeamento."]),
    "logistica": Modelo("Pedidos de logística", [
        Coluna("Referência ERP", False, "GT-2026/1532", "N.º do pedido/guia no ERP. Se já existir, o serviço é atualizado"),
        Coluna("Contrato", True, "CT-LOG-2026/0001", "N.º de um contrato de Logística existente"),
        Coluna("Loja", True, "Continente Amadora", "Nome ou código ERP da loja"),
        Coluna("Serviço", True, "Entrega", lista=["Entrega", "Recolha", "Implementação", "Entrega + Implementação", "Desmontagem"]),
        Coluna("Data", True, "15/11/2026"), Coluna("Hora início", False, "09:00", "Janela horária (hh:mm)"),
        Coluna("Hora fim", False, "12:00"), Coluna("Origem", False, "Armazém Alverca"),
        Coluna("Materiais", False, "2 expositores de chão; 50 cartazes A2"),
        Coluna("Preço", False, 85.00, "€ por serviço"), Coluna("Observações", False, None),
    ], ["Uma linha por serviço. Com «Referência ERP» o mesmo pedido pode ser carregado várias vezes: atualiza em vez de duplicar.",
        "Serviços já executados ou validados não são alterados."]),
}


def modelo_xlsx(tipo: str, zonas: list[str]) -> bytes:
    m = MODELOS[tipo]
    wb = Workbook()
    ws = wb.active
    ws.title = m.titulo
    cab = PatternFill("solid", fgColor="0F2B2A")
    for i, c in enumerate(m.colunas, start=1):
        cel = ws.cell(row=1, column=i, value=c.nome + (" *" if c.obrigatoria else ""))
        cel.font = Font(bold=True, color="FFFFFF")
        cel.fill = cab
        ws.cell(row=2, column=i, value=c.exemplo).font = Font(italic=True, color="5E6966")
        ws.column_dimensions[cel.column_letter].width = max(14, len(c.nome) + 4)
        lista = c.lista or (zonas if c.nome == "Zona" and zonas else None)
        if lista:
            dv = DataValidation(type="list", formula1='"' + ",".join(lista) + '"', allow_blank=True)
            dv.error = "Escolha um valor da lista"
            ws.add_data_validation(dv)
            dv.add(f"{cel.column_letter}2:{cel.column_letter}{MAX_LINHAS}")
    ws.freeze_panes = "A2"
    info = wb.create_sheet("Instruções")
    linhas = [f"Importação de {m.titulo.lower()} — Field Agency", "",
              "A linha 2 é um exemplo: substitua-a ou apague-a.", "As colunas com * são obrigatórias.", *m.notas, "",
              "Coluna", *[f"{c.nome}{' *' if c.obrigatoria else ''} — {c.ajuda}" for c in m.colunas if c.ajuda]]
    for i, t in enumerate(linhas, start=1):
        info.cell(row=i, column=1, value=t).font = Font(bold=i == 1)
    info.column_dimensions["A"].width = 100
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------------ leitura
def ler_folha(conteudo: bytes, tipo: str) -> list[tuple[int, dict]]:
    try:
        wb = load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    except Exception:
        raise ValueError("O ficheiro não é um Excel válido (.xlsx)")
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    try:
        cab = next(rows)
    except StopIteration:
        raise ValueError("A folha está vazia")
    nomes = {_norm(c.nome): c.nome for c in MODELOS[tipo].colunas}
    if "codigo erp" in nomes:
        nomes["codigo phc"] = nomes["codigo erp"]  # modelos antigos
    idx = {}
    for i, h in enumerate(cab):
        k = _norm(str(h or "").replace("*", ""))
        if k in nomes:
            idx[nomes[k]] = i
    falta = [c.nome for c in MODELOS[tipo].colunas if c.obrigatoria and c.nome not in idx]
    if falta:
        raise ValueError("Faltam colunas obrigatórias: " + ", ".join(falta) + ". Use o modelo descarregado.")
    out = []
    for n, r in enumerate(rows, start=2):
        if r is None or all(v is None or str(v).strip() == "" for v in r):
            continue
        out.append((n, {nome: (r[i] if i < len(r) else None) for nome, i in idx.items()}))
        if len(out) > MAX_LINHAS:
            raise ValueError(f"Máximo de {MAX_LINHAS} linhas por ficheiro")
    return out


# ------------------------------------------------------------------ processamento
@dataclass
class Resultado:
    linhas: list[dict] = field(default_factory=list)

    @property
    def erros(self) -> int:
        return sum(1 for ln in self.linhas if ln["erros"])

    def json(self) -> dict:
        acoes: dict[str, int] = {}
        for ln in self.linhas:
            if not ln["erros"]:
                acoes[ln["acao"]] = acoes.get(ln["acao"], 0) + 1
        return {"linhas": self.linhas, "resumo": {"total": len(self.linhas), "com_erros": self.erros, **acoes}}


class Contexto:
    def __init__(self, db: Session, user: User):
        self.db, self.user, self.T = db, user, user.tenant_id
        self.zonas = {_norm(z.nome): z for z in db.scalars(select(Zona).where(Zona.tenant_id == self.T)).all()}
        self.insignias = {_norm(z.nome): z for z in db.scalars(select(Insignia).where(Insignia.tenant_id == self.T)).all()}
        self.supervisores = {}
        for u in db.scalars(select(User).where(User.tenant_id == self.T, User.perfil == Perfil.supervisor)).all():
            self.supervisores[_norm(u.email)] = u
            self.supervisores[_norm(u.nome)] = u

    def zona(self, nome: str | None, criar: bool) -> tuple[Zona | None, bool]:
        if not nome:
            return None, False
        z = self.zonas.get(_norm(nome))
        if z or not criar:
            return z, False
        z = Zona(tenant_id=self.T, nome=nome.strip())
        self.db.add(z)
        self.db.flush()
        self.zonas[_norm(nome)] = z
        return z, True

    def insignia(self, nome: str | None, criar: bool) -> Insignia | None:
        if not nome:
            return None
        i = self.insignias.get(_norm(nome))
        if i or not criar:
            return i
        i = Insignia(tenant_id=self.T, nome=nome.strip())
        self.db.add(i)
        self.db.flush()
        self.insignias[_norm(nome)] = i
        return i

    def supervisor(self, v: str | None) -> User | None:
        if not v:
            return None
        u = self.supervisores.get(_norm(v))
        if not u:
            raise ValueError(f"Supervisor '{v}' não encontrado (use o email ou o nome de um utilizador supervisor)")
        return u


def _linha(n: int, chave: str, acao: str, erros: list[str], avisos: list[str] | None = None) -> dict:
    return {"linha": n, "chave": chave, "acao": acao, "erros": erros, "avisos": avisos or []}


def _clientes(ctx: Contexto, rows, gravar: bool) -> Resultado:
    res = Resultado()
    existentes = {_norm(c.nome): c for c in ctx.db.scalars(select(Cliente).where(Cliente.tenant_id == ctx.T)).all()}
    gestores: dict[str, int] = {}
    for u in ctx.db.scalars(select(User).where(User.tenant_id == ctx.T, User.perfil == Perfil.gestor_conta, User.ativo.is_(True))).all():
        gestores[_norm(u.nome)] = gestores[_norm(u.email)] = u.id
    vistos: set[str] = set()
    for n, r in rows:
        erros: list[str] = []
        nome = _txt(r.get("Nome"))
        if not nome:
            res.linhas.append(_linha(n, "", "erro", ["Nome em falta"]))
            continue
        k = _norm(nome)
        if k in vistos:
            erros.append("Cliente repetido no ficheiro")
        vistos.add(k)
        try:
            erp = int(_dec(r.get("Código ERP"), "Código ERP")) if _txt(r.get("Código ERP")) else None
        except (ValueError, TypeError) as e:
            erros.append(str(e))
            erp = None
        marcas = [m.strip() for m in re.split(r"[;\n]", _txt(r.get("Marcas")) or "") if m.strip()]
        gestor = None
        if _txt(r.get("Gestor de conta")):
            gestor = gestores.get(_norm(_txt(r.get("Gestor de conta"))))
            if gestor is None:
                erros.append("Gestor de conta desconhecido (tem de ser um utilizador ativo com o perfil Gestor de conta)")
        c = existentes.get(k)
        res.linhas.append(_linha(n, nome, "atualizar" if c else "criar", erros))
        if gravar and not erros:
            if not c:
                c = Cliente(tenant_id=ctx.T, nome=nome)
                ctx.db.add(c)
                existentes[k] = c
            c.nif = _txt(r.get("NIF")) or c.nif
            for col, attr in [("Morada", "morada"), ("Código postal", "codigo_postal"), ("Localidade", "localidade"),
                              ("Telefone", "telefone"), ("Email", "email"), ("Site", "url"), ("Contacto", "contacto_nome"),
                              ("Observações", "observacoes")]:
                v = _txt(r.get(col))
                if v is not None:
                    setattr(c, attr, v)
            c.codigo_erp = erp if erp is not None else c.codigo_erp
            if gestor is not None:
                c.gestor_conta_id = gestor
            atuais = {_norm(m.nome) for m in c.marcas}
            for m in marcas:
                if _norm(m) not in atuais:
                    c.marcas.append(Marca(tenant_id=ctx.T, nome=m))
    return res


LOJA_CAMPOS = {"Código ERP": "codigo_erp", "Nome para credencial": "nome_credencial", "Morada": "morada", "Código postal": "codigo_postal",
               "Localidade": "localidade", "Horário semana": "horario_semana", "Horário fim de semana": "horario_fim_semana",
               "Contacto": "contacto_nome", "Função do contacto": "contacto_funcao", "Telefone": "contacto_telefone",
               "Email": "contacto_email"}


def _lojas(ctx: Contexto, rows, gravar: bool) -> Resultado:
    res = Resultado()
    existentes = {_norm(x.nome): x for x in ctx.db.scalars(select(Loja).where(Loja.tenant_id == ctx.T)).all()}
    vistos: set[str] = set()
    for n, r in rows:
        erros, avisos = [], []
        nome = _txt(r.get("Nome"))
        if not nome:
            res.linhas.append(_linha(n, "", "erro", ["Nome em falta"]))
            continue
        k = _norm(nome)
        if k in vistos:
            erros.append("Loja repetida no ficheiro")
        vistos.add(k)
        sup = None
        try:
            sup = ctx.supervisor(_txt(r.get("Supervisor")))
        except ValueError as e:
            erros.append(str(e))
        zn, ins = _txt(r.get("Zona")), _txt(r.get("Insígnia"))
        if zn and _norm(zn) not in ctx.zonas:
            avisos.append(f"Zona nova: {zn}")
        if ins and _norm(ins) not in ctx.insignias:
            avisos.append(f"Insígnia nova: {ins}")
        lj = existentes.get(k)
        res.linhas.append(_linha(n, nome, "atualizar" if lj else "criar", erros, avisos))
        if gravar and not erros:
            if not lj:
                lj = Loja(tenant_id=ctx.T, nome=nome)
                ctx.db.add(lj)
                existentes[k] = lj
            z, _ = ctx.zona(zn, True)
            i = ctx.insignia(ins, True)
            lj.zona_id = z.id if z else lj.zona_id
            lj.insignia_id = i.id if i else lj.insignia_id
            lj.supervisor_id = sup.id if sup else lj.supervisor_id
            for col, attr in LOJA_CAMPOS.items():
                v = _txt(r.get(col))
                if v is not None:
                    setattr(lj, attr, v)
    return res


def _colaboradores(ctx: Contexto, rows, gravar: bool) -> Resultado:
    res = Resultado()
    existentes = {c.numero: c for c in ctx.db.scalars(select(Colaborador).where(Colaborador.tenant_id == ctx.T)).all()}
    vistos: set[str] = set()
    for n, r in rows:
        erros, avisos = [], []
        num, nome = _txt(r.get("N.º")), _txt(r.get("Nome"))
        if not num or not nome:
            res.linhas.append(_linha(n, nome or num or "", "erro", ["N.º e Nome são obrigatórios"]))
            continue
        if num in vistos:
            erros.append("N.º repetido no ficheiro")
        vistos.add(num)
        vinc = VINCULOS.get(_norm(_txt(r.get("Vínculo")) or ""))
        if not vinc:
            erros.append(f"Vínculo '{_txt(r.get('Vínculo')) or ''}' inválido (Sem termo, A termo, Muito curta duração, Recibos verdes)")
        vals: dict[str, Any] = {}
        for campo, fn, attr in [("Data de início", _data, "data_inicio"), ("Data de fim do vínculo", _data, "data_fim_vinculo"),
                                ("Custo por hora", _dec, "custo_hora")]:
            try:
                vals[attr] = fn(r.get(campo), campo)
            except ValueError as e:
                erros.append(str(e))
        try:
            vals["disponibilidade"] = _disponibilidade(r.get("Disponibilidade"))
        except ValueError as e:
            erros.append(str(e))
        sup = None
        try:
            sup = ctx.supervisor(_txt(r.get("Supervisor")))
        except ValueError as e:
            erros.append(str(e))
        zn = _txt(r.get("Zona"))
        if zn and _norm(zn) not in ctx.zonas:
            avisos.append(f"Zona nova: {zn}")
        if vals.get("custo_hora") is None and num not in existentes:
            avisos.append("Sem custo por hora: a margem fica sobrestimada")
        c = existentes.get(num)
        res.linhas.append(_linha(n, f"{num} · {nome}", "atualizar" if c else "criar", erros, avisos))
        if gravar and not erros:
            if not c:
                c = Colaborador(tenant_id=ctx.T, numero=num, nome=nome, vinculo=vinc, custo_hora=Decimal("0"))
                ctx.db.add(c)
                existentes[num] = c
            c.nome, c.vinculo = nome, vinc
            z, _ = ctx.zona(zn, True)
            c.zona_id = z.id if z else c.zona_id
            c.supervisor_id = sup.id if sup else c.supervisor_id
            for attr, v in vals.items():
                if v is not None:
                    setattr(c, attr, v)
            for col, attr in [("Função", "funcao"), ("Telemóvel", "telefone"), ("Email", "email")]:
                v = _txt(r.get(col))
                if v is not None:
                    if attr == "funcao":
                        from app.api.base import garantir_funcao
                        v = garantir_funcao(ctx.db, ctx.T, v)
                    setattr(c, attr, v)
    return res


def _contratos(ctx: Contexto, rows, gravar: bool) -> Resultado:
    res = Resultado()
    clientes = {_norm(c.nome): c for c in ctx.db.scalars(select(Cliente).where(Cliente.tenant_id == ctx.T)).all()}
    lojas = {_norm(x.nome): x for x in ctx.db.scalars(select(Loja).where(Loja.tenant_id == ctx.T)).all()}
    colabs = {c.numero: c for c in ctx.db.scalars(select(Colaborador).where(Colaborador.tenant_id == ctx.T)).all()}
    grupos: dict[str, dict] = {}
    validas: list[tuple[str, dict]] = []
    for n, r in rows:
        erros: list[str] = []
        ref = _txt(r.get("Referência"))
        if not ref:
            res.linhas.append(_linha(n, "", "erro", ["Referência em falta"]))
            continue
        tipo = TIPOS.get(_norm(_txt(r.get("Tipo")) or ""))
        if not tipo:
            erros.append("Tipo inválido (Reposição ou Promoção)")
        cli = clientes.get(_norm(_txt(r.get("Cliente")) or ""))
        if not cli:
            erros.append(f"Cliente '{_txt(r.get('Cliente')) or ''}' não existe")
        loja = lojas.get(_norm(_txt(r.get("Loja")) or ""))
        if not loja:
            erros.append(f"Loja '{_txt(r.get('Loja')) or ''}' não existe")
        v: dict[str, Any] = {}
        for campo, attr in [("Início", "inicio"), ("Fim", "fim"), ("Data do contrato", "data"),
                            ("Início da linha", "l_inicio"), ("Fim da linha", "l_fim")]:
            try:
                v[attr] = _data(r.get(campo), campo)
            except ValueError as e:
                erros.append(str(e))
        if not v.get("inicio") and "Início" not in " ".join(erros):
            erros.append("Início em falta")
        horas = []
        for d in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]:
            try:
                h = _dec(r.get(d), d) or Decimal("0")
                if h < 0 or h > 24:
                    raise ValueError(f"{d}: horas entre 0 e 24")
                horas.append(h)
            except ValueError as e:
                erros.append(str(e))
                horas.append(Decimal("0"))
        if sum(horas) == 0:
            erros.append("Indique horas em pelo menos um dia da semana")
        try:
            preco = _dec(r.get("Preço por hora"), "Preço por hora")
            if preco is None:
                erros.append("Preço por hora em falta")
        except ValueError as e:
            erros.append(str(e))
            preco = None
        hi = _txt(r.get("Hora de início"))
        if isinstance(r.get("Hora de início"), (datetime,)):
            hi = r["Hora de início"].strftime("%H:%M")
        elif hi and not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d(:00)?", hi):
            erros.append("Hora de início: use hh:mm")
        hi = hi[:5].zfill(5) if hi else None
        num_col = _txt(r.get("Colaborador (N.º)"))
        col = colabs.get(num_col) if num_col else None
        if num_col and not col:
            erros.append(f"Colaborador n.º {num_col} não existe")
        estado = EstadoContrato.proposta if _norm(_txt(r.get("Estado")) or "ativo") == "proposta" else EstadoContrato.ativo
        g = grupos.setdefault(ref, {"tipo": tipo, "cliente": cli, "inicio": v.get("inicio"), "fim": v.get("fim"), "estado": estado})
        if g["tipo"] != tipo or g["cliente"] is not cli or g["inicio"] != v.get("inicio") or g["fim"] != v.get("fim"):
            erros.append(f"As linhas da referência {ref} têm tipo, cliente ou datas diferentes")
        l_ini = v.get("l_inicio") or v.get("inicio")
        if v.get("inicio") and l_ini and l_ini < v["inicio"]:
            erros.append("O início da linha é anterior ao início do contrato")
        if v.get("fim") and v.get("inicio") and v["fim"] < v["inicio"]:
            erros.append("O fim do contrato é anterior ao início")
        res.linhas.append(_linha(n, f"{ref} · {_txt(r.get('Loja')) or ''}", "criar", erros))
        if not erros:
            validas.append((ref, {"r": r, "loja": loja, "horas": horas, "preco": preco, "hora": hi, "col": col,
                                  "l_inicio": l_ini, "l_fim": v.get("l_fim"), "data": v.get("data")}))
    if gravar and not res.erros:
        horizonte = date.today() + timedelta(days=settings.horizonte_planeamento_dias)
        criados: dict[str, Contrato] = {}
        for ref, x in validas:
            g = grupos[ref]
            c = criados.get(ref)
            if not c:
                r = x["r"]
                marca = None
                mn = _txt(r.get("Marca"))
                if mn:
                    marca = next((m for m in g["cliente"].marcas if _norm(m.nome) == _norm(mn)), None)
                    if not marca:
                        marca = Marca(tenant_id=ctx.T, nome=mn)
                        g["cliente"].marcas.append(marca)
                        ctx.db.flush()
                desc = _txt(r.get("Descrição ou evento"))
                c = Contrato(tenant_id=ctx.T, tipo=g["tipo"], cliente_id=g["cliente"].id, marca_id=marca.id if marca else None,
                             numero=op.proximo_numero(ctx.db, ctx.T, g["tipo"].value, (x["data"] or g["inicio"]).year),
                             data=x["data"] or g["inicio"], inicio=g["inicio"], fim=g["fim"], estado=g["estado"],
                             descricao=desc if g["tipo"] == TipoContrato.REP else None,
                             evento=desc if g["tipo"] == TipoContrato.PRO else None,
                             observacoes=f"Importado (referência {ref})")
                ctx.db.add(c)
                ctx.db.flush()
                criados[ref] = c
            ln = LinhaContrato(tenant_id=ctx.T, loja_id=x["loja"].id, inicio=x["l_inicio"], fim=x["l_fim"],
                               preco_hora=x["preco"], hora_inicio=x["hora"], mecanica=_txt(x["r"].get("Mecânica")),
                               **{f"h_{d}": h for d, h in zip(DIAS_PT, x["horas"])})
            c.linhas.append(ln)
            ctx.db.flush()
            if x["col"]:
                op.afetar(ctx.db, ctx.user, ln, x["col"], ln.inicio)
            if c.estado == EstadoContrato.ativo:
                op.gerar_ocorrencias(ctx.db, ln, ate=horizonte, desde=max(ln.inicio, date.today() - timedelta(days=7)))
        for c in criados.values():
            op.auditar(ctx.db, ctx.user, "contrato", c.id, "importar", {"numero": c.numero, "linhas": len(c.linhas)})
    return res


TIPOS_LOG = {"entrega": "entrega", "recolha": "recolha", "implementacao": "implementacao",
             "entrega + implementacao": "entrega_implementacao", "entrega+implementacao": "entrega_implementacao",
             "entrega e implementacao": "entrega_implementacao", "desmontagem": "desmontagem"}


def _logistica(ctx: Contexto, rows, gravar: bool) -> Resultado:
    import re
    from app.models import EstadoServicoLog, TipoServicoLog
    from app.services.periodos import motivo_bloqueio
    res = Resultado()
    contratos = {_norm(c.numero): c for c in ctx.db.scalars(select(Contrato).where(
        Contrato.tenant_id == ctx.T, Contrato.tipo == TipoContrato.LOG)).all()}
    lojas: dict[str, Loja] = {}
    for lj in ctx.db.scalars(select(Loja).where(Loja.tenant_id == ctx.T, Loja.ativo.is_(True))).all():
        lojas[_norm(lj.nome)] = lj
        if lj.codigo_erp:
            lojas.setdefault(_norm(lj.codigo_erp), lj)
    existentes = {_norm(s.referencia_erp): s for s in ctx.db.scalars(select(ServicoLogistico).where(
        ServicoLogistico.tenant_id == ctx.T, ServicoLogistico.referencia_erp.is_not(None))).all()}
    vistos: set[str] = set()
    for n, r in rows:
        erros: list[str] = []
        ref = _txt(r.get("Referência ERP"))
        if ref:
            if _norm(ref) in vistos:
                erros.append("Referência ERP repetida no ficheiro")
            vistos.add(_norm(ref))
        c = contratos.get(_norm(_txt(r.get("Contrato")) or ""))
        if not c:
            erros.append("Contrato de Logística não encontrado")
        lj = lojas.get(_norm(_txt(r.get("Loja")) or ""))
        if not lj:
            erros.append("Loja não encontrada (use o nome ou o código ERP)")
        tipo = TIPOS_LOG.get(_norm(_txt(r.get("Serviço")) or ""))
        if not tipo:
            erros.append("Serviço inválido (Entrega, Recolha, Implementação, Entrega + Implementação, Desmontagem)")
        try:
            d = _data(r.get("Data"), "Data")
            if d is None:
                erros.append("Data em falta")
        except ValueError as e:
            erros.append(str(e))
            d = None
        horas = []
        for col in ("Hora início", "Hora fim"):
            h = _txt(r.get(col))
            if h and re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", h):
                h = h[:5].zfill(5)
            elif h:
                erros.append(f"{col}: use hh:mm")
                h = None
            horas.append(h)
        if horas[0] and horas[1] and horas[1] <= horas[0]:
            erros.append("A hora de fim tem de ser depois da hora de início")
        try:
            preco = _dec(r.get("Preço"), "Preço") or Decimal("0")
        except ValueError as e:
            erros.append(str(e))
            preco = Decimal("0")
        if c and d and (d < c.inicio or (c.fim and d > c.fim)):
            erros.append("Data fora da vigência do contrato")
        if d and (m := motivo_bloqueio(ctx.db, ctx.T, d, TipoContrato.LOG.value)):
            erros.append(m)
        s = existentes.get(_norm(ref)) if ref else None
        avisos = []
        if s and s.estado in (EstadoServicoLog.executado, EstadoServicoLog.validado, EstadoServicoLog.cancelado):
            avisos.append("Serviço já executado, validado ou cancelado: não é alterado")
        res.linhas.append(_linha(n, ref or f"{_txt(r.get('Loja')) or ''} {d or ''}".strip(), "atualizar" if s else "criar", erros, avisos))
        if gravar and not erros and not avisos:
            if not s:
                s = ServicoLogistico(tenant_id=ctx.T, contrato_id=c.id)
                ctx.db.add(s)
                if ref:
                    existentes[_norm(ref)] = s
            s.contrato_id, s.loja_id, s.tipo, s.data = c.id, lj.id, TipoServicoLog(tipo), d
            s.hora_inicio, s.hora_fim, s.preco, s.referencia_erp = horas[0], horas[1], preco, ref
            for col, attr in (("Origem", "origem"), ("Materiais", "materiais"), ("Observações", "observacoes")):
                v = _txt(r.get(col))
                if v is not None:
                    setattr(s, attr, v)
    return res


PROCESSADORES: dict[str, Callable[[Contexto, list, bool], Resultado]] = {
    "clientes": _clientes, "lojas": _lojas, "colaboradores": _colaboradores, "contratos": _contratos,
    "logistica": _logistica,
}


def importar(db: Session, user: User, tipo: str, conteudo: bytes, confirmar: bool) -> dict:
    rows = ler_folha(conteudo, tipo)
    if not rows:
        raise ValueError("Não há linhas para importar")
    ctx = Contexto(db, user)
    res = PROCESSADORES[tipo](ctx, rows, False)
    out = res.json()
    if confirmar:
        if res.erros:
            raise ValueError(f"Corrija as {res.erros} linhas com erros antes de importar")
        PROCESSADORES[tipo](Contexto(db, user), rows, True)
        db.flush()
        op.auditar(db, user, "importacao", 0, tipo, out["resumo"])
        out["importado"] = True
    return out


def contagens(db: Session, tenant_id: int) -> dict:
    return {nome: db.scalar(select(func.count()).select_from(m).where(m.tenant_id == tenant_id))
            for nome, m in [("clientes", Cliente), ("lojas", Loja), ("colaboradores", Colaborador), ("contratos", Contrato),
                            ("logistica", ServicoLogistico)]}
