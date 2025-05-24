#!/bin/bash

# Script para ativar o ambiente virtual do projeto RAG
echo "🚀 Ativando ambiente virtual do projeto RAG..."

# Verifica se o ambiente virtual existe
if [ ! -d "venv" ]; then
    echo "❌ Ambiente virtual não encontrado. Execute primeiro:"
    echo "   python3 -m venv venv"
    exit 1
fi

# Ativa o ambiente virtual
source venv/bin/activate

# Verifica se a ativação foi bem-sucedida
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Ambiente virtual ativado com sucesso!"
    echo "📍 Python: $(which python)"
    echo "📦 Versão: $(python --version)"
    echo ""
    echo "Para desativar, execute: deactivate"
    echo "Para instalar dependências: pip install -r requirements.txt"
else
    echo "❌ Falha ao ativar o ambiente virtual"
    exit 1
fi 