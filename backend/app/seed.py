"""Dados de demonstração (agência fictícia "Promovida Field Services").

Uso:  python -m app.seed        (apaga e recria os dados de demonstração)
Utilizadores: marta@promovida.pt (direção), hugo@promovida.pt (gestor),
rui@promovida.pt e sara@promovida.pt (supervisores), admin@promovida.pt.
Palavra-passe de todos: demo1234
"""
from datetime import date, timedelta
from decimal import Decimal as D

from sqlalchemy import select, text

from app.db import Base, SessionLocal, engine
from app.models import (
    Ausencia, Cliente, Colaborador, Contrato, EstadoContrato, Feriado, Insignia, LinhaContrato, Loja, Marca, Perfil,
    Tenant, TipoAusencia, TipoContrato, TipoVinculo, User, Zona,
)
from app.security import hash_password
from app.services import operacao as op

FERIADOS = {
    "Ano Novo": ["2026-01-01", "2027-01-01"], "Sexta-feira Santa": ["2026-04-03", "2027-03-26"],
    "Páscoa": ["2026-04-05", "2027-03-28"], "Dia da Liberdade": ["2026-04-25", "2027-04-25"],
    "Dia do Trabalhador": ["2026-05-01", "2027-05-01"], "Corpo de Deus": ["2026-06-04", "2027-05-27"],
    "Dia de Portugal": ["2026-06-10", "2027-06-10"], "Assunção de Nossa Senhora": ["2026-08-15", "2027-08-15"],
    "Implantação da República": ["2026-10-05", "2027-10-05"], "Todos os Santos": ["2026-11-01", "2027-11-01"],
    "Restauração da Independência": ["2026-12-01", "2027-12-01"], "Imaculada Conceição": ["2026-12-08", "2027-12-08"],
    "Natal": ["2026-12-25", "2027-12-25"],
}


def run(reset: bool = True) -> None:
    if reset:
        with engine.begin() as conn:
            tabelas = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
            conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    db = SessionLocal()
    t = Tenant(nome="Promovida Field Services", nif="509000000")
    db.add(t)
    db.flush()
    T = t.id
    for nome, datas in FERIADOS.items():
        for d in datas:
            db.add(Feriado(data=date.fromisoformat(d), nome=nome))

    pw = hash_password("demo1234")
    users = {}
    for key, nome, perfil in [("admin", "Administrador", Perfil.administrador), ("marta", "Marta Ribeiro", Perfil.direcao),
                              ("hugo", "Hugo Faria", Perfil.gestor), ("rui", "Rui Matos", Perfil.supervisor),
                              ("sara", "Sara Guedes", Perfil.supervisor)]:
        u = User(tenant_id=T, email=f"{key}@promovida.pt", nome=nome, password_hash=pw, perfil=perfil)
        db.add(u)
        users[key] = u
    db.flush()

    zonas = {n: Zona(tenant_id=T, nome=n) for n in ["Amadora", "Lisboa", "Oeiras", "Sintra", "Odivelas", "Loures"]}
    ins = {n: Insignia(tenant_id=T, nome=n) for n in ["Continente", "Pingo Doce", "Auchan", "Intermarché", "Lidl"]}
    db.add_all(list(zonas.values()) + list(ins.values()))
    db.flush()

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
    for nome, marcas, phc in [("Bom Grão Cafés", ["Bom Grão"], 1201), ("Atlântico Conservas", ["Atlântico", "Mar Azul"], 1188),
                              ("Nata Doce Gelados", ["Nata Doce"], 1310), ("Pura Higiene", ["Pura"], 1022),
                              ("Quinta do Vale Sumos", ["Quinta do Vale"], 1254), ("Montado Vinhos", ["Montado"], 1099)]:
        c = Cliente(tenant_id=T, nome=nome, codigo_phc=phc, marcas=[Marca(tenant_id=T, nome=m) for m in marcas])
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
    db.commit()
    db.close()
    print("Dados de demonstração criados. Utilizadores: marta|hugo|rui|sara|admin@promovida.pt / demo1234")


if __name__ == "__main__":
    run()
