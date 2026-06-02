"""App web v0 (FastAPI) — upload de arquivos → processamento → tela de indicadores.

Fluxo: a pessoa sobe os arquivos da CERC; o sistema detecta a fonte (ingest), carrega no banco
(loaders) e calcula os indicadores (runner → indicador_snapshot). A tela mostra os indicadores
com filtro por estabelecimento (loja) ou grupo (raiz de CNPJ).

`montar_visao` é pura/testável: transforma os snapshots em "blocos" de tela (label/tabela/grafico).
As rotas e a leitura/escrita no banco são casca fina por cima.

Obs.: este módulo NÃO usa `from __future__ import annotations` de propósito — o FastAPI precisa
resolver os tipos reais (Request, UploadFile) das rotas, que são importados dentro de criar_app.
"""
import json
from datetime import date
from pathlib import Path

from . import contexto as contexto_mod
from . import db, ingest
from .indicadores import runner

# Títulos amigáveis por indicador (PT-BR).
TITULOS = {
    "radar_recebiveis": "RADAR — recebíveis",
    "raiox_estabelecimento": "Raio-X (estabelecimento)",
    "raiox_raiz": "Raio-X (grupo)",
    "ap005_constituido_por_usuario_final": "AP005 — constituído por usuário final",
    "ap005_constituido_por_titular_ur": "AP005 — constituído por titular da UR",
    "ap005_livre_por_usuario_final": "AP005 — livre por usuário final",
    "ap005_total_ur_por_usuario_final": "AP005 — total da UR por usuário final",
    "ap005_efeito_por_ordem": "AP005 — constituído do efeito por ordem",
    "ap005_onerado_por_ordem_regra": "AP005 — onerado por ordem × regra",
    "ap005_onerado_por_tipo_regra": "AP005 — onerado por tipo × regra",
    "ap005_efeito_por_ordem_beneficiario": "AP005 — constituído do efeito por ordem × beneficiário",
    "ap005_efeito_por_beneficiario": "AP005 — constituído do efeito por beneficiário",
    "onerado_proprio": "Onerado próprio (cashdireto)",
    "onerado_terceiros": "Onerado de terceiros",
    "ap013_constituido_por_usuario_final": "AP013 — constituído por usuário final",
    "ap013_constituido_por_uf_oneracao": "AP013 — constituído por UF × oneração",
    "ap013_onerado_por_usuario_final": "AP013 — onerado por usuário final",
    "ap013_onerado_por_uf_oneracao": "AP013 — onerado por UF × oneração",
    "ap013_onerado_por_uf_mes_oneracao": "AP013 — onerado por UF × mês × oneração",
    "ap013_constituido_por_uf_mes_oneracao": "AP013 — constituído por UF × mês × oneração",
    "ap013_valor_a_manter_proprio": "AP013 — valor a manter (detentor próprio)",
    "ap013b_calculado_credenciadoras_proprio": "AP013B — calculado credenciadoras (próprio)",
    "ap013c_total_constituido_efeitos_depois": "AP013C — constituído dos efeitos (pós-redistribuição)",
    "ap013c_total_suficiencia_depois": "AP013C — suficiência (pós-redistribuição)",
}

# Indicadores que devem virar gráfico (e o tipo) — o resto vira label (escalar) ou tabela (grupos).
GRAFICOS = {
    "ap013_onerado_por_uf_mes_oneracao": "barras_mes",
}
LABELS = {"onerado_proprio", "onerado_terceiros",
          "ap013c_total_constituido_efeitos_depois", "ap013c_total_suficiencia_depois"}


def _titulo(ind: str) -> str:
    return TITULOS.get(ind, ind)


def _bloco_radar(detalhe: dict) -> list[dict]:
    blocos = [{
        "tipo": "labels", "titulo": "RADAR — totais",
        "itens": [
            {"rotulo": "Livre", "valor": detalhe.get("valor_livre")},
            {"rotulo": "Comprometido", "valor": detalhe.get("valor_comprometido")},
            {"rotulo": "Constituído", "valor": detalhe.get("valor_constituido")},
            {"rotulo": "Nível de comprometimento", "valor": detalhe.get("nivel_comprometimento"), "pct": True},
        ],
    }]
    janelas = detalhe.get("por_janela") or {}
    if janelas:
        labels = sorted(janelas)
        blocos.append({
            "tipo": "grafico", "subtipo": "bar", "titulo": "RADAR — por janela de tempo",
            "labels": labels,
            "datasets": [
                {"label": "Constituído", "dados": [janelas[j].get("constituido", 0) for j in labels]},
                {"label": "Comprometido", "dados": [janelas[j].get("comprometido", 0) for j in labels]},
            ],
        })
    arr = detalhe.get("por_arranjo") or []
    if arr:
        blocos.append({
            "tipo": "tabela", "titulo": "RADAR — constituído por arranjo",
            "colunas": ["Arranjo", "Constituído", "% do total"],
            "linhas": [[a.get("arranjo"), a.get("valor_constituido"),
                        (f"{a['percentual']*100:.1f}%" if a.get("percentual") is not None else "—")] for a in arr],
        })
    return blocos


