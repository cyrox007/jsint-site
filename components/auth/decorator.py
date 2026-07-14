import functools
import logging
import traceback
from flask import redirect, url_for, session, g, flash, current_app
from werkzeug.exceptions import InternalServerError
from database import Database

logger = logging.getLogger(__name__)


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('login') is None:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def with_db_session(view):
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if hasattr(g, 'db_session'):
            db_session = g.db_session
        else:
            db_session = Database.connect_database()
            g.db_session = db_session

        kwargs['db_session'] = db_session

        try:
            return view(*args, **kwargs)
        except Exception as e:
            db_session.rollback()
            
            # ✅ Всегда логируем с полным traceback
            logger.exception(
                "Ошибка в %s: %s: %s",
                view.__name__,
                type(e).__name__,
                str(e),
            )
            
            # В debug — пробрасываем оригинал (Werkzeug покажет traceback)
            if current_app.debug:
                raise
            
            # В production — скрываем детали
            flash("Произошла внутренняя ошибка сервера.", 'error')
            raise InternalServerError() from e
        finally:
            if hasattr(g, 'db_session') and g.db_session is db_session:
                db_session.close()
                del g.db_session

    return wrapped_view