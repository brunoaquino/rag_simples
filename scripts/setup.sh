#!/bin/bash

# Script de setup automatizado para o Sistema RAG Empresarial
set -e

echo "🚀 Iniciando setup do Sistema RAG Empresarial..."
echo ""

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Por favor, instale Python 3.9 ou superior."
    exit 1
fi

# Verificar versão do Python
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "🐍 Python detectado: $PYTHON_VERSION"

# Criar ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
else
    echo "✅ Ambiente virtual já existe"
fi

# Ativar ambiente virtual
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Atualizar pip
echo "⬆️  Atualizando pip..."
pip install --upgrade pip

# Instalar dependências
echo "📚 Instalando dependências..."
if [ -f "requirements/core.txt" ]; then
    pip install -r requirements/core.txt
    pip install -r requirements/ai.txt  
    pip install -r requirements/web.txt
else
    pip install -r requirements.txt
fi

# Criar arquivo .env se não existir
if [ ! -f ".env" ]; then
    echo "⚙️  Criando arquivo .env..."
    cp config/env_example.txt .env
    echo "📝 Por favor, edite o arquivo .env com suas chaves de API"
else
    echo "✅ Arquivo .env já existe"
fi

# Testar ambiente
echo "🧪 Testando ambiente..."
python scripts/test_env.py

echo ""
echo "🎉 Setup concluído com sucesso!"
echo ""
echo "📋 Próximos passos:"
echo "1. Edite o arquivo .env com suas chaves de API"
echo "2. Execute 'source venv/bin/activate' para ativar o ambiente"
echo "3. Execute 'make help' para ver comandos disponíveis"
echo "4. Execute 'make run-streamlit' para iniciar a interface"
echo ""
echo "📖 Documentação completa disponível no README.md" 