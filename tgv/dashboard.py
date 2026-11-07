"""Static HTML dashboard (one self-contained file, no server, no JS libraries).

Open out/dashboard.html in a browser. Owner-facing text is pt-BR.
"""
from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from tgv import db
from tgv.pipeline import ranking

CSS = """
:root{--bg:#f7f7f8;--panel:#fff;--text:#16181d;--muted:#5d6470;--line:#e2e4e9;--accent:#c2410c;
--ok:#15803d;--warn:#b45309;--err:#b91c1c;--chip:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--panel:#181b21;--text:#e8eaee;--muted:#9aa3af;
--line:#2a2f38;--accent:#fb923c;--ok:#4ade80;--warn:#fbbf24;--err:#f87171;--chip:#232831}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:32px 0 10px}
.sub{color:var(--muted);margin:0 0 20px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:12px}
.wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:640px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600}tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:var(--accent)}.chip{display:inline-block;background:var(--chip);border-radius:6px;padding:0 6px;
font-size:12px;margin:1px 2px 1px 0}.ok{color:var(--ok)}.warning,.skipped{color:var(--warn)}.error{color:var(--err)}
.empty{color:var(--muted);padding:14px}
"""

MODALITY = {"A_candidate": "A? (licença)", "B": "B original", "C": "C notícia", "skip": "—"}
CLAIM = {"confirmed": "oficial", "reported": "imprensa", "unverified": "NÃO verificado", "not_a_claim": "—"}


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _num(n) -> str:
    return "—" if n is None else f"{int(n):,}".replace(",", ".")


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<div class="wrap"><div class="empty">{_e(empty)}</div></div>'
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(rows_cell for rows_cell in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _count(conn, sql, *args) -> int:
    return conn.execute(sql, args).fetchone()[0]


def _latest_views(conn, item_id):
    r = conn.execute("SELECT views FROM metric_snapshots WHERE item_id=? ORDER BY captured_at DESC LIMIT 1",
                     (item_id,)).fetchone()
    return r["views"] if r else None


def _item_rows(conn, rows):
    out = []
    for r in rows:
        flags = json.loads(r["flags"] or "[]")
        bd = json.loads(r["score_breakdown"] or "{}")
        out.append([
            f'<td class="num">{r["score"] or 0:.1f}</td>',
            f'<td><a href="{_e(r["url"])}" rel="noopener noreferrer">{_e(r["title"])}</a><br>'
            f'<span class="chip">{_e(r["source_name"])}</span>'
            + "".join(f'<span class="chip">{_e(f)}</span>' for f in flags) + "</td>",
            f'<td>{_e(MODALITY.get(r["modality"], r["modality"]))}</td>',
            f'<td>{_e(CLAIM.get(r["claim_status"], r["claim_status"]))}</td>',
            f'<td class="num">{_num(_latest_views(conn, r["id"]))}</td>',
            f'<td class="num">{_num(bd.get("views_per_hour"))}</td>',
            f'<td class="num">{_e(r["coverage"]) if "coverage" in r.keys() else "—"}</td>',
            f'<td>{_e(r["published_at"][:16].replace("T", " "))}</td>',
        ])
    return out


def render(conn: sqlite3.Connection, now: datetime) -> str:
    day_ago = db.iso(now - timedelta(hours=24))
    kpis = [
        ("Encontrados (24h)", _count(conn, "SELECT COUNT(*) FROM items WHERE first_seen_at >= ?", day_ago)),
        ("Aguardando revisão", _count(conn, "SELECT COUNT(*) FROM items WHERE status='review'")),
        ("Selecionados", _count(conn, "SELECT COUNT(*) FROM items WHERE status='selected'")),
        ("Em produção", _count(conn, "SELECT COUNT(*) FROM productions WHERE status IN ('draft','rendering','review')")),
        ("Programados", _count(conn, "SELECT COUNT(*) FROM publications WHERE status='scheduled'")),
        ("Publicados", _count(conn, "SELECT COUNT(*) FROM publications WHERE status='published'")),
        ("Alertas abertos", _count(conn, "SELECT COUNT(*) FROM alerts WHERE resolved=0 AND level!='info'")),
    ]
    revenue = conn.execute(
        "SELECT currency, SUM(amount_cents) c FROM revenue WHERE confirmed=1 GROUP BY currency").fetchall()
    rev_text = " · ".join(f"{r['currency']} {r['c'] / 100:,.2f}" for r in revenue) or "nenhuma confirmada"

    headers = ["Score", "Conteúdo", "Modalidade", "Afirmação", "Views", "Views/h", "Fontes", "Publicado (UTC)"]
    top = _table(headers, _item_rows(conn, ranking(conn, 25, ("found", "selected"))),
                 "Nada encontrado ainda. Rode: python -m tgv run")
    review = _table(headers, _item_rows(conn, ranking(conn, 25, ("review",))),
                    "Nenhum item aguardando revisão.")

    runs = conn.execute(
        """SELECT * FROM runs r WHERE id = (SELECT MAX(id) FROM runs x WHERE x.source = r.source)
           ORDER BY source""").fetchall()
    runs_html = _table(["Fonte", "Status", "Lidos", "Novos", "Quando (UTC)", "Detalhe"], [[
        f"<td>{_e(r['source'])}</td>", f'<td class="{_e(r["status"])}">{_e(r["status"])}</td>',
        f'<td class="num">{r["fetched"]}</td>', f'<td class="num">{r["new_items"]}</td>',
        f"<td>{_e(r['started_at'][:16].replace('T', ' '))}</td>", f"<td>{_e(r['error'] or '')}</td>",
    ] for r in runs], "Nenhuma execução registrada.")

    alerts = conn.execute(
        "SELECT * FROM alerts WHERE resolved=0 AND level!='info' ORDER BY id DESC LIMIT 30").fetchall()
    alerts_html = _table(["Nível", "Componente", "Mensagem", "Quando (UTC)"], [[
        f'<td class="{_e(a["level"])}">{_e(a["level"])}</td>', f"<td>{_e(a['component'])}</td>",
        f"<td>{_e(a['message'])}</td>", f"<td>{_e(a['created_at'][:16].replace('T', ' '))}</td>",
    ] for a in alerts], "Sem alertas abertos.")

    prods = conn.execute(
        """SELECT p.*, i.title, i.url FROM productions p LEFT JOIN items i ON i.id = p.item_id
           ORDER BY p.id DESC LIMIT 20""").fetchall()

    def _file(path, label):
        return f'<a href="file://{_e(path)}">{label}</a>' if path else ""

    prods_html = _table(["Status", "Pauta", "Roteiro", "Arquivos", "Observações"], [[
        f'<td class="{"error" if p["status"] == "failed" else "warning" if p["status"] == "review" else "ok"}">'
        f'{_e(p["status"])}</td>',
        f'<td><a href="{_e(p["url"])}" rel="noopener noreferrer">{_e(p["title"])}</a></td>',
        f"<td>{_e(p['writer'])} · {_e(p['modality'])}</td>",
        "<td>" + " · ".join(x for x in (_file(p["media_path"], "vídeo"), _file(p["cover_path"], "capa"),
                                         _file(p["carousel_dir"], "carrossel")) if x) + "</td>",
        f"<td>{_e(p['review_notes'] or '')}</td>",
    ] for p in prods], "Nenhuma produção ainda. Rode: python -m tgv produce")

    pubs = conn.execute("SELECT * FROM publications ORDER BY id DESC LIMIT 20").fetchall()
    pubs_html = _table(["Rede", "Status", "Agendado", "Publicado", "Link"], [[
        f"<td>{_e(p['platform'])}</td>", f"<td>{_e(p['status'])}</td>", f"<td>{_e(p['scheduled_for'])}</td>",
        f"<td>{_e(p['published_at'])}</td>",
        f'<td><a href="{_e(p["permalink"])}">abrir</a></td>' if p["permalink"] else "<td>—</td>",
    ] for p in pubs], "Distribuição ainda não ativada (etapa 4). Nada é publicado sem a sua autorização.")

    programs = conn.execute("SELECT * FROM monetization_programs ORDER BY platform").fetchall()
    prog_html = _table(["Rede", "Programa", "Status", "Evidência", "Conferido"], [[
        f"<td>{_e(p['platform'])}</td>", f"<td>{_e(p['program'])}</td>", f"<td>{_e(p['status'])}</td>",
        f"<td>{_e(p['evidence'])}</td>", f"<td>{_e(p['checked_at'])}</td>",
    ] for p in programs], "Nenhuma elegibilidade confirmada pelas plataformas (etapa 6).")

    kpi_html = "".join(f'<div class="kpi"><b>{_e(v)}</b><span>{_e(k)}</span></div>' for k, v in kpis)
    kpi_html += f'<div class="kpi"><b style="font-size:16px">{_e(rev_text)}</b><span>Receita confirmada</span></div>'

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>TGV BR Auto</title>
<style>{CSS}</style></head><body><main>
<h1>The Game Verse BR — painel</h1>
<p class="sub">Gerado em {_e(now.strftime('%d/%m/%Y %H:%M'))} UTC · foco: GTA VI</p>
<div class="kpis">{kpi_html}</div>
<h2>Melhores oportunidades (uma por história)</h2>{top}
<h2>Fila de revisão humana (rumor, vazamento ou licença a conferir)</h2>{review}
<h2>Produções (aguardando sua revisão)</h2>{prods_html}
<h2>Publicações</h2>{pubs_html}
<h2>Monetização</h2>{prog_html}
<h2>Fontes (última execução)</h2>{runs_html}
<h2>Erros e alertas</h2>{alerts_html}
</main></body></html>"""


def write(conn: sqlite3.Connection, now: datetime, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(conn, now), encoding="utf-8")
    return path
