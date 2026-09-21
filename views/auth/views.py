from __future__ import annotations

from flask import flash, redirect, render_template, request, session, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from components.auth.rate_limit import LoginRateLimiter
from components.security.csrf import rotate_csrf_token
from models.users import User
from utils.hash_password import verify_password


class LoginPage(MethodView):
    def get(self):
        if session.get("user_id"):
            return redirect(url_for("admin.publication.index"))
        return render_template("dashboard/auth/index.html")

    @with_db_session
    def post(self, db_session: Session):
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or len(email) > 320 or not password or len(password) > 1024:
            flash("Неправильный логин и/или пароль", "error")
            return redirect(url_for("auth.login"))

        try:
            if LoginRateLimiter.blocked(email):
                flash("Слишком много попыток входа. Повторите позже.", "error")
                return redirect(url_for("auth.login"))
        except RuntimeError:
            flash("Вход временно недоступен. Повторите позже.", "error")
            return redirect(url_for("auth.login"))

        user = db_session.query(User).filter(User.email == email).first()
        valid = user is not None and verify_password(password, user.hash_password)

        if not valid:
            try:
                LoginRateLimiter.record_failure(email)
            except RuntimeError:
                flash("Вход временно недоступен. Повторите позже.", "error")
                return redirect(url_for("auth.login"))

            flash("Неправильный логин и/или пароль", "error")
            return redirect(url_for("auth.login"))

        LoginRateLimiter.clear(email)

        session.clear()
        rotate_csrf_token()
        session["login"] = user.email
        session["user_id"] = str(user.id)
        session.permanent = True

        return redirect(url_for("admin.publication.index"))


class LogoutUser(MethodView):
    @login_required
    def post(self):
        session.clear()
        return redirect(url_for("auth.login"))
