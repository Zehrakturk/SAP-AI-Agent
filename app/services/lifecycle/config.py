"""
app/services/lifecycle/config.py — fact tablo + rollup tanımları.

Her fact tablo için:
  - date_col      : dönem (gün) kolonu
  - rollup_table  : özet tablo adı
  - group_dims    : GROUP BY'a giren boyutlar [(kaynak_kolon, hedef_kolon)]
  - label_cols    : boyutla 1:1 olan etiketler, MAX() ile taşınır [(sql_ifade, hedef_kolon)]
  - measures      : ölçüler [(hedef_kolon, sql_agg_ifadesi)]

NOT: shipments tablosu int=1 (Warmhaus) ve int=3 (Beyçelik) tarafından paylaşılır;
rollup her zaman integration_id + company ile gruplanır → firma izolasyonu korunur.
Press tablosu henüz fiziksel olmayabilir (veri çekilince oluşur) → modüller var olmayan
tabloyu zarifçe atlar.
"""

from __future__ import annotations

FACT_TABLES: dict[str, dict] = {
    "shipments": {
        "date_col": "ERDAT",
        "rollup_table": "shipments_daily",
        "group_dims": [
            ("ROUTE",       "route"),
            ("CITY1",       "city"),
            ("TDURUM",      "tdurum"),
            ("MUSTERI_ADI", "musteri"),
        ],
        "label_cols": [
            ("MAX(ROUTE_TNM)",  "route_name"),
            ("MAX(TDURUM_TNM)", "tdurum_name"),
            ("MAX(KUNNR)",      "kunnr"),
        ],
        "measures": [
            ("shipment_count", "COUNT(DISTINCT TKNUM)"),
            ("item_count",     "COUNT(*)"),
            ("total_qty",      "SUM(TRY_CAST(LFIMG AS FLOAT))"),
            ("avg_qty",        "AVG(TRY_CAST(LFIMG AS FLOAT))"),
            ("total_volume",   "SUM(TRY_CAST(VOLUM AS FLOAT))"),
        ],
    },
    # Press: üretim/OEE verisi. Alan semantiği (/BIC/...) tam net değil → v1 minimal:
    # sadece günlük kayıt sayısı. Admin Semantic Layer ile rafine edebilir.
    "Press": {
        "date_col": "CALDAY",
        "rollup_table": "press_daily",
        "group_dims": [],
        "label_cols": [],
        "measures": [
            ("record_count", "COUNT(*)"),
        ],
    },
}
