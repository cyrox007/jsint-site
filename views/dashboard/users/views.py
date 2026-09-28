from __future__ import annotations

from uuid import UUID

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.publication import Publication
from models.users import User
from settings import config
from utils.hash_password import hash_password


def _current_user_id() -> UUID | None:
    raw = session.get("user_id")
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _normalized_email() -> str:
    return request.form.get("email", "").strip().lower()


def _validate_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Пароль должен содержать не менее 12 символов")
    if len(password) > 1024:
        raise ValueError("Пароль слишком длинный")
    return password


def _admin_users(session_db: Session) -> list[User]:
    return [
        user
        for user in session_db.query(User).order_by(User.email.asc()).all()
        if config.is_admin_email(user.email)
    ]


class UserManagementPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        users = db_session.query(User).order_by(User.email.asc()).all()
        return render_template(
            "dashboard/users/index.html",
            users=users,
            current_user_id=_current_user_id(),
            admin_emails=config.ADMIN_EMAILS,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        action = request.form.get("action", "").strip()
        if action == "create":
            return self._create(db_session)
        if action == "update":
            return self._update(db_session)
        if action == "password":
            return self._password(db_session)
        if action == "delete":
            return self._delete(db_session)
        abort(400)

    def _create(self, db_session: Session):
        email = _normalized_email()
        if not email or len(email) > 320 or "@" not in email:
            flash("Укажите корректный email", "error")
            return redirect(url_for("admin.users.index"))
        if db_session.query(User).filter(User.email == email).first() is not None:
            flash("Пользователь с таким email уже существует", "error")
            return redirect(url_for("admin.users.index"))

        try:
            password = _validate_password(request.form.get("password", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.users.index"))

        user = User(
            email=email,
            hash_password=hash_password(password),
            firstname=request.form.get("firstname", "").strip()[:255] or None,
            lastname=request.form.get("lastname", "").strip()[:255] or None,
        )
        db_session.add(user)
        db_session.commit()
        flash("Пользователь создан", "success")
        return redirect(url_for("admin.users.index"))

    def _get_user(self, db_session: Session) -> User:
        try:
            user_id = UUID(request.form.get("user_id", "").strip())
        except ValueError:
            abort(400)
        user = db_session.query(User).filter(User.id == user_id).first()
        if user is None:
            abort(404)
        return user

    def _update(self, db_session: Session):
        user = self._get_user(db_session)
        user.firstname = request.form.get("firstname", "").strip()[:255] or None
        user.lastname = request.form.get("lastname", "").strip()[:255] or None
        db_session.add(user)
        db_session.commit()
        flash("Профиль пользователя обновлён", "success")
        return redirect(url_for("admin.users.index"))

    def _password(self, db_session: Session):
        user = self._get_user(db_session)
        try:
            password = _validate_password(request.form.get("password", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.users.index"))
        user.hash_password = hash_password(password)
        db_session.add(user)
        db_session.commit()
        flash(f"Пароль для {user.email} обновлён", "success")
        return redirect(url_for("admin.users.index"))

    def _delete(self, db_session: Session):
        user = self._get_user(db_session)
        current_user_id = _current_user_id()
        if current_user_id == user.id:
            flash("Нельзя удалить собственную активную учётную запись", "error")
            return redirect(url_for("admin.users.index"))

        if config.is_admin_email(user.email) and len(_admin_users(db_session)) <= 1:
            flash("Нельзя удалить последнего администратора", "error")
            return redirect(url_for("admin.users.index"))

        db_session.query(Publication).filter(Publication.author_id == user.id).update(
            {Publication.author_id: None},
            synchronize_session=False,
        )
        db_session.delete(user)
        db_session.commit()
        flash("Пользователь удалён. Авторство публикаций сохранено без привязки к учётной записи.", "success")
        return redirect(url_for("admin.users.index"))
