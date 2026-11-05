import os

os.environ.setdefault("FA_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/fieldagency_test")

from datetime import date  # noqa: E402
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Cliente, Colaborador, Contrato, EstadoContrato, Feriado, LinhaContrato, Loja, Perfil, Tenant, TipoContrato,
    TipoVinculo, User, Zona,
)
from app.security import hash_password  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(t.name for t in reversed(Base.metadata.sorted_tables)) + " RESTART IDENTITY CASCADE"))
    s = SessionLocal()
    yield s
    s.close()


class Mundo:
    pass


@pytest.fixture()
def mundo(db):
    m = Mundo()
    m.t = Tenant(nome="Agência Teste")
    db.add(m.t)
    db.flush()
    T = m.t.id
    pw = hash_password("x")
    m.gestor = User(tenant_id=T, email="g@t.pt", nome="Gestor", password_hash=pw, perfil=Perfil.gestor)
    m.sup1 = User(tenant_id=T, email="s1@t.pt", nome="Sup 1", password_hash=pw, perfil=Perfil.supervisor)
    m.sup2 = User(tenant_id=T, email="s2@t.pt", nome="Sup 2", password_hash=pw, perfil=Perfil.supervisor)
    m.gc = User(tenant_id=T, email="gc@t.pt", nome="Joana Pires", password_hash=pw, perfil=Perfil.gestor_conta)
    db.add_all([m.gestor, m.sup1, m.sup2, m.gc])
    m.zona = Zona(tenant_id=T, nome="Amadora")
    m.zona2 = Zona(tenant_id=T, nome="Sintra")
    db.add_all([m.zona, m.zona2])
    db.flush()
    m.sup1.zona_id, m.sup2.zona_id = m.zona.id, m.zona2.id
    m.loja = Loja(tenant_id=T, nome="Continente Amadora", zona_id=m.zona.id, supervisor_id=m.sup1.id)
    m.loja2 = Loja(tenant_id=T, nome="Pingo Doce Alfragide", zona_id=m.zona.id, supervisor_id=m.sup1.id)
    m.cliente = Cliente(tenant_id=T, nome="Bom Grão Cafés")
    db.add_all([m.loja, m.loja2, m.cliente])
    db.flush()
    m.ines = Colaborador(tenant_id=T, numero="1", nome="Inês", vinculo=TipoVinculo.a_termo, zona_id=m.zona.id,
                         supervisor_id=m.sup1.id, custo_hora=D("11.40"))
    m.pedro = Colaborador(tenant_id=T, numero="2", nome="Pedro", vinculo=TipoVinculo.sem_termo, zona_id=m.zona.id,
                          supervisor_id=m.sup1.id, custo_hora=D("11.90"))
    m.outro = Colaborador(tenant_id=T, numero="3", nome="Outra equipa", vinculo=TipoVinculo.sem_termo, zona_id=m.zona2.id,
                          supervisor_id=m.sup2.id, custo_hora=D("11.00"))
    db.add_all([m.ines, m.pedro, m.outro])
    m.contrato = Contrato(tenant_id=T, numero="CT-REP-2026/0001", tipo=TipoContrato.REP, cliente_id=m.cliente.id,
                          data=date(2026, 1, 1), inicio=date(2026, 1, 1), estado=EstadoContrato.ativo)
    db.add(m.contrato)
    db.add(Feriado(data=date(2026, 12, 1), nome="Restauração da Independência"))
    db.flush()
    m.db = db
    return m


def nova_linha(m, horas, loja=None, preco="18.00", inicio=date(2026, 11, 2), fim=None) -> LinhaContrato:
    ln = LinhaContrato(tenant_id=m.t.id, contrato_id=m.contrato.id, loja_id=(loja or m.loja).id, inicio=inicio, fim=fim,
                       preco_hora=D(preco),
                       **{f"h_{d}": D(str(h)) for d, h in zip(("seg", "ter", "qua", "qui", "sex", "sab", "dom"), horas)})
    m.contrato.linhas.append(ln)
    m.db.flush()
    return ln


@pytest.fixture()
def client():
    return TestClient(app)


def token(client, email):
    r = client.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
