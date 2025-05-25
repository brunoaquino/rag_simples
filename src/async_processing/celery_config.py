"""
Configuração do Celery para Sistema RAG
Configuração completa do Celery com Redis como broker e result backend.
"""

import os
from celery import Celery
from kombu import Queue, Exchange
from datetime import timedelta

# Configurações do Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# URL de conexão do Redis
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Configuração do Celery
app = Celery('rag_system')

# Configurações principais
app.conf.update(
    # Broker e Result Backend
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    
    # Serialização
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Configurações de resultado
    result_expires=timedelta(hours=24),  # Resultados expiram em 24h
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
        'retry_policy': {
            'timeout': 5.0
        }
    },
    
    # Configurações de worker
    worker_prefetch_multiplier=1,  # Evita acúmulo de tarefas em workers
    worker_max_tasks_per_child=1000,  # Reinicia worker após 1000 tarefas
    worker_disable_rate_limits=False,
    
    # Configurações de task
    task_acks_late=True,  # Confirma tarefa apenas após conclusão
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos timeout
    task_soft_time_limit=25 * 60,  # 25 minutos soft timeout
    
    # Configurações de retry
    task_default_retry_delay=60,  # 1 minuto entre retries
    task_max_retries=3,
    
    # Configurações de monitoramento
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Configurações de roteamento
    task_routes={
        'rag_system.document_processing.*': {'queue': 'document_processing'},
        'rag_system.embedding_generation.*': {'queue': 'embedding_generation'},
        'rag_system.vector_operations.*': {'queue': 'vector_operations'},
        'rag_system.high_priority.*': {'queue': 'high_priority'},
        'rag_system.low_priority.*': {'queue': 'low_priority'},
    },
    
    # Definição de filas com prioridades
    task_default_queue='default',
    task_queues=(
        # Fila de alta prioridade
        Queue('high_priority', 
              Exchange('high_priority'), 
              routing_key='high_priority',
              queue_arguments={'x-max-priority': 10}),
        
        # Fila de processamento de documentos
        Queue('document_processing', 
              Exchange('document_processing'), 
              routing_key='document_processing',
              queue_arguments={'x-max-priority': 5}),
        
        # Fila de geração de embeddings
        Queue('embedding_generation', 
              Exchange('embedding_generation'), 
              routing_key='embedding_generation',
              queue_arguments={'x-max-priority': 5}),
        
        # Fila de operações vetoriais
        Queue('vector_operations', 
              Exchange('vector_operations'), 
              routing_key='vector_operations',
              queue_arguments={'x-max-priority': 5}),
        
        # Fila de baixa prioridade
        Queue('low_priority', 
              Exchange('low_priority'), 
              routing_key='low_priority',
              queue_arguments={'x-max-priority': 1}),
        
        # Fila padrão
        Queue('default', 
              Exchange('default'), 
              routing_key='default',
              queue_arguments={'x-max-priority': 3}),
    ),
    
    # Configurações de beat (scheduler)
    beat_schedule={
        'cleanup-expired-results': {
            'task': 'rag_system.maintenance.cleanup_expired_results',
            'schedule': timedelta(hours=6),  # A cada 6 horas
        },
        'health-check-workers': {
            'task': 'rag_system.maintenance.health_check_workers',
            'schedule': timedelta(minutes=5),  # A cada 5 minutos
        },
        'update-system-metrics': {
            'task': 'rag_system.monitoring.update_system_metrics',
            'schedule': timedelta(minutes=1),  # A cada minuto
        },
    },
    
    # Configurações de logging
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Configurações de segurança
    worker_hijack_root_logger=False,
    worker_log_color=False,
)

# Auto-descoberta de tasks
app.autodiscover_tasks([
    'async_processing.tasks',
    'async_processing.document_tasks',
    'async_processing.embedding_tasks',
    'async_processing.vector_tasks',
    'async_processing.maintenance_tasks',
    'async_processing.monitoring_tasks',
])


class CeleryConfig:
    """Classe de configuração para facilitar customizações."""
    
    @staticmethod
    def configure_for_development():
        """Configurações otimizadas para desenvolvimento."""
        app.conf.update(
            task_always_eager=False,  # Executa tarefas assincronamente
            task_eager_propagates=True,
            worker_concurrency=2,  # Menos workers para desenvolvimento
            task_time_limit=10 * 60,  # 10 minutos timeout
            task_soft_time_limit=8 * 60,  # 8 minutos soft timeout
        )
    
    @staticmethod
    def configure_for_production():
        """Configurações otimizadas para produção."""
        app.conf.update(
            task_always_eager=False,
            worker_concurrency=4,  # Mais workers para produção
            task_time_limit=60 * 60,  # 1 hora timeout
            task_soft_time_limit=55 * 60,  # 55 minutos soft timeout
            worker_max_memory_per_child=200000,  # 200MB por worker
        )
    
    @staticmethod
    def configure_for_testing():
        """Configurações para testes."""
        app.conf.update(
            task_always_eager=True,  # Executa tarefas sincronamente
            task_eager_propagates=True,
            broker_url='memory://',
            result_backend='cache+memory://',
        )


def get_celery_app():
    """Retorna a instância configurada do Celery."""
    return app


def setup_celery_for_environment(environment='development'):
    """Configura o Celery para um ambiente específico."""
    if environment == 'development':
        CeleryConfig.configure_for_development()
    elif environment == 'production':
        CeleryConfig.configure_for_production()
    elif environment == 'testing':
        CeleryConfig.configure_for_testing()
    else:
        raise ValueError(f"Ambiente não suportado: {environment}")
    
    return app


# Configuração automática baseada na variável de ambiente
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
setup_celery_for_environment(ENVIRONMENT) 