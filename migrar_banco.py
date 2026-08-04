import sqlite3
from datetime import datetime

def migrar_banco():
    """Script de migração automática do banco de dados"""
    
    conn = sqlite3.connect('database/dbase.db')
    cursor = conn.cursor()
    
    print("🚀 Iniciando migração do banco de dados...")
    
    try:
        # 1. Criar tabelas novas
        print("📋 Criando tabelas...")
        
        tabelas = [
            """CREATE TABLE IF NOT EXISTS usuarios_sistema (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                cargo TEXT NOT NULL DEFAULT 'suporte',
                permissoes TEXT,
                ativo INTEGER DEFAULT 1,
                ultimo_login TIMESTAMP,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS logs_acesso (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                usuario_tipo TEXT,
                acao TEXT NOT NULL,
                tabela_afetada TEXT,
                registro_id INTEGER,
                descricao TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS configuracoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT UNIQUE NOT NULL,
                valor TEXT,
                descricao TEXT,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
        
        for tabela in tabelas:
            cursor.execute(tabela)
        
        # 2. Migrar tabela clientes
        print("🔄 Migrando tabela clientes...")
        
        # Verificar se precisa migrar
        cursor.execute("PRAGMA table_info(clientes)")
        colunas = [col[1] for col in cursor.fetchall()]
        
        if 'data_cadastro' not in colunas:
            # Criar tabela temporária
            cursor.execute("""
                CREATE TABLE clientes_novo (
                    id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    idade INTEGER NOT NULL,
                    cidade TEXT NOT NULL,
                    senha_hash TEXT,
                    ultimo_acesso TIMESTAMP,
                    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ativo INTEGER DEFAULT 1
                )
            """)
            
            # Copiar dados
            cursor.execute("""
                INSERT INTO clientes_novo (id_cliente, nome, email, idade, cidade)
                SELECT id_cliente, nome, email, idade, cidade FROM clientes
            """)
            
            # Renomear
            cursor.execute("ALTER TABLE clientes RENAME TO clientes_old")
            cursor.execute("ALTER TABLE clientes_novo RENAME TO clientes")
            
            print("✅ Tabela clientes migrada com sucesso!")
        else:
            print("ℹ️  Tabela clientes já está atualizada")
        
        # 3. Criar índices
        print("📊 Criando índices...")
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_clientes_email ON clientes(email)",
            "CREATE INDEX IF NOT EXISTS idx_assinaturas_cliente ON assinaturas(id_cliente)",
            "CREATE INDEX IF NOT EXISTS idx_assinaturas_status ON assinaturas(status)",
            "CREATE INDEX IF NOT EXISTS idx_pagamentos_assinatura ON pagamentos(id_assinaturas)",
        ]
        
        for indice in indices:
            cursor.execute(indice)
        
        # 4. Inserir configurações padrão
        print("⚙️  Inserindo configurações padrão...")
        configs = [
            ('nome_empresa', 'StreamFlix', 'Nome da empresa'),
            ('email_contato', 'contato@streamflix.com', 'Email de contato'),
            ('dias_teste_gratis', '7', 'Dias de teste grátis'),
        ]
        
        for chave, valor, descricao in configs:
            cursor.execute("""
                INSERT OR IGNORE INTO configuracoes (chave, valor, descricao)
                VALUES (?, ?, ?)
            """, (chave, valor, descricao))
        
        # 5. Criar views
        print("👁️  Criando views...")
        cursor.execute("DROP VIEW IF EXISTS vw_relatorio_clientes_completo")
        cursor.execute("""
            CREATE VIEW vw_relatorio_clientes_completo AS
            SELECT 
                c.id_cliente, c.nome, c.email, c.cidade, c.idade,
                a.id_assinaturas, a.plano, a.valor as valor_plano,
                a.status as status_assinatura,
                COUNT(p.id_pagamento) as total_pagamentos,
                COALESCE(SUM(p.valor), 0) as total_pago,
                MAX(p.data_pagamento) as ultimo_pagamento,
                c.data_cadastro, c.ultimo_acesso
            FROM clientes c
            LEFT JOIN assinaturas a ON c.id_cliente = a.id_cliente
            LEFT JOIN pagamentos p ON a.id_assinaturas = p.id_assinaturas
            GROUP BY c.id_cliente
        """)
        
        # Commit
        conn.commit()
        
        # Verificação final
        cursor.execute("SELECT COUNT(*) FROM clientes")
        total_clientes = cursor.fetchone()[0]
        
        print("\n" + "="*50)
        print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("="*50)
        print(f"📊 Total de clientes: {total_clientes}")
        print(f"📅 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("="*50)
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO NA MIGRAÇÃO: {str(e)}")
        raise
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrar_banco()