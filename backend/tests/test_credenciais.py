"""Credenciais: preenchimento do Word, versões dos modelos, emissão e substituição."""
import io
import zipfile
from datetime import date
from pathlib import Path

from app.services import credenciais as cr
from app.services import docx_campos as dx
from tests.conftest import nova_linha, token

MODELO = (Path(__file__).parents[1] / "app" / "assets" / "credencial_modelo.docx").read_bytes()
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx(corpo: str) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {W}><w:body>{corpo}</w:body></w:document>')
    return b.getvalue()


def _texto(docx: bytes) -> str:
    import re
    xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode()
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def test_preenche_marcadores_partidos_e_mergefields():
    corpo = (
        '<w:p><w:r><w:t>Olá {{no</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>me}}, loja </w:t></w:r><w:r><w:t>«u_creloj»</w:t></w:r></w:p>'
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> MERGEFIELD nbenef </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>«nbenef»</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '<w:r><w:t> &lt;&lt;Seguradora&gt;&gt; {{xpto}}</w:t></w:r></w:p>'
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> ASK X "Pergunta" </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Red Bull</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )
    v = {"nome": "Inês", "loja": "Continente", "niss": "123", "seguradora": "Fidelidade"}
    out, desconhecidos, _ = dx.preencher(_docx(corpo), lambda n: v.get(cr.resolver_nome(n) or ""))
    t = _texto(out)
    assert "Olá Inês, loja Continente" in t and "123" in t and "Fidelidade" in t
    assert "Red Bull" not in t and "MERGEFIELD" not in t
    assert desconhecidos == ["xpto"]


def test_modelo_padrao_so_tem_campos_conhecidos():
    _, desconhecidos, encontrados = dx.preencher(MODELO, lambda n: "x" if cr.resolver_nome(n) else None)
    assert desconhecidos == [] and {"nome", "cliente", "loja", "validade", "apolice"} <= {cr.resolver_nome(n) for n in encontrados}


def _modelo(client, h, nome="Credencial padrão", conteudo=MODELO):
    r = client.post("/api/modelos-credencial", headers=h, data={"nome": nome},
                    files={"ficheiro": ("credencial.docx", conteudo, dx.__name__ and "application/octet-stream")})
    assert r.status_code == 201, r.text
    return r.json()


def test_modelos_versionados(client, mundo):
    mundo.db.commit()
    h = token(client, "g@t.pt")
    v1 = _modelo(client, h)
    v2 = _modelo(client, h, "credencial PADRÃO".replace("PADRÃO", "padrão"))
    assert (v1["versao"], v2["versao"]) == (1, 2) and v2["nome"] == "Credencial padrão" and v2["desconhecidos"] == []
    lista = client.get("/api/modelos-credencial", headers=h).json()
    assert [(m["versao"], m["atual"]) for m in lista] == [(2, True), (1, False)]
    assert client.post("/api/modelos-credencial", headers=h, data={"nome": "x"},
                       files={"ficheiro": ("x.docx", b"nao e word", "application/octet-stream")}).status_code == 422
    r = client.post(f"/api/modelos-credencial/{v1['id']}/repor", headers=h)
    assert r.json()["versao"] == 3


def test_emitir_e_substituir_credencial(client, mundo):
    mundo.colaborador = mundo.ines
    mundo.ines.data_nascimento = date(1996, 4, 12)
    mundo.t.seguradora, mundo.t.apolice = "Fidelidade", "AT-1"
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0], inicio=date.today())
    mundo.db.commit()
    h = token(client, "g@t.pt")
    _modelo(client, h)
    prep = client.get("/api/credenciais/preparar", headers=h, params={"colaborador_id": mundo.ines.id, "linha_id": ln.id}).json()
    assert prep["modelo"]["versao"] == 1 and prep["substituiveis"] == []
    assert "n.º de Segurança Social do colaborador" in prep["em_falta"]
    r = client.post("/api/credenciais", headers=h, json={"colaborador_id": mundo.ines.id, "linha_id": ln.id, "valida_ate": "2027-06-30"})
    assert r.status_code == 201, r.text
    c1 = r.json()
    assert c1["numero"].startswith("CR-") and c1["estado"] == "emitida"
    doc = client.get(f"/api/credenciais/{c1['id']}/ficheiro", headers=h)
    t = _texto(doc.content)
    assert "Inês" in t and "12/04/1996" in t and "30/06/2027" in t and "Fidelidade" in t and "{{" not in t
    # o Pedro passa a fazer a loja: credencial por substituição
    prep = client.get("/api/credenciais/preparar", headers=h, params={"colaborador_id": mundo.pedro.id, "linha_id": ln.id}).json()
    assert [c["numero"] for c in prep["substituiveis"]] == [c1["numero"]]
    r = client.post("/api/credenciais", headers=h, json={"colaborador_id": mundo.pedro.id, "linha_id": ln.id,
                                                         "valida_ate": "2027-06-30", "substitui_id": c1["id"]})
    assert r.json()["substitui"] == c1["numero"]
    estados = {c["numero"]: c["estado"] for c in client.get("/api/credenciais", headers=h).json()}
    assert estados[c1["numero"]] == "substituida" and estados[r.json()["numero"]] == "emitida"
    # validade no passado é recusada; o supervisor de outra zona não vê as credenciais
    assert client.post("/api/credenciais", headers=h, json={"colaborador_id": mundo.ines.id, "linha_id": ln.id,
                                                            "valida_ate": "2020-01-01"}).status_code == 422
    assert client.get("/api/credenciais", headers=token(client, "s2@t.pt")).json() == []


def test_emitir_sem_modelo_da_erro_claro(client, mundo):
    ln = nova_linha(mundo, [2, 0, 0, 0, 0, 0, 0], inicio=date.today())
    mundo.db.commit()
    r = client.post("/api/credenciais", headers=token(client, "g@t.pt"), json={"colaborador_id": mundo.ines.id, "linha_id": ln.id})
    assert r.status_code == 422 and "modelo" in r.json()["detail"]
