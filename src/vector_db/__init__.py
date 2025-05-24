"""
Módulo de Banco de Dados Vetorial
Sistema completo para armazenamento e recuperação de embeddings usando Pinecone.
"""

from .pinecone_client import (
    PineconeClient,
    PineconeConfig,
    VectorRecord,
    QueryResult,
    OperationMetrics,
    create_pinecone_client,
    get_default_config
)

from .index_manager import (
    IndexManager,
    IndexType,
    IndexTemplate,
    create_index_manager
)

__all__ = [
    "PineconeClient",
    "PineconeConfig", 
    "VectorRecord",
    "QueryResult",
    "OperationMetrics",
    "create_pinecone_client",
    "get_default_config",
    "IndexManager",
    "IndexType",
    "IndexTemplate",
    "create_index_manager"
]
