from datetime import date

from app.models import Cliente, EstadoContrato, Loja
from app.services import importacao as imp
from app.services import operacao as op
from tests.conftest import nova_linha, token
from tests.test_importacao import xlsx


def test_cliente_ficha_completa_e_edicao(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    body = {"nome": "Doce Lar", "nif": "509000111", "codigo_erp": 1400, "morada": "Rua A, 1", "codigo_postal": "1000-001",
            "localidade": "Lisboa", "telefone": "210000000", "email": "geral@docelar.pt", "url": "https://docelar.pt",
            "contacto_nome": "Paulo Reis", "gestor_conta_id": mundo.gc.id, "observacoes": "Cliente novo", "marcas": ["Doce Lar"]}
    r = client.post("/api/clientes", headers=h, json=body)
    assert r.status_code == 201 and r.json()["gestor_conta"]["nome"] == "Joana Pires" and r.json()["ativo"]
    cid = r.json()["id"]
    assert client.post("/api/clientes", headers=h, json=body).status_code == 409
    r = client.put(f"/api/clientes/{cid}", headers=h, json={**body, "telefone": "219999999", "marcas": ["Doce Lar", "Lar Kids"]})
    assert r.json()["telefone"] == "219999999" and [m["nome"] for m in r.json()["marcas"]] == ["Doce Lar", "Lar Kids"]


def test_desativar_cliente_bloqueado_com_contratos_e_reativar(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    cid = mundo.cliente.id
    r = client.post(f"/api/clientes/{cid}/estado", headers=h, json={"ativo": False})
    assert r.status_code == 422 and "contrato" in r.json()["detail"]
    mundo.contrato.estado = EstadoContrato.terminado
    mundo.db.commit()
    assert client.post(f"/api/clientes/{cid}/estado", headers=h, json={"ativo": False}).json()["ativo"] is False
    assert cid not in [c["id"] for c in client.get("/api/clientes", headers=h).json()]
    assert cid in [c["id"] for c in client.get("/api/clientes", headers=h, params={"inativos": True}).json()]
    assert mundo.db.get(Cliente, cid) is not None  # nunca é apagado
    assert client.post(f"/api/clientes/{cid}/estado", headers=h, json={"ativo": True}).json()["ativo"] is True


def test_desativar_loja_e_colaborador_bloqueados_em_uso(client, mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, date(2026, 11, 2))
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post(f"/api/lojas/{mundo.loja.id}/estado", headers=h, json={"ativo": False})
    assert r.status_code == 422 and "linha" in r.json()["detail"]
    r = client.post(f"/api/colaboradores/{mundo.ines.id}/estado", headers=h, json={"ativo": False})
    assert r.status_code == 422 and "afeto" in r.json()["detail"]
    # sem uso: desativa e sai das listas
    assert client.post(f"/api/lojas/{mundo.loja2.id}/estado", headers=h, json={"ativo": False}).json()["ativo"] is False
    assert mundo.loja2.id not in [x["id"] for x in client.get("/api/lojas", headers=h).json()]
    assert client.post(f"/api/colaboradores/{mundo.pedro.id}/estado", headers=h, json={"ativo": False}).status_code == 200
    assert mundo.pedro.id not in [x["id"] for x in client.get("/api/colaboradores", headers=h).json()]
    assert mundo.db.get(Loja, mundo.loja2.id) is not None


def test_zonas_insignias_e_marcas_inativas(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    z = client.post("/api/zonas", headers=h, json={"nome": "Setúbal"}).json()
    assert client.post("/api/zonas", headers=h, json={"nome": "setúbal"}).status_code == 409
    assert client.put(f"/api/zonas/{z['id']}", headers=h, json={"nome": "Setúbal e Palmela"}).json()["nome"] == "Setúbal e Palmela"
    client.post(f"/api/zonas/{z['id']}/estado", headers=h, json={"ativo": False})
    assert z["id"] not in [x["id"] for x in client.get("/api/zonas", headers=h).json()]
    assert z["id"] in [x["id"] for x in client.get("/api/zonas", headers=h, params={"inativos": True}).json()]
    i = client.post("/api/insignias", headers=h, json={"nome": "Mercadona"}).json()
    assert client.post(f"/api/insignias/{i['id']}/estado", headers=h, json={"ativo": False}).json()["ativo"] is False
    c = client.post("/api/clientes", headers=h, json={"nome": "Marca Teste", "marcas": ["A", "B"]}).json()
    mid = c["marcas"][0]["id"]
    assert client.post(f"/api/marcas/{mid}/estado", headers=h, json={"ativo": False}).json()["ativo"] is False


def test_importacao_aceita_cabecalho_antigo_codigo_phc(mundo):
    conteudo = xlsx(["Nome", "Código PHC", "Gestor de conta"], [["Novo Cliente", 1500, "joana pires"]])
    imp.importar(mundo.db, mundo.gestor, "clientes", conteudo, True)
    c = mundo.db.query(Cliente).filter_by(nome="Novo Cliente").one()
    assert c.codigo_erp == 1500 and c.gestor_conta_id == mundo.gc.id


def test_funcoes_tabela_unica_e_renomear_propaga(client, mundo):
    from app.models import Colaborador, Funcao, RequisitoDocumental, TipoDocumento
    mundo.db.add(Funcao(tenant_id=mundo.t.id, nome="Promotor(a)"))
    tipo = TipoDocumento(tenant_id=mundo.t.id, nome="HACCP")
    mundo.db.add(tipo)
    mundo.db.commit()
    h = token(client, "g@t.pt")
    body = {"numero": "77", "nome": "Nova", "vinculo": "a_termo", "funcao": "PROMOTOR(A)"}
    assert client.post("/api/colaboradores", headers=h, json=body).json()["funcao"] == "Promotor(a)"
    r = client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": tipo.id, "funcao": "promotor(a)"})
    assert r.status_code == 201
    assert client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": tipo.id, "funcao": "Promotor(a)"}).status_code == 409
    fid = next(f["id"] for f in client.get("/api/funcoes", headers=h).json() if f["nome"] == "Promotor(a)")
    assert client.put(f"/api/funcoes/{fid}", headers=h, json={"nome": "Promotor de vendas"}).status_code == 200
    mundo.db.expire_all()
    assert mundo.db.query(Colaborador).filter_by(numero="77").one().funcao == "Promotor de vendas"
    assert mundo.db.query(RequisitoDocumental).one().funcao == "Promotor de vendas"


def test_marcas_lista_completa_logotipo_e_codigo_erp_da_loja(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    c = client.post("/api/clientes", headers=h, json={"nome": "Doce Lar", "marcas": ["A", "B"]}).json()
    base = {k: c[k] for k in ("nome",)}
    r = client.put(f"/api/clientes/{c['id']}", headers=h, json={**base, "marcas": ["B", "C"]}).json()
    assert {m["nome"]: m["ativo"] for m in r["marcas"]} == {"A": False, "B": True, "C": True}
    r = client.put(f"/api/clientes/{c['id']}", headers=h, json={**base, "marcas": ["A", "B", "C"]}).json()
    assert all(m["ativo"] for m in r["marcas"])
    # logótipo da insígnia: carregar, servir sem sessão, aparecer nas lojas
    i = client.post("/api/insignias", headers=h, json={"nome": "Continente"}).json()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    r = client.post(f"/api/insignias/{i['id']}/logo", headers=h, files={"ficheiro": ("logo.png", png, "image/png")})
    assert r.status_code == 200 and r.json()["logo_v"] == 1
    assert client.post(f"/api/insignias/{i['id']}/logo", headers=h, files={"ficheiro": ("x.txt", b"x", "text/plain")}).status_code == 422
    assert client.get(f"/api/insignias/{i['id']}/logo").content == png
    lj = client.post("/api/lojas", headers=h, json={"nome": "Continente Benfica", "codigo_erp": "L0999", "insignia_id": i["id"]}).json()
    assert lj["codigo_erp"] == "L0999" and lj["insignia"]["logo_v"] == 1
    assert [x["nome"] for x in client.get("/api/lojas", headers=h, params={"q": "l0999"}).json()] == ["Continente Benfica"]


def test_colaborador_datas_laborais_e_muito_curta_duracao(client, mundo):
    from app.models import Colaborador
    mundo.db.commit()
    h = token(client, "g@t.pt")
    body = {"numero": "88", "nome": "Vera", "vinculo": "a_termo", "muito_curta_duracao": True,
            "data_admissao": "2026-10-01", "data_saida": None, "data_inicio": "2026-10-01", "data_fim_vinculo": "2026-11-04"}
    r = client.post("/api/colaboradores", headers=h, json=body)
    assert r.status_code == 201 and r.json()["muito_curta_duracao"] and r.json()["data_admissao"] == "2026-10-01"
    cid = r.json()["id"]
    assert [c["id"] for c in client.get("/api/colaboradores", headers=h, params={"vinculo": "muito_curta_duracao"}).json()] == [cid]
    # datas incoerentes e muito curta duração sem termo são recusadas
    assert client.put(f"/api/colaboradores/{cid}", headers=h, json={**body, "data_saida": "2026-09-01"}).status_code == 422
    assert client.put(f"/api/colaboradores/{cid}", headers=h, json={**body, "data_fim_vinculo": "2026-09-01"}).status_code == 422
    assert client.put(f"/api/colaboradores/{cid}", headers=h, json={**body, "vinculo": "sem_termo"}).status_code == 422
    # recibos verdes: sem datas laborais nem tipo de contrato
    r = client.put(f"/api/colaboradores/{cid}", headers=h, json={**body, "vinculo": "recibos_verdes"})
    assert r.status_code == 200
    mundo.db.expire_all()
    c = mundo.db.get(Colaborador, cid)
    assert not c.muito_curta_duracao and c.data_admissao is None and c.data_inicio is None and c.data_fim_vinculo is None
    assert client.post("/api/colaboradores", headers=h, json={**body, "numero": "89", "vinculo": "muito_curta_duracao"}).status_code == 422


def test_saida_passada_desativa_e_bloqueia_reativar(client, mundo):
    from datetime import timedelta
    mundo.db.commit()
    h = token(client, "g@t.pt")
    cid = mundo.outro.id
    body = client.get(f"/api/colaboradores/{cid}", headers=h).json()
    ontem = (date.today() - timedelta(days=1)).isoformat()
    r = client.put(f"/api/colaboradores/{cid}", headers=h, json={**body, "data_admissao": "2025-01-01", "data_saida": ontem})
    assert r.status_code == 200 and r.json()["ativo"] is False and "desativado" in r.json()["aviso"]
    assert client.post(f"/api/colaboradores/{cid}/estado", headers=h, json={"ativo": True}).status_code == 422
    r = client.put(f"/api/colaboradores/{cid}", headers=h, json={**r.json(), "data_saida": None})
    assert client.post(f"/api/colaboradores/{cid}/estado", headers=h, json={"ativo": True}).json()["ativo"] is True
