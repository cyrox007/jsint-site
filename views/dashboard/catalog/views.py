from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session


class CatalogList(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        return