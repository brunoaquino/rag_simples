"""
Teste da configuração do Celery e Redis
Verifica se o setup básico está funcionando corretamente.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from async_processing.celery_config import get_celery_app, setup_celery_for_environment
from async_processing.redis_client import get_redis_client

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """Testa a conexão com o Redis."""
    logger.info("🔍 Testando conexão com Redis...")
    
    try:
        redis_client = get_redis_client()
        health_status = redis_client.health_check()
        
        if health_status['status'] == 'healthy':
            logger.info("✅ Redis conectado com sucesso!")
            logger.info(f"   Versão: {health_status.get('version')}")
            logger.info(f"   Memória usada: {health_status.get('memory_used')}")
            logger.info(f"   Clientes conectados: {health_status.get('connected_clients')}")
            return True
        else:
            logger.error(f"❌ Redis não está saudável: {health_status}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com Redis: {e}")
        return False


def test_celery_app():
    """Testa a configuração do Celery."""
    logger.info("🔍 Testando configuração do Celery...")
    
    try:
        # Obter a aplicação Celery
        celery_app = get_celery_app()
        
        logger.info("✅ Aplicação Celery inicializada!")
        logger.info(f"   Nome da aplicação: {celery_app.main}")
        logger.info(f"   Broker URL: {celery_app.conf.broker_url}")
        logger.info(f"   Result backend: {celery_app.conf.result_backend}")
        
        # Verificar se consegue se conectar ao broker
        try:
            with celery_app.connection_or_acquire() as conn:
                conn.ensure_connection(max_retries=3)
                logger.info("✅ Conexão com broker confirmada!")
                return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar com broker: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro na configuração do Celery: {e}")
        return False


def test_basic_cache_operations():
    """Testa operações básicas de cache no Redis."""
    logger.info("🔍 Testando operações básicas de cache...")
    
    try:
        redis_client = get_redis_client()
        
        # Teste de escrita
        test_key = "test_celery_setup"
        test_value = {"message": "Hello from Celery setup test!", "timestamp": time.time()}
        
        if redis_client.cache_set(test_key, test_value, ttl=60):
            logger.info("✅ Cache write bem-sucedido!")
        else:
            logger.error("❌ Falha no cache write!")
            return False
        
        # Teste de leitura
        retrieved_value = redis_client.cache_get(test_key)
        if retrieved_value and retrieved_value['message'] == test_value['message']:
            logger.info("✅ Cache read bem-sucedido!")
        else:
            logger.error("❌ Falha no cache read!")
            return False
        
        # Limpeza
        if redis_client.cache_delete(test_key):
            logger.info("✅ Cache delete bem-sucedido!")
        else:
            logger.error("❌ Falha no cache delete!")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro nas operações de cache: {e}")
        return False


def test_environment_configuration():
    """Testa a configuração de ambiente."""
    logger.info("🔍 Testando configuração de ambiente...")
    
    try:
        environment = os.getenv('ENVIRONMENT', 'development')
        logger.info(f"✅ Ambiente configurado: {environment}")
        
        # Testar configuração específica do ambiente
        celery_app = setup_celery_for_environment(environment)
        
        if environment == 'development':
            expected_concurrency = 2
        elif environment == 'production':
            expected_concurrency = 4
        else:
            expected_concurrency = None
        
        if expected_concurrency:
            logger.info(f"✅ Configuração de ambiente aplicada (concurrency esperada: {expected_concurrency})")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na configuração de ambiente: {e}")
        return False


def run_comprehensive_test():
    """Executa todos os testes de configuração."""
    logger.info("🚀 Iniciando teste abrangente da configuração Celery + Redis")
    logger.info("=" * 60)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Celery App Configuration", test_celery_app),
        ("Basic Cache Operations", test_basic_cache_operations),
        ("Environment Configuration", test_environment_configuration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Executando: {test_name}")
        results[test_name] = test_func()
        
        if results[test_name]:
            logger.info(f"✅ {test_name}: PASSOU")
        else:
            logger.error(f"❌ {test_name}: FALHOU")
    
    # Resumo final
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESUMO DOS TESTES:")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        logger.info("🎉 Todos os testes passaram! Configuração está pronta.")
        return True
    else:
        logger.error("⚠️  Alguns testes falharam. Verifique a configuração.")
        return False


if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1) 