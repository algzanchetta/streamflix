from datetime import datetime

from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config

# ---------------------------------------------------------------------------
# Extensões (inicializadas sem app — padrão Application Factory)
# ---------------------------------------------------------------------------
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário autenticado a partir do ID gravado na sessão.

    Como temos login duplo, o `get_id()` de cada model grava um ID
    "namespaced" (ex.: "usuario:5" ou "cliente:3"). Aqui fazemos o
    parse e consultamos a tabela correta.
    """
    from app.models import Cliente, UsuarioSistema

    tipo, _, valor = str(user_id).partition(':')
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        return None

    if tipo == 'usuario':
        return db.session.get(UsuarioSistema, valor)
    if tipo == 'cliente':
        return db.session.get(Cliente, valor)
    return None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa as extensões vinculadas a este app
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    # Página para onde o Flask-Login redireciona quem não está autenticado
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para acessar esta área.'
    login_manager.login_message_category = 'warning'

    # Registro dos Blueprints (cada um com seu url_prefix)
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.cliente.routes import cliente_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(cliente_bp, url_prefix='/cliente')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.route('/')
    def index():
        """Rota raiz: redireciona conforme o perfil do usuário."""
        if current_user.is_authenticated:
            if getattr(current_user, 'eh_admin', False):
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('cliente.dashboard'))
        return redirect(url_for('auth.login'))

    @app.context_processor
    def injetar_variaveis_globais():
        """Disponibiliza o ano atual para o rodapé de todos os templates."""
        return {'now': datetime.utcnow()}

    return app
