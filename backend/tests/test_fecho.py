from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from sqlalchemy import select

from app.models import EstadoOcorrencia, Ocorrencia, OrigemExecucao, Perfil, TipoPeriodo, TipoVinculo, User
from app.security import hash_password
from app.services import fecho
from app.services import operacao as op
from tests.conftest import nova_linha, token

OUT = date(2026, 10, 1)
HOJE = date(2026, 11, 2)


def ocs(m, ln):
    return m.db.scalars(select(Ocorrencia).where(Ocorrencia.linha_id == ln.id).order_by(Ocorrencia.data)).all()


def preparar(m, horas=(2, 0, 0, 0, 0, 0, 0), inicio=OUT, colab=None):
    ln = nova_linha(m, list(horas), inicio=inicio)
    op.afetar(m.db, m.gestor, ln, colab or m.ines, inicio)
    op.gerar_ocorrencias(m.db, ln, ate=date(2026, 11, 30))
    return ln


def test_aceitacao_tacita_so_passado_e_com_colaborador(mundo):
    ln = preparar(mundo)
    sem = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0], inicio=OUT, loja=mundo.loja2)
    op.gerar_ocorrencias(mundo.db, sem, ate=date(2026, 11, 30))
    n = fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    assert n == 4  # segundas de outubro: 5, 12, 19, 26
    o = ocs(mundo, ln)[0]
    assert o.estado == EstadoOcorrencia.executado and o.origem_execucao == OrigemExecucao.tacita
    assert o.horas_executadas == o.horas_planeadas
    assert all(x.estado == EstadoOcorrencia.planeado for x in ocs(mundo, sem))
    assert fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31)) == 0


def test_aceitacao_tacita_desligada_no_tenant(mundo):
    preparar(mundo)
    mundo.t.aceitacao_tacita = False
    assert fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31)) == 0


def test_validar_e_corrigir_horas(mundo):
    ln = preparar(mundo)
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    o = ocs(mundo, ln)[0]
    fecho.registar_execucao(mundo.db, mundo.gestor, o, D("2.5"), "Extra", HOJE)
    assert o.origem_execucao == OrigemExecucao.manual
    fecho.validar(mundo.db, mundo.gestor, [o], True, None, HOJE)
    assert o.estado == EstadoOcorrencia.validado and o.horas_aprovadas == D("2.5")
    with pytest.raises(ValueError, match="motivo"):
        fecho.registar_execucao(mundo.db, mundo.gestor, o, D("2"), None, HOJE)
    fecho.registar_execucao(mundo.db, mundo.gestor, o, D("2"), "Correção", HOJE)
    assert o.estado == EstadoOcorrencia.executado and o.horas_aprovadas is None  # tem de ser revalidada


def test_nao_regista_servico_futuro(mundo):
    ln = preparar(mundo)
    futura = [o for o in ocs(mundo, ln) if o.data > HOJE][0]
    with pytest.raises(ValueError, match="futuro"):
        fecho.registar_execucao(mundo.db, mundo.gestor, futura, D("2"), None, HOJE)
    assert fecho.validar(mundo.db, mundo.gestor, [futura], True, None, HOJE)["erros"]


def test_prefaturacao_reposicao_por_horas_contratadas(mundo):
    # 3 h/semana a 18 €: 3 × 52/12 × 18 = 234 € em mês completo, independentemente do executado
    ln = preparar(mundo, horas=(1.5, 0, 1.5, 0, 0, 0, 0))
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    rej = ocs(mundo, ln)[0]
    fecho.validar(mundo.db, mundo.gestor, [rej], False, "Loja fechada", HOJE)
    p = fecho.prefaturacao(mundo.db, mundo.t.id, OUT, "REP", HOJE)
    linha = p["clientes"][0]["contratos"][0]["linhas"][0]
    assert linha["valor"] == 234.0 and linha["horas_contratadas"] == 13.0
    # custo: horas executadas (sem a rejeitada) × 11,40
    n_exec = len([o for o in ocs(mundo, ln) if o.data.month == 10]) - 1
    assert linha["horas_executadas"] == 1.5 * n_exec
    assert linha["custo"] == round(1.5 * n_exec * 11.40, 2)


