from datetime import date

from tests.conftest import token


def test_login_invalido(client, mundo):
    mundo.db.commit()
    r = client.post("/api/auth/login", data={"username": "g@t.pt", "password": "errada"})
    assert r.status_code == 401


def test_fluxo_contrato_linha_afetacao_planeamento(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post("/api/contratos", headers=h, json={"tipo": "REP", "cliente_id": mundo.cliente.id, "data": "2026-10-20",
                                                       "inicio": "2026-11-02"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["numero"] == "CT-REP-2026/0002"  # já existe a 0001
    linha = {"loja_id": mundo.loja.id, "inicio": "2026-11-02", "h_seg": 1.5, "h_qua": 1.5, "preco_hora": 18}
    r = client.post(f"/api/contratos/{c['id']}/linhas", headers=h, json=linha)
    assert r.status_code == 201, r.text
    ln = r.json()["linhas"][0]
    assert ln["horas_semana"] == "3.00" and ln["valor_mensal"] == "234.00"
    r = client.post(f"/api/contratos/{c['id']}/estado", headers=h, json={"estado": "ativo"})
    assert r.status_code == 200
    r = client.post(f"/api/linhas/{ln['id']}/afetacao", headers=h, json={"colaborador_id": mundo.ines.id, "desde": "2026-11-02"})
    assert r.status_code == 200, r.text
    assert r.json()["linhas"][0]["afetacao_atual"]["colaborador_nome"] == "Inês"
    r = client.get("/api/planeamento", headers=h, params={"inicio": "2026-11-04"})
    v = r.json()
    assert v["inicio"] == "2026-11-02"
    assert len([o for o in v["ocorrencias"] if o["contrato_id"] == c["id"]]) == 2


def test_linha_sem_horas_e_rejeitada(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post(f"/api/contratos/{mundo.contrato.id}/linhas", headers=h,
                    json={"loja_id": mundo.loja.id, "inicio": "2026-11-02", "preco_hora": 18})
    assert r.status_code == 422
    assert "pelo menos um dia" in r.text


def test_supervisor_nao_edita_contratos(client, mundo):
    mundo.db.commit()
    h = token(client, "s1@t.pt")
    r = client.post("/api/contratos", headers=h, json={"tipo": "REP", "cliente_id": mundo.cliente.id, "data": "2026-10-20",
                                                       "inicio": "2026-11-02"})
    assert r.status_code == 403


def test_supervisor_nao_afeta_colaborador_de_outra_equipa(client, mundo):
    from tests.conftest import nova_linha
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    mundo.db.commit()
    h = token(client, "s1@t.pt")
    r = client.post(f"/api/linhas/{ln.id}/afetacao", headers=h, json={"colaborador_id": mundo.outro.id, "desde": str(date(2026, 11, 2))})
    assert r.status_code == 403


def test_colaboradores_carga_afetada_e_filtro_zona(client, mundo):
    from datetime import date as d_
    from app.models import Zona
    from app.services import operacao as op
    from tests.conftest import nova_linha
    hoje = d_.today()
    a = nova_linha(mundo, [1.5, 0, 1.5, 0, 0, 0, 0], inicio=hoje)
    b = nova_linha(mundo, [0, 0, 0, 3, 0, 0, 0], loja=mundo.loja2, inicio=hoje)
    for ln in (a, b):
        op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, hoje)
    outra = Zona(tenant_id=mundo.t.id, nome="Sintra")
    mundo.db.add(outra)
    mundo.db.flush()
    mundo.outro.zona_id = outra.id
    mundo.db.commit()
    h = token(client, "g@t.pt")
    lista = {c["nome"]: c for c in client.get("/api/colaboradores", headers=h).json()}
    assert float(lista["Inês"]["horas_afetadas"]) == 6.0 and float(lista["Pedro"]["horas_afetadas"]) == 0
    assert lista["Outra equipa"]["zona"]["nome"] == "Sintra"
    so_sintra = client.get("/api/colaboradores", headers=h, params={"zona_id": outra.id}).json()
    assert [c["nome"] for c in so_sintra] == ["Outra equipa"]
    af = client.get(f"/api/colaboradores/{mundo.ines.id}/afetacoes", headers=h).json()
    assert len(af) == 2 and sum(x["horas_semana"] for x in af) == 6.0
    r = client.get("/api/planeamento", headers=h, params={"colaborador_id": mundo.ines.id, "inicio": hoje.isoformat()})
    assert [c["id"] for c in r.json()["colaboradores"]] == [mundo.ines.id]
