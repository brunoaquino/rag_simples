#!/usr/bin/env python3
"""
Script para verificar se as variáveis de ambiente estão configuradas corretamente.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional

def load_env_file(env_path: str = ".env") -> bool:
    """Carrega o arquivo .env se existir."""
    if not os.path.exists(env_path):
        return False
    
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return True
    except ImportError:
        print("⚠️  python-dotenv não instalado. Instale com: pip install python-dotenv")
        return False

def check_required_vars() -> List[Tuple[str, bool, str]]:
    """Verifica variáveis obrigatórias."""
    required_vars = [
        ("OPENAI_API_KEY", "Chave API da OpenAI"),
        ("PINECONE_API_KEY", "Chave API do Pinecone"),
        ("SECRET_KEY", "Chave secreta para JWT"),
    ]
    
    results = []
    for var_name, description in required_vars:
        value = os.getenv(var_name)
        if value:
            # Verificações específicas
            if var_name == "OPENAI_API_KEY" and not value.startswith("sk-"):
                results.append((var_name, False, f"❌ {description}: Deve começar com 'sk-'"))
            elif var_name == "SECRET_KEY" and len(value) < 16:
                results.append((var_name, False, f"❌ {description}: Muito curta (mínimo 16 caracteres)"))
            else:
                results.append((var_name, True, f"✅ {description}: Configurada"))
        else:
            results.append((var_name, False, f"❌ {description}: Não encontrada"))
    
    return results

def check_optional_vars() -> List[Tuple[str, bool, str]]:
    """Verifica variáveis opcionais."""
    optional_vars = [
        ("PINECONE_ENVIRONMENT", "us-west1-gcp-free", "Ambiente Pinecone"),
        ("PINECONE_INDEX_NAME", "rag-embeddings", "Nome do índice Pinecone"),
        ("DATABASE_URL", "sqlite:///./data/rag_system.db", "URL do banco de dados"),
        ("LOG_LEVEL", "INFO", "Nível de log"),
        ("FASTAPI_PORT", "8000", "Porta da API"),
        ("STREAMLIT_SERVER_PORT", "8501", "Porta do Streamlit"),
    ]
    
    results = []
    for var_name, default_value, description in optional_vars:
        value = os.getenv(var_name, default_value)
        if value == default_value:
            results.append((var_name, True, f"🔧 {description}: Usando padrão ({default_value})"))
        else:
            results.append((var_name, True, f"✅ {description}: Personalizada ({value})"))
    
    return results

def validate_database_connection() -> Tuple[bool, str]:
    """Valida a conexão com o banco de dados."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/rag_system.db")
    
    if database_url.startswith("sqlite:"):
        # Para SQLite, verifica se o diretório existe
        db_path = database_url.replace("sqlite:///", "").replace("sqlite://", "")
        db_dir = Path(db_path).parent
        
        if not db_dir.exists():
            return False, f"❌ Diretório do banco SQLite não existe: {db_dir}"
        
        return True, f"✅ Diretório do banco SQLite: {db_dir}"
    
    else:
        # Para outros bancos, apenas verifica se a URL parece válida
        if "://" in database_url:
            return True, f"✅ URL do banco: {database_url.split('://')[0]}://***"
        else:
            return False, f"❌ URL do banco inválida: {database_url}"

def generate_secret_key() -> str:
    """Gera uma chave secreta segura."""
    try:
        import secrets
        return secrets.token_urlsafe(32)
    except ImportError:
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def main():
    """Executa todas as verificações."""
    print("🔍 Verificando configuração de variáveis de ambiente...\n")
    
    # Carrega arquivo .env
    env_loaded = load_env_file()
    if env_loaded:
        print("✅ Arquivo .env carregado\n")
    else:
        print("⚠️  Arquivo .env não encontrado. Criando exemplo...\n")
        # Cria .env de exemplo se não existir
        if not os.path.exists(".env"):
            try:
                with open("config/env_example.txt", "r") as f:
                    content = f.read()
                with open(".env", "w") as f:
                    f.write(content)
                print("✅ Arquivo .env criado a partir do exemplo")
                print("📝 Por favor, edite o arquivo .env com suas configurações reais\n")
            except FileNotFoundError:
                print("❌ Arquivo de exemplo não encontrado: config/env_example.txt\n")
    
    # Verifica variáveis obrigatórias
    print("🔑 Variáveis Obrigatórias:")
    print("-" * 50)
    required_results = check_required_vars()
    required_ok = 0
    
    for var_name, success, message in required_results:
        print(message)
        if success:
            required_ok += 1
    
    print(f"\n📊 Obrigatórias: {required_ok}/{len(required_results)} OK\n")
    
    # Verifica variáveis opcionais
    print("⚙️  Variáveis Opcionais:")
    print("-" * 50)
    optional_results = check_optional_vars()
    
    for var_name, success, message in optional_results:
        print(message)
    
    # Valida banco de dados
    print("\n💾 Banco de Dados:")
    print("-" * 50)
    db_ok, db_message = validate_database_connection()
    print(db_message)
    
    # Resumo final
    print("\n" + "=" * 60)
    if required_ok == len(required_results) and db_ok:
        print("🎉 Configuração OK! Ambiente pronto para uso.")
        return 0
    else:
        print("⚠️  Configuração incompleta. Verifique as variáveis acima.")
        
        # Sugestões
        print("\n💡 Dicas:")
        if not os.getenv("SECRET_KEY"):
            secret = generate_secret_key()
            print(f"   - SECRET_KEY sugerida: {secret}")
        
        print("   - Consulte docs/environment_setup.md para mais detalhes")
        print("   - Execute: cp config/env_example.txt .env")
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 