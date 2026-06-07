"""
app/services/semantic_layer.py — Metrik Sözlüğü (Semantic Layer).

İş terimlerinin ('gecikme', 'aktif sevkiyat', 'toplam miktar') SQL karşılığını tek yerde
tanımlar → NL→SQL üretiminde LLM tahmin yürütmek yerine TANIMLI ifadeyi kullanır
(tutarlı, doğru KPI). Rollup ölçüleriyle tek kaynak olacak şekilde tasarlandı.

Scope: company + integration_id (paylaşılan `shipments` tablosu nedeniyle tablo adı tek
başına yetmez). company=NULL/ALL ve integration_id=NULL → global (her firma/entegrasyon).

Tablo idempotent oluşur (_ensure_table). CRUD + prompt enjeksiyonu yardımcıları burada.
"""

from __future__ import annotations

import datetime as _dt

from app.services.db import get_connection


# ─────────────────────────────────────────────────────────────────────────────
def _ensure_table():
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'semantic_metrics')
            CREATE TABLE semantic_metrics (
                id             INT IDENTITY(1,1) PRIMARY KEY,
                company        NVARCHAR(50)  NULL,
                integration_id INT           NULL,
                table_name     NVARCHAR(128) NULL,
                metric_key     NVARCHAR(100) NOT NULL,
                label          NVARCHAR(200) NULL,
                description    NVARCHAR(500) NULL,
                metric_type    NVARCHAR(20)  NOT NULL DEFAULT 'measure',
                expression     NVARCHAR(1000) NOT NULL,
                unit           NVARCHAR(50)  NULL,
                synonyms       NVARCHAR(500) NULL,
                is_active      BIT NOT NULL DEFAULT 1,
                created_at     DATETIME2 DEFAULT SYSDATETIME(),
                updated_at     DATETIME2 DEFAULT SYSDATETIME()
            )
        """)
        conn.commit()
    finally:
        conn.close()


try:
    _ensure_table()
except Exception as _e:
    print(f"[SEMANTIC] Tablo oluşturma atlandı (DB yok?): {_e}")


# ─────────────────────────────────────────────────────────────────────────────
def _row_to_dict(row, cols) -> dict:
    d = dict(zip(cols, row))
    for k in ("created_at", "updated_at"):
        if isinstance(d.get(k), _dt.datetime):
            d[k] = d[k].strftime("%Y-%m-%d %H:%M")
    d["is_active"] = bool(d.get("is_active"))
    d["synonym_list"] = [s.strip() for s in (d.get("synonyms") or "").split(",") if s.strip()]
    return d


def list_metrics(company: str | None = None, only_active: bool = False) -> list[dict]:
    """Yönetim listesi. company verilirse o firma + global; admin (ALL/None) → hepsi."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        where, params = [], []
        if company and company != "ALL":
            where.append("(company = ? OR company IS NULL OR company = 'ALL')")
            params.append(company)
        if only_active:
            where.append("is_active = 1")
        sql = "SELECT * FROM semantic_metrics"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY table_name, metric_key"
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [_row_to_dict(r, cols) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_for(company: str | None, integration_ids: list[int] | None) -> list[dict]:
    """
    NL→SQL için geçerli AKTİF metrikler:
      - company eşleşir veya global (NULL/ALL)
      - integration_id verilenlerden biri veya global (NULL)
    """
    conn = get_connection()
    cur  = conn.cursor()
    try:
        where  = ["is_active = 1"]
        params: list = []
        if company and company != "ALL":
            where.append("(company = ? OR company IS NULL OR company = 'ALL')")
            params.append(company)
        if integration_ids:
            ph = ",".join("?" * len(integration_ids))
            where.append(f"(integration_id IN ({ph}) OR integration_id IS NULL)")
            params.extend(integration_ids)
        cur.execute("SELECT * FROM semantic_metrics WHERE " + " AND ".join(where), params)
        cols = [c[0] for c in cur.description]
        return [_row_to_dict(r, cols) for r in cur.fetchall()]
    finally:
        conn.close()


def get_metric(metric_id: int) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM semantic_metrics WHERE id = ?", (metric_id,))
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return _row_to_dict(row, cols) if row else None
    finally:
        conn.close()


def create_metric(data: dict) -> dict:
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO semantic_metrics
              (company, integration_id, table_name, metric_key, label, description,
               metric_type, expression, unit, synonyms, is_active)
            OUTPUT INSERTED.id
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("company"), data.get("integration_id"), data.get("table_name"),
            (data.get("metric_key") or "").strip(), data.get("label"),
            data.get("description"), (data.get("metric_type") or "measure"),
            (data.get("expression") or "").strip(), data.get("unit"),
            data.get("synonyms"),
            1 if data.get("is_active", True) else 0,
        ))
        new_id = cur.fetchone()[0]
        conn.commit()
        return get_metric(new_id)
    finally:
        conn.close()


