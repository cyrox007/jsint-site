from flask import redirect, url_for
from flask.views import MethodView

from components.auth.decorator import login_required


class DashboardMain(MethodView):
    @login_required
    def get(self):
        return redirect(url_for("admin.publication.index"))
