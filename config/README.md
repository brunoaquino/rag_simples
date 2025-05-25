# Configuração de Ambiente - Sistema RAG

Este diretório contém arquivos de configuração e templates para o Sistema RAG Empresarial.

## Configuração Rápida

### 1. Criar arquivo .env

```bash
# Executar script automatizado
./scripts/create_env.sh

# OU copiar manualmente
cp config/env_example.txt .env
```

### 2. Configurar Redis

Para usar Redis localmente via Docker:

```bash
# Iniciar Redis
docker-compose up -d redis

# Verificar se está funcionando
docker-compose logs redis
```

**Configurações padrão:**

- `REDIS_HOST=localhost`
- `REDIS_PORT=6379`
- `REDIS_DB=0` (desenvolvimento)
- `REDIS_DB=1` (testes)

### 3. Configurar Chaves de API

Edite o arquivo `.env` e configure as chaves necessárias:

#### Obrigatórias para funcionalidade básica:

```bash
# Para processamento de embeddings
PINECONE_API_KEY=xxxxx
PINECONE_INDEX_NAME=rag-documentos

# Para IA (pelo menos uma)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
# OU
OPENAI_API_KEY=sk-xxxxx
```

#### Opcionais para funcionalidades avançadas:

```bash
# Para pesquisa e análise
PERPLEXITY_API_KEY=pplx-xxxxx

# Para outros modelos
GOOGLE_API_KEY=xxxxx
MISTRAL_API_KEY=xxxxx
```

## Variáveis de Ambiente Disponíveis

### Redis/Cache

- `REDIS_HOST` - Host do Redis (padrão: localhost)
- `REDIS_PORT` - Porta do Redis (padrão: 6379)
- `REDIS_DB` - Database do Redis (padrão: 0)
- `REDIS_PASSWORD` - Senha do Redis (opcional)
- `REDIS_MAX_CONNECTIONS` - Pool de conexões (padrão: 20)

### Processamento Assíncrono

- `ENVIRONMENT` - Ambiente de execução (development/production/testing)

### Provedores de IA

- `ANTHROPIC_API_KEY` - Claude (recomendado)
- `OPENAI_API_KEY` - GPT/Embeddings
- `PERPLEXITY_API_KEY` - Pesquisa
- `GOOGLE_API_KEY` - Gemini
- `MISTRAL_API_KEY` - Mistral
- `XAI_API_KEY` - Grok
- `OPENROUTER_API_KEY` - Múltiplos modelos

### Vector Database

- `PINECONE_API_KEY` - Chave da API Pinecone
- `PINECONE_ENVIRONMENT` - Ambiente Pinecone
- `PINECONE_INDEX_NAME` - Nome do índice

### Performance

- `MAX_WORKERS` - Workers para processamento (padrão: 4)
- `TIMEOUT_SECONDS` - Timeout geral (padrão: 300)

### Logging

- `LOG_LEVEL` - Nível de log (DEBUG/INFO/WARNING/ERROR)

## Ambientes

### Desenvolvimento

```bash
ENVIRONMENT=development
LOG_LEVEL=INFO
DEBUG=true
```

### Produção

```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
DEBUG=false
MAX_WORKERS=8
REDIS_MAX_CONNECTIONS=50
```

### Testes

```bash
ENVIRONMENT=testing
REDIS_DB=1
LOG_LEVEL=DEBUG
```

## Verificação da Configuração

Para testar se tudo está configurado corretamente:

```bash
# Testar Redis
docker-compose exec redis redis-cli ping

# Testar sistema assíncrono
python -m pytest tests/test_async_setup.py -v

# Verificar logs
tail -f logs/rag_system.log
```

## Troubleshooting

### Redis não conecta

1. Verificar se Docker está rodando
2. Verificar se a porta 6379 está livre
3. Verificar logs: `docker-compose logs redis`

### Chaves de API inválidas

1. Verificar se as chaves estão corretas no `.env`
2. Verificar se as chaves têm permissões necessárias
3. Testar as chaves individualmente

### Problemas de performance

1. Ajustar `MAX_WORKERS` conforme recursos
2. Aumentar `REDIS_MAX_CONNECTIONS` se necessário
3. Monitorar uso de memória Redis
