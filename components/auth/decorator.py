from __future__ import annotations

import functools
import logging
from uuid import UUID

from flask import current_app, flash, g, redirect, session, url_for
from werkzeug.exceptions import HTTPException, InternalServerError

from database import Database
from settings import config

logger = logging.getLogger(__name__)


def _session_user_exists() -> bool:
    raw_user_id = session.get("user_id")
    if not isinstance(raw_user_id, str):
        return False

    try:
        user_id = UUID(raw_user_id)
    except (TypeError, ValueError):
        return False

    from models.users import User

    db_session = getattr(g, "db_session", None)
    owns_session = db_session is None
    if owns_session:
        db_session = Database.connect_database()

    try:
        user = db_session.query(User.id, User.email).filter(User.id == user_id).first()
        return user is not None and config.is_admin_email(user.email)
    except Exception:
        logger.exception("Unable to validate authenticated user")
        return False
    finally:
        if owns_session:
            db_session.close()


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if not _session_user_exists():
            session.clear()
            flash("Пожалуйста, войдите в систему.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def with_db_session(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if hasattr(g, "db_session"):
            db_session = g.db_session
            owns_session = False
        else:
            db_session = Database.connect_database()
            g.db_session = db_session
            owns_session = True

        kwargs["db_session"] = db_session

        try:
            return view(*args, **kwargs)
        except HTTPException:
            db_session.rollback()
            raise
        except Exception as exc:
            db_session.rollback()
            logger.exception(
                "Ошибка в %s: %s: %s",
                view.__name__,
                type(exc).__name__,
                str(exc),
            )

            if current_app.debug:
                raise

            raise InternalServerError() from exc
        finally:
            if owns_session and getattr(g, "db_session", None) is db_session:
                db_session.close()
                del g.db_session

    return wrapped_view
