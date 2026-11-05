"""Equipas Fixas: rotas, escala, geração dos dias, faltas/substituições, validação, pré-faturação, apuramento e fecho."""
from datetime import date, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from app.models import Perfil, ServicoEquipa, TipoVinculo, User
from app.security import hash_password
from app.services import operacao as op
from tests.conftest import token

HOJE = date.today()
MES_ANT = (HOJE.replace(day=1) - timedelta(days=1)).replace(day=1)
ESCALA = lambda rota: [{"dia": d, "rota_id": rota, "hora_inicio": "09:00", "hora_fim": "18:00", "pausa_min": 60} for d in range(5)]  # noqa: E731


def _montar(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    r = client.post("/api/contratos", headers=h, json={
        "tipo": "EQF", "cliente_id": mundo.cliente.id, "data": MES_ANT.isoformat(), "inicio": MES_ANT.isoformat(),
        "descricao": "Equipa fixa · merchandisers", "valor_gestao": "300", "acrescimo_despesas_pct": "10"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["valor_gestao"] == "300.00" or float(c["valor_gestao"]) == 300
    rota = client.post(f"/api/contratos/{c['id']}/rotas", headers=h,
                       json={"nome": "Rota Amadora", "lojas": [mundo.loja.id, mundo.loja2.id]})
    assert rota.status_code == 201, rota.text
    return h, c, rota.json()


def test_equipa_fixa_fluxo_completo(client, mundo):
    h, c, rota = _montar(client, mundo)
    cid = c["id"]
    assert [x["nome"] for x in rota["lojas"]] == ["Continente Amadora", "Pingo Doce Alfragide"]
    # sem colaboradores com escala não passa a Em curso
    assert client.post(f"/api/contratos/{cid}/estado", headers=h, json={"estado": "ativo"}).status_code == 422
    # prestador não pode entrar; colaborador com escala de seg a sex, 8 h/dia
    mundo.outro.vinculo = TipoVinculo.recibos_verdes
    mundo.db.commit()
    assert client.post(f"/api/contratos/{cid}/elementos", headers=h,
                       json={"colaborador_id": mundo.outro.id, "desde": MES_ANT.isoformat(), "escala": ESCALA(rota["id"])}).status_code == 422
    el = client.post(f"/api/contratos/{cid}/elementos", headers=h,
                     json={"colaborador_id": mundo.ines.id, "desde": MES_ANT.isoformat(), "escala": ESCALA(rota["id"])})
    assert el.status_code == 201, el.text
    assert el.json()["horas_semana"] == 40.0
    assert client.post(f"/api/contratos/{cid}/elementos", headers=h,
                       json={"colaborador_id": mundo.ines.id, "desde": MES_ANT.isoformat(), "escala": []}).status_code == 409
    r = client.post(f"/api/contratos/{cid}/estado", headers=h, json={"estado": "ativo"})
    assert r.status_code == 200, r.text
    assert r.json()["n_linhas"] == 1 and float(r.json()["horas_semana"]) == 40
    # dias gerados a partir do início do contrato, só em dias úteis
    servs = mundo.db.scalars(select(ServicoEquipa).where(ServicoEquipa.contrato_id == cid).order_by(ServicoEquipa.data)).all()
    assert servs and all(s.data.weekday() < 5 for s in servs) and servs[0].data >= MES_ANT
    # semana: aparece com a rota e o horário
    seg = HOJE - timedelta(days=HOJE.weekday())
    sem = client.get("/api/equipas/semana", headers=h, params={"inicio": seg.isoformat()}).json()
    assert sem["linhas"][0]["colaborador"] == "Inês" and sem["resumo"]["elementos"] == 1
    dia = next(iter(sem["linhas"][0]["dias"].values()))
    assert dia["rota"] == "Rota Amadora" and dia["horas_planeadas"] == 8.0
    # os dias da equipa contam nas horas do colaborador (planeamento e candidatos)
    assert op.horas_colaborador_dia(mundo.db, mundo.t.id, seg, seg + timedelta(days=6))[(mundo.ines.id, date.fromisoformat(dia["data"]))] == D("8.00")

    # mês anterior: uma substituição, uma falta e o resto validado
    ant = [s for s in servs if s.data < HOJE.replace(day=1)]
    sub, falta, resto = ant[0], ant[1], ant[2:]
    r = client.put(f"/api/servicos-equipa/{sub.id}", headers=h, json={"colaborador_id": mundo.pedro.id, "hora_inicio": "09:00",
                                                                     "hora_fim": "14:00", "pausa_min": 0})
    assert r.json()["substituicao"] and r.json()["horas_planeadas"] == 5.0
    assert client.post(f"/api/servicos-equipa/{falta.id}/falta", headers=h, json={"motivo": "Doença"}).json()["estado"] == "falta"
    # fecho bloqueado com dias por validar
    mundo.db.add(User(tenant_id=mundo.t.id, email="f@t.pt", nome="Fin", password_hash=hash_password("x"), perfil=Perfil.financeiro))
    mundo.db.commit()
    hf = token(client, "f@t.pt")
    r = client.post("/api/periodos/fechar", headers=hf, json={"tipo": "faturacao", "mes": MES_ANT.isoformat()[:7], "area": "EQF"})
    assert r.status_code == 422 and "por validar" in r.json()["detail"]
    v = client.post("/api/servicos-equipa/validar", headers=h, json={"ids": [sub.id] + [s.id for s in resto]}).json()
    assert v["validados"] == 1 + len(resto)
    # despesas: 100 € refaturados com 10 % = 110 €; 20 € só custo
    assert client.post(f"/api/contratos/{cid}/despesas", headers=h, json={"data": MES_ANT.isoformat(), "tipo": "combustivel",
                                                                          "valor": "100", "refaturar": True}).status_code == 201
    d2 = client.post(f"/api/contratos/{cid}/despesas", headers=h, json={"data": MES_ANT.isoformat(), "tipo": "telemovel",
                                                                        "valor": "20", "refaturar": False}).json()
    assert client.post(f"/api/contratos/{cid}/despesas", headers=h, json={"data": MES_ANT.isoformat(), "tipo": "xpto",
                                                                          "valor": "1"}).status_code == 422
    desp = client.get(f"/api/contratos/{cid}/despesas", headers=h, params={"mes": MES_ANT.isoformat()}).json()
    assert desp["totais"] == {"custo": 120.0, "refaturado": 110.0}

    # pré-faturação: custo real (horas validadas da Inês × 11,40 + 5 h do Pedro × 11,90) + gestão 300 + despesas 110
    p = client.get("/api/prefaturacao", headers=h, params={"mes": MES_ANT.isoformat()[:7], "area": "EQF"}).json()
    linhas = p["clientes"][0]["contratos"][0]["linhas"]
    el_l = next(x for x in linhas if x["tipo"] == "elemento")
    horas_ines = 8 * len(resto)
    custo = round(horas_ines * 11.40 + 5 * 11.90, 2)
    assert el_l["gestao"] == 300.0 and el_l["faltas"] == 1 and el_l["pendentes_validacao"] == 0
    assert abs(el_l["custo"] - custo) < 0.01 and abs(el_l["valor"] - (custo + 300)) < 0.01
    dl = next(x for x in linhas if x["tipo"] == "despesas")
    assert dl["valor"] == 110.0 and dl["custo"] == 120.0
    assert abs(p["totais"]["margem"] - (300 + 110 - 120)) < 0.01
    # apuramento: horas validadas de quem fez
    ap = client.get("/api/apuramento", headers=h, params={"mes": MES_ANT.isoformat()[:7]}).json()
    por = {x["nome"]: x for x in ap["colaboradores"]}
    assert por["Inês"]["horas"] == horas_ines and por["Pedro"]["horas"] == 5.0
    # fecha; despesas do mês fechado já não se alteram
    r = client.post("/api/periodos/fechar", headers=hf, json={"tipo": "faturacao", "mes": MES_ANT.isoformat()[:7], "area": "EQF"})
    assert r.status_code == 200, r.text
    assert client.delete(f"/api/despesas-equipa/{d2['id']}", headers=h).status_code == 422


def test_escala_regenera_futuro_e_saida(client, mundo):
    h, c, rota = _montar(client, mundo)
    cid = c["id"]
    el = client.post(f"/api/contratos/{cid}/elementos", headers=h,
                     json={"colaborador_id": mundo.ines.id, "desde": MES_ANT.isoformat(), "escala": ESCALA(rota["id"])}).json()
    client.post(f"/api/contratos/{cid}/estado", headers=h, json={"estado": "ativo"})
    # passa a trabalhar só às segundas: os dias futuros refazem-se, os passados ficam
    passados = mundo.db.scalars(select(ServicoEquipa).where(ServicoEquipa.contrato_id == cid, ServicoEquipa.data < HOJE)).all()
    r = client.put(f"/api/elementos-equipa/{el['id']}", headers=h,
                   json={"colaborador_id": mundo.ines.id, "desde": MES_ANT.isoformat(), "escala": ESCALA(rota["id"])[:1]})
    assert r.status_code == 200, r.text
    mundo.db.expire_all()
    futuros = mundo.db.scalars(select(ServicoEquipa).where(ServicoEquipa.contrato_id == cid, ServicoEquipa.data >= HOJE)).all()
    assert futuros and all(s.data.weekday() == 0 for s in futuros)
    assert len(mundo.db.scalars(select(ServicoEquipa).where(ServicoEquipa.contrato_id == cid, ServicoEquipa.data < HOJE)).all()) == len(passados)
    # rota em uso não se desativa
    assert client.post(f"/api/rotas-equipa/{rota['id']}/estado", headers=h, json={"ativo": False}).status_code == 422
    # data de saída: termina na equipa e os dias seguintes saem
    saida = HOJE + timedelta(days=3)
    body = client.get(f"/api/colaboradores/{mundo.ines.id}", headers=h).json()
    r = client.put(f"/api/colaboradores/{mundo.ines.id}", headers=h, json={**body, "data_saida": saida.isoformat()})
    assert r.status_code == 200, r.text
    mundo.db.expire_all()
    assert not mundo.db.scalars(select(ServicoEquipa).where(ServicoEquipa.contrato_id == cid, ServicoEquipa.data > saida)).all()
    eq = client.get(f"/api/contratos/{cid}/equipa", headers=h).json()
    assert eq["elementos"][0]["ate"] == saida.isoformat()


def test_supervisor_ve_equipas_da_zona(client, mundo):
    h, c, rota = _montar(client, mundo)
    client.post(f"/api/contratos/{c['id']}/elementos", headers=h,
                json={"colaborador_id": mundo.ines.id, "desde": MES_ANT.isoformat(), "escala": ESCALA(rota["id"])})
    client.post(f"/api/contratos/{c['id']}/estado", headers=h, json={"estado": "ativo"})
    seg = (HOJE - timedelta(days=HOJE.weekday())).isoformat()
    assert client.get("/api/equipas/semana", headers=token(client, "s1@t.pt"), params={"inicio": seg}).json()["linhas"]
    assert client.get("/api/equipas/semana", headers=token(client, "s2@t.pt"), params={"inicio": seg}).json()["linhas"] == []
    assert c["id"] in [x["id"] for x in client.get("/api/contratos", headers=token(client, "s1@t.pt")).json()]
