import os
from datetime import datetime
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func, or_

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


def _redirecionar_volta():
    """Volta para a página de origem mantendo filtros (apenas URLs internas)."""
    destino = request.referrer or url_for('admin.dashboard')
    if not destino.startswith('/'):
        destino = url_for('admin.dashboard')
    return redirect(destino)


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Painel administrativo com métricas simples de clientes e faturamento."""

    # 1. Total de clientes cadastrados
    total_clientes = db.session.query(func.count(Cliente.id_cliente)).scalar()

    # 2. Faturamento total = soma de todos os pagamentos quitados
    faturamento_total = db.session.query(
        func.coalesce(func.sum(Pagamento.valor), 0.0)
    ).filter(func.lower(Pagamento.status) == 'pago').scalar()

    # 3. Assinaturas ativas (status normalizado como 'ativo')
    assinaturas_ativas = db.session.query(func.count(Assinatura.id_assinaturas)).filter(
        func.lower(Assinatura.status) == 'ativo'
    ).scalar()

    # 4. Pagamentos pendentes (para alerta no painel)
    pagamentos_pendentes = db.session.query(func.count(Pagamento.id_pagamento)).filter(
        func.lower(Pagamento.status) == 'pendente'
    ).scalar()

    # 5. Últimos 5 clientes cadastrados (para a tabela do painel)
    ultimos_clientes = (
        Cliente.query.order_by(Cliente.data_cadastro.desc()).limit(5).all()
    )

    return render_template(
        'admin/dashboard.html',
        total_clientes=total_clientes,
        faturamento_total=faturamento_total,
        assinaturas_ativas=assinaturas_ativas,
        total_pagamentos=db.session.query(func.count(Pagamento.id_pagamento)).scalar(),
        pagamentos_pendentes=pagamentos_pendentes,
        ultimos_clientes=ultimos_clientes,
    )


# ---------------------------------------------------------------------------
# Gestão de usuários (clientes)
# ---------------------------------------------------------------------------
@admin_bp.route('/usuarios')
@login_required
@admin_required
def usuarios():
    """Lista TODOS os clientes com busca, filtro de status e paginação."""
    pagina = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()  # '', 'ativos', 'inativos'

    query = Cliente.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(
            Cliente.nome.ilike(like),
            Cliente.email.ilike(like),
            Cliente.cidade.ilike(like),
            Cliente.cpf.like(like),
        ))
    if status == 'ativos':
        query = query.filter_by(ativo=True)
    elif status == 'inativos':
        query = query.filter_by(ativo=False)

    paginacao = query.order_by(Cliente.data_cadastro.desc()).paginate(
        page=pagina, per_page=20, error_out=False)

    return render_template(
        'admin/usuarios.html',
        paginacao=paginacao,
        q=q,
        status=status,
        total_ativos=Cliente.query.filter_by(ativo=True).count(),
        total_inativos=Cliente.query.filter_by(ativo=False).count(),
    )


@admin_bp.route('/usuarios/<int:cliente_id>/alternar', methods=['POST'])
@login_required
@admin_required
def alternar_usuario(cliente_id):
    """Ativa/desativa um cliente. Desativado não consegue mais logar."""
    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        abort(404)
    cliente.ativo = not cliente.ativo
    db.session.commit()
    if cliente.ativo:
        flash(f'Cliente "{cliente.nome}" ativado.', 'success')
    else:
        flash(f'Cliente "{cliente.nome}" desativado.', 'warning')
    return _redirecionar_volta()


# ---------------------------------------------------------------------------
# Gestão de pagamentos
# ---------------------------------------------------------------------------
@admin_bp.route('/pagamentos')
@login_required
@admin_required
def pagamentos():
    """Lista pagamentos com filtro pendentes/quitados e paginação."""
    pagina = request.args.get('page', 1, type=int)
    status = request.args.get('status', '').strip()  # '', 'pendentes', 'pagos'

    query = Pagamento.query.join(Assinatura).join(Cliente)
    if status == 'pendentes':
        query = query.filter(func.lower(Pagamento.status) == 'pendente')
    elif status == 'pagos':
        query = query.filter(func.lower(Pagamento.status) == 'pago')

    paginacao = query.order_by(Pagamento.id_pagamento.desc()).paginate(
        page=pagina, per_page=20, error_out=False)

    total_pendentes = Pagamento.query.filter(
        func.lower(Pagamento.status) == 'pendente').count()
    total_pagos = Pagamento.query.filter(
        func.lower(Pagamento.status) == 'pago').count()
    total_valor_pago = db.session.query(
        func.coalesce(func.sum(Pagamento.valor), 0.0)
    ).filter(func.lower(Pagamento.status) == 'pago').scalar()

    return render_template(
        'admin/pagamentos.html',
        paginacao=paginacao,
        status=status,
        total_pendentes=total_pendentes,
        total_pagos=total_pagos,
        total_valor_pago=total_valor_pago,
    )


@admin_bp.route('/pagamentos/<int:pagamento_id>/quitar', methods=['POST'])
@login_required
@admin_required
def quitar_pagamento(pagamento_id):
    """Marca um pagamento pendente como quitado."""
    pagamento = db.session.get(Pagamento, pagamento_id)
    if not pagamento:
        abort(404)
    if pagamento.eh_pago:
        flash('Este pagamento já estava quitado.', 'info')
    else:
        pagamento.status = 'pago'
        if not pagamento.data_pagamento:
            pagamento.data_pagamento = datetime.utcnow()
        db.session.commit()
        flash(f'Pagamento de R$ {pagamento.valor:.2f} quitado com sucesso!', 'success')
    return _redirecionar_volta()


# ---------------------------------------------------------------------------
# Gestão do catálogo de vídeos (CRUD)
# ---------------------------------------------------------------------------
def _avisar_arquivo_inexistente(video):
    """Avisa (sem bloquear) se o arquivo informado não existe na pasta."""
    caminho = os.path.join(current_app.config['VIDEOS_FOLDER'], video.caminho_arquivo)
    if not os.path.isfile(caminho):
        flash('Atenção: arquivo de vídeo não encontrado na pasta de vídeos.', 'warning')


def _incluir_valor_atual(form, campo, valor):
    """Garante que o valor já salvo apareça no select (mesmo se saiu das opções)."""
    if valor and valor not in [c[0] for c in getattr(form, campo).choices]:
        getattr(form, campo).choices = [(valor, valor)] + list(getattr(form, campo).choices)


def _opcoes_videos():
    tipos = [t[0] for t in db.session.query(Video.tipo).distinct().order_by(Video.tipo).all()]
    categorias = [c[0] for c in db.session.query(Video.categoria)
                  .distinct().order_by(Video.categoria).all()]
    return tipos, categorias


@admin_bp.route('/videos')
@login_required
@admin_required
def listar_videos():
    """Lista vídeos com busca por título/descrição e filtros tipo/categoria."""
    q = request.args.get('q', '').strip()
    tipo = request.args.get('tipo', '').strip()
    categoria = request.args.get('categoria', '').strip()

    query = Video.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Video.titulo.ilike(like), Video.descricao.ilike(like)))
    if tipo:
        query = query.filter_by(tipo=tipo)
    if categoria:
        query = query.filter_by(categoria=categoria)

    videos = query.order_by(Video.criado_em.desc()).all()
    tipos, categorias = _opcoes_videos()
    return render_template(
        'admin/videos.html',
        videos=videos,
        q=q,
        tipo=tipo,
        categoria=categoria,
        tipos=tipos,
        categorias=categorias,
    )


@admin_bp.route('/videos/novo', methods=['GET', 'POST'])
@login_required
@admin_required
def novo_video():
    form = VideoForm()
    if form.validate_on_submit():
        video = Video(
            titulo=form.titulo.data.strip(),
            descricao=form.descricao.data,
            tipo=form.tipo.data,
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
    _incluir_valor_atual(form, 'tipo', video.tipo)
    _incluir_valor_atual(form, 'categoria', video.categoria)
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
