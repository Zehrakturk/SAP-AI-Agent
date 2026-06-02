from flask import Flask, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# Yeni fetcher modülü — Factory pattern
from app.services.fetchers import fetch_all_active

# Insights motoru
from app.services.insights import generate_insights

# Human-in-the-loop ingestion worker
from app.services.ingestion import process_pending_jobs


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
    # 02:00 — tüm aktif entegrasyonlardan veri çek
    scheduler.add_job(fetch_all_active, "cron", hour=2, minute=0)
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

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return render_template("index.html")

    return app