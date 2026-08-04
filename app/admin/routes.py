import os
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.forms import VideoForm
from app.models import Assinatura, Cliente, Pagamento, Video

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(view):
    """Bloqueia o acesso à área administrativa para quem não é admin."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not getattr(current_user, 'eh_admin', False):
            flash('Acesso restrito à área administrativa.', 'danger')
            return redirect(url_for('cliente.dashboard'))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Painel administrativo com métricas simples de clientes e faturamento."""

    # 1. Total de clientes cadastrados
    total_clientes = db.session.query(func.count(Cliente.id_cliente)).scalar()

    # 2. Faturamento total = soma de todos os pagamentos
    faturamento_total = db.session.query(
        func.coalesce(func.sum(Pagamento.valor), 0.0)
    ).scalar()

    # 3. Assinaturas ativas (status normalizado como 'ativo')
    assinaturas_ativas = db.session.query(func.count(Assinatura.id_assinaturas)).filter(
        func.lower(Assinatura.status) == 'ativo'
    ).scalar()

    # 4. Total de pagamentos registrados
    total_pagamentos = db.session.query(func.count(Pagamento.id_pagamento)).scalar()

    # 5. Últimos 5 clientes cadastrados (para a tabela do painel)
    ultimos_clientes = (
        Cliente.query.order_by(Cliente.data_cadastro.desc()).limit(5).all()
    )

    return render_template(
        'admin/dashboard.html',
        total_clientes=total_clientes,
        faturamento_total=faturamento_total,
        assinaturas_ativas=assinaturas_ativas,
        total_pagamentos=total_pagamentos,
        ultimos_clientes=ultimos_clientes,
    )


# ---------------------------------------------------------------------------
# Gestão do catálogo de vídeos (CRUD)
# ---------------------------------------------------------------------------
def _avisar_arquivo_inexistente(video):
    """Avisa (sem bloquear) se o arquivo informado não existe na pasta."""
    caminho = os.path.join(current_app.config['VIDEOS_FOLDER'], video.caminho_arquivo)
    if not os.path.isfile(caminho):
        flash('Atenção: arquivo de vídeo não encontrado na pasta de vídeos.', 'warning')


@admin_bp.route('/videos')
@login_required
@admin_required
def listar_videos():
    videos = Video.query.order_by(Video.criado_em.desc()).all()
    return render_template('admin/videos.html', videos=videos)


@admin_bp.route('/videos/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_video():
    form = VideoForm()
    if form.validate_on_submit():
        video = Video(
            titulo=form.titulo.data.strip(),
            descricao=form.descricao.data,
            categoria=form.categoria.data,
            caminho_arquivo=form.caminho_arquivo.data.strip(),
            capa=form.capa.data or None,
            duracao=form.duracao.data or None,
            ano_lancamento=form.ano_lancamento.data,
            ativo=form.ativo.data,
        )
        db.session.add(video)
        db.session.commit()
        _avisar_arquivo_inexistente(video)
        flash('Vídeo cadastrado no catálogo!', 'success')
        return redirect(url_for('admin.listar_videos'))
    return render_template('admin/video_form.html', form=form, video=None)


@admin_bp.route('/videos/<int:video_id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        abort(404)

    form = VideoForm(obj=video)
    if form.validate_on_submit():
        form.populate_obj(video)
        db.session.commit()
        _avisar_arquivo_inexistente(video)
        flash('Vídeo atualizado!', 'success')
        return redirect(url_for('admin.listar_videos'))
    return render_template('admin/video_form.html', form=form, video=video)


@admin_bp.route('/videos/<int:video_id>/excluir', methods=['POST'])
@login_required
@admin_required
def excluir_video(video_id):
    video = db.session.get(Video, video_id)
    if not video:
        abort(404)
    titulo = video.titulo
    db.session.delete(video)
    db.session.commit()
    flash(f'Vídeo "{titulo}" excluído do catálogo.', 'info')
    return redirect(url_for('admin.listar_videos'))
