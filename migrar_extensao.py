"""
Migração complementar: cadastro completo + catálogo de vídeos.

Adiciona ao banco existente:
  - Colunas em `clientes`: cpf, deve_trocar_senha
  - Novas tabelas: planos, cartoes, videos
  - Seed dos planos iniciais (Básico / Padrão / Premium)
  - Cria a pasta padrão de vídeos (se não existir)

Executar com:  python migrar_extensao.py
O script é idempotente (pode rodar mais de uma vez).
"""
import os
import sqlite3
import sys

from datetime import datetime

# Garante exibição correta de acentos/emojis no console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, 'database', 'dbase.db')
VIDEOS_FOLDER = os.path.join(basedir, 'videos')


def colunas_da_tabela(conn, tabela):
    return [col[1] for col in conn.execute(f'PRAGMA table_info({tabela})').fetchall()]


def migrar():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print('🚀 Iniciando migração do cadastro completo e catálogo...')

    # ---------------------------------------------------------------
    # 1. Novas colunas em `clientes`
    # ---------------------------------------------------------------
    colunas = colunas_da_tabela(conn, 'clientes')
    if 'cpf' not in colunas:
        cur.execute('ALTER TABLE clientes ADD COLUMN cpf TEXT')
        print('✅ Coluna clientes.cpf adicionada')
    else:
        print('ℹ️  clientes.cpf já existe')

    if 'deve_trocar_senha' not in colunas:
        cur.execute('ALTER TABLE clientes ADD COLUMN deve_trocar_senha INTEGER DEFAULT 0')
        print('✅ Coluna clientes.deve_trocar_senha adicionada')
    else:
        print('ℹ️  clientes.deve_trocar_senha já existe')

    # Índice único de CPF (SQLite não permite UNIQUE via ALTER TABLE,
    # por isso criamos um índice único — múltiplos NULLs são permitidos).
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_cpf ON clientes(cpf)')
    print('✅ Índice único idx_clientes_cpf garantido')

    # ---------------------------------------------------------------
    # 2. Tabela `planos`
    # ---------------------------------------------------------------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT,
            preco REAL NOT NULL,
            duracao_dias INTEGER DEFAULT 30,
            ativo INTEGER DEFAULT 1
        )
    ''')
    print('✅ Tabela planos garantida')

    # ---------------------------------------------------------------
    # 3. Tabela `cartoes` (apenas dados mascarados — nunca o número completo)
    # ---------------------------------------------------------------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cartoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL,
            numero_final TEXT NOT NULL,
            bandeira TEXT NOT NULL,
            nome_titular TEXT,
            validade_mes INTEGER NOT NULL,
            validade_ano INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1,
            FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente)
        )
    ''')
    print('✅ Tabela cartoes garantida')

    # ---------------------------------------------------------------
    # 4. Tabela `videos` (catálogo)
    # ---------------------------------------------------------------
    cur.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            categoria TEXT DEFAULT 'Outro',
            caminho_arquivo TEXT,
            capa TEXT,
            duracao TEXT,
            ano_lancamento INTEGER,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print('✅ Tabela videos garantida')

    # ---------------------------------------------------------------
    # 5. Seed dos planos (INSERT OR IGNORE respeita o UNIQUE de nome)
    # ---------------------------------------------------------------
    planos = [
        ('Básico', 'Qualidade SD em 1 tela simultânea.', 29.90, 30, 1),
        ('Padrão', 'Qualidade HD em 2 telas simultâneas.', 49.90, 30, 1),
        ('Premium', 'Qualidade Full HD/4K em 4 telas simultâneas.', 79.90, 30, 1),
    ]
    for nome, desc, preco, dias, ativo in planos:
        cur.execute('''
            INSERT OR IGNORE INTO planos (nome, descricao, preco, duracao_dias, ativo)
            VALUES (?, ?, ?, ?, ?)
        ''', (nome, desc, preco, dias, ativo))
    print('✅ Planos iniciais garantidos')

    # ---------------------------------------------------------------
    # 6. Pasta padrão de vídeos
    # ---------------------------------------------------------------
    os.makedirs(VIDEOS_FOLDER, exist_ok=True)
    if not os.listdir(VIDEOS_FOLDER):
        with open(os.path.join(VIDEOS_FOLDER, 'LEIA-ME.txt'), 'w', encoding='utf-8') as f:
            f.write('Coloque aqui os arquivos de vídeo do catálogo (.mp4, .webm).\n'
                    'Depois cadastre-os pelo Painel Admin -> Vídeos.\n')
    print('✅ Pasta de vídeos pronta:', VIDEOS_FOLDER)

    conn.commit()

    # Verificação final
    total_planos = cur.execute('SELECT COUNT(*) FROM planos').fetchone()[0]
    total_videos = cur.execute('SELECT COUNT(*) FROM videos').fetchone()[0]
    print('\n' + '=' * 50)
    print('✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!')
    print('=' * 50)
    print(f'📦 Planos cadastrados: {total_planos}')
    print(f'🎬 Vídeos no catálogo: {total_videos}')
    print(f'📅 Data/Hora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
    print('=' * 50)
    conn.close()


if __name__ == '__main__':
    migrar()
