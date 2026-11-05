"""Preenchimento de modelos Word (.docx) com campos.

Aceita três formas de marcar um campo no modelo, para que modelos já existentes funcionem:
- campos de impressão em série do Word (MERGEFIELD nome), também em «nome»;
- marcadores de texto {{nome}} (forma recomendada) ou <<nome>>.

O Word parte muitas vezes um marcador por vários "runs" de texto (formatação, revisões);
a substituição junta o texto do parágrafo, troca o marcador e devolve o resultado ao primeiro run,
mantendo a formatação desse run. Imagens, cabeçalhos e rodapés ficam intactos.
Campos ASK/FILLIN/SET (perguntas do Word) são removidos; CREATEDATE/DATE ficam com a data de emissão.
"""
import io
import re
import zipfile
from collections.abc import Callable

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
q = lambda tag: f"{{{W}}}{tag}"  # noqa: E731

MARCADOR = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}|«\s*([^«»]+?)\s*»|<<\s*([^<>]+?)\s*>>")
PARTES = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")
REMOVER = ("ASK", "FILLIN", "SET")
DATAS = ("CREATEDATE", "DATE", "SAVEDATE", "PRINTDATE")

Resolver = Callable[[str], str | None]  # nome do campo no modelo → valor (None = desconhecido)


def _texto_run(r) -> str:
    return "".join(t.text or "" for t in r.iter(q("t")))


def _novo_run(modelo, texto: str):
    r = etree.Element(q("r"))
    rpr = modelo.find(q("rPr")) if modelo is not None else None
    if rpr is not None:
        r.append(etree.fromstring(etree.tostring(rpr)))
    t = etree.SubElement(r, q("t"))
    t.text = texto
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def _instr_nome(instr: str) -> tuple[str, str]:
    partes = instr.strip().split()
    if not partes:
        return "", ""
    tipo = partes[0].upper()
    nome = partes[1].strip('"') if len(partes) > 1 else ""
    return tipo, nome


def _campos_complexos(raiz, resolver: Resolver, data_emissao: str, desconhecidos: set[str], encontrados: set[str]):
    """Campos com fldChar begin/separate/end (podem atravessar vários runs)."""
    runs = list(raiz.iter(q("r")))
    i = 0
    while i < len(runs):
        r = runs[i]
        fc = r.find(q("fldChar"))
        if fc is None or fc.get(q("fldCharType")) != "begin":
            i += 1
            continue
        # recolhe o campo (com campos aninhados contados pela profundidade)
        prof, j, instr, sep = 0, i, [], None
        while j < len(runs):
            f = runs[j].find(q("fldChar"))
            tipo_fc = f.get(q("fldCharType")) if f is not None else None
            if tipo_fc == "begin":
                prof += 1
            elif tipo_fc == "separate" and prof == 1:
                sep = j
            elif tipo_fc == "end":
                prof -= 1
                if prof == 0:
                    break
            if prof == 1 and sep is None:
                instr += [t.text or "" for t in runs[j].iter(q("instrText"))]
            j += 1
        fim = min(j, len(runs) - 1)
        tipo, nome = _instr_nome("".join(instr))
        bloco = runs[i:fim + 1]
        valor = None
        if tipo == "MERGEFIELD":
            encontrados.add(nome)
            valor = resolver(nome)
            if valor is None:
                desconhecidos.add(nome)
                valor = f"«{nome}»"
        elif tipo in DATAS:
            valor = data_emissao
        if tipo in REMOVER or valor is not None:
            modelo = runs[sep + 1] if sep is not None and sep + 1 < fim else r
            novo = _novo_run(modelo, valor) if valor is not None else None
            pai = bloco[0].getparent()
            if novo is not None and pai is not None:
                pai.insert(pai.index(bloco[0]), novo)
            for x in bloco:
                if x.getparent() is not None:
                    x.getparent().remove(x)
        i = fim + 1