def _bloco_raiox(detalhe: dict) -> list[dict]:
    ind = detalhe.get("indicadores") or {}
    blocos = [{
        "tipo": "labels", "titulo": "Raio-X — indicadores",
        "itens": [{"rotulo": k, "valor": v} for k, v in ind.items()],
    }]
    serie = detalhe.get("serie_mensal") or []
    if serie:
        comps = sorted({str(s.get("competencia")) for s in serie})
        series_nomes = sorted({s.get("serie") for s in serie})
        datasets = []
        for nome in series_nomes:
            por = {str(s["competencia"]): s["valor"] for s in serie if s.get("serie") == nome}
            datasets.append({"label": nome, "dados": [por.get(c, 0) for c in comps]})
        blocos.append({"tipo": "grafico", "subtipo": "bar", "titulo": "Raio-X — histórico (agenda × antecipação)",
                       "labels": comps, "datasets": datasets})
    for chave, titulo in (("socios", "Sócios"), ("relacionamentos", "Quadro de relacionamento")):
        itens = detalhe.get(chave)
        if itens:
            if isinstance(itens[0], str):
                blocos.append({"tipo": "tabela", "titulo": titulo, "colunas": ["Nome"], "linhas": [[x] for x in itens]})
    for chave, titulo in (("instituicoes_pagamento", "Instituições de pagamento"), ("financiadores", "Financiadores")):
        itens = detalhe.get(chave) or []
        if itens:
            blocos.append({"tipo": "tabela", "titulo": titulo, "colunas": ["Nome", "%"],
                           "linhas": [[x.get("nome"), (f"{x['percentual']:.2f}%" if x.get("percentual") is not None else "—")] for x in itens]})
    return blocos


def _bloco_grupos(ind: str, detalhe: dict) -> dict:
    """Renderiza um indicador {total, grupos} como tabela (grupos pode ser dict ou lista)."""
    grupos = detalhe.get("grupos")
    if isinstance(grupos, dict):                       # {chave: {total, por_mes}}
        linhas = [[k, g.get("total")] for k, g in grupos.items()]
        return {"tipo": "tabela", "titulo": _titulo(ind), "colunas": ["Chave", "Total"], "linhas": linhas}
    grupos = grupos or []                              # [ {dim..., valor} ]
    colunas = [c for c in (grupos[0].keys() if grupos else []) if c != "valor"] + ["valor"]
    linhas = [[g.get(c) for c in colunas] for g in grupos]
    return {"tipo": "tabela", "titulo": _titulo(ind), "colunas": colunas, "linhas": linhas}


def _grafico_por_mes(ind: str, detalhe: dict) -> dict:
    """Soma os grupos por ano-mês e devolve um gráfico de barras (eixo x = ano-mês)."""
    grupos = detalhe.get("grupos")
    por_mes: dict[str, float] = {}
    if isinstance(grupos, dict):
        for g in grupos.values():
            for mes, val in (g.get("por_mes") or {}).items():
                por_mes[mes] = por_mes.get(mes, 0) + val
    else:
        for g in grupos or []:
            mes = g.get("ano_mes")
            if mes:
                por_mes[mes] = por_mes.get(mes, 0) + (g.get("valor") or 0)
    meses = sorted(por_mes)
    return {"tipo": "grafico", "subtipo": "bar", "titulo": _titulo(ind),
            "labels": meses, "datasets": [{"label": _titulo(ind), "dados": [por_mes[m] for m in meses]}]}


