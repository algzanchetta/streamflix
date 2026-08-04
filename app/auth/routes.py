from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import db
from app.forms import LoginForm, RecuperarSenhaForm, RedefinirSenhaForm, RegistroForm
from app.models import Assinatura, Cartao, Cliente, Pagamento, Plano, UsuarioSistema
from app.validators import detectar_bandeira, so_digitos

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Tempo de validade do token de recuperação de senha (em segundos)
VALIDADE_TOKEN = 3600  # 1 hora


def _destino_pos_login(user=None):
    """Define a página inicial de cada perfil após o login."""
    user = user or current_user
    if getattr(user, 'eh_admin', False):
        return url_for('admin.dashboard')
    return url_for('cliente.dashboard')


def _proxima_url_segura(destino):
    """Evita open redirect: só aceita URLs relativas do próprio site."""
    if destino and destino.startswith('/') and not destino.startswith('//'):
        return destino
    return None


def _senha_provisoria():
    return current_app.config['SENHA_PROVISORIA']


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Autentica UsuarioSistema (equipe/admin) ou Cliente (login duplo)."""
    if current_user.is_authenticated:
        return redirect(_destino_pos_login())

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        senha = form.senha.data

        # 1º) Tenta um usuário interno (admin/suporte)
        usuario = UsuarioSistema.query.filter_by(email=email).first()
        if usuario and usuario.ativo and usuario.check_password(senha):
            login_user(usuario, remember=form.lembrar.data)
            usuario.ultimo_login = datetime.utcnow()
            db.session.commit()
            flash(f'Bem-vindo(a), {usuario.nome.split(" ")[0]}!', 'success')

            destino = _proxima_url_segura(request.args.get('next'))
            return redirect(destino or _destino_pos_login(usuario))

        # 2º) Tenta um cliente final
        cliente = Cliente.query.filter_by(email=email).first()
        if cliente and cliente.ativo:
            # 2.1) Primeiro acesso: cliente sem senha usa a senha provisória
            #      e é forçado a configurar a conta (trocar senha + CPF + cartão).
            if cliente.senha_hash is None:
                if senha == _senha_provisoria():
                    cliente.deve_trocar_senha = True
                    cliente.ultimo_acesso = datetime.utcnow()
                    db.session.commit()
                    login_user(cliente, remember=form.lembrar.data)
                    flash('Primeiro acesso! Defina sua senha e complete seu cadastro.', 'warning')
                    return redirect(url_for('cliente.configurar_acesso'))
            elif cliente.check_password(senha):
                login_user(cliente, remember=form.lembrar.data)
                cliente.ultimo_acesso = datetime.utcnow()
                db.session.commit()
                flash(f'Bem-vindo(a) de volta, {cliente.nome.split(" ")[0]}!', 'success')

                # Cliente que ainda precisa concluir o cadastro é redirecionado
                if cliente.deve_trocar_senha:
                    return redirect(url_for('cliente.configurar_acesso'))

                destino = _proxima_url_segura(request.args.get('next'))
                return redirect(destino or _destino_pos_login(cliente))

        flash('E-mail ou senha inválidos.', 'danger')

    return render_template('auth/login.html', form=form)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Encerra a sessão. Usa POST para evitar logout via CSRF."""
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------------------------
# Registro (cria um Cliente)
# ---------------------------------------------------------------------------
@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    """Cadastro completo: cria Cliente + Cartão + Assinatura + 1º pagamento."""
    if current_user.is_authenticated:
        return redirect(_destino_pos_login())

    form = RegistroForm()
    # Preenche as opções de plano a partir da tabela `planos`
    planos_ativos = Plano.query.filter_by(ativo=True).order_by(Plano.preco).all()
    form.plano_id.choices = [
        (p.id, f'{p.nome} — R$ {p.preco:.2f}/mês') for p in planos_ativos
    ]

    if form.validate_on_submit():
        plano = db.session.get(Plano, form.plano_id.data)
        if not plano or not plano.ativo:
            flash('Plano inválido. Escolha um plano disponível.', 'danger')
            return render_template('auth/registro.html', form=form, planos=planos_ativos)

        # 1) Cliente
        cliente = Cliente(
            nome=form.nome.data.strip(),
            email=form.email.data.lower().strip(),
            cpf=so_digitos(form.cpf.data),
            idade=form.idade.data,
            cidade=form.cidade.data.strip(),
            ativo=True,
            deve_trocar_senha=False,
        )
        cliente.set_password(form.senha.data)
        db.session.add(cliente)
        db.session.flush()  # gera o id_cliente

        # 2) Cartão (apenas dados mascarados — nunca o número completo)
        cartao = Cartao(
            id_cliente=cliente.id_cliente,
            numero_final=so_digitos(form.cartao_numero.data)[-4:],
            bandeira=detectar_bandeira(form.cartao_numero.data),
            nome_titular=form.cartao_nome.data.strip(),
            validade_mes=form.cartao_validade_mes.data,
            validade_ano=form.cartao_validade_ano.data,
            ativo=True,
        )
        db.session.add(cartao)

        # 3) Assinatura do plano escolhido
        assinatura = Assinatura(
            id_cliente=cliente.id_cliente,
            plano=plano.nome,
            valor=plano.preco,
            status='Ativo',
        )
        db.session.add(assinatura)
        db.session.flush()  # gera o id_assinaturas

        # 4) Primeira mensalidade registrada (faturamento do admin)
        pagamento = Pagamento(
            id_assinaturas=assinatura.id_assinaturas,
            data_pagamento=datetime.utcnow(),
            valor=plano.preco,
            metodo_pagamento=f'{cartao.bandeira} •••• {cartao.numero_final}',
        )
        db.session.add(pagamento)
        db.session.commit()

        flash(f'Conta criada com sucesso! Plano {plano.nome} ativado. Faça login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/registro.html', form=form, planos=planos_ativos)


