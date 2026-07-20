import os
from flask import render_template, request, flash, redirect, url_for, session
from flask.views import MethodView

from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from components.auth.decorator import login_required, with_db_session
from models.users import User
from database import Database
from settings import config

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}


class LoginPage(MethodView):
    def get(self):
        return render_template('dashboard/auth/index.html')

    @with_db_session
    def post(self, db_session: Session):
        email = request.form.get('email')
        password = request.form.get('password')

        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            flash('Неправильный логин и/или пароль', 'error')
            return redirect(url_for('auth.login'))

        if check_password_hash(user.hash_password, password) is False: 
            flash('Неправильный логин и/или пароль', 'error')
            return redirect(url_for('auth.login'))
        
        session['login'] = user.email
        return redirect(url_for('index'))


class RegisterPage(MethodView):
    def get(self):
        return render_template('auth/register.html')

    def allowed_file(filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def post(self):
        db_session = Database.connect_database()
        
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first-name')
        surname = request.form.get('surname')
        age = request.form.get('age')
        avatar = request.files['avatar']
        
        if User.login(db_session, username) is not None:
            flash('Пользователь с таким логином уже зарегестрирован')
            return render_template('auth/register.html')
        
        if avatar.filename == '':
            avatarPath = 'uploads/us_avatars/user_default.jpg'
        else:
            filename = secure_filename(avatar.filename)
            avatarPath = config.AVATAR_DIR+filename
            avatar.save(os.path.join(config.FULL_AVATARS_PATH, filename))

        new_user = User.registering_new_user(
                db_session=db_session, 
                login=username, 
                password=password
            )
        
        getUser = User.login(db_session, new_user.username)
        update_profile = Profile.insert_profile(
            db_session=db_session,
            user_id=getUser.id,
            first_name=first_name,
            surname=surname,
            age=age,
            avatar=avatarPath
        )
        
        if new_user is not None:
            session['login'] = getUser.username
            return redirect(url_for('index'))

        


class LogoutUser(MethodView):
    @login_required
    def get(self):
        session.clear()
        return redirect(url_for('login'))