def montar_visao(snaps: list[dict]) -> list[dict]:
    """Pura: transforma snapshots [{indicador, valor, detalhe}] em blocos de tela."""
    blocos: list[dict] = []
    for s in snaps:
        ind, valor, det = s["indicador"], s.get("valor"), s.get("detalhe")
        if ind == "radar_recebiveis" and isinstance(det, dict):
            blocos += _bloco_radar(det)
        elif ind in ("raiox_estabelecimento", "raiox_raiz") and isinstance(det, dict):
            blocos += _bloco_raiox(det)
        elif ind in LABELS or (det is None):
            blocos.append({"tipo": "labels", "titulo": _titulo(ind),
                           "itens": [{"rotulo": _titulo(ind), "valor": valor}]})
        elif ind in GRAFICOS and isinstance(det, dict):
            blocos.append(_grafico_por_mes(ind, det))
        elif isinstance(det, dict) and "grupos" in det:
            blocos.append(_bloco_grupos(ind, det))
        else:
            blocos.append({"tipo": "labels", "titulo": _titulo(ind),
                           "itens": [{"rotulo": _titulo(ind), "valor": valor}]})
    return blocos


# ───────────────────────── App ─────────────────────────

def criar_app():
    from fastapi import FastAPI, Request, UploadFile
    from fastapi.responses import HTMLResponse, RedirectResponse
    from fastapi.templating import Jinja2Templates

    app = FastAPI(title="Cockpit de Recebíveis — v0")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    def _num(v):
        if v is None:
            return "—"
        try:
            f = float(v)
        except (TypeError, ValueError):
            return str(v)
        return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    templates.env.filters["num"] = _num

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        return templates.TemplateResponse(request, "upload.html")

    @app.post("/processar", response_class=HTMLResponse)
    async def processar(request: Request, arquivos: list[UploadFile]):
        resultados, erros = [], []
        with db.conectar() as conn:
            for up in arquivos:
                try:
                    conteudo = await up.read()
                    resultados.append(ingest.processar_arquivo(
                        conn, up.filename, conteudo, fallback_date=date.today()))
                except Exception as exc:  # noqa: BLE001 — mostra o erro do arquivo na tela
                    erros.append({"arquivo": up.filename, "erro": str(exc)})
            ctx = contexto_mod.ler_contexto(conn)
            n = runner.executar(conn, ctx, date.today())
            conn.commit()
        return templates.TemplateResponse(request, "upload.html", {
            "resultados": resultados, "erros": erros, "n_indicadores": n})

    @app.post("/recalcular", response_class=HTMLResponse)
    def recalcular(request: Request):
        # recomputa os indicadores a partir dos dados já carregados (sem novo upload)
        with db.conectar() as conn:
            ctx = contexto_mod.ler_contexto(conn)
            n = runner.executar(conn, ctx, date.today())
            conn.commit()
        return templates.TemplateResponse(request, "upload.html",
                                          {"resultados": [], "erros": [], "n_indicadores": n})

    @app.get("/indicadores", response_class=HTMLResponse)
    def indicadores(request: Request, escopo: str = "loja", chave: str | None = None):
        with db.conectar() as conn, conn.cursor() as cur:
            cur.execute("select t.cnpj, coalesce(t.razao_social, t.cnpj) from core.indicador_snapshot s "
                        "join core.titular t on t.id = s.titular_id where s.escopo='loja' "
                        "group by t.cnpj, t.razao_social order by 2")
            lojas = [{"chave": r[0], "nome": r[1]} for r in cur.fetchall()]
            cur.execute("select distinct cnpj_raiz from core.indicador_snapshot where escopo='grupo' "
                        "and cnpj_raiz is not null order by 1")
            grupos = [{"chave": r[0], "nome": r[0]} for r in cur.fetchall()]

            blocos = []
            if chave:
                if escopo == "loja":
                    cur.execute(
                        "select indicador, valor, detalhe from core.indicador_snapshot "
                        "where escopo='loja' and titular_id=(select id from core.titular where cnpj=%s) "
                        "and data_referencia=(select max(data_referencia) from core.indicador_snapshot "
                        "where escopo='loja' and titular_id=(select id from core.titular where cnpj=%s))",
                        (chave, chave))
                else:
                    cur.execute(
                        "select indicador, valor, detalhe from core.indicador_snapshot "
                        "where escopo='grupo' and cnpj_raiz=%s and data_referencia="
                        "(select max(data_referencia) from core.indicador_snapshot where escopo='grupo' and cnpj_raiz=%s)",
                        (chave, chave))
                snaps = [{"indicador": r[0], "valor": float(r[1]) if r[1] is not None else None,
                          "detalhe": r[2]} for r in cur.fetchall()]
                blocos = montar_visao(snaps)
        return templates.TemplateResponse(request, "indicadores.html", {
            "escopo": escopo, "chave": chave,
            "lojas": lojas, "grupos": grupos, "blocos": blocos})

    return app


app = None  # criado sob demanda por criar_app() (evita exigir fastapi nos testes puros)
