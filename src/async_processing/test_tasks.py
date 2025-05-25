"""
Teste das tasks do Celery
Testa a execução de tasks básicas para validar a configuração.
"""

import sys
import time
import logging
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from async_processing.tasks import (
    hello_world_task,
    simulate_document_processing,
    simulate_embedding_generation,
    urgent_task
)
from async_processing.redis_client import get_redis_client

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_hello_world_task():
    """Testa a task básica hello_world."""
    logger.info("🧪 Testando hello_world_task...")
    
    try:
        # Executar a task de forma síncrona para teste
        result = hello_world_task.apply_async(args=["Celery"], countdown=1)
        
        # Aguardar resultado
        logger.info(f"Task ID: {result.id}")
        logger.info("Aguardando resultado...")
        
        final_result = result.get(timeout=10)
        logger.info(f"✅ Resultado: {final_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na hello_world_task: {e}")
        return False


def test_document_processing():
    """Testa a task de processamento de documento."""
    logger.info("🧪 Testando simulate_document_processing...")
    
    try:
        # Executar task de processamento
        result = simulate_document_processing.apply_async(
            args=["doc_123"], 
            kwargs={"chunk_count": 3}
        )
        
        logger.info(f"Task ID: {result.id}")
        logger.info("Monitorando progresso...")
        
        redis_client = get_redis_client()
        
        # Monitorar progresso
        while not result.ready():
            progress = redis_client.get_task_progress(result.id)
            if progress:
                logger.info(f"Progresso: {progress.get('progress', 0)}% - {progress.get('current_operation', 'Processando...')}")
            time.sleep(1)
        
        final_result = result.get()
        logger.info(f"✅ Processamento concluído: {final_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento de documento: {e}")
        return False


def test_embedding_generation():
    """Testa a task de geração de embeddings."""
    logger.info("🧪 Testando simulate_embedding_generation...")
    
    try:
        # Primeira execução (deve gerar novo embedding)
        text = "Este é um texto de exemplo para gerar embedding"
        result1 = simulate_embedding_generation.apply_async(
            args=[text], 
            kwargs={"model_name": "test-model"}
        )
        
        logger.info(f"Task ID: {result1.id}")
        final_result1 = result1.get(timeout=10)
        logger.info(f"✅ Primeiro resultado: {final_result1}")
        
        # Segunda execução (deve usar cache)
        result2 = simulate_embedding_generation.apply_async(
            args=[text], 
            kwargs={"model_name": "test-model"}
        )
        
        final_result2 = result2.get(timeout=10)
        logger.info(f"✅ Segundo resultado (cache): {final_result2}")
        
        # Verificar se o segundo resultado veio do cache
        if final_result2['source'] == 'cache':
            logger.info("✅ Cache funcionando corretamente!")
        else:
            logger.warning("⚠️ Cache não funcionou como esperado")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na geração de embedding: {e}")
        return False


def test_priority_task():
    """Testa a task de alta prioridade."""
    logger.info("🧪 Testando urgent_task...")
    
    try:
        # Executar task urgente
        result = urgent_task.apply_async(
            args=["critical"],
            queue='high_priority'  # Especificar fila de alta prioridade
        )
        
        logger.info(f"Task ID: {result.id}")
        final_result = result.get(timeout=5)
        logger.info(f"✅ Task urgente concluída: {final_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na task urgente: {e}")
        return False


def run_task_tests():
    """Executa todos os testes de tasks."""
    logger.info("🚀 Iniciando testes das tasks do Celery")
    logger.info("=" * 60)
    
    # Verificar se o Redis está disponível
    redis_client = get_redis_client()
    health = redis_client.health_check()
    
    if health['status'] != 'healthy':
        logger.error("❌ Redis não está saudável. Não é possível executar os testes.")
        return False
    
    logger.info("✅ Redis está saudável, iniciando testes...")
    
    tests = [
        ("Hello World Task", test_hello_world_task),
        ("Document Processing Task", test_document_processing),
        ("Embedding Generation Task", test_embedding_generation),
        ("Priority Task", test_priority_task),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Executando: {test_name}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ Erro inesperado em {test_name}: {e}")
            results[test_name] = False
        
        if results[test_name]:
            logger.info(f"✅ {test_name}: PASSOU")
        else:
            logger.error(f"❌ {test_name}: FALHOU")
        
        # Pequena pausa entre testes
        time.sleep(1)
    
    # Resumo final
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESUMO DOS TESTES DE TASKS:")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        logger.info("🎉 Todos os testes de tasks passaram! Sistema está funcionando.")
        return True
    else:
        logger.error("⚠️ Alguns testes falharam. Verifique a configuração.")
        return False


if __name__ == "__main__":
    success = run_task_tests()
    sys.exit(0 if success else 1) 