from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import (BooleanField, IntegerField, PasswordField, SelectField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length,
                                NumberRange, ValidationError)

from app.models import Cliente, UsuarioSistema
from app.validators import so_digitos, validar_cpf, validar_luhn

# ---------------------------------------------------------------------------
# Constantes dos campos de cartão (validade futura)
# ---------------------------------------------------------------------------
ANOS_VALIDADE = range(datetime.utcnow().year, datetime.utcnow().year + 11)
MESES_VALIDADE = range(1, 13)

TIPOS_VIDEO = ['Filme', 'Show', 'Documentário', 'Outro']
CATEGORIAS_VIDEO = [
    'Ação', 'Aventura', 'Animação', 'Comédia', 'Drama', 'Documentário',
    'Ficção Científica', 'Música', 'Terror', 'Outro',
]


class CartaoMixin:
    """Campos + validações comuns de cartão (registro e primeiro acesso)."""

    cartao_numero = StringField('Número do cartão', validators=[
        DataRequired(message='Informe o número do cartão.'),
    ])
    cartao_nome = StringField('Nome impresso no cartão', validators=[
        DataRequired(message='Informe o nome do titular.'),
        Length(max=120),
    ])
    cartao_validade_mes = SelectField('Mês', coerce=int,
                                      choices=[(m, f'{m:02d}') for m in MESES_VALIDADE],
                                      validators=[DataRequired(message='Informe o mês.')])
    cartao_validade_ano = SelectField('Ano', coerce=int,
                                      choices=[(a, str(a)) for a in ANOS_VALIDADE],
                                      validators=[DataRequired(message='Informe o ano.')])

    def validate_cartao_numero(self, field):
        num = so_digitos(field.data)
        if len(num) < 12 or len(num) > 19:
            raise ValidationError('Número de cartão inválido.')
        if not validar_luhn(num):
            raise ValidationError('Número de cartão inválido (verificação de Luhn falhou).')

    def validate_cartao_validade_mes(self, field):
        mes = self.cartao_validade_mes.data
        ano = self.cartao_validade_ano.data
        if not mes or not ano:
            return
        agora = datetime.utcnow()
        if (ano, mes) < (agora.year, agora.month):
            raise ValidationError('Cartão vencido.')


class LoginForm(FlaskForm):
    """Formulário de login (funciona para Cliente e UsuarioSistema)."""

    email = StringField('E-mail', validators=[
        DataRequired(message='Informe seu e-mail.'),
        Email(message='E-mail inválido.'),
    ])
    senha = PasswordField('Senha', validators=[
        DataRequired(message='Informe sua senha.'),
    ])
    lembrar = BooleanField('Manter conectado')
    submit = SubmitField('Entrar')


class RegistroForm(CartaoMixin, FlaskForm):
    """Cadastro completo: dados pessoais + CPF + plano + cartão de crédito."""

    nome = StringField('Nome completo', validators=[
        DataRequired(message='Informe seu nome.'),
        Length(min=2, max=120, message='O nome deve ter entre 2 e 120 caracteres.'),
    ])
    email = StringField('E-mail', validators=[
        DataRequired(message='Informe seu e-mail.'),
        Email(message='E-mail inválido.'),
        Length(max=120),
    ])
    cpf = StringField('CPF', validators=[
        DataRequired(message='Informe seu CPF.'),
    ])
    idade = IntegerField('Idade', validators=[
        DataRequired(message='Informe sua idade.'),
        NumberRange(min=0, max=120, message='Informe uma idade válida (0 a 120).'),
    ])
    cidade = StringField('Cidade', validators=[
        DataRequired(message='Informe sua cidade.'),
        Length(max=100),
    ])
    senha = PasswordField('Senha', validators=[
        DataRequired(message='Crie uma senha.'),
        Length(min=8, message='A senha deve ter no mínimo 8 caracteres.'),
    ])
    confirmar_senha = PasswordField('Confirmar senha', validators=[
        DataRequired(message='Confirme sua senha.'),
        EqualTo('senha', message='As senhas não coincidem.'),
    ])
    plano_id = SelectField('Plano de assinatura', coerce=int, validators=[
        DataRequired(message='Escolha um plano.'),
    ])
    submit = SubmitField('Criar conta e assinar')

    def validate_cpf(self, field):
        if not validar_cpf(field.data):
            raise ValidationError('CPF inválido.')
        cpf = so_digitos(field.data)
        if Cliente.query.filter_by(cpf=cpf).first():
            raise ValidationError('Este CPF já está cadastrado.')

    def validate_email(self, field):
        """Impede e-mail duplicado tanto em `clientes` quanto em `usuarios_sistema`."""
        email = field.data.lower().strip()
        if Cliente.query.filter_by(email=email).first():
            raise ValidationError('Este e-mail já está cadastrado.')
        if UsuarioSistema.query.filter_by(email=email).first():
            raise ValidationError('Este e-mail já está cadastrado.')


