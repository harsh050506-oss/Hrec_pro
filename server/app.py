import os
from datetime import timedelta
from urllib.parse import urlencode

from dotenv import load_dotenv
from flask import Flask, send_from_directory, jsonify, redirect, url_for, request, session
from flask_cors import CORS
from flask_dance.contrib.google import make_google_blueprint, google
from flask_mail import Mail

from utils.db import DbUnavailable, init_db
from utils.security import create_token
from routes.auth import auth_bp
from routes.jobs import jobs_bp
from routes.applications import applications_bp
from routes.resumes import resumes_bp
from routes.interviews import interviews_bp
from routes.tasks import tasks_bp
from routes.performance import performance_bp
from routes.notifications import notifications_bp
from routes.users import users_bp
from utils.analytics import hiring_funnel_counts, performance_series

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


def create_app():
    app = Flask(__name__, static_folder=None)

    app.secret_key = os.getenv("HREC_SECRET_KEY", "dev-secret-change-me")

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    app.config["JWT_EXPIRES_MINUTES"] = int(os.getenv("HREC_JWT_EXPIRES_MINUTES", "720"))
    app.config["UPLOAD_DIR"] = os.path.join(os.path.dirname(__file__), "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

    app.config.update(
        MAIL_SERVER=os.getenv("MAIL_SERVER"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    )

    mail = Mail(app)
    app.mail = mail

    app.permanent_session_lifetime = timedelta(
        minutes=app.config["JWT_EXPIRES_MINUTES"]
    )

    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if google_client_id and google_client_secret:
        google_bp = make_google_blueprint(
            client_id=google_client_id,
            client_secret=google_client_secret,
            scope=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            redirect_to="google_login_success",
        )
        app.register_blueprint(google_bp, url_prefix="/login")

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(applications_bp, url_prefix="/api/applications")
    app.register_blueprint(resumes_bp, url_prefix="/api/resumes")
    app.register_blueprint(interviews_bp, url_prefix="/api/interviews")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    app.register_blueprint(performance_bp, url_prefix="/api/performance")
    app.register_blueprint(notifications_bp, url_prefix="/api/notifications")
    app.register_blueprint(users_bp, url_prefix="/api/users")

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    @app.errorhandler(DbUnavailable)
    def handle_db_unavailable(e):
        return jsonify({"error": str(e)}), 503

    @app.get("/api/analytics/hiring-funnel")
    def analytics_hiring_funnel():
        return jsonify({"funnel": hiring_funnel_counts()})

    @app.get("/api/analytics/performance")
    def analytics_performance():
        limit = int(request.args.get("limit", "30"))
        return jsonify({"series": performance_series(limit=limit)})

    @app.get("/google-login-start")
    def google_login_start():
        role = (request.args.get("role") or "Candidate").strip()

        if role.lower() == "hr":
            role = "HR"
        elif role.lower() == "employee":
            role = "Employee"
        else:
            role = "Candidate"

        session["google_role"] = role
        return redirect(url_for("google.login"))

    @app.get("/google-login-success")
    def google_login_success():
        if not google.authorized:
            return redirect(url_for("google.login"))

        resp = google.get("/oauth2/v2/userinfo")
        if not resp.ok:
            return jsonify({"error": "Google fetch failed"}), 400

        info = resp.json()
        email = (info.get("email") or "").strip().lower()
        name = (info.get("name") or "Google User").strip()

        if not email:
            return jsonify({"error": "No email from Google"}), 400

        role = session.pop("google_role", "Candidate").strip()
        if role.lower() == "hr":
            role = "HR"
        elif role.lower() == "employee":
            role = "Employee"
        else:
            role = "Candidate"

        db = init_db()
        user = db.users.find_one({"email": email})

        if user:
            user_doc = user
        else:
            user_doc = {
                "name": name,
                "email": email,
                "password": None,
                "role": role,
            }
            inserted = db.users.insert_one(user_doc)
            user_doc["_id"] = inserted.inserted_id

        final_role = str(user_doc.get("role") or "Candidate").strip()
        if final_role.lower() == "hr":
            final_role = "HR"
        elif final_role.lower() == "employee":
            final_role = "Employee"
        else:
            final_role = "Candidate"

        jwt_token = create_token(str(user_doc["_id"]), final_role)

        query = urlencode(
            {
                "token": jwt_token,
                "name": user_doc.get("name", ""),
                "email": user_doc.get("email", ""),
                "role": final_role,
            }
        )

        return redirect(f"http://127.0.0.1:5000/dashboard.html?{query}")

    client_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "client"))

    @app.get("/")
    def root():
        return send_from_directory(client_dir, "index.html")

    @app.get("/<path:path>")
    def client_files(path):
        return send_from_directory(client_dir, path)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)