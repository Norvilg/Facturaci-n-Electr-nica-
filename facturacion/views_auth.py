from django.contrib.auth.views import LoginView

from .auth_utils import url_inicio_usuario


class FacturacionLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        return url_inicio_usuario(self.request.user)