def _campos_simples(raiz, resolver: Resolver, data_emissao: str, desconhecidos: set[str], encontrados: set[str]):
    for fs in list(raiz.iter(q("fldSimple"))):
        tipo, nome = _instr_nome(fs.get(q("instr")) or "")
        valor = None
        if tipo == "MERGEFIELD":
            encontrados.add(nome)
            valor = resolver(nome)
            if valor is None:
                desconhecidos.add(nome)
                valor = f"«{nome}»"
        elif tipo in DATAS:
            valor = data_emissao
        if tipo in REMOVER or valor is not None:
            pai = fs.getparent()
            if valor is not None:
                pai.insert(pai.index(fs), _novo_run(fs.find(q("r")), valor))
            pai.remove(fs)


def _marcadores(raiz, resolver: Resolver, desconhecidos: set[str], encontrados: set[str]):
    for p in raiz.iter(q("p")):
        ts = [t for t in p.iter(q("t"))]
        if not ts:
            continue
        texto = "".join(t.text or "" for t in ts)
        if not MARCADOR.search(texto):
            continue
        # posições de cada w:t no texto do parágrafo
        pos, k = [], 0
        for t in ts:
            n = len(t.text or "")
            pos.append((k, k + n))
            k += n
        for m in reversed(list(MARCADOR.finditer(texto))):
            nome = next(g for g in m.groups() if g is not None)
            encontrados.add(nome)
            valor = resolver(nome)
            if valor is None:
                desconhecidos.add(nome)
                continue
            a, b = m.span()
            primeiro = True
            for idx, (s, e) in enumerate(pos):
                if e <= a or s >= b:
                    continue
                t = ts[idx]
                txt = t.text or ""
                ini, fim = max(a, s) - s, min(b, e) - s
                t.text = txt[:ini] + (valor if primeiro else "") + txt[fim:]
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                primeiro = False
            texto = "".join(t.text or "" for t in ts)
            pos, k = [], 0
            for t in ts:
                n = len(t.text or "")
                pos.append((k, k + n))
                k += n


def substituir_texto(modelo: bytes, trocas: list[tuple[str, str]]) -> bytes:
    """Troca texto livre (expressões regulares) parágrafo a parágrafo, mesmo partido em vários runs."""
    entrada = zipfile.ZipFile(io.BytesIO(modelo))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if PARTES.match(item.filename):
                raiz = etree.fromstring(dados)
                for p in raiz.iter(q("p")):
                    ts = list(p.iter(q("t")))
                    texto = "".join(t.text or "" for t in ts)
                    novo = texto
                    for padrao, sub in trocas:
                        novo = re.sub(padrao, sub, novo)
                    if novo != texto and ts:
                        ts[0].text = novo
                        ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                        for t in ts[1:]:
                            t.text = ""
                dados = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
            z.writestr(item, dados)
    return saida.getvalue()


def preencher(modelo: bytes, resolver: Resolver, data_emissao: str = "") -> tuple[bytes, list[str], list[str]]:
    """Devolve (docx preenchido, campos desconhecidos, campos encontrados)."""
    desconhecidos: set[str] = set()
    encontrados: set[str] = set()
    entrada = zipfile.ZipFile(io.BytesIO(modelo))
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for item in entrada.infolist():
            dados = entrada.read(item.filename)
            if PARTES.match(item.filename):
                raiz = etree.fromstring(dados)
                _campos_complexos(raiz, resolver, data_emissao, desconhecidos, encontrados)
                _campos_simples(raiz, resolver, data_emissao, desconhecidos, encontrados)
                _marcadores(raiz, resolver, desconhecidos, encontrados)
                dados = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
            elif item.filename == "word/settings.xml":
                # o modelo pode estar ligado a uma origem de dados de impressão em série: retirar
                raiz = etree.fromstring(dados)
                for mm in raiz.findall(q("mailMerge")):
                    raiz.remove(mm)
                dados = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)
            z.writestr(item, dados)
    return saida.getvalue(), sorted(desconhecidos), sorted(encontrados)


def validar_docx(conteudo: bytes) -> None:
    try:
        z = zipfile.ZipFile(io.BytesIO(conteudo))
        z.getinfo("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise ValueError("O ficheiro não é um documento Word (.docx) válido")
