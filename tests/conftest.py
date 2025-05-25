"""
Configuração global de testes para o sistema RAG.
"""

import pytest
import redis
import time
from src.async_processing.redis_client import RedisClient, get_redis_client, close_redis_client


@pytest.fixture(scope="session")
def redis_connection():
    """
    Fixture que fornece uma conexão Redis para testes.
    Assume que há uma instância Redis rodando em localhost:6379.
    """
    # Aguarda Redis estar disponível
    max_retries = 30
    for i in range(max_retries):
        try:
            client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
            client.ping()
            break
        except redis.ConnectionError:
            if i == max_retries - 1:
                pytest.skip("Redis não está disponível. Execute: docker-compose up -d redis")
            time.sleep(1)
    
    yield client
    
    # Limpeza após os testes
    client.flushdb()
    client.close()


@pytest.fixture(scope="function")
def redis_client(redis_connection):
    """
    Fixture que fornece um RedisClient configurado para testes.
    """
    # Usa database 1 para testes (separado do desenvolvimento)
    client = RedisClient(
        host='localhost',
        port=6379,
        db=1,  # Database específico para testes
        decode_responses=True,
        max_connections=10
    )
    
    # Limpa o database antes de cada teste
    client.redis.flushdb()
    
    yield client
    
    # Limpeza após cada teste
    client.redis.flushdb()
    client.close()


@pytest.fixture(scope="function")
def clean_redis_singleton(redis_connection):
    """
    Fixture para limpar o singleton do Redis antes e depois dos testes.
    """
    # Limpa singleton anterior se existir
    close_redis_client()
    
    yield
    
    # Limpa singleton após o teste
    close_redis_client()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """
    Fixture que roda automaticamente antes de cada teste.
    Configura variáveis de ambiente para testes.
    """
    import os
    
    # Configurações de ambiente para testes
    os.environ['REDIS_HOST'] = 'localhost'
    os.environ['REDIS_PORT'] = '6379'
    os.environ['REDIS_DB'] = '1'  # Database específico para testes
    
    yield
    
    # Cleanup após o teste
    env_vars_to_clean = ['REDIS_HOST', 'REDIS_PORT', 'REDIS_DB']
    for var in env_vars_to_clean:
        if var in os.environ:
            del os.environ[var] 