def test_prefaturacao_prorata_linha_a_meio_do_mes(mundo):
    nova_linha(mundo, [1, 1, 1, 1, 1, 1, 1], inicio=date(2026, 10, 17))  # 7 h/sem, 15 de 31 dias
    p = fecho.prefaturacao(mundo.db, mundo.t.id, OUT, "REP", HOJE)
    linha = p["clientes"][0]["contratos"][0]["linhas"][0]
    assert linha["dias_vigencia"] == 15
    assert linha["valor"] == round(7 * 52 / 12 * 18 * 15 / 31, 2)


def test_apuramento_por_colaborador_e_cliente_com_custo_especial(mundo):
    a = preparar(mundo)
    b = preparar(mundo, horas=(0, 3, 0, 0, 0, 0, 0))
    b.custo_hora_especial = D("13.00")
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    passadas = [o for ln in (a, b) for o in ocs(mundo, ln) if o.data.month == 10]
    fecho.validar(mundo.db, mundo.gestor, passadas[:-1], True, None, HOJE)
    r = fecho.apuramento(mundo.db, mundo.t.id, OUT, HOJE)
    ines = r["colaboradores"][0]
    assert ines["pendentes"] == 1
    valores = sorted((ln["valor_hora"], ln["horas"]) for ln in ines["linhas"])
    assert valores[0][0] == 11.40 and valores[1][0] == 13.00
    assert r["totais"]["pendentes"] == 1
    with pytest.raises(ValueError, match="por validar"):
        fecho.fechar(mundo.db, mundo.gestor, TipoPeriodo.remuneracao, OUT, "*", HOJE)
    fecho.validar(mundo.db, mundo.gestor, passadas[-1:], True, None, HOJE)
    fecho.fechar(mundo.db, mundo.gestor, TipoPeriodo.remuneracao, OUT, "*", HOJE)
    csv = fecho.apuramento_csv(fecho.apuramento(mundo.db, mundo.t.id, OUT, HOJE))
    assert csv.startswith("﻿Mes;Numero;Colaborador")
    assert "Bom Grão Cafés" in csv and ";11,40;" in csv


def test_periodo_fechado_bloqueia_alteracoes(mundo):
    ln = preparar(mundo)
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    out = [o for o in ocs(mundo, ln) if o.data.month == 10]
    fecho.validar(mundo.db, mundo.gestor, out, True, None, HOJE)
    fecho.fechar(mundo.db, mundo.gestor, TipoPeriodo.remuneracao, OUT, "*", HOJE)
    with pytest.raises(ValueError, match="fechado"):
        fecho.registar_execucao(mundo.db, mundo.gestor, out[0], D("1"), "x", HOJE)
    assert fecho.validar(mundo.db, mundo.gestor, [out[0]], False, "x", HOJE)["erros"]
    with pytest.raises(PermissionError):
        fecho.reabrir(mundo.db, mundo.gestor, TipoPeriodo.remuneracao, OUT, "*")
    mundo.gestor.perfil = Perfil.direcao
    fecho.reabrir(mundo.db, mundo.gestor, TipoPeriodo.remuneracao, OUT, "*")
    fecho.registar_execucao(mundo.db, mundo.gestor, out[0], D("1"), "Correção após reabertura", HOJE)


def test_nao_fecha_mes_corrente(mundo):
    with pytest.raises(ValueError, match="terminados"):
        fecho.fechar(mundo.db, mundo.gestor, TipoPeriodo.faturacao, HOJE, "REP", HOJE)