def update_metric(metric_id: int, data: dict) -> dict | None:
    fields = ["company", "integration_id", "table_name", "metric_key", "label",
              "description", "metric_type", "expression", "unit", "synonyms"]
    sets, params = [], []
    for f in fields:
        if f in data:
            sets.append(f"{f} = ?")
            params.append(data[f])
    if "is_active" in data:
        sets.append("is_active = ?")
        params.append(1 if data["is_active"] else 0)
    if not sets:
        return get_metric(metric_id)
    sets.append("updated_at = SYSDATETIME()")
    params.append(metric_id)
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute(f"UPDATE semantic_metrics SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return get_metric(metric_id)
    finally:
        conn.close()


def delete_metric(metric_id: int) -> bool:
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM semantic_metrics WHERE id = ?", (metric_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# NL→SQL prompt yardımcıları
# ─────────────────────────────────────────────────────────────────────────────
def format_for_prompt(metrics: list[dict]) -> str:
    """Metrik listesini NL→SQL prompt bloğuna çevirir."""
    if not metrics:
        return ""
    lines = []
    for m in metrics:
        syn = m.get("synonym_list") or []
        syn_txt = f"  [eş anlamlı: {', '.join(syn)}]" if syn else ""
        kind = m.get("metric_type") or "measure"
        lines.append(
            f"- {m['metric_key']}"
            + (f" ({m['label']})" if m.get("label") else "")
            + f" [{kind}]: {m['expression']}"
            + (f"  — {m['description']}" if m.get("description") else "")
            + syn_txt
        )
    return (
        "\n=== METRİK SÖZLÜĞÜ (Semantic Layer) ===\n"
        "Kullanıcı aşağıdaki iş terimlerinden birini kastediyorsa, TANIMLI SQL ifadesini "
        "AYNEN kullan (kendi yorumunu üretme). 'measure' = SELECT/aggregate ifadesi, "
        "'filter' = WHERE koşulu, 'dimension' = GROUP BY kolonu.\n"
        "ÖNEMLİ: Bu ifadeler YALNIZ HAM (detay) tablolar içindir. Bir ROLLUP/özet tablo "
        "(*_daily) kullanıyorsan bu ham-kolon ifadelerini KULLANMA; rollup tablosunun kendi "
        "hazır ölçü kolonlarını (ör. shipment_count, item_count, total_qty) kullan.\n"
        + "\n".join(lines)
    )


_TR_MAP = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")


def _norm(s: str) -> str:
    """Küçük harf + Türkçe karakter sadeleştirme (eşleşme dayanıklılığı için)."""
    return (s or "").lower().translate(_TR_MAP)


def detect_used(question: str, metrics: list[dict]) -> list[dict]:
    """Soruda geçen metrikleri anahtar/etiket/eş-anlamlı eşleşmesiyle bulur (LLM'siz)."""
    q = _norm(question)
    used = []
    for m in metrics:
        needles = [m.get("metric_key", ""), m.get("label", "")] + (m.get("synonym_list") or [])
        for n in needles:
            nn = _norm((n or "").strip())
            if nn and nn in q:
                used.append({"key": m["metric_key"], "label": m.get("label") or m["metric_key"]})
                break
    return used
