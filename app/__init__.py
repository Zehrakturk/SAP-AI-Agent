import sys
import logging

# .env'i EN BAŞTA ve override=True ile yükle — sistem ortamında eski bir OPENAI_API_KEY
# (veya DB/SAP) varsa, .env dosyası YETKİLİ olsun. Aksi halde load_dotenv() sistem
# değişkenini ezmez ve eski/yanlış anahtar kullanılır (OpenAI client import'ta oluşuyor).
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(override=True)

# Windows konsolu (cp1254) Unicode karakterleri (←, →, emoji, Türkçe) basamaz ve
# print() sırasında UnicodeEncodeError fırlatır → SOAP fetch / insight üretimi çöker.
# Tüm çıktıyı UTF-8'e zorla (tek noktadan, tüm giriş yolları için).
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8")
    except Exception:
        pass

# Werkzeug dev-server her API isteği için "127.0.0.1 ... 200" satırı basar.
# Polling (admin zili 12sn, onay 4sn) yüzünden konsolu doldurur → sadece uyarı+üstü göster.
logging.getLogger("werkzeug").setLevel(logging.WARNING)

from flask import Flask, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# Yeni fetcher modülü — Factory pattern
from app.services.fetchers import fetch_all_active

# Insights motoru
from app.services.insights import generate_insights

# Human-in-the-loop ingestion worker
from app.services.ingestion import process_pending_jobs

# Veri yaşam döngüsü (rollup + retention) — MSSQL şişmesini engeller
from app.services.lifecycle import run_nightly_maintenance


def create_app():
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )
    app.config["SECRET_KEY"] = "sap-ai-portal-dev-secret"
    app.config["DEBUG"] = True

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Scheduler
    scheduler = BackgroundScheduler()
    # 02:00 — tüm aktif entegrasyonlardan veri çek (artımlı: sadece yeni veri)
    scheduler.add_job(fetch_all_active, "cron", hour=2, minute=0)
    # 02:30 — veri yaşam döngüsü bakımı (rollup → retention) — şişmeyi engeller
    scheduler.add_job(run_nightly_maintenance, "cron", hour=2, minute=30)
    # 03:00 — gece veri çekildikten sonra insight üret
    scheduler.add_job(lambda: generate_insights(), "cron", hour=3, minute=0)
    # Her 5 sn — onaylanmış ingestion job'larını işle (fetch→index→rerun)
    scheduler.add_job(process_pending_jobs, "interval", seconds=5,
                      max_instances=1, coalesce=True)
    scheduler.start()

    # Blueprint'ler
    from app.api.auth         import auth_bp
    from app.api.users        import users_bp
    from app.api.chats        import chats_bp
    from app.api.logs         import logs_bp
    from app.api.analytics    import analytics_bp
    from app.api.settings     import settings_bp
    from app.api.query        import query_bp
    from app.api.integrations import integrations_bp
    from app.api.enhance      import enhance_bp
    from app.api.insights     import insights_bp
    from app.api.reports      import reports_bp
    from app.api.approvals    import approvals_bp
    from app.api.documents    import documents_bp
    from app.api.lifecycle     import lifecycle_bp
    from app.api.semantics     import metrics_bp

    app.register_blueprint(auth_bp,          url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp,         url_prefix="/api/v1/users")
    app.register_blueprint(chats_bp,         url_prefix="/api/v1/chats")
    app.register_blueprint(logs_bp,          url_prefix="/api/v1/logs")
    app.register_blueprint(analytics_bp,     url_prefix="/api/v1/analytics")
    app.register_blueprint(settings_bp,      url_prefix="/api/v1/settings")
    app.register_blueprint(query_bp,         url_prefix="/api/v1/query")
    app.register_blueprint(integrations_bp,  url_prefix="/api/v1/integrations")
    app.register_blueprint(enhance_bp,       url_prefix="/api/v1/enhance")
    app.register_blueprint(insights_bp,      url_prefix="/api/v1/insights")
    app.register_blueprint(reports_bp,       url_prefix="/api/v1/reports")
    app.register_blueprint(approvals_bp,     url_prefix="/api/v1/approvals")
    app.register_blueprint(documents_bp,     url_prefix="/api/v1/documents")
    app.register_blueprint(lifecycle_bp,     url_prefix="/api/v1/lifecycle")
    app.register_blueprint(metrics_bp,       url_prefix="/api/v1/metrics")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return render_template("index.html")

    return app