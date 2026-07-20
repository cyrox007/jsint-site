from datetime import datetime, timezone
from uuid import UUID

from flask.views import MethodView
from flask import jsonify, render_template, session, redirect, url_for, request, flash
from sqlalchemy.orm import Session
from database import Database
from components.auth.decorator import login_required, with_db_session
from models.users import User
from models.publication import Publication
from schemas.publication import PublicationCreate, PublicationUpdate
from services.publication import PublicationService


class PublicationListPage(MethodView):
    @with_db_session
    @login_required
    def get(self, db_session):
        publications = PublicationService.get_publications(db_session, is_published=None)
        return render_template('dashboard/publication/index.html', publications=publications)


class CreatePost(MethodView):
    @login_required
    def get(self):
        categories = []

        return render_template('dashboard/publication/edit.html', categories=categories)

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()  # у вас было body, исправлено
        slug = request.form.get('slug', '').strip()
        source_type = request.form.get('source-type', 'article')
        category_id = request.form.get('category_id')
        is_published = request.form.get('is_published', False)  # 'published' или 'draft'
        tags_str = request.form.get('tags', '')  # список технологий через запятую, например "python,fastapi,redis"
        remove_preview = bool(request.form.get('remove_preview'))  # возможно, флаг для удаления превью
        
        # 2. Валидация обязательных полей
        if not title:
            flash("Заголовок не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.create'))
        if not content:
            flash("Текст не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.create'))
        
        if not slug:
            flash("Слаг (URL) не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.create'))
        
         # 3. Проверка уникальности слага
        existing = db_session.query(Publication).filter(Publication.slug == slug).first()
        if existing:
            flash("Публикация с таким URL уже существует", "error")
            return redirect(request.referrer or url_for('admin.publication.create'))
        
        data = PublicationCreate(
            title=title,
            slug=slug,
            content=content,
            source_type=source_type,
            extra_data=None,
            category_id=category_id,
            author_id=session.get('user_id'),
            is_published=is_published,
            technology_ids=[]
        )
        publication = PublicationService.create_publication(db_session, data)
        flash("Сохранено", "success")
        return redirect(url_for('admin.publication.edit', id=publication.id))
    
class CheckSlug(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, slug: str):
        if not slug:
            return jsonify({'error': 'Slug is required'}), 400
        
        original_slug = slug
        candidate = slug
        counter = 1

        # Проверяем, существует ли уже такой слаг
        while db_session.query(Publication).filter(Publication.slug == candidate).first():
            # Если существует, генерируем новый вариант
            # Удаляем существующий числовой суффикс (если есть) и добавляем новый
            # Но проще: всегда добавляем "-{counter}"
            # Чтобы избежать накопления суффиксов (my-article-1-2), можно сначала убрать суффикс
            # Но для простоты: если candidate уже заканчивается на цифру, можно заменить.
            # Однако проще использовать оригинальный слаг + counter
            candidate = f"{original_slug}-{counter}"
            counter += 1

        return jsonify({'slug': candidate})


class UpdatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id):
        publication = PublicationService.get_publication(db_session, id)

        context = {
            'categories': [],
            'publication': publication
        }
        
        return render_template('dashboard/publication/edit.html', **context)

    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()  # у вас было body, исправлено
        slug = request.form.get('slug', '').strip()
        source_type = request.form.get('source-type', 'article')
        category_id = request.form.get('category_id')
        is_published = request.form.get('is_published', False)  # 'published' или 'draft'
        tags_str = request.form.get('tags', '')  # список технологий через запятую, например "python,fastapi,redis"
        remove_preview = bool(request.form.get('remove_preview'))  # возможно, флаг для удаления превью
        
        # 2. Валидация обязательных полей
        if not title:
            flash("Заголовок не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.edit', id=id))
        if not content:
            flash("Текст не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.edit', id=id))
        
        if not slug:
            flash("Слаг (URL) не может быть пустым", "error")
            return redirect(request.referrer or url_for('admin.publication.edit', id=id))
        
         # 3. Проверка уникальности слага
        existing = db_session.query(Publication).filter(Publication.slug == slug).first()
        if existing and existing.id != id:
            flash("Публикация с таким URL уже существует", "error")
            return redirect(request.referrer or url_for('admin.publication.edit', id=id))
        
        data = PublicationUpdate(
            title=title,
            slug=slug,
            content=content,
            source_type=source_type,
            extra_data=None,
            category_id=category_id,
            author_id=session.get('user_id'),
            is_published=is_published,
            technology_ids=[]
        )

        publication = PublicationService.update_publication(db_session, id, data)
        flash("Сохранено", "success")
        return redirect(url_for('admin.publication.edit', id=publication.id))


class DeletePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        deleted = PublicationService.delete_publication(db_session, id)

        return redirect(url_for('admin.publication.index'))