#!/usr/bin/env python3
"""
Script para iniciar o worker do Celery para o Sistema RAG
Uso: python start_celery_worker.py [options]
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Adicionar src ao path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def start_worker(concurrency=2, loglevel="info", queues=None, environment="development"):
    """
    Inicia o worker do Celery com as configurações apropriadas.
    
    Args:
        concurrency: Número de workers concorrentes
        loglevel: Nível de log (debug, info, warning, error)
        queues: Filas específicas para processar (padrão: todas)
        environment: Ambiente de execução
    """
    
    # Configurar variável de ambiente
    os.environ['ENVIRONMENT'] = environment
    
    # Comando base do Celery
    cmd = [
        sys.executable, "-m", "celery", 
        "-A", "src.async_processing.celery_config",
        "worker",
        "--concurrency", str(concurrency),
        "--loglevel", loglevel
    ]
    
    # Adicionar filas específicas se fornecidas
    if queues:
        cmd.extend(["--queues", queues])
    
    print(f"🚀 Iniciando Celery Worker para o Sistema RAG")
    print(f"   Ambiente: {environment}")
    print(f"   Concorrência: {concurrency}")
    print(f"   Log Level: {loglevel}")
    print(f"   Filas: {queues or 'todas'}")
    print(f"   Comando: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        # Executar o comando
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Worker interrompido pelo usuário")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar o worker: {e}")
        sys.exit(1)

def start_beat(loglevel="info", environment="development"):
    """
    Inicia o Celery Beat scheduler.
    
    Args:
        loglevel: Nível de log
        environment: Ambiente de execução
    """
    
    # Configurar variável de ambiente
    os.environ['ENVIRONMENT'] = environment
    
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "src.async_processing.celery_config",
        "beat",
        "--loglevel", loglevel
    ]
    
    print(f"⏰ Iniciando Celery Beat Scheduler")
    print(f"   Ambiente: {environment}")
    print(f"   Log Level: {loglevel}")
    print(f"   Comando: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Beat scheduler interrompido pelo usuário")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar o beat scheduler: {e}")
        sys.exit(1)

def start_flower(port=5555, environment="development"):
    """
    Inicia o Flower para monitoramento.
    
    Args:
        port: Porta para o Flower
        environment: Ambiente de execução
    """
    
    # Configurar variável de ambiente
    os.environ['ENVIRONMENT'] = environment
    
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "src.async_processing.celery_config",
        "flower",
        "--port", str(port)
    ]
    
    print(f"🌸 Iniciando Flower Monitoring")
    print(f"   Ambiente: {environment}")
    print(f"   Porta: {port}")
    print(f"   URL: http://localhost:{port}")
    print(f"   Comando: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 Flower interrompido pelo usuário")
    except subprocess.CalledProcessError as e:
        print(f"❌ Erro ao executar o Flower: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Iniciar componentes do Celery para o Sistema RAG"
    )
    
    parser.add_argument(
        "component",
        choices=["worker", "beat", "flower", "all"],
        help="Componente para iniciar"
    )
    
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=2,
        help="Número de workers concorrentes (padrão: 2)"
    )
    
    parser.add_argument(
        "--loglevel", "-l",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Nível de log (padrão: info)"
    )
    
    parser.add_argument(
        "--queues", "-q",
        help="Filas específicas para processar (ex: 'high_priority,document_processing')"
    )
    
    parser.add_argument(
        "--environment", "-e",
        choices=["development", "production", "testing"],
        default="development",
        help="Ambiente de execução (padrão: development)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=5555,
        help="Porta para o Flower (padrão: 5555)"
    )
    
    args = parser.parse_args()
    
    # Verificar se o Redis está rodando
    try:
        sys.path.insert(0, "src")
        from async_processing.redis_client import get_redis_client
        
        redis_client = get_redis_client()
        health = redis_client.health_check()
        
        if health['status'] != 'healthy':
            print("❌ Redis não está saudável. Verifique se o Redis está rodando.")
            print("   Dica: execute 'docker-compose up -d redis' para iniciar o Redis")
            sys.exit(1)
        
        print("✅ Redis está saudável")
        
    except Exception as e:
        print(f"❌ Erro ao verificar Redis: {e}")
        print("   Verifique se o Redis está rodando e as dependências estão instaladas")
        sys.exit(1)
    
    # Iniciar o componente solicitado
    if args.component == "worker":
        start_worker(
            concurrency=args.concurrency,
            loglevel=args.loglevel,
            queues=args.queues,
            environment=args.environment
        )
    elif args.component == "beat":
        start_beat(
            loglevel=args.loglevel,
            environment=args.environment
        )
    elif args.component == "flower":
        start_flower(
            port=args.port,
            environment=args.environment
        )
    elif args.component == "all":
        print("🚀 Para iniciar todos os componentes, execute em terminais separados:")
        print(f"   1. Worker: python {__file__} worker --environment {args.environment}")
        print(f"   2. Beat: python {__file__} beat --environment {args.environment}")
        print(f"   3. Flower: python {__file__} flower --environment {args.environment}")

if __name__ == "__main__":
    main() 