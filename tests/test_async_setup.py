"""
Testes para o sistema de processamento assíncrono com Redis real.
"""

import unittest
import json
import time
from datetime import datetime, timedelta
from src.async_processing.celery_config import get_celery_app, setup_celery_for_environment, CeleryConfig
from src.async_processing.redis_client import RedisClient, get_redis_client


class TestCeleryConfiguration(unittest.TestCase):
    """Testes para configuração do Celery."""
    
    def test_celery_app_creation(self):
        """Testa criação da app Celery."""
        app = get_celery_app()
        self.assertIsNotNone(app)
        # Verifica se as configurações básicas estão presentes
        self.assertIn('redis', app.conf.broker_url)
        self.assertIn('redis', app.conf.result_backend)
    
    def test_celery_configuration(self):
        """Testa configurações do Celery."""
        app = get_celery_app()
        
        # Configurações básicas
        self.assertEqual(app.conf.task_serializer, 'json')
        self.assertEqual(app.conf.result_serializer, 'json')
        self.assertIn('json', app.conf.accept_content)
        self.assertTrue(app.conf.enable_utc)
        
        # Configurações de worker
        self.assertEqual(app.conf.worker_prefetch_multiplier, 1)
        self.assertEqual(app.conf.worker_max_tasks_per_child, 1000)
        
        # Configurações de task
        self.assertTrue(app.conf.task_acks_late)
        self.assertTrue(app.conf.task_reject_on_worker_lost)
        self.assertTrue(app.conf.task_track_started)
    
    def test_queue_configuration(self):
        """Testa configuração de filas."""
        app = get_celery_app()
        
        expected_queues = [
            'high_priority', 'document_processing', 'embedding_generation',
            'vector_operations', 'low_priority', 'default'
        ]
        
        queue_names = [queue.name for queue in app.conf.task_queues]
        for expected_queue in expected_queues:
            self.assertIn(expected_queue, queue_names)
    
    def test_task_routing(self):
        """Testa roteamento de tarefas."""
        app = get_celery_app()
        routes = app.conf.task_routes
        
        # Testa alguns roteamentos esperados
        self.assertIn('rag_system.document_processing.*', routes)
        self.assertIn('rag_system.embedding_generation.*', routes)
        self.assertIn('rag_system.vector_operations.*', routes)
        self.assertIn('rag_system.high_priority.*', routes)
        self.assertIn('rag_system.low_priority.*', routes)
    
    def test_environment_configuration(self):
        """Testa configurações por ambiente."""
        # Teste para desenvolvimento
        app_dev = setup_celery_for_environment('development')
        self.assertEqual(app_dev.conf.worker_concurrency, 2)
        self.assertEqual(app_dev.conf.task_time_limit, 10 * 60)
        
        # Teste para produção
        app_prod = setup_celery_for_environment('production')
        self.assertEqual(app_prod.conf.worker_concurrency, 4)
        self.assertEqual(app_prod.conf.task_time_limit, 60 * 60)
        
        # Teste para testing
        app_test = setup_celery_for_environment('testing')
        self.assertTrue(app_test.conf.task_always_eager)
        self.assertEqual(app_test.conf.broker_url, 'memory://')
    
    def test_invalid_environment(self):
        """Testa erro para ambiente inválido."""
        with self.assertRaises(ValueError):
            setup_celery_for_environment('invalid_env')
    
    def test_celery_config_class(self):
        """Testa métodos da classe CeleryConfig."""
        # Teste desenvolvimento
        CeleryConfig.configure_for_development()
        app = get_celery_app()
        self.assertEqual(app.conf.worker_concurrency, 2)
        
        # Teste produção
        CeleryConfig.configure_for_production()
        self.assertEqual(app.conf.worker_concurrency, 4)
        
        # Teste testing
        CeleryConfig.configure_for_testing()
        self.assertTrue(app.conf.task_always_eager)


