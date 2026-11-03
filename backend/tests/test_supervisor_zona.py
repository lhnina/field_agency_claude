"""Supervisor: só vê lojas e colaboradores da sua zona; sem zona (TODAS) vê tudo."""
from app.models import Loja
from tests.conftest import token


def test_supervisor_ve_so_a_sua_zona(client, mundo):
    mundo.db.add(Loja(tenant_id=mundo.t.id, nome="Continente Sintra", zona_id=mundo.zona2.id))
    mundo.db.commit()
    h1 = token(client, "s1@t.pt")
    assert {c["nome"] for c in client.get("/api/colaboradores", headers=h1).json()} == {"Inês", "Pedro"}
    assert {lj["nome"] for lj in client.get("/api/lojas", headers=h1).json()} == {"Continente Amadora", "Pingo Doce Alfragide"}
    assert client.get(f"/api/colaboradores/{mundo.outro.id}", headers=h1).status_code == 404
    assert client.get("/api/auth/me", headers=h1).json()["zona"] == "Amadora"
    # a Direção passa o supervisor 1 para TODAS as zonas
    from app.models import Perfil, User
    from app.security import hash_password
    mundo.db.add(User(tenant_id=mundo.t.id, email="d@t.pt", nome="Dir", password_hash=hash_password("x"), perfil=Perfil.direcao))
    mundo.db.commit()
    hd = token(client, "d@t.pt")
    r = client.put(f"/api/utilizadores/{mundo.sup1.id}", headers=hd,
                   json={"nome": "Sup 1", "email": "s1@t.pt", "perfil": "supervisor", "ativo": True, "zona_id": None})
    assert r.status_code == 200 and r.json()["zona"] is None
    assert len(client.get("/api/colaboradores", headers=h1).json()) == 3
    assert len(client.get("/api/lojas", headers=h1).json()) == 3
    r = client.put(f"/api/utilizadores/{mundo.sup1.id}", headers=hd,
                   json={"nome": "Sup 1", "email": "s1@t.pt", "perfil": "supervisor", "ativo": True, "zona_id": mundo.zona2.id})
    assert r.json()["zona"] == "Sintra"
    assert {c["nome"] for c in client.get("/api/colaboradores", headers=h1).json()} == {"Outra equipa"}
