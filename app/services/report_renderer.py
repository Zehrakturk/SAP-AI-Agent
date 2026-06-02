"""
app/services/report_renderer.py — Sprint 2.2

HTML rapor üretir; mümkünse WeasyPrint ile PDF'e çevirir.
WeasyPrint yoksa (Windows'ta GTK gerektirir) HTML byte'ları döner —
caller `pdf_available` bayrağına göre attachment uzantısını belirler.
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime
from typing import Any

try:
    from weasyprint import HTML  # type: ignore
    _WEASY_OK = True
except Exception:
    _WEASY_OK = False


def pdf_available() -> bool:
    return _WEASY_OK


# ─────────────────────────────────────────────────────────────────────────────

def _esc(v: Any) -> str:
    return _html.escape(str(v) if v is not None else "")


def _table_html(rows: list[dict], limit: int = 50) -> str:
    if not rows:
        return "<p style='color:#888'>Veri yok.</p>"
    cols = list(rows[0].keys())
    head = "".join(f"<th>{_esc(c)}</th>" for c in cols)
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(r.get(c))}</td>" for c in cols) + "</tr>"
        for r in rows[:limit]
    )
    extra = f"<p style='color:#888;font-size:11px'>+ {len(rows) - limit} kayıt daha</p>" if len(rows) > limit else ""
    return (
        "<table><thead><tr>" + head + "</tr></thead><tbody>"
        + body + "</tbody></table>" + extra
    )


def _kpi_html(kpis: list[dict]) -> str:
    if not kpis:
        return ""
    cards = "".join(
        f"<div class='kpi'><div class='kpi-label'>{_esc(k.get('label',''))}</div>"
        f"<div class='kpi-value'>{_esc(k.get('value',''))}</div>"
        f"<div class='kpi-change'>{_esc(k.get('change') or '')}</div></div>"
        for k in kpis
    )
    return f"<div class='kpi-row'>{cards}</div>"


def _highlights_html(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_esc(h)}</li>" for h in items)
    return f"<div class='highlights'><h3>Öne Çıkanlar</h3><ul>{lis}</ul></div>"


def render_report_html(report: dict) -> str:
    """`report` payload'undan tek dosya HTML raporu üretir."""
    question  = report.get("question", "")
    summary   = report.get("summary", "")
    rows      = report.get("rows", [])
    count     = report.get("count", len(rows))
    sql       = report.get("sql", "")
    kpis      = report.get("kpis", [])
    highlights = report.get("highlights", [])
    chart_data = report.get("chart_data", {})
    tables     = ", ".join(report.get("tables_used") or [])
    when       = datetime.now().strftime("%d.%m.%Y %H:%M")

    chart_block = (
        f"<details><summary>Grafik Verisi (JSON)</summary>"
        f"<pre>{_esc(json.dumps(chart_data, ensure_ascii=False, indent=2))}</pre></details>"
        if chart_data else ""
    )
    sql_block = (
        f"<details><summary>SQL</summary><pre>{_esc(sql)}</pre></details>"
        if sql else ""
    )

    return f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8"><title>SAP-AI Rapor</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color:#222; font-size:12px; line-height:1.55; }}
  h1 {{ font-size:20px; margin:0 0 4px; color:#1a56db; }}
  h2 {{ font-size:14px; margin:18px 0 8px; color:#374151; border-bottom:1px solid #e5e7eb; padding-bottom:4px; }}
  h3 {{ font-size:13px; margin:10px 0 6px; color:#1e40af; }}
  .meta {{ color:#6b7280; font-size:11px; margin-bottom:14px; }}
  .summary {{ background:#f8fafc; border-left:3px solid #1a56db; padding:10px 12px; margin:8px 0 14px; }}
  .kpi-row {{ display:flex; gap:10px; margin:10px 0; flex-wrap:wrap; }}
  .kpi {{ flex:1; min-width:120px; border:1px solid #e5e7eb; border-top:3px solid #1a56db;
          border-radius:6px; padding:8px 10px; }}
  .kpi-label {{ font-size:10px; color:#6b7280; text-transform:uppercase; }}
  .kpi-value {{ font-size:18px; font-weight:700; color:#111827; margin-top:2px; }}
  .kpi-change {{ font-size:11px; color:#10b981; margin-top:2px; }}
  .highlights ul {{ margin:4px 0 10px 18px; padding:0; }}
  table {{ width:100%; border-collapse:collapse; margin-top:6px; font-size:11px; }}
  th, td {{ border:1px solid #e5e7eb; padding:5px 7px; text-align:left; }}
  th {{ background:#f1f5f9; font-weight:600; }}
  pre {{ background:#0f172a; color:#7dd3fc; padding:8px 10px; border-radius:6px;
         font-size:10px; white-space:pre-wrap; word-break:break-word; }}
  details {{ margin-top:10px; }}
  summary {{ cursor:pointer; color:#6b7280; font-size:11px; }}
  .footer {{ margin-top:20px; padding-top:10px; border-top:1px solid #e5e7eb;
             font-size:10px; color:#9ca3af; }}
</style></head><body>
  <h1>SAP-AI Analiz Raporu</h1>
  <div class="meta">Oluşturulma: {when} · Kayıt sayısı: {count} · Tablo: {_esc(tables) or '—'}</div>

  <h2>Soru</h2>
  <div class="summary"><b>{_esc(question)}</b></div>

  <h2>Özet</h2>
  <div class="summary">{_esc(summary).replace(chr(10), '<br>')}</div>

  {_kpi_html(kpis)}
  {_highlights_html(highlights)}

  <h2>Veri Tablosu</h2>
  {_table_html(rows)}

  {chart_block}
  {sql_block}

  <div class="footer">SAP-AI Copilot · otomatik üretilmiştir</div>
</body></html>"""


def render_pdf_bytes(report: dict) -> tuple[bytes, str, str]:
    """
    Rapor payload'undan ikili dosya üretir.
    Döner: (bytes, mime_type, file_extension)
    WeasyPrint varsa PDF, yoksa HTML döner.
    """
    html_text = render_report_html(report)
    if _WEASY_OK:
        pdf_bytes = HTML(string=html_text).write_pdf()
        return pdf_bytes, "application/pdf", "pdf"
    return html_text.encode("utf-8"), "text/html; charset=utf-8", "html"
