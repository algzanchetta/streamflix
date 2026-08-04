from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class Cliente(UserMixin, db.Model):
    """Cliente final do serviço de streaming (tabela `clientes`).

    Também implementa Flask-Login (UserMixin) porque o cliente consegue
    logar na "área do cliente". O `get_id()` é namespaced para não
    conflitar com o ID da tabela `usuarios_sistema`.
    """

    __tablename__ = 'clientes'

    # Colunas — nomes idênticos ao banco existente
    id_cliente = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    idade = db.Column(db.Integer, nullable=False)
    cidade = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=True)
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    # Colunas da extensão "cadastro completo" (adicionadas via migrar_extensao.py)
    cpf = db.Column(db.String(11), unique=True, nullable=True)
    deve_trocar_senha = db.Column(db.Boolean, nullable=False, default=False)

    # Relacionamentos: um cliente pode ter várias assinaturas e cartões
    assinaturas = db.relationship('Assinatura', backref='cliente', lazy=True)
    cartoes = db.relationship('Cartao', backref='cliente', lazy=True)

    @property
    def cartao_principal(self):
        """Retorna o cartão ativo de referência (primeiro ativo)."""
        for cartao in self.cartoes:
            if cartao.ativo:
                return cartao
        return None

    def precisa_completar_cadastro(self):
        """True se o cliente ainda precisa de senha própria / dados no 1º acesso."""
        return not self.senha_hash or self.deve_trocar_senha

    # --- Flask-Login (login duplo com UsuarioSistema) ---
    def get_id(self):
        return f'cliente:{self.id_cliente}'

    # NOTA: is_active NÃO usa `ativo` porque um cliente inativo ainda precisa
    # logar para ver a tela de reativação. O bloqueio de rotas é feito via
    # before_request (cliente_bp) e admin_required. O atributo `ativo` é checado
    # explicitamente onde for necessário (login, admin, etc.).
    @property
    def is_active(self):
        return True

    # Flask-Login 0.6.x define is_authenticated = is_active. Como sobrescrevemos
    # is_active acima (sempre True), is_authenticated também será True para
    # clientes logados, incluindo os inativos — o acesso é controlado pelo
    # before_request do cliente_bp e pelo admin_required.
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    # --- Senhas com Werkzeug ---
    def set_password(self, senha):
        """Gera e armazena o hash da senha (nunca guardamos texto puro)."""
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        """Verifica se a senha informada confere com o hash armazenado."""
        if not self.senha_hash:
            return False
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f'<Cliente {self.nome}>'


class Assinatura(db.Model):
    """Assinatura contratada por um cliente (tabela `assinaturas`)."""

    __tablename__ = 'assinaturas'

    id_assinaturas = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    plano = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Ativo')

    # Relacionamento: uma assinatura gera vários pagamentos
    pagamentos = db.relationship('Pagamento', backref='assinatura', lazy=True)

    @property
    def eh_ativa(self):
        """Normaliza o status (o banco tem 'Ativo', 'ativo', 'Cancelado'...)."""
        return bool(self.status) and self.status.lower() == 'ativo'

    def __repr__(self):
        return f'<Assinatura {self.plano} ({self.status})>'


class Pagamento(db.Model):
    """Pagamento de uma assinatura (tabela `pagamentos`)."""

    __tablename__ = 'pagamentos'

    id_pagamento = db.Column(db.Integer, primary_key=True)
    id_assinaturas = db.Column(db.Integer, db.ForeignKey('assinaturas.id_assinaturas'), nullable=False)
    data_pagamento = db.Column(db.DateTime, nullable=True)
    valor = db.Column(db.Float, nullable=False)
    metodo_pagamento = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pendente')

    @property
    def eh_pendente(self):
        """Pagamento ainda não confirmado/quitado."""
        return bool(self.status) and self.status.lower() in ('pendente', 'aguardando', 'em_aberto')

    @property
    def eh_pago(self):
        return bool(self.status) and self.status.lower() == 'pago'

    @property
    def status_exibicao(self):
        if self.eh_pago:
            return 'Quitado'
        if self.eh_pendente:
            return 'Pendente'
        return self.status.capitalize()

    def __repr__(self):
        return f'<Pagamento R${self.valor} {self.status}>'


class UsuarioSistema(UserMixin, db.Model):
    """Usuário interno do sistema (equipe/admin) — tabela `usuarios_sistema`."""

    __tablename__ = 'usuarios_sistema'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    cargo = db.Column(db.String(50), nullable=False, default='suporte')
    permissoes = db.Column(db.Text, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ultimo_login = db.Column(db.DateTime, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False,
                              default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Flask-Login (login duplo com Cliente) ---
    def get_id(self):
        return f'usuario:{self.id}'

    @property
    def is_active(self):
        return bool(self.ativo)

    @property
    def eh_admin(self):
        """True se o cargo do usuário for 'admin'."""
        return bool(self.cargo) and self.cargo.lower() == 'admin'

    # --- Senhas com Werkzeug ---
    def set_password(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_password(self, senha):
        if not self.senha_hash:
            return False
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f'<UsuarioSistema {self.email}>'


class Plano(db.Model):
    """Plano de assinatura disponível (tabela `planos`)."""

    __tablename__ = 'planos'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    preco = db.Column(db.Float, nullable=False)
    duracao_dias = db.Column(db.Integer, nullable=False, default=30)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f'<Plano {self.nome} R${self.preco}>'


class Cartao(db.Model):
    """Cartão de crédito do cliente (tabela `cartoes`).

    Por segurança (PCI-DSS), NUNCA armazenamos o número completo:
    guardamos apenas os 4 últimos dígitos + bandeira + validade.
    """

    __tablename__ = 'cartoes'

    id = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False)
    numero_final = db.Column(db.String(4), nullable=False)
    bandeira = db.Column(db.String(30), nullable=False)
    nome_titular = db.Column(db.String(120), nullable=True)
    validade_mes = db.Column(db.Integer, nullable=False)
    validade_ano = db.Column(db.Integer, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def numero_mascarado(self):
        return f'•••• •••• •••• {self.numero_final}'

    @property
    def validade_formatada(self):
        return f'{self.validade_mes:02d}/{self.validade_ano}'

    def __repr__(self):
        return f'<Cartao {self.bandeira} **** {self.numero_final}>'


class Video(db.Model):
    """Vídeo do catálogo (tabela `videos`).

    `caminho_arquivo` guarda apenas o NOME do arquivo dentro da pasta
    configurada em `Config.VIDEOS_FOLDER` (nunca um caminho absoluto,
    para evitar path traversal ao servir o arquivo).
    """

    __tablename__ = 'videos'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    tipo = db.Column(db.String(50), nullable=False, default='Filme')
    categoria = db.Column(db.String(50), nullable=False, default='Outro')
    caminho_arquivo = db.Column(db.String(255), nullable=True)
    capa = db.Column(db.String(255), nullable=True)
    duracao = db.Column(db.String(30), nullable=True)
    ano_lancamento = db.Column(db.Integer, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Video {self.titulo}>'
