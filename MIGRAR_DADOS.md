# Migração de Dados: SQLite → PostgreSQL

## Passo 1: Criar PostgreSQL no Railway

1. Acesse https://railway.app
2. Clique em **"New Project"**
3. Selecione **"Database"** > **"PostgreSQL"**
4. Railway vai criar um banco automático
5. Copie a URL de conexão (Railway fornece em "DATABASE_URL")

## Passo 2: Configurar variável de ambiente

1. No Railway, vá até o serviço do backend (`plataforma-farmaceutica`)
2. Clique em **"Variables"**
3. Adicione uma nova variável:
   - Nome: `DATABASE_URL`
   - Valor: (copie a URL do PostgreSQL que criou)
4. O backend vai usar essa variável automaticamente

## Passo 3: Rodar a migração

**No seu computador local:**

```bash
# Instala psycopg2
pip install psycopg2-binary

# Define a variável de ambiente com a URL do PostgreSQL
set DATABASE_URL=postgresql://user:pass@host:port/dbname

# Roda o script de migração
python migrate_db.py
```

## Passo 4: Fazer deploy

1. Commit e push do código atualizado (já feito)
2. Railway vai detectar a variável `DATABASE_URL` e usar PostgreSQL
3. Pronto! Dados online 🎉

---

**⚠️ SEGURANÇA:**
- Backup foi feito em `bkp/pharma_backup_*.db`
- Dados originais no SQLite local continuam intactos
- PostgreSQL é um backup adicional
