"""Dados de demonstração (agência fictícia "Promovida Field Services").

Uso:  python -m app.seed        (apaga e recria os dados de demonstração)
Utilizadores: marta@promovida.pt (direção), hugo@promovida.pt (gestor),
rui@promovida.pt e sara@promovida.pt (supervisores), admin@promovida.pt.
Palavra-passe de todos: demo1234
"""
import zlib
from datetime import date, timedelta
from decimal import Decimal as D

from sqlalchemy import select, text

from app.db import Base, SessionLocal, engine
from app.models import (
    Ausencia, Cliente, Colaborador, Contrato, DocumentoColaborador, ModeloCredencial, EstadoContrato, Feriado, Funcao, Insignia, LinhaContrato, Loja,
    Marca, Perfil, RequisitoDocumental, Tenant, TipoAusencia, TipoContrato, TipoDocumento, TipoVinculo, User, Zona,
)
from app.security import hash_password
from app.services import operacao as op


def run(reset: bool = True) -> None:
    if reset:
        with engine.begin() as conn:
            tabelas = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
            conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    db = SessionLocal()
    # Encargos de demonstração (ajustáveis em Configuração): trabalhadores +40 %, prestadores 0 %
    t = Tenant(nome="Promovida Field Services", nif="509000000", encargos_sem_termo_pct=D("40"), encargos_a_termo_pct=D("40"),
               encargos_muito_curta_pct=D("40"), encargos_recibos_verdes_pct=D("0"),
               morada="Avenida da República, 50, 3.º", codigo_postal="1050-196", localidade="Lisboa",
               registo_comercial="matriculada na Conservatória do Registo Comercial de Lisboa sob o n.º 509000000",
               seguradora="Fidelidade – Companhia de Seguros, S.A.", apolice="AT-2026-0045871", apolice_validade=date(2026, 12, 31))
    db.add(t)
    db.flush()
    T = t.id
    # Os feriados nacionais são calculados; aqui só um municipal de exemplo (Amadora, 11 de setembro)

    pw = hash_password("demo1234")
    users = {}
    for key, nome, perfil in [("admin", "Administrador", Perfil.administrador), ("marta", "Marta Ribeiro", Perfil.direcao),
                              ("hugo", "Hugo Faria", Perfil.gestor), ("rui", "Rui Matos", Perfil.supervisor),
                              ("sara", "Sara Guedes", Perfil.supervisor), ("joana", "Joana Pires", Perfil.gestor_conta),
                              ("tomas", "Tomás Reis", Perfil.gestor_conta)]:
        u = User(tenant_id=T, email=f"{key}@promovida.pt", nome=nome, password_hash=pw, perfil=perfil)
        db.add(u)
        users[key] = u
    db.flush()

    zonas = {n: Zona(tenant_id=T, nome=n) for n in ["Amadora", "Lisboa", "Oeiras", "Sintra", "Odivelas", "Loures"]}
    ins = {n: Insignia(tenant_id=T, nome=n) for n in ["Continente", "Pingo Doce", "Auchan", "Intermarché", "Lidl"]}
    db.add_all(list(zonas.values()) + list(ins.values()))
    db.flush()
    users["rui"].zona_id = zonas["Amadora"].id   # supervisiona a Amadora; a Sara supervisiona TODAS as zonas
    for ano in (date.today().year, date.today().year + 1):
        db.add(Feriado(tenant_id=T, zona_id=zonas["Amadora"].id, data=date(ano, 9, 11), nome="Feriado municipal da Amadora"))

    lojas_def = [
        ("Continente Amadora", "Continente", "Amadora", "rui"), ("Continente Colombo", "Continente", "Lisboa", "rui"),
        ("Continente Oeiras", "Continente", "Oeiras", "sara"), ("Continente Queluz", "Continente", "Sintra", "sara"),
        ("Continente Sintra", "Continente", "Sintra", "sara"), ("Pingo Doce Alfragide", "Pingo Doce", "Amadora", "rui"),
        ("Pingo Doce Benfica", "Pingo Doce", "Lisboa", "rui"), ("Pingo Doce Telheiras", "Pingo Doce", "Lisboa", "rui"),
        ("Pingo Doce Loures", "Pingo Doce", "Loures", "rui"), ("Auchan Amadora", "Auchan", "Amadora", "rui"),
        ("Auchan Alfragide", "Auchan", "Amadora", "rui"), ("Auchan Sintra", "Auchan", "Sintra", "sara"),
        ("Intermarché Odivelas", "Intermarché", "Odivelas", "rui"), ("Lidl Odivelas", "Lidl", "Odivelas", "rui"),
    ]
    lojas = {}
    for k, (nome, i, z, s) in enumerate(lojas_def):
        lj = Loja(tenant_id=T, nome=nome, codigo_erp=f"L{401 + k:04d}", nome_credencial=nome.upper(), insignia_id=ins[i].id, zona_id=zonas[z].id,
                  supervisor_id=users[s].id, horario_semana="08:00–22:00", horario_fim_semana="09:00–21:00",
                  localidade=z)
        db.add(lj)
        lojas[nome] = lj

    clientes = {}
    GESTOR_CONTA = {"Bom Grão Cafés": "joana", "Nata Doce Gelados": "joana", "Pura Higiene": "joana",
                    "Atlântico Conservas": "tomas", "Quinta do Vale Sumos": "tomas", "Montado Vinhos": "tomas"}
    for nome, marcas, erp in [("Bom Grão Cafés", ["Bom Grão"], 1201), ("Atlântico Conservas", ["Atlântico", "Mar Azul"], 1188),
                              ("Nata Doce Gelados", ["Nata Doce"], 1310), ("Pura Higiene", ["Pura"], 1022),
                              ("Quinta do Vale Sumos", ["Quinta do Vale"], 1254), ("Montado Vinhos", ["Montado"], 1099)]:
        c = Cliente(tenant_id=T, nome=nome, codigo_erp=erp, marcas=[Marca(tenant_id=T, nome=m) for m in marcas],
                    localidade="Lisboa", gestor_conta_id=users[GESTOR_CONTA[nome]].id, contacto_nome="Departamento comercial",
                    email="comercial@" + nome.split()[0].lower().replace("ã", "a").replace("â", "a") + ".pt")
        db.add(c)
        clientes[nome] = c

    col_def = [
        ("0412", "Inês Carvalho", "Repositor(a)", TipoVinculo.a_termo, "Amadora", "rui", "11.40", "1111100"),
        ("0198", "Pedro Almeida", "Repositor(a)", TipoVinculo.sem_termo, "Lisboa", "rui", "11.90", "1111110"),
        ("0877", "Sofia Martins", "Promotor(a)", "mcd", "Amadora", "rui", "10.80", "1010011"),
        ("0233", "Carla Sousa", "Repositor(a)", TipoVinculo.sem_termo, "Oeiras", "sara", "12.20", "1111100"),
        ("0951", "João Ferreira", "Promotor(a)", TipoVinculo.recibos_verdes, "Odivelas", "rui", "14.00", "0101000"),
        ("0560", "Ana Lopes", "Repositor(a)", TipoVinculo.a_termo, "Sintra", "sara", "11.40", "1111100"),
        ("0734", "Beatriz Nunes", "Repositor(a)", TipoVinculo.a_termo, "Odivelas", "rui", "11.20", "1101100"),
        ("0902", "Tiago Moreira", "Promotor(a)", "mcd", "Loures", "rui", "10.80", "0001111"),
        ("0645", "Marco Dias", "Repositor(a)", TipoVinculo.sem_termo, "Amadora", "rui", "11.40", "1111100"),
        ("0388", "Rita Gonçalves", "Repositor(a)", TipoVinculo.a_termo, "Sintra", "sara", "11.40", "1111100"),
    ]
    db.add_all([Funcao(tenant_id=T, nome=n) for n in ("Repositor(a)", "Promotor(a)", "Chefe de equipa")])
    cols = {}
    for num, nome, funcao, vinc, z, s, custo, disp in col_def:
        mcd = vinc == "mcd"
        vinc = TipoVinculo.a_termo if mcd else vinc
        c = Colaborador(tenant_id=T, numero=num, nome=nome, funcao=funcao, vinculo=vinc, zona_id=zonas[z].id, muito_curta_duracao=mcd,
                        supervisor_id=users[s].id, custo_hora=D(custo), disponibilidade=disp,
                        email=nome.lower().replace(" ", ".").replace("ç", "c").replace("ê", "e").replace("ã", "a") + "@promovida.pt",
                        data_inicio=date(2025, 2, 3), data_admissao=date(2025, 2, 3))
        if vinc == TipoVinculo.recibos_verdes:
            c.data_inicio = c.data_admissao = None
        if mcd:  # contrato atual recente (máx. 35 dias seguidos)
            c.data_inicio = date.today() - timedelta(days=29 if nome == "Sofia Martins" else 12)
            c.data_fim_vinculo = c.data_inicio + timedelta(days=34)
            c.data_admissao = c.data_inicio
        db.add(c)
        cols[nome] = c
    db.flush()

    hoje = date.today()
    desde = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)  # início do mês anterior
    horizonte = hoje + timedelta(days=56)
    marta = users["hugo"]

    def contrato(tipo, cliente, numero_ano, inicio, fim=None, descricao=None, evento=None):
        c = Contrato(tenant_id=T, tipo=tipo, cliente_id=clientes[cliente].id, marca_id=clientes[cliente].marcas[0].id,
                     numero=op.proximo_numero(db, T, tipo.value, numero_ano), data=inicio - timedelta(days=20),
                     inicio=inicio, fim=fim, estado=EstadoContrato.ativo, descricao=descricao, evento=evento)
        db.add(c)
        db.flush()
        return c

    def linha(c, loja, horas, preco="18.00", colab=None, hora=None, mecanica=None, inicio=None, fim=None):
        ln = LinhaContrato(tenant_id=T, contrato_id=c.id, loja_id=lojas[loja].id, inicio=inicio or c.inicio, fim=fim or c.fim,
                           preco_hora=D(preco), hora_inicio=hora, mecanica=mecanica,
                           **{f"h_{d}": D(str(h)) for d, h in zip(("seg", "ter", "qua", "qui", "sex", "sab", "dom"), horas)})
        c.linhas.append(ln)
        db.flush()
        if colab:
            op.afetar(db, marta, ln, cols[colab], ln.inicio)
        op.gerar_ocorrencias(db, ln, ate=horizonte, desde=desde)
        return ln

    bg = contrato(TipoContrato.REP, "Bom Grão Cafés", 2026, date(2026, 1, 1), descricao="Reposição em lojas da Grande Lisboa")
    linha(bg, "Continente Amadora", [1.5, 0, 1.5, 0, 0, 0, 0], colab="Inês Carvalho")
    linha(bg, "Pingo Doce Alfragide", [1.5, 0, 0, 1.5, 0, 0, 0], colab="Inês Carvalho")
    linha(bg, "Continente Colombo", [0, 3, 0, 0, 3, 0, 0])
    linha(bg, "Continente Oeiras", [0, 3, 0, 0, 3, 0, 0], colab="Carla Sousa")
    linha(bg, "Continente Queluz", [0, 2, 0, 2, 0, 0, 0], colab="Carla Sousa")
    linha(bg, "Intermarché Odivelas", [2, 0, 0, 2, 0, 0, 0], colab="Beatriz Nunes")
    linha(bg, "Auchan Amadora", [0, 0, 2, 0, 2, 0, 0], colab="Ana Lopes")
    linha(bg, "Pingo Doce Benfica", [2, 0, 2, 0, 0, 0, 0], colab="Pedro Almeida")
    linha(bg, "Continente Sintra", [0, 3, 0, 3, 0, 0, 0], colab="Rita Gonçalves")
    linha(bg, "Auchan Alfragide", [0, 0, 0, 0, 3, 0, 0], colab="Inês Carvalho")
    linha(bg, "Pingo Doce Telheiras", [2, 0, 0, 0, 2, 0, 0], colab="Pedro Almeida", fim=date(2026, 6, 30))  # já terminou

    at = contrato(TipoContrato.REP, "Atlântico Conservas", 2026, date(2026, 3, 1), date(2027, 2, 28), descricao="Reposição em 38 lojas")
    linha(at, "Continente Colombo", [4, 4, 4, 4, 4, 0, 0], preco="18.00", colab="Pedro Almeida")
    linha(at, "Lidl Odivelas", [0, 2, 0, 2, 0, 0, 0], preco="17.50", colab="Marco Dias")
    linha(at, "Pingo Doce Loures", [2, 0, 2, 0, 2, 0, 0], preco="17.50")

    ph = contrato(TipoContrato.REP, "Pura Higiene", 2026, date(2026, 5, 1), descricao="Reposição")
    linha(ph, "Auchan Sintra", [4, 0, 4, 0, 0, 0, 0], preco="17.00", colab="Ana Lopes")
    linha(ph, "Auchan Amadora", [0, 3, 0, 3, 0, 0, 0], preco="17.00", colab="João Ferreira")

    natal_ini = hoje - timedelta(days=hoje.weekday())
    nd = contrato(TipoContrato.PRO, "Nata Doce Gelados", 2026, natal_ini, natal_ini + timedelta(days=55),
                  descricao="Degustações em loja", evento="Campanha de Natal")
    linha(nd, "Continente Amadora", [4, 0, 4, 0, 0, 4, 4], preco="19.00", colab="Sofia Martins", hora="14:00", mecanica="Degustação")
    linha(nd, "Pingo Doce Telheiras", [0, 0, 2, 0, 0, 0, 0], preco="19.00", colab="Pedro Almeida", hora="10:00", mecanica="Degustação")
    linha(nd, "Pingo Doce Benfica", [0, 0, 0, 4, 0, 4, 0], preco="19.00", hora="16:00", mecanica="Degustação")

    # Férias da Carla Sousa nesta semana (segunda a sexta)
    seg = hoje - timedelta(days=hoje.weekday())
    db.add(Ausencia(tenant_id=T, colaborador_id=cols["Carla Sousa"].id, tipo=TipoAusencia.ferias, inicio=seg,
                    fim=seg + timedelta(days=4), observacoes="Férias aprovadas"))
    db.flush()

    # Execução do mês anterior: aceitação tácita até ontem; validado até 7 dias atrás,
    # com algumas correções e uma rejeição, para haver casos reais na validação.
    from app.models import EstadoOcorrencia, Ocorrencia
    from app.services import fecho
    fecho.aplicar_aceitacao_tacita(db, T, hoje - timedelta(days=1))
    passadas = db.scalars(select(Ocorrencia).where(Ocorrencia.tenant_id == T, Ocorrencia.data <= hoje - timedelta(days=7),
                                                   Ocorrencia.estado == EstadoOcorrencia.executado).order_by(Ocorrencia.id)).all()
    for i, o in enumerate(passadas):
        if i % 23 == 5:
            fecho.registar_execucao(db, users["rui"], o, o.horas_planeadas + D("0.5"), "Reposição de promoção extra", hoje)
        if i % 41 == 9:
            fecho.validar(db, users["rui"], [o], False, "Loja fechada para inventário", hoje)
        else:
            fecho.validar(db, users["rui"], [o], True, None, hoje)
    recentes = db.scalars(select(Ocorrencia).where(Ocorrencia.tenant_id == T, Ocorrencia.data > hoje - timedelta(days=7),
                                                   Ocorrencia.data < hoje, Ocorrencia.estado == EstadoOcorrencia.executado).order_by(Ocorrencia.id)).all()
    for i, o in enumerate(recentes):
        if i % 7 == 2:
            fecho.registar_execucao(db, users["rui"], o, max(o.horas_planeadas - D("1"), D("0")), "Saiu mais cedo (loja sem stock)", hoje)
    _documentacao(db, T, cols, clientes, ins, users["hugo"], hoje)
    _credenciais(db, T, cols, users["hugo"], hoje)
    lg = contrato(TipoContrato.LOG, "Quinta do Vale Sumos", 2026, date(2026, 9, 1), date(2026, 12, 31),
                  descricao="Entregas e montagem de expositores — campanha de inverno")
    _logistica(db, T, lg, lojas, cols, users["hugo"], hoje)
    db.commit()
    db.close()
    print("Dados de demonstração criados. Utilizadores: marta|hugo|joana|tomas|rui|sara|admin@promovida.pt / demo1234")


