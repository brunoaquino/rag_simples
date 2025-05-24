# Configuração de Variáveis de Ambiente

Este documento explica como configurar as variáveis de ambiente necessárias para o Sistema RAG Empresarial.

## 📋 Arquivo .env

O projeto usa um arquivo `.env` para gerenciar configurações sensíveis. Este arquivo **NÃO** deve ser commitado no repositório.

### Setup Inicial

1. Copie o arquivo de exemplo:

```bash
cp config/env_example.txt .env
```

2. Edite o arquivo `.env` com suas configurações reais:

```bash
nano .env  # ou seu editor preferido
```

## 🔑 Variáveis Obrigatórias

### APIs de IA

```env
# OpenAI (Obrigatório para LLM)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Pinecone (Obrigatório para vector database)
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_ENVIRONMENT=us-west1-gcp-free
PINECONE_INDEX_NAME=rag-embeddings
```

### Banco de Dados

```env
# SQLite local (padrão) ou PostgreSQL para produção
DATABASE_URL=sqlite:///./data/rag_system.db
```

### Segurança

```env
# Chave secreta para JWT (gere uma chave forte)
SECRET_KEY=your-strong-secret-key-here
```

## ⚙️ Variáveis Opcionais

### Configurações de Embeddings

```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### Configurações de Log

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Configurações de Servidor

```env
STREAMLIT_SERVER_PORT=8501
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
```

## 🛡️ Segurança

### Geração de SECRET_KEY

```python
# Execute este código Python para gerar uma chave secreta:
import secrets
print(secrets.token_urlsafe(32))
```

### Permissões do Arquivo

```bash
# Defina permissões restritivas para o .env
chmod 600 .env
```

## 🔍 Validação

Execute o script de teste para validar suas configurações:

```bash
python scripts/test_env.py
```

## 📝 Variáveis por Ambiente

### Desenvolvimento

```env
DEBUG=true
LOG_LEVEL=DEBUG
DATABASE_ECHO=true
```

### Produção

```env
DEBUG=false
LOG_LEVEL=INFO
DATABASE_ECHO=false
CORS_ORIGINS=["https://seu-dominio.com"]
```

## 🚨 Troubleshooting

### Erro: OpenAI API Key

- Verifique se a chave começa com `sk-`
- Confirme que a chave está ativa no dashboard da OpenAI

### Erro: Pinecone Connection

- Verifique se o ambiente Pinecone está correto
- Confirme se o índice existe no Pinecone

### Erro: Database Connection

- Para SQLite: verifique se o diretório `data/` existe
- Para PostgreSQL: confirme se o servidor está rodando

## 📚 Referências

- [OpenAI API Keys](https://platform.openai.com/api-keys)
- [Pinecone Getting Started](https://docs.pinecone.io/docs/quickstart)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
