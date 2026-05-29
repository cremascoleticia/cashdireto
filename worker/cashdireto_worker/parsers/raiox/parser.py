"""Parser da fonte RAIOX ("Raio-X do Cliente" da CERC/KYP) — HTML de SPA → canônico.

Puro: não toca em banco. Layout vem de docs/fontes/RAIOX.md; nada inferido além do documentado.
Estratégia (a página é SPA com classes hasheadas que mudam por exportação):
- escopo na subárvore React (classe `cerc-web-react-customer-x-ray-*`), ignorando o shell Angular;
- cadastro: grid <h4>rótulo</h4><h5>valor</h5>;
- cards: ordem dos rótulos (texto visível) → valor; valor EXATO dos monetários vem do aria-label;
- série mensal: reconstruída da geometria das barras Recharts + TRAVA de reconciliação com os cards;
- relacionamentos: seções "Sócios em Comum" / "Instituições de Pagamento" / "Financiadores".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup

# (chave, rótulo na tela, unidade)
CARDS = [
    ("nivel_comprometimento", "Nível de Comprometimento", "percentual"),
    ("faturamento_estimado", "Faturamento Estimado", "reais"),
    ("potencial_chargeback", "Potencial de ChargeBack", "percentual"),
    ("faturamento_medio_diario", "Faturamento Médio Diário", "reais"),
    ("agenda_mensal_media", "Agenda Mensal Média", "reais"),
    ("historico_agenda", "Histórico de Agenda", "reais"),
    ("volume_antecipacao", "Volume de Antecipação", "reais"),
    ("constatacoes_criticas", "Constatações críticas outros ativos", "contagem"),
    ("fraudes_detectadas", "Fraudes Detectadas", "contagem"),
    ("indice_conformidade_risco", "Índice de Conformidade e Risco", "indice"),
]
# cards monetários abreviados na tela (valor exato vem do aria-label, em ordem de documento)
CARDS_MONET_ABREV = ["faturamento_estimado", "agenda_mensal_media", "historico_agenda", "volume_antecipacao"]

MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

_CNPJ_RE = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")
_REACT_CLS = re.compile(r"customer-x-ray")


class RaioxParseError(ValueError):
    """Erro de parsing do RAIOX (estrutura inesperada ou série que não reconcilia)."""


@dataclass
class RaioxParseResult:
    sha256: str
    data_referencia: date
    cadastro: dict          # cnpj, razao_social, natureza_juridica, setor_economico, situacao_cadastral
    indicadores: list       # {chave, valor, unidade, texto_extra, definicao}
    serie_mensal: list      # {competencia(date), serie, valor}
    relacionamentos: list   # {tipo, nome, percentual}
    reconciliacao: dict = field(default_factory=dict)


# ───────────────────────── helpers de valor ─────────────────────────

def _num_br(s: str) -> float:
    """'18.262,82' -> 18262.82 ; '99' -> 99 ; '0.8' -> 0.8"""
    s = s.strip().replace("%", "").strip()
    if "," in s:                       # formato BR: . milhar, , decimal
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _money(s: str) -> float:
    """'R$ 10.537.000,00' -> 10537000.0 ; 'R$ 10M' -> 10000000 ; 'R$&nbsp;0,00' -> 0.0"""
    import html as _html
    s = _html.unescape(s).replace("\xa0", " ").replace("R$", "")
    m = re.search(r"([\d\.,]+)\s*([KkMm]?)", s)
    if not m:
        raise ValueError(f"valor monetário não reconhecido: {s!r}")
    base = _num_br(m.group(1))
    suf = m.group(2)
    if suf in ("M", "m"):
        return base * 1_000_000
    if suf in ("K", "k"):
        return base * 1_000
    return base


def _tem_cls(node) -> bool:
    c = node.get("class") if hasattr(node, "get") else None
    return bool(c) and any("customer-x-ray" in x for x in c)


def _react_root(soup):
    el = soup.find(class_=_REACT_CLS)
    if el is None:
        return soup
    while el.parent is not None and _tem_cls(el.parent):  # sobe até o topo COM a classe
        el = el.parent
    return el


def _tokens(root) -> list[str]:
    out = []
    for s in root.stripped_strings:
        t = s.replace("\xa0", " ").strip()
        if t:
            out.append(t)
    return out


# ───────────────────────── blocos ─────────────────────────

def _cadastro(root) -> dict:
    cad = {"cnpj": None, "razao_social": None, "natureza_juridica": None,
           "setor_economico": None, "situacao_cadastral": None}
    # acha o CNPJ e, a partir do card dele, lê os pares h4/h5
    h5_cnpj = root.find("h5", string=_CNPJ_RE)
    if h5_cnpj:
        cad["cnpj"] = _CNPJ_RE.search(h5_cnpj.get_text()).group(0)
        card = h5_cnpj.find_parent(class_=re.compile("dashboardCardGridBox")) or h5_cnpj.find_parent("div")
        h4 = h5_cnpj.find_previous("h4")
        if h4:
            cad["razao_social"] = h4.get_text(strip=True)
        if card:
            pares = {}
            for item in card.find_all(["h4", "h5"]):
                pass
            # varre h4(rótulo)->h5(valor) dentro do card
            h4s = card.find_all("h4")
            for h4el in h4s:
                rot = h4el.get_text(strip=True)
                val_el = h4el.find_next("h5")
                val = val_el.get_text(strip=True) if val_el else None
                if rot == "Natureza Jurídica": cad["natureza_juridica"] = val
                elif rot == "Setor Econômico": cad["setor_economico"] = val
                elif rot == "Situação Cadastral": cad["situacao_cadastral"] = val
    return cad


def _aria_money_em_ordem(root) -> list[float]:
    vals = []
    for el in root.find_all(attrs={"aria-label": re.compile(r"R\$")}):
        vals.append(_money(el["aria-label"]))
    return vals


def _definicoes(root) -> dict:
    """Mapeia definição (aria-label longo) -> chave do card, por palavra distintiva."""
    chave_por_palavra = [
        ("chargeback", "potencial_chargeback"),
        ("estimativa de faturamento", "faturamento_estimado"),
        ("agenda contratada futura", "nivel_comprometimento"),
        ("média mensal das agendas", "agenda_mensal_media"),
        ("últimos 12 meses de agendas", "historico_agenda"),
        ("antecipação", "volume_antecipacao"),
    ]
    out = {}
    for el in root.find_all(attrs={"aria-label": True}):
        txt = el["aria-label"].replace("\xa0", " ").strip()
        low = txt.lower()
        if txt.startswith("R$") or len(txt) < 20:
            continue
        for palavra, chave in chave_por_palavra:
            if palavra in low:
                out.setdefault(chave, txt)
                break
    return out


def _cards(root) -> list[dict]:
    toks = _tokens(root)
    pos = {}
    for chave, rotulo, _ in CARDS:
        try:
            pos[chave] = toks.index(rotulo)
        except ValueError:
            pos[chave] = None
    aria_money = _aria_money_em_ordem(root)           # ordem: fat_estimado, agenda_media, historico, volume
    defs = _definicoes(root)
    monet_iter = iter(aria_money)

    indicadores = []
    for chave, rotulo, unidade in CARDS:
        i = pos[chave]
        valor = None
        texto_extra = None
        if i is not None and i + 1 < len(toks):
            bruto = toks[i + 1]
            if chave in CARDS_MONET_ABREV:
                valor = next(monet_iter, None)        # valor EXATO do aria-label
            elif unidade == "reais":
                valor = _money(bruto)                 # ex.: faturamento_medio_diario (exato na tela)
                # texto extra tipo "98% abaixo do setor"
                if i + 2 < len(toks) and "setor" in toks[i + 2].lower():
                    texto_extra = toks[i + 2]
            elif unidade == "percentual":
                valor = _num_br(bruto) if "%" in bruto else None
            else:  # contagem / indice
                try:
                    valor = _num_br(bruto)
                except ValueError:
                    valor = None
        indicadores.append({
            "chave": chave, "valor": valor, "unidade": unidade,
            "texto_extra": texto_extra, "definicao": defs.get(chave),
        })
    return indicadores


def _serie_mensal(soup, html: str, cards_por_chave: dict) -> tuple[list, dict]:
    # escala Y a partir dos ticks rotulados (R$ ... com coordenada y)
    ticks = []
    for m in re.finditer(r'<text[^>]*\by="([\d\.]+)"[^>]*>(?:<[^>]*>)*\s*(R\$[^<]*)', html):
        y = float(m.group(1))
        ticks.append((y, _money(m.group(2))))
    if len(ticks) < 2:
        raise RaioxParseError("eixo Y do gráfico não encontrado")
    ticks.sort()
    (y_top, v_top), (y_bot, v_bot) = ticks[0], ticks[-1]
    rs_per_px = (v_top - v_bot) / (y_bot - y_top)     # R$ por pixel (valor cresce p/ cima)

    # rótulos de mês no eixo X (texto + x)
    meses_x = []
    for m in re.finditer(r'<text[^>]*\bx="([\d\.]+)"[^>]*\by="375[^"]*"[^>]*>(?:<[^>]*>)*\s*([a-z]{3})\b', html):
        meses_x.append((float(m.group(1)), m.group(2)))
    meses_x.sort()

    # barras
    bars = []
    for m in re.finditer(r'class="recharts-rectangle"[^>]*\bd="M\s*([\d\.]+),([\d\.]+)\s*h\s*28\s*v\s*([\d\.]+)', html):
        x, _top, h = float(m.group(1)), float(m.group(2)), float(m.group(3))
        bars.append((x, h * rs_per_px))
    if not bars:
        return [], {"status": "sem_barras"}

    # 2 grupos por offset de x (esquerda/direita dentro do mês)
    xs = sorted({round(b[0], 1) for b in bars})
    # separa em dois conjuntos pela paridade de proximidade ao centro do mês
    def mes_idx(x):
        return min(range(len(meses_x)), key=lambda k: abs(meses_x[k][0] - x)) if meses_x else None
    grupos = {}
    for x, v in bars:
        mi = mes_idx(x)
        # grupo = bar à esquerda (menor x) ou direita dentro do mês
        grupos.setdefault(mi, []).append((x, v))
    s1, s2 = [], []
    comp = []
    for mi in sorted(grupos):
        pair = sorted(grupos[mi], key=lambda p: p[0])
        if len(pair) >= 1: s1.append(pair[0][1])
        if len(pair) >= 2: s2.append(pair[1][1])
        nome, _ = (meses_x[mi] and (meses_x[mi][1], None)) if meses_x else (None, None)
        comp.append(meses_x[mi][1] if meses_x else None)

    # ano: a partir dos rótulos de ano no eixo (375/388) — simplificação: deriva por virada de mês
    return _monta_serie(s1, s2, comp, cards_por_chave)


def _monta_serie(s1, s2, meses_nome, cards):
    # competência: assume sequência contígua terminando no último mês; ano sobe quando mês reinicia
    # (eixo tinha 2025 e 2026). Inferimos a partir da ordem dos meses.
    comps = _competencias(meses_nome)

    hist = (cards.get("historico_agenda") or {}).get("valor")
    vol = (cards.get("volume_antecipacao") or {}).get("valor")
    soma1, soma2 = round(sum(s1), 2), round(sum(s2), 2)

    def bate(a, b): return a is not None and b is not None and abs(a - b) <= 1.0
    # identifica qual série é agenda x volume reconciliando com os cards
    if bate(soma1, hist) and bate(soma2, vol):
        agenda, volume = s1, s2
    elif bate(soma2, hist) and bate(soma1, vol):
        agenda, volume = s2, s1
    else:
        raise RaioxParseError(
            f"série não reconcilia com os cards (soma1={soma1}, soma2={soma2}, "
            f"historico_agenda={hist}, volume_antecipacao={vol})"
        )

    serie = []
    for comp, va, vv in zip(comps, agenda, volume):
        serie.append({"competencia": comp, "serie": "agenda", "valor": round(va, 2)})
        serie.append({"competencia": comp, "serie": "volume_antecipacao", "valor": round(vv, 2)})
    recon = {"soma_agenda": round(sum(agenda), 2), "soma_volume": round(sum(volume), 2),
             "card_historico": hist, "card_volume": vol, "ok": True}
    return serie, recon


def _competencias(meses_nome) -> list[date]:
    comps = []
    ano = None
    anterior = None
    # determina ano inicial: se a sequência cruza de dez->jan, o ano sobe. Ancora o ÚLTIMO mês
    # no ano mais recente plausível. Estratégia simples: começa num ano base e incrementa na virada.
    base_ano = 2025
    for nome in meses_nome:
        mnum = MESES.get(nome)
        if mnum is None:
            comps.append(None); continue
        if anterior is not None and mnum < anterior:
            base_ano += 1
        comps.append(date(base_ano, mnum, 1))
        anterior = mnum
    return comps


def _relacionamentos(root) -> list[dict]:
    toks = _tokens(root)
    rel = []
    secoes = {"Sócios em Comum": "socio_comum",
              "Instituições de Pagamento": "instituicao_pagamento",
              "Financiadores": "financiador"}
    idxs = {nome: toks.index(nome) for nome in secoes if nome in toks}
    ordem = sorted(idxs.items(), key=lambda kv: kv[1])
    for n, (nome, ini) in enumerate(ordem):
        fim = ordem[n + 1][1] if n + 1 < len(ordem) else len(toks)
        bloco = toks[ini + 1:fim]
        tipo = secoes[nome]
        i = 0
        while i < len(bloco):
            t = bloco[i]
            if re.fullmatch(r"\d+", t):           # numeração de sócios (1,2,3)
                i += 1; continue
            pct = None
            # nome possivelmente seguido de percentual
            if i + 1 < len(bloco) and re.search(r"%|^\d", bloco[i + 1]) and tipo != "socio_comum":
                try: pct = _num_br(bloco[i + 1]); i += 1
                except ValueError: pass
            if len(t) > 2 and not re.fullmatch(r"[\d\.,%]+", t):
                rel.append({"tipo": tipo, "nome": t, "percentual": pct})
            i += 1
    return rel


def _data_ref(filename, fallback) -> date:
    m = re.search(r"(?<!\d)(\d{8})(?!\d)", filename or "")
    if m:
        t = m.group(1)
        try:
            y, mo, d = int(t[:4]), int(t[4:6]), int(t[6:8])
            if 2000 <= y <= 2100:
                return date(y, mo, d)
        except ValueError:
            pass
    return fallback


def parse(content: str | bytes, *, original_filename: str | None, fallback_date: date) -> RaioxParseResult:
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    html = raw.decode("utf-8", "ignore")
    soup = BeautifulSoup(html, "lxml")
    root = _react_root(soup)

    cadastro = _cadastro(root)
    indicadores = _cards(root)
    cards_por_chave = {d["chave"]: d for d in indicadores}
    serie, recon = _serie_mensal(soup, html, cards_por_chave)
    relac = _relacionamentos(root)

    return RaioxParseResult(
        sha256=sha,
        data_referencia=_data_ref(original_filename, fallback_date),
        cadastro=cadastro,
        indicadores=indicadores,
        serie_mensal=serie,
        relacionamentos=relac,
        reconciliacao=recon,
    )