class ConfigurarAcessoForm(CartaoMixin, FlaskForm):
    """Primeiro acesso: define senha própria + completa CPF e cartão."""

    senha = PasswordField('Nova senha', validators=[
        DataRequired(message='Crie uma senha.'),
        Length(min=8, message='A senha deve ter no mínimo 8 caracteres.'),
    ])
    confirmar_senha = PasswordField('Confirmar senha', validators=[
        DataRequired(message='Confirme sua senha.'),
        EqualTo('senha', message='As senhas não coincidem.'),
    ])
    cpf = StringField('CPF', validators=[
        DataRequired(message='Informe seu CPF.'),
    ])
    submit = SubmitField('Completar cadastro')

    # Preenchido pela rota com o usuário autenticado (para permitir o próprio CPF)
    usuario_atual = None

    def validate_cpf(self, field):
        if not validar_cpf(field.data):
            raise ValidationError('CPF inválido.')
        cpf = so_digitos(field.data)
        existente = Cliente.query.filter_by(cpf=cpf).first()
        if existente and (self.usuario_atual is None
                          or existente.id_cliente != self.usuario_atual.id_cliente):
            raise ValidationError('Este CPF já está cadastrado para outro cliente.')


class ReativarContaForm(CartaoMixin, FlaskForm):
    """Reativação de conta inativa: senha + CPF + cartão + escolha de plano."""

    senha = PasswordField('Senha', validators=[
        DataRequired(message='Crie uma senha.'),
        Length(min=8, message='A senha deve ter no mínimo 8 caracteres.'),
    ])
    confirmar_senha = PasswordField('Confirmar senha', validators=[
        EqualTo('senha', message='As senhas não coincidem.'),
    ])
    cpf = StringField('CPF', validators=[
        DataRequired(message='Informe seu CPF.'),
    ])
    plano_id = SelectField('Plano de assinatura', coerce=int, validators=[
        DataRequired(message='Escolha um plano.'),
    ])
    submit = SubmitField('Reativar conta e assinar')

    # Preenchido pela rota com o cliente autenticado (para permitir o próprio CPF)
    cliente_atual = None

    def validate_cpf(self, field):
        if not validar_cpf(field.data):
            raise ValidationError('CPF inválido.')
        cpf = so_digitos(field.data)
        existente = Cliente.query.filter_by(cpf=cpf).first()
        if existente and (self.cliente_atual is None
                          or existente.id_cliente != self.cliente_atual.id_cliente):
            raise ValidationError('Este CPF já está cadastrado para outro cliente.')


class RecuperarSenhaForm(FlaskForm):
    """Solicita link de recuperação de senha pelo e-mail."""

    email = StringField('E-mail', validators=[
        DataRequired(message='Informe seu e-mail.'),
        Email(message='E-mail inválido.'),
    ])
    submit = SubmitField('Recuperar senha')


class RedefinirSenhaForm(FlaskForm):
    """Define uma nova senha usando o token de recuperação."""

    senha = PasswordField('Nova senha', validators=[
        DataRequired(message='Informe a nova senha.'),
        Length(min=8, message='A senha deve ter no mínimo 8 caracteres.'),
    ])
    confirmar_senha = PasswordField('Confirmar nova senha', validators=[
        DataRequired(message='Confirme a nova senha.'),
        EqualTo('senha', message='As senhas não coincidem.'),
    ])
    submit = SubmitField('Redefinir senha')


class VideoForm(FlaskForm):
    """Cadastro/edição de vídeo do catálogo (área administrativa)."""

    titulo = StringField('Título', validators=[
        DataRequired(message='Informe o título.'),
        Length(max=200),
    ])
    descricao = TextAreaField('Descrição')
    tipo = SelectField('Tipo',
                       choices=[(t, t) for t in TIPOS_VIDEO],
                       validators=[DataRequired()])
    categoria = SelectField('Categoria (gênero)',
                            choices=[(c, c) for c in CATEGORIAS_VIDEO],
                            validators=[DataRequired()])
    caminho_arquivo = StringField('Nome do arquivo de vídeo', validators=[
        DataRequired(message='Informe o nome do arquivo (ex.: filme.mp4).'),
        Length(max=255),
    ])
    capa = StringField('URL da capa (opcional)', validators=[Length(max=255)])
    duracao = StringField('Duração (ex.: 1h 32min)', validators=[Length(max=30)])
    ano_lancamento = IntegerField('Ano de lançamento')
    ativo = BooleanField('Disponível no catálogo', default=True)
    submit = SubmitField('Salvar')
