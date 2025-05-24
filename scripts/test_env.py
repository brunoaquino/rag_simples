#!/usr/bin/env python3
"""
Script para testar se o ambiente virtual e dependências estão funcionando.
"""

import sys
import importlib
from typing import List, Tuple

def test_import(module_name: str) -> Tuple[bool, str]:
    """Testa se um módulo pode ser importado."""
    try:
        importlib.import_module(module_name)
        return True, f"✅ {module_name}"
    except ImportError as e:
        return False, f"❌ {module_name}: {str(e)}"

def main():
    """Executa todos os testes de dependências."""
    print("🧪 Testando ambiente do projeto RAG...\n")
    
    # Lista de dependências para testar (nome do módulo, não do pacote pip)
    dependencies = [
        "langchain",
        "langchain_openai", 
        "openai",
        "pinecone",
        "streamlit",
        "fastapi",
        "transformers",
        "sentence_transformers",
        "pandas",
        "numpy",
        "pydantic",
        "uvicorn",
        "sqlalchemy",
        "pdfplumber",
        "PyPDF2",  # Corrigido para o nome real do módulo
        "docx",    # Corrigido para o nome real do módulo (python-docx se importa como docx)
        "markdown",
        "black",
        "pytest"
    ]
    
    results = []
    success_count = 0
    
    for dep in dependencies:
        success, message = test_import(dep)
        results.append((success, message))
        if success:
            success_count += 1
    
    # Exibe resultados
    print("📦 Resultados dos testes de dependências:")
    print("-" * 50)
    
    for success, message in results:
        print(message)
    
    print("-" * 50)
    print(f"📊 Resumo: {success_count}/{len(dependencies)} dependências OK")
    
    if success_count == len(dependencies):
        print("🎉 Todos os testes passaram! Ambiente pronto para uso.")
        return 0
    else:
        print(f"⚠️  {len(dependencies) - success_count} dependências com problemas.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 