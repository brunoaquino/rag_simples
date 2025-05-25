"""
Teste simples das configurações do Celery
Verifica se as tasks podem ser executadas corretamente.
"""

import sys
import time
import logging
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from async_processing.celery_config import app, setup_celery_for_environment

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_celery_configuration():
    """Testa se a configuração do Celery está correta."""
    logger.info("🔍 Testando configuração do Celery...")
    
    try:
        # Configurar para testes
        app.conf.task_always_eager = True
        app.conf.task_eager_propagates = True
        
        logger.info("✅ Configuração aplicada com sucesso")
        logger.info(f"   App name: {app.main}")
        logger.info(f"   Broker: {app.conf.broker_url}")
        logger.info(f"   Result backend: {app.conf.result_backend}")
        logger.info(f"   Always eager: {app.conf.task_always_eager}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na configuração: {e}")
        return False


def test_basic_task():
    """Testa uma task básica inline."""
    logger.info("🔍 Testando task básica inline...")
    
    try:
        @app.task
        def add_numbers(x, y):
            return x + y
        
        # Executar a task
        result = add_numbers.apply_async(args=[4, 5])
        final_result = result.get()
        
        if final_result == 9:
            logger.info(f"✅ Task executada com sucesso: 4 + 5 = {final_result}")
            return True
        else:
            logger.error(f"❌ Resultado inesperado: {final_result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na task básica: {e}")
        return False


def test_redis_connection():
    """Testa a conexão com Redis."""
    logger.info("🔍 Testando conexão com Redis...")
    
    try:
        from async_processing.redis_client import get_redis_client
        
        redis_client = get_redis_client()
        health = redis_client.health_check()
        
        if health['status'] == 'healthy':
            logger.info("✅ Redis conectado com sucesso")
            logger.info(f"   Versão: {health.get('version')}")
            logger.info(f"   Memória: {health.get('memory_used')}")
            return True
        else:
            logger.error(f"❌ Redis não está saudável: {health}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com Redis: {e}")
        return False


def test_queue_configuration():
    """Testa se as filas estão configuradas corretamente."""
    logger.info("🔍 Testando configuração de filas...")
    
    try:
        queues = app.conf.task_queues
        queue_names = [q.name for q in queues]
        
        expected_queues = [
            'high_priority',
            'document_processing', 
            'embedding_generation',
            'vector_operations',
            'low_priority',
            'default'
        ]
        
        missing_queues = set(expected_queues) - set(queue_names)
        
        if not missing_queues:
            logger.info("✅ Todas as filas configuradas corretamente")
            logger.info(f"   Filas: {', '.join(queue_names)}")
            return True
        else:
            logger.error(f"❌ Filas faltando: {missing_queues}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na configuração de filas: {e}")
        return False


def run_simple_tests():
    """Executa testes simples de configuração."""
    logger.info("🚀 Iniciando testes simples do Celery")
    logger.info("=" * 50)
    
    tests = [
        ("Configuração do Celery", test_celery_configuration),
        ("Conexão com Redis", test_redis_connection),
        ("Configuração de Filas", test_queue_configuration),
        ("Task Básica", test_basic_task),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 {test_name}")
        results[test_name] = test_func()
        
        if results[test_name]:
            logger.info(f"✅ {test_name}: PASSOU")
        else:
            logger.error(f"❌ {test_name}: FALHOU")
    
    # Resumo
    logger.info("\n" + "=" * 50)
    logger.info("📊 RESUMO:")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        logger.info("🎉 Configuração básica está funcionando!")
        logger.info("\n📋 Próximos passos:")
        logger.info("   1. Inicie o worker: python start_celery_worker.py worker")
        logger.info("   2. Teste tasks assíncronas: python src/async_processing/test_tasks.py")
        logger.info("   3. Inicie o Flower: python start_celery_worker.py flower")
        return True
    else:
        logger.error("⚠️ Alguns testes falharam. Verifique a configuração.")
        return False


if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1) 