def test_muito_curta_duracao_alertas(mundo):
    mundo.pedro.vinculo = TipoVinculo.muito_curta_duracao
    mundo.pedro.data_inicio = HOJE - timedelta(days=30)
    preparar(mundo, horas=(1, 1, 1, 1, 1, 1, 0), inicio=date(2026, 9, 1), colab=mundo.pedro)
    r = fecho.indicadores_colaborador(mundo.db, mundo.pedro, HOJE)
    assert r["dias_contrato_atual"] == 31
    assert r["dias_trabalhados_ano"] + r["dias_planeados_ano"] > 70
    textos = " ".join(a["texto"] for a in r["alertas"])
    assert "excedem 70" in textos and "31 de 35" in textos


def test_api_supervisor_valida_so_a_sua_equipa(client, mundo):
    a = preparar(mundo)
    b = preparar(mundo, colab=mundo.outro)
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    mundo.db.commit()
    h = token(client, "s1@t.pt")
    r = client.get("/api/validacao", headers=h, params={"inicio": "2026-10-01", "fim": "2026-10-31"})
    assert r.status_code == 200
    assert {x["colaborador_id"] for x in r.json()["itens"]} == {mundo.ines.id}
    alheio = ocs(mundo, b)[0].id
    assert client.post("/api/validacao", headers=h, json={"ids": [alheio]}).status_code == 403
    proprio = ocs(mundo, a)[0].id
    r = client.post("/api/validacao", headers=h, json={"ids": [proprio]})
    assert r.status_code == 200 and r.json()["processadas"] == 1


def test_api_fecho_so_financeiro_ou_direcao(client, mundo):
    mundo.db.add(User(tenant_id=mundo.t.id, email="f@t.pt", nome="Fin", password_hash=hash_password("x"), perfil=Perfil.financeiro))
    mundo.db.commit()
    body = {"tipo": "faturacao", "mes": "2026-10", "area": "REP"}
    assert client.post("/api/periodos/fechar", headers=token(client, "g@t.pt"), json=body).status_code == 403
    r = client.post("/api/periodos/fechar", headers=token(client, "f@t.pt"), json=body)
    assert r.status_code == 200, r.text
    assert client.get("/api/prefaturacao", headers=token(client, "f@t.pt"), params={"mes": "2026-10"}).json()["fechado"]


def test_encargos_entram_na_margem_mas_nao_no_apuramento(mundo):
    ln = preparar(mundo)  # Inês, a termo, 11,40 €/h
    fecho.aplicar_aceitacao_tacita(mundo.db, mundo.t.id, date(2026, 10, 31))
    out = [o for o in ocs(mundo, ln) if o.data.month == 10]
    fecho.validar(mundo.db, mundo.gestor, out, True, None, HOJE)
    horas = 2 * len(out)
    base = fecho.prefaturacao(mundo.db, mundo.t.id, OUT, "REP", HOJE)["totais"]["custo"]
    assert base == round(horas * 11.40, 2)
    mundo.t.encargos_a_termo_pct = D("40")
    com = fecho.prefaturacao(mundo.db, mundo.t.id, OUT, "REP", HOJE)["totais"]["custo"]
    assert com == round(horas * 11.40 * 1.4, 2)
    ap = fecho.apuramento(mundo.db, mundo.t.id, OUT, HOJE)
    assert ap["colaboradores"][0]["linhas"][0]["valor_hora"] == 11.40  # salário sem encargos


def test_api_configuracao_so_direcao(client, mundo):
    mundo.db.commit()
    body = {"aceitacao_tacita": True, "limite_margem_pct": 20, "encargos_sem_termo_pct": 38.5,
            "encargos_a_termo_pct": 38.5, "encargos_muito_curta_pct": 30, "encargos_recibos_verdes_pct": 0}
    assert client.put("/api/configuracao", headers=token(client, "g@t.pt"), json=body).status_code == 403
    mundo.gestor.perfil = Perfil.direcao
    mundo.db.commit()
    r = client.put("/api/configuracao", headers=token(client, "g@t.pt"), json=body)
    assert r.status_code == 200 and float(r.json()["encargos_muito_curta_pct"]) == 30
