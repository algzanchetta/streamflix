import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Chave secreta — em produção, defina a variável de ambiente.
    # O fallback existe apenas para desenvolvimento local não quebrar.
    SECRET_KEY = os.environ.get('BY_ANDERSON_ZANCHETTA') or 'dev-secret-key-nao-uso-em-producao'
    
    #CAMINHO ABOLSUTO PARA BANCO DE DADOS
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'database', 'dbase.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pasta onde ficam os arquivos de vídeo do catálogo (arquivos locais do HD).
    # Em produção, aponte para a pasta real via env var STREAMFLIX_VIDEOS_FOLDER.
    VIDEOS_FOLDER = os.environ.get('STREAMFLIX_VIDEOS_FOLDER') or os.path.join(basedir, 'videos')

    # Senha provisória usada no PRIMEIRO acesso de clientes que ainda não têm senha.
    # O sistema força a troca logo após o login. Troque em produção.
    SENHA_PROVISORIA = os.environ.get('STREAMFLIX_SENHA_PROVISORIA') or 'StreamFlix@2026'