"""Documentação: tipos, requisitos, estado, renovação, anexos e alertas no planeamento."""
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Auditoria, DocumentoColaborador
from app.services import operacao as op
from tests.conftest import nova_linha, token

HOJE = date.today()


def _base(client, mundo):
    mundo.ines.funcao = "Promotora"
    mundo.db.commit()
    h = token(client, "g@t.pt")
    cc = client.post("/api/tipos-documento", headers=h, json={"nome": "Cartão de Cidadão", "tem_validade": True, "dias_aviso": 30}).json()
    haccp = client.post("/api/tipos-documento", headers=h, json={"nome": "Formação HACCP", "dias_aviso": 60}).json()
    rc = client.post("/api/tipos-documento", headers=h, json={"nome": "Registo criminal"}).json()
    assert client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": cc["id"]}).status_code == 201
    assert client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": haccp["id"], "funcao": "promotora"}).status_code == 201
    assert client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": rc["id"], "cliente_id": mundo.cliente.id}).status_code == 201
    assert client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": cc["id"]}).status_code == 409
    return h, cc, haccp, rc


def _linha_da_ines(mundo):
    ln = nova_linha(mundo, [2, 2, 2, 2, 2, 0, 0], inicio=HOJE - timedelta(days=HOJE.weekday()))
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, ln.inicio)
    op.gerar_ocorrencias(mundo.db, ln, ate=HOJE + timedelta(days=14))
    mundo.db.commit()
    return ln


def test_situacao_documental_requisitos_e_estados(client, mundo):
    h, cc, haccp, rc = _base(client, mundo)
    sit = {(x["colaborador"], x["tipo"]): x for x in client.get("/api/documentos", headers=h).json()["linhas"]}
    assert sit[("Inês", "Cartão de Cidadão")]["estado"] == "em_falta"
    assert sit[("Inês", "Formação HACCP")]["motivo"] == "função promotora"
    assert ("Pedro", "Formação HACCP") not in sit                       # Pedro não é promotor
    assert ("Inês", "Registo criminal") not in sit                      # ainda não trabalha para o cliente
    _linha_da_ines(mundo)
    sit = {(x["colaborador"], x["tipo"]): x for x in client.get("/api/documentos", headers=h).json()["linhas"]}
    assert sit[("Inês", "Registo criminal")]["motivo"] == "cliente Bom Grão Cafés"
    # registar: validade obrigatória quando o tipo tem validade
    url = f"/api/colaboradores/{mundo.ines.id}/documentos"
    assert client.post(url, headers=h, data={"tipo_documento_id": cc["id"]}).status_code == 422
    r = client.post(url, headers=h, data={"tipo_documento_id": cc["id"], "numero": "12345678",
                                          "validade": (HOJE + timedelta(days=10)).isoformat()})
    assert r.status_code == 201
    r = client.post(url, headers=h, data={"tipo_documento_id": haccp["id"], "validade": (HOJE - timedelta(days=1)).isoformat()})
    assert r.status_code == 201
    d = client.get(f"/api/colaboradores/{mundo.ines.id}/documentos", headers=h).json()
    est = {x["tipo"]: x["estado"] for x in d["linhas"]}
    assert est == {"Cartão de Cidadão": "a_expirar", "Formação HACCP": "expirado", "Registo criminal": "em_falta"}
    assert d["resumo"]["expirados"] == 1 and d["resumo"]["em_falta"] == 1 and d["resumo"]["a_expirar"] == 1
    # renovar: o anterior passa ao histórico
    client.post(url, headers=h, data={"tipo_documento_id": haccp["id"], "validade": (HOJE + timedelta(days=400)).isoformat()})
    d = client.get(f"/api/colaboradores/{mundo.ines.id}/documentos", headers=h).json()
    assert {x["tipo"]: x["estado"] for x in d["linhas"]}["Formação HACCP"] == "valido"
    assert len(d["historico"]) == 1


