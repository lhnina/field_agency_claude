from datetime import date, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from app.models import Ausencia, Ocorrencia, TipoAusencia
from app.services import operacao as op
from tests.conftest import nova_linha

SEG = date(2026, 11, 2)  # segunda-feira


def ocs(m, ln):
    return m.db.scalars(select(Ocorrencia).where(Ocorrencia.linha_id == ln.id).order_by(Ocorrencia.data)).all()


def test_valor_mensal_horas_semana_x_52_12(mundo):
    ln = nova_linha(mundo, [1.5, 0, 1.5, 0, 0, 0, 0])
    assert ln.horas_semana == D("3.0")
    assert op.horas_mes_linha(ln) == D("13.00")
    assert op.valor_mensal_linha(ln) == D("234.00")  # 3 × 52/12 × 18
    grande = nova_linha(mundo, [16, 16, 16, 16, 16, 16, 16], loja=mundo.loja2)
    assert op.valor_mensal_linha(grande) == D("8736.00")  # 112 h/sem, como no contrato de exemplo


def test_gera_ocorrencias_nos_dias_com_horas_e_e_idempotente(mundo):
    ln = nova_linha(mundo, [1.5, 0, 1.5, 0, 0, 0, 0])
    assert op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=13)) == 4
    assert [o.data.weekday() for o in ocs(mundo, ln)] == [0, 2, 0, 2]
    assert all(o.horas_planeadas == D("1.5") for o in ocs(mundo, ln))
    assert op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=13)) == 0


def test_respeita_fim_da_linha(mundo):
    ln = nova_linha(mundo, [2, 2, 2, 2, 2, 0, 0], fim=SEG + timedelta(days=2))
    assert op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=30)) == 3


def test_feriado_passa_para_outro_dia(mundo):
    # 1 dez 2026 é terça e feriado; a linha só tem horas à terça
    ln = nova_linha(mundo, [0, 3, 0, 0, 0, 0, 0], inicio=date(2026, 11, 30))
    op.gerar_ocorrencias(mundo.db, ln, ate=date(2026, 12, 6))
    o = ocs(mundo, ln)[0]
    assert o.data_original == date(2026, 12, 1)
    assert o.data == date(2026, 12, 2)
    assert o.reagendada_feriado


def test_feriado_evita_dia_que_ja_tem_horas(mundo):
    ln = nova_linha(mundo, [0, 3, 2, 0, 0, 0, 0], inicio=date(2026, 11, 30))
    op.gerar_ocorrencias(mundo.db, ln, ate=date(2026, 12, 6))
    reag = [o for o in ocs(mundo, ln) if o.reagendada_feriado][0]
    assert reag.data == date(2026, 12, 3)  # quarta já tem serviço, passa para quinta


def test_afetacao_persistente_preenche_futuras_e_novas(mundo):
    ln = nova_linha(mundo, [2, 0, 0, 2, 0, 0, 0])
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=13))
    assert all(o.colaborador_id is None for o in ocs(mundo, ln))
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
    assert all(o.colaborador_id == mundo.ines.id for o in ocs(mundo, ln))
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=27))
    assert len(ocs(mundo, ln)) == 8
    assert all(o.colaborador_id == mundo.ines.id for o in ocs(mundo, ln))


def test_afetacao_temporaria_e_regresso_ao_titular(mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=27))
    op.afetar(mundo.db, mundo.gestor, ln, mundo.pedro, SEG + timedelta(days=7), SEG + timedelta(days=13))
    assert [o.colaborador_id for o in ocs(mundo, ln)] == [mundo.ines.id, mundo.pedro.id, mundo.ines.id, mundo.ines.id]


def test_substituicao_altera_so_a_ocorrencia(mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=13))
    primeira, segunda = ocs(mundo, ln)
    op.substituir(mundo.db, mundo.gestor, primeira, mundo.pedro.id, "Férias")
    assert primeira.colaborador_id == mundo.pedro.id
    assert primeira.colaborador_previsto_id == mundo.ines.id  # histórico previsto vs efetivo
    assert segunda.colaborador_id == mundo.ines.id
    op.substituir(mundo.db, mundo.gestor, primeira, None, None)  # anular substituição
    assert primeira.colaborador_id == mundo.ines.id


def test_ausencia_lista_servicos_por_substituir(mundo):
    ln = nova_linha(mundo, [2, 2, 2, 2, 2, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=13))
    aus = Ausencia(tenant_id=mundo.t.id, colaborador_id=mundo.ines.id, tipo=TipoAusencia.ferias, inicio=SEG,
                   fim=SEG + timedelta(days=4))
    mundo.db.add(aus)
    mundo.db.flush()
    afetadas = op.ocorrencias_afetadas(mundo.db, aus)
    assert len(afetadas) == 5
    op.substituir(mundo.db, mundo.gestor, afetadas[0], mundo.pedro.id, "Férias")
    assert len(op.ocorrencias_afetadas(mundo.db, aus)) == 4


def test_editar_linha_regenera_so_o_futuro(mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=20))
    ln.h_seg, ln.h_qua = D("0"), D("3")
    op.regenerar_futuras(mundo.db, ln, SEG + timedelta(days=7), SEG + timedelta(days=20))
    res = [(o.data.weekday(), o.horas_planeadas) for o in ocs(mundo, ln)]
    assert res == [(0, D("2.00")), (2, D("3.00")), (2, D("3.00"))]


def test_planeamento_alerta_mais_de_8h_no_dia(mundo):
    a = nova_linha(mundo, [5, 0, 0, 0, 0, 0, 0])
    b = nova_linha(mundo, [4, 0, 0, 0, 0, 0, 0], loja=mundo.loja2)
    for ln in (a, b):
        op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
        op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=6))
    v = op.planeamento_semana(mundo.db, mundo.gestor, SEG, op.FiltroPlaneamento())
    assert all("excede_horas_dia" in o["alertas"] for o in v["ocorrencias"])
    linha_ines = next(c for c in v["colaboradores"] if c["id"] == mundo.ines.id)
    assert linha_ines["horas_semana"] == 9.0 and linha_ines["alertas"]
    assert v["resumo"]["conflitos"] == 2


def test_supervisor_ve_so_a_sua_equipa(mundo):
    a = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    b = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0], loja=mundo.loja2)
    op.afetar(mundo.db, mundo.gestor, a, mundo.ines, SEG)
    op.afetar(mundo.db, mundo.gestor, b, mundo.outro, SEG)
    for ln in (a, b):
        op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=6))
    v1 = op.planeamento_semana(mundo.db, mundo.sup1, SEG, op.FiltroPlaneamento())
    v2 = op.planeamento_semana(mundo.db, mundo.sup2, SEG, op.FiltroPlaneamento())
    assert {o["colaborador_id"] for o in v1["ocorrencias"]} == {mundo.ines.id}
    assert {o["colaborador_id"] for o in v2["ocorrencias"]} == {mundo.outro.id}


def test_candidatos_explicaveis(mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0])
    op.afetar(mundo.db, mundo.gestor, ln, mundo.ines, SEG)
    op.gerar_ocorrencias(mundo.db, ln, ate=SEG + timedelta(days=6))
    o = ocs(mundo, ln)[0]
    res = op.candidatos(mundo.db, o)
    assert res[0]["colaborador_id"] == mundo.pedro.id
    assert "Mesma zona da loja" in res[0]["motivos"]
    assert mundo.ines.id not in [r["colaborador_id"] for r in res]
