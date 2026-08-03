from flask import render_template
from flask.views import MethodView

from components.auth.decorator import login_required


class DashboardMain(MethodView):
    @login_required
    def get(self):
        context = {}
        return render_template('/dashboard/main/index.html', **context)