import os

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_from_directory, url_for)
from flask_login import current_user, login_required

from app import db
from app.forms import ConfigurarAcessoForm
from app.models import Assinatura, Cartao, Cliente, Pagamento, Video
from app.validators import detectar_bandeira, so_digitos

cliente_bp = Blueprint('cliente', __name__)


@cliente_bp.before_request
def _verificar_primeiro_acesso():
    """Força o cliente que ainda não completou o cadastro a concluir primeiro."""
    if (current_user.is_authenticated
            and isinstance(current_user, Cliente)
            and current_user.deve_trocar_senha
            and request.endpoint != 'cliente.configurar_acesso'):
        return redirect(url_for('cliente.configurar_acesso'))
    return None


def _assinatura_atual(cliente=None):
    """Assinatura mais recente do cliente."""
    cliente = cliente or current_user
    return (
        Assinatura.query
        .filter_by(id_cliente=cliente.id_cliente)
        .order_by(Assinatura.id_assinaturas.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@cliente_bp.route('/')
@login_required
def dashboard():
    """Área do cliente: perfil, cartão e assinatura atual."""
    if isinstance(current_user, Cliente):
        cliente_dados = current_user
    else:
        # UsuarioSistema: vincula pelo e-mail (email único em `clientes`)
        cliente_dados = Cliente.query.filter_by(email=current_user.email).first()

    cartao = cliente_dados.cartao_principal if cliente_dados else None
    assinatura = _assinatura_atual(cliente_dados) if cliente_dados else None

    pagamentos = []
    if assinatura:
        pagamentos = (
            Pagamento.query
            .filter_by(id_assinaturas=assinatura.id_assinaturas)
            .order_by(Pagamento.id_pagamento.desc())
            .limit(5)
            .all()
        )

    return render_template(
        'cliente/dashboard.html',
        cliente=cliente_dados or current_user,
        cartao=cartao,
        assinatura=assinatura,
        pagamentos=pagamentos,
    )


# ---------------------------------------------------------------------------
# Primeiro acesso (troca de senha + CPF + cartão)
# ---------------------------------------------------------------------------
@cliente_bp.route('/configurar', methods=['GET', 'POST'])
@login_required
def configurar_acesso():
    """Cliente em primeiro acesso define senha própria e completa o cadastro."""
    if not isinstance(current_user, Cliente):
        return redirect(url_for('cliente.dashboard'))

    form = ConfigurarAcessoForm()
    form.usuario_atual = current_user

    if form.validate_on_submit():
        current_user.set_password(form.senha.data)
        current_user.cpf = so_digitos(form.cpf.data)
        current_user.deve_trocar_senha = False
        db.session.commit()

        if not current_user.cartao_principal:
            cartao = Cartao(
                id_cliente=current_user.id_cliente,
                numero_final=so_digitos(form.cartao_numero.data)[-4:],
                bandeira=detectar_bandeira(form.cartao_numero.data),
                nome_titular=form.cartao_nome.data.strip(),
                validade_mes=form.cartao_validade_mes.data,
                validade_ano=form.cartao_validade_ano.data,
                ativo=True,
            )
            db.session.add(cartao)
            db.session.commit()

        flash('Cadastro completo! Bem-vindo(a) ao StreamFlix.', 'success')
        return redirect(url_for('cliente.dashboard'))

    return render_template('cliente/configurar_acesso.html', form=form)


# ---------------------------------------------------------------------------
# Catálogo de vídeos
# ---------------------------------------------------------------------------
@cliente_bp.route('/catalogo')
@login_required
def catalogo():
    """Lista os vídeos disponíveis, com filtro por categoria."""
    categoria = request.args.get('categoria', '').strip()
    query = Video.query.filter_by(ativo=True)
    if categoria:
        query = query.filter_by(categoria=categoria)
    videos = query.order_by(Video.titulo).all()

    categorias = [
        c[0] for c in db.session.query(Video.categoria)
        .filter_by(ativo=True).distinct().order_by(Video.categoria).all()
    ]
    return render_template(
        'cliente/catalogo.html',
        videos=videos,
        categorias=categorias,
        categoria_atual=categoria,
    )


@cliente_bp.route('/catalogo/<int:video_id>')
@login_required
def assistir(video_id):
    """Página do player do vídeo."""
    video = db.session.get(Video, video_id)
    if not video or not video.ativo:
        abort(404)
    return render_template('cliente/assistir.html', video=video)


@cliente_bp.route('/video/<int:video_id>')
@login_required
def servir_video(video_id):
    """Serve o arquivo de vídeo do HD com segurança (send_from_directory).

    A pasta base é Config.VIDEOS_FOLDER e no banco guardamos apenas o nome
    do arquivo — qualquer tentativa de path traversal é bloqueada.
    """
    video = db.session.get(Video, video_id)
    if not video or not video.ativo or not video.caminho_arquivo:
        abort(404)

    pasta = current_app.config['VIDEOS_FOLDER']
    if not os.path.isdir(pasta):
        abort(404)
    return send_from_directory(pasta, video.caminho_arquivo, conditional=True)


# ---------------------------------------------------------------------------
# Assinatura: cancelar / reativar
# ---------------------------------------------------------------------------
@cliente_bp.route('/assinatura/cancelar', methods=['POST'])
@login_required
def cancelar_assinatura():
    assinatura = _assinatura_atual()
    if assinatura and assinatura.eh_ativa:
        assinatura.status = 'Cancelado'
        db.session.commit()
        flash('Sua assinatura foi cancelada. Esperamos você de volta!', 'info')
    return redirect(url_for('cliente.dashboard'))


@cliente_bp.route('/assinatura/reativar', methods=['POST'])
@login_required
def reativar_assinatura():
    assinatura = _assinatura_atual()
    if assinatura and not assinatura.eh_ativa:
        assinatura.status = 'Ativo'
        db.session.commit()
        flash('Sua assinatura foi reativada. Bem-vindo de volta!', 'success')
    return redirect(url_for('cliente.dashboard'))