class TestRedisClient(unittest.TestCase):
    """Testes para o cliente Redis com instância real."""
    
    def setUp(self):
        """Configuração antes de cada teste."""
        self.client = RedisClient(
            host='localhost',
            port=6379,
            db=1,  # Database específico para testes
            decode_responses=True,
            max_connections=10
        )
        # Limpa o database antes de cada teste
        self.client.redis.flushdb()
    
    def tearDown(self):
        """Limpeza após cada teste."""
        self.client.redis.flushdb()
        self.client.close()
    
    def test_redis_client_creation(self):
        """Testa criação do cliente Redis."""
        self.assertIsNotNone(self.client)
        self.assertEqual(self.client.host, 'localhost')
        self.assertEqual(self.client.port, 6379)
        self.assertEqual(self.client.db, 1)
    
    def test_redis_health_check_success(self):
        """Testa health check bem-sucedido."""
        health = self.client.health_check()
        
        self.assertEqual(health['status'], 'healthy')
        self.assertTrue(health['ping'])
        self.assertIn('version', health)
        self.assertIn('memory_used', health)
        self.assertIn('connected_clients', health)
    
    def test_redis_health_check_failure(self):
        """Testa health check com falha."""
        # Cria cliente com configuração inválida
        bad_client = RedisClient(host='invalid_host', port=9999, db=1)
        health = bad_client.health_check()
        
        self.assertEqual(health['status'], 'unhealthy')
        self.assertIn('error', health)
        bad_client.close()
    
    def test_cache_operations(self):
        """Testa operações básicas de cache."""
        # Set
        result = self.client.cache_set('test_key', {'message': 'hello'}, ttl=60)
        self.assertTrue(result)
        
        # Get
        value = self.client.cache_get('test_key')
        self.assertEqual(value['message'], 'hello')
        
        # Exists
        self.assertTrue(self.client.cache_exists('test_key'))
        
        # Delete
        self.assertTrue(self.client.cache_delete('test_key'))
        self.assertFalse(self.client.cache_exists('test_key'))
    
    def test_embedding_cache(self):
        """Testa cache de embeddings."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        text_hash = 'test_hash_123'
        
        # Armazena embedding
        result = self.client.cache_embedding(text_hash, embedding, ttl=60)
        self.assertTrue(result)
        
        # Recupera embedding
        cached_embedding = self.client.get_cached_embedding(text_hash)
        self.assertEqual(cached_embedding, embedding)
        
        # Testa embedding inexistente
        self.assertIsNone(self.client.get_cached_embedding('nonexistent'))
    
    def test_task_progress_operations(self):
        """Testa operações de progresso de tarefas."""
        task_id = 'test_task_123'
        progress_data = {
            'timestamp': datetime.now().isoformat(),
            'status': 'processing',
            'percentage': 50,
            'message': 'Halfway done',
            'details': {'items_processed': 5, 'total_items': 10}
        }
        
        # Set progress
        result = self.client.set_task_progress(task_id, progress_data, ttl=60)
        self.assertTrue(result)
        
        # Get progress
        retrieved_progress = self.client.get_task_progress(task_id)
        self.assertEqual(retrieved_progress['status'], 'processing')
        self.assertEqual(retrieved_progress['percentage'], 50)
        self.assertEqual(retrieved_progress['message'], 'Halfway done')
        
        # Testa progresso inexistente
        self.assertIsNone(self.client.get_task_progress('nonexistent_task'))
    
    def test_pubsub_operations(self):
        """Testa operações de pub/sub."""
        channel = 'test_channel'
        message = {'event': 'test_event', 'data': {'key': 'value'}}
        
        # Publica mensagem
        subscribers = self.client.publish_message(channel, message)
        # Como não há subscribers, deve retornar 0
        self.assertEqual(subscribers, 0)
        
        # Cria subscriber
        pubsub = self.client.subscribe_to_channel(channel)
        self.assertIsNotNone(pubsub)
        
        # Publica outra mensagem
        subscribers = self.client.publish_message(channel, message)
        self.assertEqual(subscribers, 1)
        
        # Lê mensagem
        messages = []
        for _ in range(2):  # primeira mensagem é de confirmação de subscription
            msg = pubsub.get_message(timeout=1)
            if msg:
                messages.append(msg)
        
        # Verifica se recebeu a mensagem
        self.assertTrue(len(messages) >= 1)
        
        pubsub.close()
    
    def test_metrics_operations(self):
        """Testa operações de métricas."""
        metric_name = 'test_metric'
        
        # Incrementa métrica
        value = self.client.increment_metric(metric_name, 5)
        self.assertEqual(value, 5)
        
        # Incrementa novamente
        value = self.client.increment_metric(metric_name, 3)
        self.assertEqual(value, 8)
        
        # Get métrica
        value = self.client.get_metric(metric_name)
        self.assertEqual(value, 8)
        
        # Set métrica
        result = self.client.set_metric(metric_name, 10, ttl=60)
        self.assertTrue(result)
        
        value = self.client.get_metric(metric_name)
        self.assertEqual(value, 10)


class TestIntegration(unittest.TestCase):
    """Testes de integração."""
    
    def setUp(self):
        """Configuração antes de cada teste."""
        # Limpa singleton existente
        from src.async_processing.redis_client import close_redis_client
        close_redis_client()
    
    def tearDown(self):
        """Limpeza após cada teste."""
        from src.async_processing.redis_client import close_redis_client
        close_redis_client()
    
    def test_get_redis_client_singleton(self):
        """Testa o padrão singleton do cliente Redis."""
        client1 = get_redis_client()
        client2 = get_redis_client()
        
        # Deve retornar a mesma instância
        self.assertIs(client1, client2)
        
        # Testa funcionalidade
        health = client1.health_check()
        self.assertEqual(health['status'], 'healthy')


if __name__ == '__main__':
    unittest.main() 