def _pdf(titulo: str) -> bytes:
    """PDF mínimo de uma página, só para demonstrar os anexos."""
    txt = titulo.encode("latin-1", "replace")
    stream = b"BT /F1 18 Tf 72 720 Td (" + txt + b") Tj ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def _documentacao(db, T, cols, clientes, ins, autor, hoje) -> None:
    """Tipos, requisitos e documentos de demonstração, com alguns expirados, a expirar e em falta."""
    tipos = {}
    for nome, val, aviso in [("Doc. de Identificação", True, 60), ("Formação HACCP", True, 30), ("Registo criminal", True, 30),
                             ("Seguro de acidentes pessoais", True, 30), ("Declaração de início de atividade", False, 0),
                             ("Exame médico (ficha de aptidão)", True, 30)]:
        tipos[nome] = TipoDocumento(tenant_id=T, nome=nome, tem_validade=val, dias_aviso=aviso)
    db.add_all(tipos.values())
    db.flush()
    for tipo, kw in [("Doc. de Identificação", {}), ("Formação HACCP", {"funcao": "Promotor(a)"}),
                     ("Formação HACCP", {"cliente_id": clientes["Nata Doce Gelados"].id}),
                     ("Registo criminal", {"insignia_id": ins["Continente"].id}),
                     ("Seguro de acidentes pessoais", {"cliente_id": clientes["Atlântico Conservas"].id})]:
        db.add(RequisitoDocumental(tenant_id=T, tipo_documento_id=tipos[tipo].id, **kw))
    d = lambda n: hoje + timedelta(days=n)  # noqa: E731
    docs = [  # (colaborador, tipo, validade, com anexo)
        ("Inês Carvalho", "Doc. de Identificação", d(1400), True), ("Inês Carvalho", "Registo criminal", d(200), True),
        ("Pedro Almeida", "Doc. de Identificação", d(900), True), ("Pedro Almeida", "Seguro de acidentes pessoais", d(20), False),
        ("Sofia Martins", "Doc. de Identificação", d(2000), True), ("Sofia Martins", "Formação HACCP", d(300), True),
        ("Carla Sousa", "Doc. de Identificação", d(45), False), ("Carla Sousa", "Registo criminal", d(-12), True),
        ("João Ferreira", "Doc. de Identificação", d(700), False), ("João Ferreira", "Formação HACCP", d(-40), True),
        ("João Ferreira", "Declaração de início de atividade", None, True),
        ("Ana Lopes", "Doc. de Identificação", d(1100), True), ("Beatriz Nunes", "Doc. de Identificação", d(-5), False),
        ("Marco Dias", "Doc. de Identificação", d(25), True), ("Marco Dias", "Seguro de acidentes pessoais", d(150), True),
        ("Rita Gonçalves", "Doc. de Identificação", d(500), True), ("Rita Gonçalves", "Registo criminal", d(10), False),
        ("Inês Carvalho", "Exame médico (ficha de aptidão)", d(300), False), ("Pedro Almeida", "Exame médico (ficha de aptidão)", d(200), False),
        ("Marco Dias", "Exame médico (ficha de aptidão)", d(120), False), ("Carla Sousa", "Exame médico (ficha de aptidão)", d(250), False),
    ]  # o Tiago Moreira não entregou nada
    for nome, tipo, val, anexo in docs:
        doc = DocumentoColaborador(tenant_id=T, colaborador_id=cols[nome].id, tipo_documento_id=tipos[tipo].id,
                                   numero=f"{zlib.crc32(nome.encode()) % 10**8:08d}" if tipo == "Doc. de Identificação" else None,
                                   emissao=(val - timedelta(days=365 if tipo.startswith("Exame") else 365 * 5)) if val else d(-400), validade=val, criado_por_id=autor.id)
        if anexo:
            doc.ficheiro = _pdf(f"{tipo} - {nome}")
            doc.ficheiro_nome = f"{tipo} - {nome}.pdf"
            doc.ficheiro_tipo, doc.ficheiro_tamanho = "application/pdf", len(doc.ficheiro)
        db.add(doc)
    db.flush()



