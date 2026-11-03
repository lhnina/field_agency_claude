from datetime import date

from sqlalchemy import select

from app.models import Feriado, Ocorrencia, Perfil, User, Zona
from app.security import hash_password
from app.services import feriados as fer
from app.services import operacao as op
from tests.conftest import nova_linha, token


def test_pascoa_e_feriados_moveis():
    assert fer.pascoa(2026) == date(2026, 4, 5)
    assert fer.pascoa(2027) == date(2027, 3, 28)
    assert fer.pascoa(2030) == date(2030, 4, 21)
    n = fer.nacionais(2030)
    assert n[date(2030, 4, 19)] == "Sexta-feira Santa" and n[date(2030, 6, 20)] == "Corpo de Deus"
    assert len(n) == 13


def test_feriado_nacional_calculado_sem_tabela(mundo):
    mundo.db.execute(Feriado.__table__.delete())
    ln = nova_linha(mundo, [0, 0, 0, 0, 1, 0, 0], inicio=date(2030, 4, 15))  # sexta-feira santa 2030
    op.gerar_ocorrencias(mundo.db, ln, ate=date(2030, 4, 21))
    o = mundo.db.scalar(select(Ocorrencia).where(Ocorrencia.linha_id == ln.id))
    assert o.reagendada_feriado and o.data == date(2030, 4, 20)


def test_feriado_municipal_so_afeta_a_zona(mundo):
    outra = Zona(tenant_id=mundo.t.id, nome="Lisboa")
    mundo.db.add(outra)
    mundo.db.flush()
    mundo.db.add(Feriado(tenant_id=mundo.t.id, zona_id=mundo.zona.id, data=date(2026, 11, 10), nome="Municipal"))
    mundo.loja2.zona_id = outra.id
    a = nova_linha(mundo, [0, 2, 0, 0, 0, 0, 0])
    b = nova_linha(mundo, [0, 2, 0, 0, 0, 0, 0], loja=mundo.loja2)
    for ln in (a, b):
        op.gerar_ocorrencias(mundo.db, ln, ate=date(2026, 11, 15))
    oa = mundo.db.scalars(select(Ocorrencia).where(Ocorrencia.linha_id == a.id).order_by(Ocorrencia.data)).all()
    ob = mundo.db.scalars(select(Ocorrencia).where(Ocorrencia.linha_id == b.id).order_by(Ocorrencia.data)).all()
    assert [o.data for o in oa] == [date(2026, 11, 3), date(2026, 11, 11)]
    assert [o.data for o in ob] == [date(2026, 11, 3), date(2026, 11, 10)]


def test_api_novo_feriado_reagenda_servicos_ja_gerados(client, mundo):
    ln = nova_linha(mundo, [0, 2, 0, 0, 0, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, date(2026, 11, 2))
    op.gerar_ocorrencias(mundo.db, ln, ate=date(2026, 11, 15))
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post("/api/feriados", headers=h, json={"data": "2026-11-10", "nome": "Municipal", "zona_id": mundo.zona.id})
    assert r.status_code == 201 and r.json()["servicos_reagendados"] == 1
    assert client.post("/api/feriados", headers=h, json={"data": "2026-12-25", "nome": "Natal"}).status_code == 422
    lista = client.get("/api/feriados", headers=h, params={"ano": 2026}).json()
    assert any(f["ambito"] == "zona" and f["data"] == "2026-11-10" for f in lista)
    assert sum(1 for f in lista if f["ambito"] == "nacional") == 13
    assert client.post("/api/feriados", headers=token(client, "s1@t.pt"), json={"data": "2026-11-11", "nome": "x"}).status_code == 403


def test_api_utilizadores_regras(client, mundo):
    admin = User(tenant_id=mundo.t.id, email="a@t.pt", nome="Admin", password_hash=hash_password("x"), perfil=Perfil.administrador)
    mundo.db.add(admin)
    mundo.db.commit()
    hg = token(client, "g@t.pt")
    assert client.get("/api/utilizadores", headers=hg).status_code == 403
    ha = token(client, "a@t.pt")
    novo = {"nome": "Nova Supervisora", "email": "Nova@T.pt", "perfil": "supervisor", "password": "curta"}
    assert client.post("/api/utilizadores", headers=ha, json=novo).status_code == 422
    novo["password"] = "segura123"
    r = client.post("/api/utilizadores", headers=ha, json=novo)
    assert r.status_code == 201 and r.json()["email"] == "nova@t.pt"
    assert client.post("/api/utilizadores", headers=ha, json=novo).status_code == 409
    assert client.post("/api/auth/login", data={"username": "nova@t.pt", "password": "segura123"}).status_code == 200
    # não se desativa a si próprio; tem de ficar um administrador ativo
    eu = {"nome": "Admin", "email": "a@t.pt", "perfil": "administrador", "ativo": False}
    assert client.put(f"/api/utilizadores/{admin.id}", headers=ha, json=eu).status_code == 422
    # desativar impede o login
    uid = r.json()["id"]
    assert client.put(f"/api/utilizadores/{uid}", headers=ha, json={**novo, "ativo": False}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "nova@t.pt", "password": "segura123"}).status_code == 401
    # repor e alterar a própria palavra-passe
    assert client.post(f"/api/utilizadores/{mundo.gestor.id}/password", headers=ha, json={"password": "outra1234"}).status_code == 200
    r = client.post("/api/auth/login", data={"username": "g@t.pt", "password": "outra1234"})
    hg = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.put("/api/auth/password", headers=hg, json={"atual": "errada", "nova": "nova12345"}).status_code == 422
    assert client.put("/api/auth/password", headers=hg, json={"atual": "outra1234", "nova": "nova12345"}).status_code == 200


def test_direcao_nao_cria_administradores(client, mundo):
    mundo.gestor.perfil = Perfil.direcao
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post("/api/utilizadores", headers=h, json={"nome": "X", "email": "x@t.pt", "perfil": "administrador", "password": "segura123"})
    assert r.status_code == 403