# ---------------------------------------------------------------------------
# Recuperação de senha (token assinado — sem e-mail real nesta aula)
# ---------------------------------------------------------------------------
def _serializer():
    return URLSafeTimedSerializer(
        current_app_secret_key(), salt='recuperar-senha'
    )


def current_app_secret_key():
    from flask import current_app
    return current_app.config['SECRET_KEY']


def gerar_token_recuperacao(email):
    """Gera um token assinado que expira em VALIDADE_TOKEN segundos."""
    return _serializer().dumps(email)


def validar_token_recuperacao(token):
    """Retorna o e-mail se o token for válido, ou None caso contrário."""
    try:
        return _serializer().loads(token, max_age=VALIDADE_TOKEN)
    except (BadSignature, SignatureExpired):
        return None


@auth_bp.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    """Solicita recuperação de senha pelo e-mail.

    Em produção, o link com o token seria enviado por e-mail (ex.: Flask-Mail).
    Nesta aula, o link é exibido via flash para fins didáticos.
    """
    form = RecuperarSenhaForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()

        existe = (UsuarioSistema.query.filter_by(email=email).first()
                  or Cliente.query.filter_by(email=email).first())

        if existe:
            token = gerar_token_recuperacao(email)
            link = url_for('auth.redefinir_senha', token=token, _external=True)
            flash(f'Link de recuperação gerado: {link}', 'info')
            return redirect(url_for('auth.login'))

        flash('Nenhuma conta encontrada com este e-mail.', 'danger')

    return render_template('auth/recuperar_senha.html', form=form)


@auth_bp.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    """Valida o token e permite definir uma nova senha."""
    email = validar_token_recuperacao(token)
    if not email:
        flash('Link inválido ou expirado. Solicite uma nova recuperação.', 'danger')
        return redirect(url_for('auth.recuperar_senha'))

    form = RedefinirSenhaForm()
    if form.validate_on_submit():
        alvo = (UsuarioSistema.query.filter_by(email=email).first()
                or Cliente.query.filter_by(email=email).first())
        if not alvo:
            flash('Conta não encontrada.', 'danger')
            return redirect(url_for('auth.login'))

        alvo.set_password(form.senha.data)
        db.session.commit()
        flash('Senha redefinida com sucesso! Faça login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/redefinir_senha.html', form=form)