def _credenciais(db, T, cols, autor, hoje) -> None:
    """Modelo de credencial (a partir do modelo do cliente) e dados de identificação dos colaboradores."""
    from pathlib import Path
    ficheiro = (Path(__file__).parent / "assets" / "credencial_modelo.docx").read_bytes()
    db.add(ModeloCredencial(tenant_id=T, nome="Credencial padrão", versao=1, atual=True, ativo=True,
                            notas="Modelo inicial, adaptado da credencial em uso", ficheiro_nome="Credencial padrão.docx",
                            ficheiro_tamanho=len(ficheiro), ficheiro=ficheiro, criado_por_id=autor.id))
    nasc = {"Inês Carvalho": date(1996, 4, 12), "Pedro Almeida": date(1988, 9, 3), "Sofia Martins": date(2001, 1, 27),
            "Carla Sousa": date(1979, 11, 30), "Marco Dias": date(1992, 6, 18), "Ana Lopes": date(1990, 2, 8),
            "Rita Gonçalves": date(1998, 7, 21), "Beatriz Nunes": date(1985, 5, 5)}
    for nome, dn in nasc.items():
        cols[nome].data_nascimento = dn
        cols[nome].niss = f"1{zlib.crc32(nome.encode()) % 10**10:010d}"
    db.flush()



