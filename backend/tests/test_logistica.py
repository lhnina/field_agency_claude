"""Logística: viaturas, serviços, atribuição com conflitos, execução com custos, validação e pré-faturação."""
from datetime import date, timedelta


from app.models import Contrato, EstadoContrato, TipoContrato
from tests.conftest import token

HOJE = date.today()


def _contrato(m, ativo=True) -> Contrato:
    c = Contrato(tenant_id=m.t.id, numero="CT-LOG-2026/0001", tipo=TipoContrato.LOG, cliente_id=m.cliente.id,
                 data=HOJE - timedelta(days=60), inicio=HOJE - timedelta(days=60), fim=HOJE + timedelta(days=60),
                 estado=EstadoContrato.ativo if ativo else EstadoContrato.proposta)
    m.db.add(c)
    m.db.commit()
    return c


def _viatura(client, h, mat="AA-12-BC", custo="0.30"):
    r = client.post("/api/viaturas", headers=h, json={"matricula": mat, "descricao": "Carrinha", "custo_km": custo})
    assert r.status_code == 201, r.text
    return r.json()


def test_viaturas(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    v = _viatura(client, h, "aa 12 bc")
    assert v["matricula"] == "AA-12-BC"
    assert client.post("/api/viaturas", headers=h, json={"matricula": "AA-12-BC"}).status_code == 409
    assert client.put(f"/api/viaturas/{v['id']}", headers=h, json={"matricula": "AA-12-BC", "custo_km": "0.35"}).json()["custo_km"] == 0.35


def test_fluxo_servico_logistico(client, mundo):
    c = _contrato(mundo)
    h = token(client, "g@t.pt")
    v = _viatura(client, h)
    ontem = (HOJE - timedelta(days=1)).isoformat()
    base = {"loja_id": mundo.loja.id, "tipo": "entrega_implementacao", "data": ontem, "hora_inicio": "09:00", "hora_fim": "12:00",
            "materiais": "2 expositores", "preco": "150.00"}
    # fora da vigência e janela inválida
    assert client.post(f"/api/contratos/{c.id}/servicos", headers=h, json={**base, "data": "2020-01-01"}).status_code == 422
    assert client.post(f"/api/contratos/{c.id}/servicos", headers=h, json={**base, "hora_fim": "08:00"}).status_code == 422
    s = client.post(f"/api/contratos/{c.id}/servicos", headers=h, json=base).json()
    assert s["estado"] == "planeado" and s["tipo_label"] == "Entrega + Implementação"
    s2 = client.post(f"/api/contratos/{c.id}/servicos", headers=h, json={**base, "loja_id": mundo.loja2.id, "hora_inicio": "11:00", "hora_fim": "13:00"}).json()
    # sem viatura/motorista não se regista a execução
    assert client.post(f"/api/servicos-logisticos/{s['id']}/execucao", headers=h, data={"km_partida": "1"}).status_code == 422
    # atribuição: com viatura e motorista fica "atribuído"; a mesma viatura à mesma hora gera alerta
    r = client.put(f"/api/servicos-logisticos/{s['id']}/atribuicao", headers=h,
                   json={"viatura_id": v["id"], "colaborador_id": mundo.ines.id, "ajudante_id": mundo.pedro.id}).json()
    assert r["estado"] == "atribuido"
    r2 = client.put(f"/api/servicos-logisticos/{s2['id']}/atribuicao", headers=h, json={"viatura_id": v["id"], "colaborador_id": mundo.outro.id}).json()
    assert "Viatura com outro serviço à mesma hora" in r2["alertas"]
    cand = client.get(f"/api/servicos-logisticos/{s2['id']}/candidatos", headers=h).json()
    assert next(x for x in cand["viaturas"] if x["id"] == v["id"])["conflito"] is True
    # execução: km 100→160 (60 km × 0,30 = 18 €), portagens 4,50, 3 h × (11,40 + 11,90) = 69,90 → 92,40 €
    assert client.post(f"/api/servicos-logisticos/{s['id']}/execucao", headers=h,
                       data={"km_partida": "160", "km_chegada": "100"}).status_code == 422
    r = client.post(f"/api/servicos-logisticos/{s['id']}/execucao", headers=h,
                    data={"km_partida": "100", "km_chegada": "160", "portagens": "4,50", "inicio_real": "09:00", "fim_real": "12:00"},
                    files={"comprovativo": ("guia.pdf", b"%PDF-1.4 x", "application/pdf")}).json()
    assert r["estado"] == "executado" and r["custos"]["km"] == 60 and r["custos"]["total"] == 92.4 and r["margem"] == 57.6
    assert client.get(f"/api/servicos-logisticos/{s['id']}/comprovativo", headers=h).content.startswith(b"%PDF")
    # pré-faturação: o executado fatura; o atribuído aparece sem valor
    pf = client.get("/api/prefaturacao", headers=h, params={"mes": HOJE.strftime("%Y-%m") if ontem[:7] == HOJE.strftime("%Y-%m") else ontem[:7], "area": "LOG"}).json()
    linhas = pf["clientes"][0]["contratos"][0]["linhas"]
    assert {(ln["estado"], ln["valor"]) for ln in linhas} == {("executado", 150.0), ("atribuido", 0.0)}
    assert pf["totais"]["pendentes"] == 1 and pf["totais"]["por_executar"] == 1
    # validar; depois de validado não se altera nem cancela
    assert client.post("/api/servicos-logisticos/validar", headers=h, json={"ids": [s["id"]]}).json()["processados"] == 1
    assert client.put(f"/api/servicos-logisticos/{s['id']}", headers=h, json=base).status_code == 422
    assert client.post(f"/api/servicos-logisticos/{s['id']}/cancelar", headers=h, json={"motivo": "teste"}).status_code == 422
    # cancelar o outro; o contrato soma só os não cancelados
    assert client.post(f"/api/servicos-logisticos/{s2['id']}/cancelar", headers=h, json={"motivo": "Loja fechada"}).json()["ok"]
    resumo = next(x for x in client.get("/api/contratos", headers=h).json() if x["id"] == c.id)
    assert resumo["n_linhas"] == 1 and float(resumo["valor_mensal"]) == 150.0
    # apuramento: horas validadas do motorista e do ajudante
    ap = client.get("/api/apuramento", headers=h, params={"mes": ontem[:7]}).json()
    horas = {x["nome"]: x["horas"] for x in ap["colaboradores"]}
    assert horas.get("Inês") == 3.0 and horas.get("Pedro") == 3.0


def test_ativar_contrato_log_exige_servicos_e_ambitos(client, mundo):
    c = _contrato(mundo, ativo=False)
    h = token(client, "g@t.pt")
    r = client.post(f"/api/contratos/{c.id}/estado", headers=h, json={"estado": "ativo"})
    assert r.status_code == 422 and "sem serviços" in r.text
    amanha = (HOJE + timedelta(days=1)).isoformat()
    client.post(f"/api/contratos/{c.id}/servicos", headers=h, json={"loja_id": mundo.loja.id, "tipo": "entrega", "data": amanha})
    assert client.post(f"/api/contratos/{c.id}/estado", headers=h, json={"estado": "ativo"}).status_code == 200
    lista = client.get("/api/logistica/servicos", headers=h, params={"inicio": HOJE.isoformat(), "fim": amanha}).json()
    assert lista["resumo"]["por_atribuir"] == 1 and lista["itens"][0]["alertas"] == ["Sem viatura", "Sem motorista"]
    # supervisor de outra zona não vê; gestor de conta sem o cliente não vê
    assert client.get("/api/logistica/servicos", headers=token(client, "s2@t.pt"), params={"inicio": HOJE.isoformat(), "fim": amanha}).json()["itens"] == []
    assert client.get("/api/logistica/servicos", headers=token(client, "s1@t.pt"), params={"inicio": HOJE.isoformat(), "fim": amanha}).json()["resumo"]["total"] == 1
    assert client.get("/api/logistica/servicos", headers=token(client, "gc@t.pt"), params={"inicio": HOJE.isoformat(), "fim": amanha}).json()["itens"] == []



def test_importar_pedidos_de_logistica(mundo):
    from app.services import importacao as imp
    from tests.test_importacao import xlsx
    c = _contrato(mundo)
    mundo.loja.codigo_erp = "L0457"
    mundo.db.flush()
    d = (HOJE + timedelta(days=3)).strftime("%d/%m/%Y")
    cab = ["Referência ERP", "Contrato", "Loja", "Serviço", "Data", "Hora início", "Hora fim", "Materiais", "Preço"]
    linhas = [["GT-1", c.numero, "l0457", "Entrega + Implementação", d, "09:00", "11:00", "2 expositores", 120],
              ["GT-2", c.numero, "Loja que não existe", "Entrega", d, None, None, None, 50],
              ["GT-3", c.numero, "Pingo Doce Alfragide", "Teleporte", d, None, None, None, 50]]
    r = imp.importar(mundo.db, mundo.gestor, "logistica", xlsx(cab, linhas), False)
    assert r["resumo"]["com_erros"] == 2
    r = imp.importar(mundo.db, mundo.gestor, "logistica", xlsx(cab, linhas[:1]), True)
    assert r["importado"] and r["resumo"]["criar"] == 1
    # o mesmo pedido outra vez: atualiza em vez de duplicar
    linhas[0][8] = 135
    r = imp.importar(mundo.db, mundo.gestor, "logistica", xlsx(cab, linhas[:1]), True)
    assert r["resumo"]["atualizar"] == 1
    from app.models import ServicoLogistico
    s = mundo.db.query(ServicoLogistico).one()
    assert float(s.preco) == 135 and s.hora_inicio == "09:00" and s.tipo.value == "entrega_implementacao"