def test_alerta_no_planeamento_e_nos_candidatos(client, mundo):
    h, cc, haccp, rc = _base(client, mundo)
    _linha_da_ines(mundo)
    seg = HOJE - timedelta(days=HOJE.weekday())
    v = client.get("/api/planeamento", headers=h, params={"inicio": seg.isoformat()}).json()
    o = next(x for x in v["ocorrencias"] if x["colaborador_id"] == mundo.ines.id)
    assert "documentacao" in o["alertas"] and "Registo criminal em falta" in o["documentacao"]
    assert v["resumo"]["documentacao"] >= 1
    ines = next(c for c in v["colaboradores"] if c["id"] == mundo.ines.id)
    assert any(a.startswith("Documentação:") for a in ines["alertas"])
    cand = client.get(f"/api/ocorrencias/{o['id']}/candidatos", headers=h).json()
    pedro = next(c for c in cand if c["colaborador_id"] == mundo.pedro.id)
    assert "Documentação: Registo criminal em falta" in pedro["alertas"]   # aviso, não impede
    d = client.get("/api/dashboard/operacional", headers=h).json()
    assert d["documentacao"]["em_falta"] >= 3


def test_anexo_guardado_descarregado_com_registo_e_ambito(client, mundo):
    h, cc, haccp, rc = _base(client, mundo)
    url = f"/api/colaboradores/{mundo.ines.id}/documentos"
    pdf = b"%PDF-1.4 teste"
    r = client.post(url, headers=h, data={"tipo_documento_id": cc["id"], "validade": "2030-01-01"},
                    files={"ficheiro": ("cc.pdf", pdf, "application/pdf")})
    assert r.status_code == 201 and r.json()["ficheiro_nome"] == "cc.pdf"
    did = r.json()["id"]
    r = client.post(url, headers=h, data={"tipo_documento_id": rc["id"], "validade": "2030-01-01"},
                    files={"ficheiro": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422
    r = client.get(f"/api/documentos/{did}/ficheiro", headers=h)
    assert r.status_code == 200 and r.content == pdf
    assert mundo.db.scalar(select(Auditoria).where(Auditoria.entidade == "documento_colaborador", Auditoria.acao == "descarregar"))
    # supervisor de outra zona: não vê nem descarrega
    hs2 = token(client, "s2@t.pt")
    assert client.get(f"/api/documentos/{did}/ficheiro", headers=hs2).status_code == 404
    assert all(x["colaborador_id"] != mundo.ines.id for x in client.get("/api/documentos", headers=hs2).json()["linhas"])
    # o supervisor da zona regista documentos, mas não configura tipos
    hs1 = token(client, "s1@t.pt")
    assert client.post("/api/tipos-documento", headers=hs1, json={"nome": "X"}).status_code == 403
    assert client.post(f"/api/colaboradores/{mundo.pedro.id}/documentos", headers=hs1,
                       data={"tipo_documento_id": cc["id"], "validade": "2030-01-01"}).status_code == 201
    assert mundo.db.scalar(select(DocumentoColaborador).where(DocumentoColaborador.colaborador_id == mundo.pedro.id))


def test_editar_requisito(client, mundo):
    from app.models import TipoDocumento
    t1, t2 = TipoDocumento(tenant_id=mundo.t.id, nome="HACCP"), TipoDocumento(tenant_id=mundo.t.id, nome="Registo criminal")
    mundo.db.add_all([t1, t2])
    mundo.db.commit()
    h = token(client, "g@t.pt")
    a = client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": t1.id}).json()
    b = client.post("/api/requisitos-documentais", headers=h, json={"tipo_documento_id": t2.id}).json()
    r = client.put(f"/api/requisitos-documentais/{a['id']}", headers=h, json={"tipo_documento_id": t1.id, "cliente_id": mundo.cliente.id})
    assert r.status_code == 200 and r.json()["cliente"] == "Bom Grão Cafés"
    # não pode ficar igual a outro requisito existente
    assert client.put(f"/api/requisitos-documentais/{a['id']}", headers=h, json={"tipo_documento_id": t2.id}).status_code == 409
    assert b["id"]
