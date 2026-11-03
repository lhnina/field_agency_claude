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
    Ausencia, Cliente, Colaborador, Contrato, DocumentoColaborador, ModeloCredencial, EstadoContrato, Feriado, Insignia, LinhaContrato, Loja,
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
    for nome, i, z, s in lojas_def:
        lj = Loja(tenant_id=T, nome=nome, nome_credencial=nome.upper(), insignia_id=ins[i].id, zona_id=zonas[z].id,
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
        ("0412", "Inês Carvalho", "Repositora", TipoVinculo.a_termo, "Amadora", "rui", "11.40", "1111100"),
        ("0198", "Pedro Almeida", "Repositor", TipoVinculo.sem_termo, "Lisboa", "rui", "11.90", "1111110"),
        ("0877", "Sofia Martins", "Promotora", TipoVinculo.muito_curta_duracao, "Amadora", "rui", "10.80", "1010011"),
        ("0233", "Carla Sousa", "Repositora", TipoVinculo.sem_termo, "Oeiras", "sara", "12.20", "1111100"),
        ("0951", "João Ferreira", "Promotor", TipoVinculo.recibos_verdes, "Odivelas", "rui", "14.00", "0101000"),
        ("0560", "Ana Lopes", "Repositora", TipoVinculo.a_termo, "Sintra", "sara", "11.40", "1111100"),
        ("0734", "Beatriz Nunes", "Repositora", TipoVinculo.a_termo, "Odivelas", "rui", "11.20", "1101100"),
        ("0902", "Tiago Moreira", "Promotor", TipoVinculo.muito_curta_duracao, "Loures", "rui", "10.80", "0001111"),
        ("0645", "Marco Dias", "Repositor", TipoVinculo.sem_termo, "Amadora", "rui", "11.40", "1111100"),
        ("0388", "Rita Gonçalves", "Repositora", TipoVinculo.a_termo, "Sintra", "sara", "11.40", "1111100"),
    ]
    cols = {}
    for num, nome, funcao, vinc, z, s, custo, disp in col_def:
        c = Colaborador(tenant_id=T, numero=num, nome=nome, funcao=funcao, vinculo=vinc, zona_id=zonas[z].id,
                        supervisor_id=users[s].id, custo_hora=D(custo), disponibilidade=disp,
                        email=nome.lower().replace(" ", ".").replace("ç", "c").replace("ê", "e").replace("ã", "a") + "@promovida.pt",
                        data_inicio=date(2025, 2, 3))
        if vinc == TipoVinculo.muito_curta_duracao:  # contrato atual recente (máx. 35 dias seguidos)
            c.data_inicio = date.today() - timedelta(days=29 if nome == "Sofia Martins" else 12)
            c.data_fim_vinculo = c.data_inicio + timedelta(days=34)
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
    for nome, val, aviso in [("Cartão de Cidadão", True, 60), ("Formação HACCP", True, 30), ("Registo criminal", True, 30),
                             ("Seguro de acidentes pessoais", True, 30), ("Declaração de início de atividade", False, 0),
                             ("Exame médico (ficha de aptidão)", True, 30)]:
        tipos[nome] = TipoDocumento(tenant_id=T, nome=nome, tem_validade=val, dias_aviso=aviso)
    db.add_all(tipos.values())
    db.flush()
    for tipo, kw in [("Cartão de Cidadão", {}), ("Formação HACCP", {"funcao": "Promotora"}), ("Formação HACCP", {"funcao": "Promotor"}),
                     ("Formação HACCP", {"cliente_id": clientes["Nata Doce Gelados"].id}),
                     ("Registo criminal", {"insignia_id": ins["Continente"].id}),
                     ("Seguro de acidentes pessoais", {"cliente_id": clientes["Atlântico Conservas"].id})]:
        db.add(RequisitoDocumental(tenant_id=T, tipo_documento_id=tipos[tipo].id, **kw))
    d = lambda n: hoje + timedelta(days=n)  # noqa: E731
    docs = [  # (colaborador, tipo, validade, com anexo)
        ("Inês Carvalho", "Cartão de Cidadão", d(1400), True), ("Inês Carvalho", "Registo criminal", d(200), True),
        ("Pedro Almeida", "Cartão de Cidadão", d(900), True), ("Pedro Almeida", "Seguro de acidentes pessoais", d(20), False),
        ("Sofia Martins", "Cartão de Cidadão", d(2000), True), ("Sofia Martins", "Formação HACCP", d(300), True),
        ("Carla Sousa", "Cartão de Cidadão", d(45), False), ("Carla Sousa", "Registo criminal", d(-12), True),
        ("João Ferreira", "Cartão de Cidadão", d(700), False), ("João Ferreira", "Formação HACCP", d(-40), True),
        ("João Ferreira", "Declaração de início de atividade", None, True),
        ("Ana Lopes", "Cartão de Cidadão", d(1100), True), ("Beatriz Nunes", "Cartão de Cidadão", d(-5), False),
        ("Marco Dias", "Cartão de Cidadão", d(25), True), ("Marco Dias", "Seguro de acidentes pessoais", d(150), True),
        ("Rita Gonçalves", "Cartão de Cidadão", d(500), True), ("Rita Gonçalves", "Registo criminal", d(10), False),
        ("Inês Carvalho", "Exame médico (ficha de aptidão)", d(300), False), ("Pedro Almeida", "Exame médico (ficha de aptidão)", d(200), False),
        ("Marco Dias", "Exame médico (ficha de aptidão)", d(120), False), ("Carla Sousa", "Exame médico (ficha de aptidão)", d(250), False),
    ]  # o Tiago Moreira não entregou nada
    for nome, tipo, val, anexo in docs:
        doc = DocumentoColaborador(tenant_id=T, colaborador_id=cols[nome].id, tipo_documento_id=tipos[tipo].id,
                                   numero=f"{zlib.crc32(nome.encode()) % 10**8:08d}" if tipo == "Cartão de Cidadão" else None,
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


if __name__ == "__main__":
    run()