def _logistica(db, T, c, lojas, cols, autor, hoje) -> None:
    """Viaturas e serviços logísticos: alguns feitos e validados, alguns por executar, um sem viatura."""
    from app.models import EstadoServicoLog as E, ServicoLogistico, TipoServicoLog as TS, Viatura
    v = {m: Viatura(tenant_id=T, matricula=m, descricao=d, custo_km=D(k)) for m, d, k in [
        ("AA-12-BC", "Renault Master · caixa fechada", "0.32"), ("BD-45-ZX", "Citroën Berlingo", "0.21"),
        ("CE-78-QR", "Iveco Daily · plataforma", "0.38")]}
    db.add_all(v.values())
    db.flush()
    seg = hoje - timedelta(days=hoje.weekday())
    d = lambda n: seg + timedelta(days=n)  # noqa: E731
    servicos = [  # (dias desde segunda, loja, tipo, janela, materiais, preço, viatura, motorista, ajudante, estado, execução)
        (-7, "Continente Colombo", TS.entrega_implementacao, ("08:00", "11:00"), "2 expositores de chão; 1 ilha de frio", "145.00", "AA-12-BC", "Pedro Almeida", "Marco Dias", E.validado, (45210, 45262, "6.40", "08:05", "11:20")),
        (-6, "Pingo Doce Loures", TS.entrega, ("09:00", "12:00"), "40 cartazes A2; 6 wobblers", "65.00", "BD-45-ZX", "Tiago Moreira", None, E.validado, (88120, 88171, "3.20", "09:10", "10:40")),
        (-4, "Auchan Sintra", TS.implementacao, ("14:00", "18:00"), "Montagem de topo de gôndola", "120.00", "AA-12-BC", "Pedro Almeida", None, E.executado, (45262, 45318, "4.85", "14:00", "17:15")),
        (-2, "Continente Oeiras", TS.recolha, None, "Recolha de 1 expositor danificado", "55.00", "BD-45-ZX", "Tiago Moreira", None, E.atribuido, None),
        (1, "Continente Amadora", TS.entrega_implementacao, ("08:00", "12:00"), "3 expositores de chão; 100 folhetos", "160.00", "AA-12-BC", "Pedro Almeida", "Marco Dias", E.atribuido, None),
        (1, "Intermarché Odivelas", TS.entrega, ("10:00", "12:00"), "20 cartazes A2", "55.00", "AA-12-BC", "João Ferreira", None, E.atribuido, None),
        (2, "Lidl Odivelas", TS.entrega, ("09:00", "11:00"), "Display de balcão", "50.00", None, None, None, E.planeado, None),
        (3, "Pingo Doce Benfica", TS.implementacao, ("15:00", "18:00"), "Montagem de ilha promocional", "130.00", "CE-78-QR", "Tiago Moreira", None, E.atribuido, None),
        (8, "Continente Colombo", TS.desmontagem, ("20:00", "23:00"), "Desmontagem e recolha da ilha de frio", "110.00", None, None, None, E.planeado, None),
    ]
    for dia, loja, tipo, janela, mat, preco, vt, mot, aj, estado, ex in servicos:
        s = ServicoLogistico(tenant_id=T, contrato_id=c.id, loja_id=lojas[loja].id, tipo=tipo, data=d(dia),
                             hora_inicio=janela[0] if janela else None, hora_fim=janela[1] if janela else None,
                             origem="Armazém Alverca", materiais=mat, preco=D(preco), estado=estado,
                             referencia_erp=f"GT-2026/{1500 + len(mat)}{dia + 10:02d}",
                             viatura_id=v[vt].id if vt else None, colaborador_id=cols[mot].id if mot else None,
                             ajudante_id=cols[aj].id if aj else None)
        if ex:
            s.km_partida, s.km_chegada, s.portagens, s.inicio_real, s.fim_real = ex[0], ex[1], D(ex[2]), ex[3], ex[4]
            s.executado_por_id = autor.id
            if estado == E.validado:
                s.validado_por_id = autor.id
        db.add(s)
    db.flush()


if __name__ == "__main__":
    import sys
    # Proteção: nunca apaga uma base de dados que já tem dados, a não ser que se peça explicitamente.
    with engine.connect() as conn:
        tem_dados = conn.execute(text("SELECT EXISTS (SELECT 1 FROM tenants)")).scalar()
    if tem_dados and "--apagar-tudo" not in sys.argv:
        print("A base de dados já tem dados: os dados de demonstração NÃO foram carregados (nada foi apagado).\n"
              "Só se quiser mesmo APAGAR TUDO e recomeçar com a demonstração: python -m app.seed --apagar-tudo")
        sys.exit(1)
    run()
