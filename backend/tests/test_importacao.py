import io
from datetime import date

from openpyxl import Workbook, load_workbook
from sqlalchemy import select

from app.models import Colaborador, Contrato, EstadoContrato, Loja, Ocorrencia, TipoVinculo
from app.services import importacao as imp
from tests.conftest import token


def xlsx(cab: list[str], linhas: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(cab)
    for ln in linhas:
        ws.append(ln)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_modelo_tem_cabecalhos_e_instrucoes():
    wb = load_workbook(io.BytesIO(imp.modelo_xlsx("colaboradores", ["Amadora"])))
    cab = [c.value for c in wb.worksheets[0][1]]
    assert cab[:4] == ["N.º *", "Nome *", "Função", "Vínculo *"]
    assert wb.sheetnames == ["Colaboradores", "Instruções"]


def test_lojas_cria_atualiza_e_cria_zona(mundo):
    conteudo = xlsx(["Nome", "Insígnia", "Zona", "Supervisor"], [
        ["Continente Amadora", "Continente", "Amadora", "s1@t.pt"],  # já existe → atualizar
        ["Lidl Odivelas", "Lidl", "Odivelas", "Sup 2"],              # nova, zona e insígnia novas
    ])
    pre = imp.importar(mundo.db, mundo.gestor, "lojas", conteudo, False)
    assert pre["resumo"] == {"total": 2, "com_erros": 0, "atualizar": 1, "criar": 1}
    assert "Zona nova: Odivelas" in pre["linhas"][1]["avisos"]
    imp.importar(mundo.db, mundo.gestor, "lojas", conteudo, True)
    lidl = mundo.db.scalar(select(Loja).where(Loja.nome == "Lidl Odivelas"))
    assert lidl.zona.nome == "Odivelas" and lidl.insignia.nome == "Lidl" and lidl.supervisor_id == mundo.sup2.id


def test_colaboradores_valida_linha_a_linha_e_nao_grava_com_erros(mundo):
    conteudo = xlsx(["N.º", "Nome", "Vínculo", "Data de início", "Custo por hora", "Disponibilidade", "Supervisor"], [
        ["100", "Rita", "A termo", "01/02/2026", "11,40", "Seg,Ter,Qua", "s1@t.pt"],
        ["101", "Tiago", "Estagiário", "31/02/2026", "abc", "Lun", "ninguém"],
        ["1", "Inês Carvalho", "Sem termo", None, None, "1111110", None],  # existente → atualizar
    ])
    pre = imp.importar(mundo.db, mundo.gestor, "colaboradores", conteudo, False)
    assert pre["resumo"]["com_erros"] == 1
    erros = " | ".join(pre["linhas"][1]["erros"])
    for txt in ("Vínculo", "data", "número", "Disponibilidade", "Supervisor"):
        assert txt in erros
    try:
        imp.importar(mundo.db, mundo.gestor, "colaboradores", conteudo, True)
        raise AssertionError("devia falhar")
    except ValueError as e:
        assert "Corrija" in str(e)
    ok = xlsx(["N.º", "Nome", "Vínculo", "Data de início", "Custo por hora", "Disponibilidade"],
              [["100", "Rita", "A termo", date(2026, 2, 1), 11.4, "Seg,Ter,Qua"], ["1", "Inês Carvalho", "Sem termo", None, None, "1111110"]])
    imp.importar(mundo.db, mundo.gestor, "colaboradores", ok, True)
    rita = mundo.db.scalar(select(Colaborador).where(Colaborador.numero == "100"))
    assert rita.disponibilidade == "1110000" and float(rita.custo_hora) == 11.4 and rita.data_inicio == date(2026, 2, 1)
    assert mundo.ines.nome == "Inês Carvalho" and mundo.ines.vinculo == TipoVinculo.sem_termo
    assert float(mundo.ines.custo_hora) == 11.40  # vazio não apaga o valor existente


def test_contratos_agrupa_por_referencia_afeta_e_gera(mundo):
    cab = ["Referência", "Tipo", "Cliente", "Início", "Loja", "Seg", "Qua", "Preço por hora", "Colaborador (N.º)"]
    conteudo = xlsx(cab, [
        ["BG", "Reposição", "Bom Grão Cafés", "02/11/2026", "Continente Amadora", 1.5, 1.5, 18, "1"],
        ["BG", "Reposição", "Bom Grão Cafés", "02/11/2026", "Pingo Doce Alfragide", 2, 0, "18,00", None],
        ["X", "Promoção", "Cliente Fantasma", "02/11/2026", "Loja Fantasma", 0, 0, None, "999"],
    ])
    pre = imp.importar(mundo.db, mundo.gestor, "contratos", conteudo, False)
    erros = " | ".join(pre["linhas"][2]["erros"])
    for txt in ("Cliente", "Loja", "pelo menos um dia", "Preço", "999"):
        assert txt in erros
    ok = xlsx(cab, [r for r in [
        ["BG", "Reposição", "Bom Grão Cafés", "02/11/2026", "Continente Amadora", 1.5, 1.5, 18, "1"],
        ["BG", "Reposição", "Bom Grão Cafés", "02/11/2026", "Pingo Doce Alfragide", 2, 0, "18,00", None],
    ]])
    imp.importar(mundo.db, mundo.gestor, "contratos", ok, True)
    novo = mundo.db.scalar(select(Contrato).where(Contrato.observacoes.like("Importado%")))
    assert novo.numero == "CT-REP-2026/0002" and novo.estado == EstadoContrato.ativo and len(novo.linhas) == 2
    ocs = mundo.db.scalars(select(Ocorrencia).where(Ocorrencia.linha_id == novo.linhas[0].id)).all()
    assert ocs and all(o.colaborador_previsto_id == mundo.ines.id for o in ocs)


def test_contratos_referencia_incoerente(mundo):
    cab = ["Referência", "Tipo", "Cliente", "Início", "Loja", "Seg", "Preço por hora"]
    conteudo = xlsx(cab, [
        ["BG", "Reposição", "Bom Grão Cafés", "02/11/2026", "Continente Amadora", 2, 18],
        ["BG", "Reposição", "Bom Grão Cafés", "01/12/2026", "Pingo Doce Alfragide", 2, 18],
    ])
    pre = imp.importar(mundo.db, mundo.gestor, "contratos", conteudo, False)
    assert "datas diferentes" in " ".join(pre["linhas"][1]["erros"])


def test_colunas_obrigatorias_em_falta(mundo):
    try:
        imp.importar(mundo.db, mundo.gestor, "lojas", xlsx(["Morada"], [["Rua X"]]), False)
        raise AssertionError
    except ValueError as e:
        assert "Nome" in str(e)


def test_api_permissoes_e_upload(client, mundo):
    mundo.db.commit()
    conteudo = xlsx(["Nome", "Zona"], [["Auchan Sintra", "Sintra"]])
    files = {"ficheiro": ("lojas.xlsx", conteudo, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    assert client.post("/api/importacao/lojas", headers=token(client, "s1@t.pt"), files=files).status_code == 403
    h = token(client, "g@t.pt")
    r = client.post("/api/importacao/lojas", headers=h, files=files)
    assert r.status_code == 200 and r.json()["resumo"]["criar"] == 1
    assert client.get("/api/importacao/contagens", headers=h).json()["lojas"] == 2  # pré-visualização não grava
    r = client.post("/api/importacao/lojas", headers=h, params={"confirmar": True}, files=files)
    assert r.status_code == 200 and r.json()["importado"]
    assert client.get("/api/importacao/contagens", headers=h).json()["lojas"] == 3
    m = client.get("/api/importacao/modelo/contratos", headers=h)
    assert m.status_code == 200 and m.content[:2] == b"PK"
    bad = {"ficheiro": ("x.xlsx", b"nao e excel", "application/octet-stream")}
    assert client.post("/api/importacao/lojas", headers=h, files=bad).status_code == 422
