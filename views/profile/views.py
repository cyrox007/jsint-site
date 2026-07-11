from flask.views import MethodView
from flask import render_template, session, redirect, url_for, request, flash
from database import Database
from components.user.model import User, Profile, UserToSubscriptions
from models.articles import Posts
from components.auth.decorator import login_required

from datetime import datetime


class ProfilePage(MethodView):
    @login_required
    def get(self, login):
        db_session = Database.connect_database()
        subscribe_author = None

        if session.get('login') != login:
            user = User.login(db_session, session.get('login'))
            otherUser = User.login(db_session, login)
            
            subscribe_author = UserToSubscriptions.check_substract(
                db_session=db_session,
                user_login=session.get('login'),
                author=login
            )
            
            profile = Profile.get_profile(db_session, otherUser.id)
            posts = Posts.get_user_posts(db_session, otherUser.id)
        else:
            user = User.login(db_session, login)
            profile = Profile.get_profile(db_session, user.id)
            posts = Posts.get_user_posts(db_session, user.id)

        db_session.close()
        return render_template(
            'profile/index.html',
            user_id=user.id,
            login=login,
            profile=profile,
            subscribe=subscribe_author,
            posts=posts
        )


class EditProfile(MethodView):
    @login_required
    def get(self, login):
        db_session = Database.connect_database()

        if session.get('login') != login:
            return redirect(url_for('404'))

        user = User.login(db_session, login)
        user_profile = Profile.get_profile(db_session, user.id)

        db_session.close()
        return render_template(
            'profile/edit.html', 
            profile=user_profile
            )

    @login_required
    def post(self, login):
        db_session = Database.connect_database()
        
        user = User.login(db_session, login)

        first_name = request.form.get('first-name')
        surname = request.form.get('surname')
        age = request.form.get('age')
        avatar = request.files['avatar']

        Profile.update_profile(
            db_session=db_session, 
            user_id=user.id,
            first_name=first_name,
            surname=surname,
            age=age,
            avatar=avatar
            )

        
        db_session.close()
        return redirect(url_for('profile.index', login=login))


class SubstractAuthor(MethodView):
    @login_required
    def post(self, login):
        db_session = Database.connect_database()
        UserToSubscriptions.subscribe(
            db_session=db_session, 
            user_login=session.get('login'), 
            author_login=login
            )
        db_session.close()
        return redirect(url_for('profile.index', login=login))


class UnsubscribeAuthor(MethodView):
    @login_required
    def post(self, login):
        db_session = Database.connect_database()
        
        UserToSubscriptions.unsubscribe(
            db_session=db_session,
            user_l=session.get('login'),
            author_l=login
        )
        
        db_session.close()
        return redirect(url_for('profile.index', login=login))


class UsersListPage(MethodView):
    @login_required
    def get(self):
        db_session = Database.connect_database()
        users = User.get_users(db_session)
        db_session.close()
        return render_template(
            'users/index.html',
            users=users
        )