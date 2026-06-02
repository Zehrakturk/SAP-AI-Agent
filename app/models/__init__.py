from flask import Flask, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.sap_fetcher import fetch_and_store

def create_app():
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates",
    )
    app.config["SECRET_KEY"] = "sap-ai-portal-dev-secret"
    app.config["DEBUG"] = True

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Scheduler — her gece 02:00'de çalışır
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store, "cron", hour=2, minute=0)
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

    app.register_blueprint(auth_bp,            url_prefix="/api/v1/auth")
    app.register_blueprint(users_bp,           url_prefix="/api/v1/users")
    app.register_blueprint(chats_bp,           url_prefix="/api/v1/chats")
    app.register_blueprint(logs_bp,            url_prefix="/api/v1/logs")
    app.register_blueprint(analytics_bp,       url_prefix="/api/v1/analytics")
    app.register_blueprint(settings_bp,        url_prefix="/api/v1/settings")
    app.register_blueprint(query_bp,           url_prefix="/api/v1/query")
    app.register_blueprint(integrations_bp,    url_prefix="/api/v1/integrations")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return render_template("index.html")

    return app