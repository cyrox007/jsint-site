import functools
import logging
from flask import redirect, url_for, session, g, flash, current_app
from werkzeug.exceptions import InternalServerError
from database import Database

logger = logging.getLogger(__name__)

def login_required(view):
    """Проверяет, авторизован ли пользователь."""
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get('login') is None:
            flash('Пожалуйста, войдите в систему.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def with_db_session(view):
    """
    Декоратор, который создаёт сессию БД и передаёт её как именованный аргумент `db_session`.
    Сессия автоматически закрывается после выполнения представления.
    """
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        # Проверяем, не создана ли уже сессия в g (например, для вложенных вызовов)
        if hasattr(g, 'db_session'):
            db_session = g.db_session
        else:
            db_session = Database.connect_database()
            g.db_session = db_session

        # Добавляем db_session в kwargs, если функция ожидает его
        kwargs['db_session'] = db_session

        try:
            return view(*args, **kwargs)
        except Exception as e:
            # Логируем ошибку
            logger.exception("Ошибка в представлении: %s", str(e))
            # Откатываем транзакцию
            db_session.rollback()
            flash("Произошла внутренняя ошибка сервера.", 'error')
            raise InternalServerError("Внутренняя ошибка сервера") from e
        finally:
            # Закрываем сессию, если она была создана в этом запросе
            if hasattr(g, 'db_session') and g.db_session is db_session:
                db_session.close()
                # Удаляем из g, чтобы не закрыть повторно
                del g.db_session

    return wrapped_view