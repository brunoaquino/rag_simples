"""
Sistema de Ingestão de Documentos
Módulo responsável pelo processamento e ingestão de documentos em vários formatos.
"""

from .document_parser import DocumentParser
from .chunking_system import ChunkingSystem, ChunkConfig, Chunk
from .metadata_extractor import MetadataExtractor
from .document_versioning import DocumentVersionManager, DocumentVersion, ProcessingResult, VersionStatus
from .ingestion_pipeline import IngestionPipeline, IngestionConfig, IngestionResult
from .validation_system import (
    ValidationManager, ValidationLevel, ValidationSeverity,
    ValidationRule, ValidationIssue, ValidationResult,
    DocumentValidator, ContentValidator, ChunkValidator, MetadataValidator
)

__all__ = [
    'DocumentParser',
    'ChunkingSystem', 
    'ChunkConfig',
    'Chunk',
    'MetadataExtractor',
    'DocumentVersionManager',
    'DocumentVersion',
    'ProcessingResult',
    'VersionStatus',
    'IngestionPipeline',
    'IngestionConfig',
    'IngestionResult',
    'ValidationManager',
    'ValidationLevel',
    'ValidationSeverity',
    'ValidationRule',
    'ValidationIssue',
    'ValidationResult',
    'DocumentValidator',
    'ContentValidator',
    'ChunkValidator',
    'MetadataValidator'
]
