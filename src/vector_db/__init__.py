"""
Vector Database Module

Módulo para integração com bancos de dados vetoriais (Pinecone).
Inclui gerenciamento de clientes, índices e schemas.
"""

from .pinecone_client import (
    PineconeClient,
    PineconeConfig,
    VectorRecord,
    QueryResult,
    OperationMetrics,
    PINECONE_AVAILABLE
)

from .index_manager import (
    IndexManager,
    IndexType,
    IndexTemplate
)

from .schemas import (
    IndexSchema,
    MetadataField,
    IndexEnvironment,
    EmbeddingModel,
    SchemaRegistry,
    get_embedding_dimensions,
    validate_schema,
    create_migration_plan
)

__all__ = [
    # Cliente principal
    "PineconeClient",
    "PineconeConfig",
    "VectorRecord",
    "QueryResult", 
    "OperationMetrics",
    "PINECONE_AVAILABLE",
    
    # Gerenciador de índices
    "IndexManager",
    "IndexType",
    "IndexTemplate",
    
    # Sistema de schemas
    "IndexSchema",
    "MetadataField",
    "IndexEnvironment",
    "EmbeddingModel",
    "SchemaRegistry",
    "get_embedding_dimensions",
    "validate_schema",
    "create_migration_plan"
]
