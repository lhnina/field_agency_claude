"""Perfil Gestor de conta: acessos do gestor operacional, mas só nos seus clientes."""
from datetime import date

from app.models import Cliente, Contrato, EstadoContrato, TipoContrato
from app.services import operacao as op
from tests.conftest import nova_linha, token


def _dois_clientes(m):
    """Cliente 1 (Bom Grão, da Joana) e cliente 2 (sem gestor de conta), cada um com uma linha afetada."""
    m.cliente.gestor_conta_id = m.gc.id
    outro = Cliente(tenant_id=m.t.id, nome="Atlântico Conservas")
    m.db.add(outro)
    m.db.flush()
    c2 = Contrato(tenant_id=m.t.id, numero="CT-REP-2026/0002", tipo=TipoContrato.REP, cliente_id=outro.id,
                  data=date(2026, 1, 1), inicio=date(2026, 1, 1), estado=EstadoContrato.ativo)
    m.db.add(c2)
    m.db.flush()
    ln1 = nova_linha(m, [2, 0, 0, 0, 0, 0, 0])
    op.afetar(m.db, m.gestor, ln1, m.ines, date(2026, 11, 2))
    op.gerar_ocorrencias(m.db, ln1, ate=date(2026, 11, 30))
    m.contrato = c2
    ln2 = nova_linha(m, [0, 3, 0, 0, 0, 0, 0], loja=m.loja2)
    op.afetar(m.db, m.gestor, ln2, m.pedro, date(2026, 11, 2))
    op.gerar_ocorrencias(m.db, ln2, ate=date(2026, 11, 30))
    m.db.commit()
    return outro, c2, ln2


def test_gestor_conta_so_ve_os_seus_clientes(client, mundo):
    outro, c2, ln2 = _dois_clientes(mundo)
    h = token(client, "gc@t.pt")
    assert [c["nome"] for c in client.get("/api/clientes", headers=h).json()] == ["Bom Grão Cafés"]
    assert client.get(f"/api/clientes/{outro.id}", headers=h).status_code == 404
    assert [c["numero"] for c in client.get("/api/contratos", headers=h).json()] == ["CT-REP-2026/0001"]
    assert client.get(f"/api/contratos/{c2.id}", headers=h).status_code == 404
    assert client.put(f"/api/linhas/{ln2.id}", headers=h, json={}).status_code in (404, 422)
    pl = client.get("/api/planeamento", headers=h, params={"inicio": "2026-11-02"}).json()
    lojas = {o["loja"] for o in pl["ocorrencias"] + pl["por_atribuir"]}
    assert lojas == {"Continente Amadora"}
    assert [c["nome"] for c in pl["colaboradores"]] == ["Inês"]
    pf = client.get("/api/prefaturacao", headers=h, params={"mes": "2026-11"}).json()
    assert [c["cliente"] for c in pf["clientes"]] == ["Bom Grão Cafés"]
    # o gestor operacional continua a ver tudo
    hg = token(client, "g@t.pt")
    assert len(client.get("/api/contratos", headers=hg).json()) == 2


def test_gestor_conta_fica_gestor_dos_clientes_que_cria(client, mundo):
    mundo.db.commit()
    h = token(client, "gc@t.pt")
    r = client.post("/api/clientes", headers=h, json={"nome": "Cliente Novo", "gestor_conta_id": None, "marcas": []})
    assert r.status_code == 201 and r.json()["gestor_conta"]["id"] == mundo.gc.id
    hg = token(client, "g@t.pt")
    assert [u["nome"] for u in client.get("/api/utilizadores/gestores-conta", headers=hg).json()] == ["Joana Pires"]
    r = client.post("/api/clientes", headers=hg, json={"nome": "Outro", "gestor_conta_id": mundo.sup1.id, "marcas": []})
    assert r.status_code == 422
