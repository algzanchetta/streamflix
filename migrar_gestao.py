"""
Migração de gestão: tipos de vídeo + status de pagamento.

Adiciona ao banco existente:
  - Coluna em `videos`: tipo ('Filme' | 'Show' | 'Documentário' | 'Outro')
  - Coluna em `pagamentos`: status ('pago' | 'pendente') com backfill
    a partir da data do pagamento (NULL = pendente)
  - Índices para as novas colunas

Executar com:  python migrar_gestao.py
O script é idempotente (pode rodar mais de uma vez).
"""
import os
import sqlite3
import sys

from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

basedir = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(basedir, 'database', 'dbase.db')


def colunas_da_tabela(conn, tabela):
    return [col[1] for col in conn.execute(f'PRAGMA table_info({tabela})').fetchall()]


def migrar():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print('🚀 Iniciando migração de gestão (tipos de vídeo e status de pagamento)...')

    # ---------------------------------------------------------------
    # 1. Coluna `tipo` em `videos`
    # ---------------------------------------------------------------
    colunas = colunas_da_tabela(conn, 'videos')
    if 'tipo' not in colunas:
        cur.execute("ALTER TABLE videos ADD COLUMN tipo TEXT DEFAULT 'Filme'")
        print('✅ Coluna videos.tipo adicionada (padrão: Filme)')
    else:
        print('ℹ️  videos.tipo já existe')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_videos_tipo ON videos(tipo)')
    print('✅ Índice idx_videos_tipo garantido')

    # ---------------------------------------------------------------
    # 2. Coluna `status` em `pagamentos` (pago / pendente)
    # ---------------------------------------------------------------
    colunas = colunas_da_tabela(conn, 'pagamentos')
    if 'status' not in colunas:
        cur.execute("ALTER TABLE pagamentos ADD COLUMN status TEXT DEFAULT 'pago'")
        # Backfill: pagamento com data registrada = pago; sem data = pendente
        cur.execute(
            "UPDATE pagamentos SET status = CASE "
            "WHEN data_pagamento IS NULL THEN 'pendente' ELSE 'pago' END"
        )
        print('✅ Coluna pagamentos.status adicionada e preenchida (backfill)')
    else:
        print('ℹ️  pagamentos.status já existe')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status)')
    print('✅ Índice idx_pagamentos_status garantido')

    conn.commit()

    # Verificação final
    pendentes = cur.execute(
        "SELECT COUNT(*) FROM pagamentos WHERE status = 'pendente'"
    ).fetchone()[0]
    pagos = cur.execute(
        "SELECT COUNT(*) FROM pagamentos WHERE status = 'pago'"
    ).fetchone()[0]
    tipos = cur.execute(
        'SELECT tipo, COUNT(*) FROM videos GROUP BY tipo'
    ).fetchall()

    print('\n' + '=' * 50)
    print('✅ MIGRAÇÃO DE GESTÃO CONCLUÍDA!')
    print('=' * 50)
    print(f'💳 Pagamentos: {pagos} pagos, {pendentes} pendentes')
    for tipo, qtd in tipos:
        print(f'🎬  Vídeos do tipo "{tipo}": {qtd}')
    print(f'📅 Data/Hora: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
    print('=' * 50)
    conn.close()


if __name__ == '__main__':
    migrar()
