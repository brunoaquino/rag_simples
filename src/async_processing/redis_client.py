"""
Cliente Redis para Sistema RAG
Cliente robusto para Redis com suporte a cache, pub/sub e operações distribuídas.
"""

import os
import json
import logging
import redis
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta
from contextlib import contextmanager
import pickle

logger = logging.getLogger(__name__)


class RedisClient:
    """Cliente Redis com funcionalidades avançadas para o sistema RAG."""
    
    def __init__(self, 
                 host: str = None,
                 port: int = None,
                 db: int = None,
                 password: str = None,
                 decode_responses: bool = True,
                 max_connections: int = 20):
        """
        Inicializa o cliente Redis.
        
        Args:
            host: Host do Redis
            port: Porta do Redis
            db: Número do banco de dados
            password: Senha do Redis
            decode_responses: Se deve decodificar respostas automaticamente
            max_connections: Máximo de conexões no pool
        """
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db or int(os.getenv('REDIS_DB', 0))
        self.password = password or os.getenv('REDIS_PASSWORD')
        
        # Pool de conexões
        self.connection_pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
            health_check_interval=30
        )
        
        # Cliente principal
        self.redis = redis.Redis(connection_pool=self.connection_pool)
        
        # Cliente para pub/sub (sem decode_responses para binary data)
        self.pubsub_pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=False,
            max_connections=5
        )
        self.pubsub_redis = redis.Redis(connection_pool=self.pubsub_pool)
        
        # Prefixos para diferentes tipos de dados
        self.CACHE_PREFIX = "cache:"
        self.SESSION_PREFIX = "session:"
        self.TASK_PREFIX = "task:"
        self.PROGRESS_PREFIX = "progress:"
        self.METRICS_PREFIX = "metrics:"
        self.EMBEDDING_PREFIX = "embedding:"
        
        logger.info(f"Redis client inicializado: {self.host}:{self.port}/{self.db}")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Verifica a saúde da conexão Redis.
        
        Returns:
            Status de saúde do Redis
        """
        try:
            # Teste básico de conectividade
            ping_result = self.redis.ping()
            
            # Informações do servidor
            info = self.redis.info()
            
            # Estatísticas de conexão (com tratamento de erro para testes)
            pool_stats = {}
            try:
                if hasattr(self.connection_pool, 'created_connections'):
                    pool_stats = {
                        'created_connections': self.connection_pool.created_connections,
                        'available_connections': len(self.connection_pool._available_connections),
                        'in_use_connections': len(self.connection_pool._in_use_connections)
                    }
            except (AttributeError, TypeError):
                # Durante testes com mocks, estes atributos podem não existir
                pool_stats = {
                    'created_connections': 'N/A (mock)',
                    'available_connections': 'N/A (mock)',
                    'in_use_connections': 'N/A (mock)'
                }
            
            return {
                'status': 'healthy' if ping_result else 'unhealthy',
                'ping': ping_result,
                'version': info.get('redis_version'),
                'memory_used': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'pool_stats': pool_stats,
                'host': self.host,
                'port': self.port,
                'db': self.db
            }
        except Exception as e:
            logger.error(f"Erro no health check do Redis: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'host': self.host,
                'port': self.port,
                'db': self.db
            }
    
    # === OPERAÇÕES DE CACHE ===
    
    def cache_set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """
        Armazena um valor no cache.
        
        Args:
            key: Chave do cache
            value: Valor a ser armazenado
            ttl: Tempo de vida em segundos
            
        Returns:
            True se armazenado com sucesso
        """
        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            serialized_value = json.dumps(value) if not isinstance(value, (str, bytes)) else value
            return self.redis.setex(cache_key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache {key}: {e}")
            return False
    
    def cache_get(self, key: str) -> Optional[Any]:
        """
        Recupera um valor do cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            Valor armazenado ou None se não encontrado
        """
        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            value = self.redis.get(cache_key)
            if value is None:
                return None
            
            # Tenta deserializar JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Erro ao recuperar do cache {key}: {e}")
            return None
    
    def cache_delete(self, key: str) -> bool:
        """
        Remove um valor do cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            True se removido com sucesso
        """
        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            return bool(self.redis.delete(cache_key))
        except Exception as e:
            logger.error(f"Erro ao remover do cache {key}: {e}")
            return False
    
    def cache_exists(self, key: str) -> bool:
        """
        Verifica se uma chave existe no cache.
        
        Args:
            key: Chave do cache
            
        Returns:
            True se a chave existe
        """
        try:
            cache_key = f"{self.CACHE_PREFIX}{key}"
            return bool(self.redis.exists(cache_key))
        except Exception as e:
            logger.error(f"Erro ao verificar existência no cache {key}: {e}")
            return False
    
    # === OPERAÇÕES DE EMBEDDING CACHE ===
    
    def cache_embedding(self, text_hash: str, embedding: List[float], ttl: int = 86400) -> bool:
        """
        Armazena um embedding no cache com TTL.
        
        Args:
            text_hash: Hash único do texto
            embedding: Vetor de embedding
            ttl: Tempo de vida em segundos (padrão 24h)
            
        Returns:
            True se armazenado com sucesso
        """
        try:
            key = f"{self.EMBEDDING_PREFIX}{text_hash}"
            # Usa JSON ao invés de pickle para compatibilidade com decode_responses=True
            embedding_data = json.dumps(embedding)
            return self.redis.setex(key, ttl, embedding_data)
        except Exception as e:
            logger.error(f"Erro ao armazenar embedding {text_hash}: {e}")
            return False
    
    def get_cached_embedding(self, text_hash: str) -> Optional[List[float]]:
        """
        Recupera um embedding do cache.
        
        Args:
            text_hash: Hash do texto
            
        Returns:
            Vetor de embedding ou None se não encontrado
        """
        try:
            key = f"{self.EMBEDDING_PREFIX}{text_hash}"
            value = self.redis.get(key)
            if value is None:
                return None
            # Usa JSON ao invés de pickle para compatibilidade com decode_responses=True
            return json.loads(value)
        except Exception as e:
            logger.error(f"Erro ao recuperar embedding {text_hash}: {e}")
            return None
    
    # === OPERAÇÕES DE PROGRESSO ===
    
    def set_task_progress(self, task_id: str, progress: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Armazena o progresso de uma tarefa.
        
        Args:
            task_id: ID da tarefa
            progress: Dados de progresso
            ttl: Tempo de vida em segundos
            
        Returns:
            True se armazenado com sucesso
        """
        try:
            key = f"{self.PROGRESS_PREFIX}{task_id}"
            progress_data = {
                'task_id': task_id,
                'timestamp': progress.get('timestamp'),
                'status': progress.get('status'),
                'percentage': progress.get('percentage', 0),
                'message': progress.get('message', ''),
                'details': progress.get('details', {})
            }
            return self.redis.setex(key, ttl, json.dumps(progress_data))
        except Exception as e:
            logger.error(f"Erro ao armazenar progresso da tarefa {task_id}: {e}")
            return False
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera o progresso de uma tarefa.
        
        Args:
            task_id: ID da tarefa
            
        Returns:
            Dados de progresso ou None se não encontrado
        """
        try:
            key = f"{self.PROGRESS_PREFIX}{task_id}"
            value = self.redis.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.error(f"Erro ao recuperar progresso da tarefa {task_id}: {e}")
            return None
    
    # === OPERAÇÕES DE PUB/SUB ===
    
    def publish_message(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publica uma mensagem em um canal.
        
        Args:
            channel: Nome do canal
            message: Mensagem a ser publicada
            
        Returns:
            Número de subscribers que receberam a mensagem
        """
        try:
            serialized_message = json.dumps(message)
            return self.pubsub_redis.publish(channel, serialized_message)
        except Exception as e:
            logger.error(f"Erro ao publicar mensagem no canal {channel}: {e}")
            return 0
    
    def subscribe_to_channel(self, channel: str):
        """
        Cria um subscriber para um canal.
        
        Args:
            channel: Nome do canal
            
        Returns:
            Objeto PubSub configurado
        """
        try:
            pubsub = self.pubsub_redis.pubsub()
            pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error(f"Erro ao se inscrever no canal {channel}: {e}")
            return None
    
    # === OPERAÇÕES DE MÉTRICAS ===
    
    def increment_metric(self, metric_name: str, value: int = 1) -> int:
        """
        Incrementa uma métrica.
        
        Args:
            metric_name: Nome da métrica
            value: Valor a incrementar
            
        Returns:
            Novo valor da métrica
        """
        try:
            key = f"{self.METRICS_PREFIX}{metric_name}"
            return self.redis.incrby(key, value)
        except Exception as e:
            logger.error(f"Erro ao incrementar métrica {metric_name}: {e}")
            return 0
    
    def get_metric(self, metric_name: str) -> int:
        """
        Recupera o valor de uma métrica.
        
        Args:
            metric_name: Nome da métrica
            
        Returns:
            Valor da métrica
        """
        try:
            key = f"{self.METRICS_PREFIX}{metric_name}"
            value = self.redis.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"Erro ao recuperar métrica {metric_name}: {e}")
            return 0
    
    def set_metric(self, metric_name: str, value: int, ttl: Optional[int] = None) -> bool:
        """
        Define o valor de uma métrica.
        
        Args:
            metric_name: Nome da métrica
            value: Valor da métrica
            ttl: Tempo de vida em segundos (opcional)
            
        Returns:
            True se definido com sucesso
        """
        try:
            key = f"{self.METRICS_PREFIX}{metric_name}"
            if ttl:
                return self.redis.setex(key, ttl, value)
            else:
                return self.redis.set(key, value)
        except Exception as e:
            logger.error(f"Erro ao definir métrica {metric_name}: {e}")
            return False
    
    # === OPERAÇÕES DE LIMPEZA ===
    
    def cleanup_expired_keys(self, pattern: str = None) -> int:
        """
        Remove chaves expiradas ou por padrão.
        
        Args:
            pattern: Padrão de chaves a remover (opcional)
            
        Returns:
            Número de chaves removidas
        """
        try:
            if pattern:
                keys = self.redis.keys(pattern)
                if keys:
                    return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Erro na limpeza de chaves {pattern}: {e}")
            return 0
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Retorna informações de uso de memória.
        
        Returns:
            Informações de memória
        """
        try:
            info = self.redis.info('memory')
            return {
                'used_memory': info.get('used_memory'),
                'used_memory_human': info.get('used_memory_human'),
                'used_memory_peak': info.get('used_memory_peak'),
                'used_memory_peak_human': info.get('used_memory_peak_human'),
                'total_system_memory': info.get('total_system_memory'),
                'total_system_memory_human': info.get('total_system_memory_human'),
                'memory_fragmentation_ratio': info.get('mem_fragmentation_ratio')
            }
        except Exception as e:
            logger.error(f"Erro ao obter uso de memória: {e}")
            return {}
    
    @contextmanager
    def pipeline(self):
        """
        Context manager para operações em pipeline.
        
        Yields:
            Pipeline do Redis
        """
        pipe = self.redis.pipeline()
        try:
            yield pipe
            pipe.execute()
        except Exception as e:
            logger.error(f"Erro no pipeline: {e}")
            raise
    
    def close(self):
        """Fecha as conexões Redis."""
        try:
            self.connection_pool.disconnect()
            self.pubsub_pool.disconnect()
            logger.info("Conexões Redis fechadas")
        except Exception as e:
            logger.error(f"Erro ao fechar conexões Redis: {e}")


# Instância global do cliente Redis
_redis_client = None


def get_redis_client() -> RedisClient:
    """
    Retorna a instância global do cliente Redis.
    
    Returns:
        Instância do RedisClient
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis_client():
    """Fecha a instância global do cliente Redis."""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None 