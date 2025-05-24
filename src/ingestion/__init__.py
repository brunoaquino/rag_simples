"""
Módulo de Ingestão de Documentos
Sistema completo para ingestão, processamento e versionamento de documentos.
"""

from .document_parser import DocumentParser, BaseParser
from .chunking_system import ChunkingSystem, ChunkConfig, Chunk
from .metadata_extractor import MetadataExtractor
from .document_versioning import DocumentVersionManager, DocumentVersion, ProcessingResult, VersionStatus
from .validation_system import (
    ValidationManager, ValidationLevel, ValidationSeverity,
    ValidationRule, ValidationIssue, ValidationResult,
    DocumentValidator, ContentValidator, ChunkValidator, MetadataValidator
)
from .ingestion_pipeline import IngestionPipeline, IngestionConfig, IngestionResult
from .progress_tracking import (
    ProgressTracker, ProcessingStage, ProcessingStatus, NotificationType,
    ProcessingMetrics, StageProgress, DocumentProgress, BatchProgress,
    Notification, get_global_tracker, set_global_tracker
)

__all__ = [
    # Document Processing
    'DocumentParser', 'BaseParser',
    'ChunkingSystem', 'ChunkConfig', 'Chunk',
    'MetadataExtractor',
    
    # Versioning
    'DocumentVersionManager', 'DocumentVersion', 'ProcessingResult', 'VersionStatus',
    
    # Validation
    'ValidationManager', 'ValidationLevel', 'ValidationSeverity',
    'ValidationRule', 'ValidationIssue', 'ValidationResult',
    'DocumentValidator', 'ContentValidator', 'ChunkValidator', 'MetadataValidator',
    
    # Pipeline
    'IngestionPipeline', 'IngestionConfig', 'IngestionResult',
    
    # Progress Tracking
    'ProgressTracker', 'ProcessingStage', 'ProcessingStatus', 'NotificationType',
    'ProcessingMetrics', 'StageProgress', 'DocumentProgress', 'BatchProgress',
    'Notification', 'get_global_tracker', 'set_global_tracker'
]
