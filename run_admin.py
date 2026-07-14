#!/usr/bin/env python
from flask_admin import Admin

from components.user import admin as user_admin_view

from app import create_app
from settings import db_session, config

app = create_app()
app.config.from_object(config)
app.secret_key = config.secret_key

@app.teardown_request
def teardown_request(*_, **__):
    db_session.expire_all()


admin = Admin(app, name='Urn', template_mode='bootstrap3')

user_admin_view.load_views(admin, db_session)


if __name__ == '__main__':
    app.run(port=9990, debug=True)