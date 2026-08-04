"""
Cria o usuário administrador do sistema (tabela `usuarios_sistema`).

Uso:
    python criar_admin.py
    python criar_admin.py --email admin@streamflix.com --nome "Anderson" --senha "SuaSenhaForte"

Sem argumentos, pergunta interativamente. Se a variável de ambiente
BY_ANDERSON_ZANCHETTA não estiver definida, a chave de dev do config.py
será usada (apenas para desenvolvimento).
"""
import argparse
import getpass
import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, basedir)

from app import create_app, db
from app.models import UsuarioSistema


def criar_admin(email, nome, senha):
    app = create_app()
    with app.app_context():
        if not email or not nome or not senha:
            print('❌ E-mail, nome e senha são obrigatórios.')
            sys.exit(1)
        if len(senha) < 8:
            print('❌ A senha deve ter no mínimo 8 caracteres.')
            sys.exit(1)

        existente = UsuarioSistema.query.filter_by(email=email.lower().strip()).first()
        if existente:
            print(f'❌ Já existe um usuário com o e-mail {email}.')
            sys.exit(1)

        admin = UsuarioSistema(
            email=email.lower().strip(),
            nome=nome.strip(),
            cargo='admin',
            permissoes='*',
            ativo=True,
        )
        admin.set_password(senha)
        db.session.add(admin)
        db.session.commit()
        print(f'✅ Administrador criado com sucesso: {admin.email} (cargo: admin)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cria o usuário administrador do StreamFlix.')
    parser.add_argument('--email', help='E-mail do administrador')
    parser.add_argument('--nome', help='Nome do administrador')
    parser.add_argument('--senha', help='Senha do administrador (mín. 8 caracteres)')
    args = parser.parse_args()

    email = args.email or input('E-mail do administrador: ').strip()
    nome = args.nome or input('Nome do administrador: ').strip()
    if args.senha:
        senha = args.senha
    else:
        senha = getpass.getpass('Senha do administrador: ')

    criar_admin(email, nome, senha)
