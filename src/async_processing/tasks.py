"""
Tasks básicas do Celery para o Sistema RAG
Demonstração de funcionalidade e tasks de exemplo.
"""

import time
import logging
from typing import Dict, Any
from celery import current_task
from .celery_config import app
from .redis_client import get_redis_client

logger = logging.getLogger(__name__)


@app.task(bind=True, name='rag_system.basic.hello_world')
def hello_world_task(self, name: str = "World") -> Dict[str, Any]:
    """
    Task básica de teste para verificar se o Celery está funcionando.
    
    Args:
        name: Nome para cumprimentar
        
    Returns:
        Resultado da task com informações básicas
    """
    task_id = self.request.id
    logger.info(f"Executando hello_world_task com ID: {task_id}")
    
    # Simular algum processamento
    time.sleep(2)
    
    result = {
        "message": f"Hello, {name}!",
        "task_id": task_id,
        "status": "completed",
        "timestamp": time.time()
    }
    
    logger.info(f"Task {task_id} concluída com sucesso")
    return result


@app.task(bind=True, name='rag_system.document_processing.simulate_processing')
def simulate_document_processing(self, document_id: str, chunk_count: int = 5) -> Dict[str, Any]:
    """
    Simula processamento de documento com progresso em tempo real.
    
    Args:
        document_id: ID do documento para processar
        chunk_count: Número de chunks para processar
        
    Returns:
        Resultado do processamento
    """
    task_id = self.request.id
    logger.info(f"Iniciando processamento do documento {document_id} (Task ID: {task_id})")
    
    redis_client = get_redis_client()
    
    # Atualizar progresso inicial
    progress_data = {
        "document_id": document_id,
        "task_id": task_id,
        "status": "processing",
        "progress": 0,
        "total_chunks": chunk_count,
        "processed_chunks": 0,
        "current_operation": "Iniciando processamento"
    }
    redis_client.set_task_progress(task_id, progress_data)
    
    # Simular processamento de chunks
    for i in range(chunk_count):
        # Simular tempo de processamento
        time.sleep(1)
        
        processed_chunks = i + 1
        progress = int((processed_chunks / chunk_count) * 100)
        
        progress_data.update({
            "progress": progress,
            "processed_chunks": processed_chunks,
            "current_operation": f"Processando chunk {processed_chunks}/{chunk_count}"
        })
        
        redis_client.set_task_progress(task_id, progress_data)
        
        # Atualizar status da task no Celery
        self.update_state(
            state='PROGRESS',
            meta={
                'document_id': document_id,
                'progress': progress,
                'processed_chunks': processed_chunks,
                'total_chunks': chunk_count
            }
        )
        
        logger.info(f"Chunk {processed_chunks}/{chunk_count} processado ({progress}%)")
    
    # Finalizar processamento
    final_result = {
        "document_id": document_id,
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "processed_chunks": chunk_count,
        "total_chunks": chunk_count,
        "processing_time": chunk_count,  # segundos
        "timestamp": time.time()
    }
    
    redis_client.set_task_progress(task_id, final_result, ttl=7200)  # 2 horas
    logger.info(f"Processamento do documento {document_id} concluído com sucesso")
    
    return final_result


@app.task(bind=True, name='rag_system.embedding_generation.simulate_embedding')
def simulate_embedding_generation(self, text: str, model_name: str = "default") -> Dict[str, Any]:
    """
    Simula geração de embeddings para texto.
    
    Args:
        text: Texto para gerar embedding
        model_name: Nome do modelo a usar
        
    Returns:
        Resultado da geração de embedding
    """
    task_id = self.request.id
    logger.info(f"Gerando embedding para texto (Task ID: {task_id})")
    
    redis_client = get_redis_client()
    
    # Verificar cache primeiro
    text_hash = str(hash(text))
    cached_embedding = redis_client.get_cached_embedding(text_hash)
    
    if cached_embedding:
        logger.info(f"Embedding encontrado no cache para hash {text_hash}")
        return {
            "text_hash": text_hash,
            "task_id": task_id,
            "status": "completed",
            "source": "cache",
            "model_name": model_name,
            "embedding_size": len(cached_embedding),
            "timestamp": time.time()
        }
    
    # Simular geração de embedding
    logger.info(f"Gerando novo embedding com modelo {model_name}")
    time.sleep(3)  # Simular tempo de processamento
    
    # Simular embedding de 1024 dimensões
    import random
    fake_embedding = [random.random() for _ in range(1024)]
    
    # Armazenar no cache
    redis_client.cache_embedding(text_hash, fake_embedding, ttl=86400)  # 24 horas
    
    result = {
        "text_hash": text_hash,
        "task_id": task_id,
        "status": "completed",
        "source": "generated",
        "model_name": model_name,
        "embedding_size": len(fake_embedding),
        "text_length": len(text),
        "timestamp": time.time()
    }
    
    logger.info(f"Embedding gerado com sucesso (Task ID: {task_id})")
    return result


@app.task(bind=True, name='rag_system.high_priority.urgent_task')
def urgent_task(self, priority_level: str = "high") -> Dict[str, Any]:
    """
    Task de alta prioridade para demonstrar o sistema de filas priorizadas.
    
    Args:
        priority_level: Nível de prioridade da task
        
    Returns:
        Resultado da task urgente
    """
    task_id = self.request.id
    logger.info(f"Executando task urgente com prioridade {priority_level} (Task ID: {task_id})")
    
    # Processamento rápido para tasks prioritárias
    time.sleep(0.5)
    
    result = {
        "task_id": task_id,
        "priority_level": priority_level,
        "status": "completed",
        "execution_time": 0.5,
        "message": "Task urgente processada com prioridade",
        "timestamp": time.time()
    }
    
    logger.info(f"Task urgente {task_id} concluída")
    return result


@app.task(name='rag_system.maintenance.cleanup_expired_results')
def cleanup_expired_results() -> Dict[str, Any]:
    """
    Task de manutenção para limpar resultados expirados.
    Executada periodicamente pelo Celery Beat.
    
    Returns:
        Estatísticas da limpeza
    """
    logger.info("Iniciando limpeza de resultados expirados")
    
    redis_client = get_redis_client()
    
    # Simular limpeza
    cleaned_keys = redis_client.cleanup_expired_keys("cache:*")
    
    result = {
        "operation": "cleanup_expired_results",
        "cleaned_keys": cleaned_keys,
        "status": "completed",
        "timestamp": time.time()
    }
    
    logger.info(f"Limpeza concluída: {cleaned_keys} chaves removidas")
    return result


@app.task(name='rag_system.monitoring.update_system_metrics')
def update_system_metrics() -> Dict[str, Any]:
    """
    Task de monitoramento para atualizar métricas do sistema.
    Executada periodicamente pelo Celery Beat.
    
    Returns:
        Métricas atualizadas do sistema
    """
    redis_client = get_redis_client()
    
    # Obter métricas básicas
    health_status = redis_client.health_check()
    memory_usage = redis_client.get_memory_usage()
    
    # Atualizar métricas no Redis
    metrics = {
        "redis_status": health_status["status"],
        "redis_memory": health_status.get("memory_used", "unknown"),
        "connected_clients": health_status.get("connected_clients", 0),
        "timestamp": time.time()
    }
    
    redis_client.set_metric("system_health", 1 if health_status["status"] == "healthy" else 0)
    redis_client.set_metric("connected_clients", health_status.get("connected_clients", 0))
    
    logger.info("Métricas do sistema atualizadas")
    return metrics 