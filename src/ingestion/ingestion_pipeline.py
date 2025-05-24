"""
Pipeline de Ingestão Integrado
Combina todos os componentes de ingestão em um fluxo de trabalho unificado.
"""

import time
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .document_parser import DocumentParser
from .chunking_system import ChunkingSystem, ChunkConfig, Chunk
from .metadata_extractor import MetadataExtractor
from .document_versioning import DocumentVersionManager, DocumentVersion, ProcessingResult, VersionStatus
from .validation_system import ValidationManager, ValidationLevel, ValidationResult

logger = logging.getLogger(__name__)

@dataclass
class IngestionConfig:
    """Configuração para o pipeline de ingestão."""
    # Configurações de chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200
    chunking_strategy: str = 'fixed_size'
    min_chunk_size: int = 100
    
    # Configurações de versionamento
    storage_path: str = "data/versions"
    enable_versioning: bool = True
    
    # Configurações de validação
    enable_validation: bool = True
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    stop_on_validation_error: bool = False
    
    # Configurações gerais
    enable_deduplication: bool = True
    archive_old_versions: bool = True
    max_versions_per_document: int = 5

@dataclass
class IngestionResult:
    """Resultado do processamento de ingestão."""
    success: bool
    document_version: Optional[DocumentVersion]
    chunks: List[Chunk]
    metadata: Dict[str, Any]
    processing_time: float
    validation_results: Optional[Dict[str, ValidationResult]] = None
    validation_score: Optional[float] = None
    validation_issues: Optional[List[str]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte resultado para dicionário."""
        result = {
            'success': self.success,
            'version_id': self.document_version.version_id if self.document_version else None,
            'chunks_count': len(self.chunks),
            'processing_time': self.processing_time,
            'error_message': self.error_message,
            'metadata': self.metadata
        }
        
        # Adiciona informações de validação se disponíveis
        if self.validation_results:
            result['validation'] = {
                'score': self.validation_score,
                'is_valid': all(vr.is_valid for vr in self.validation_results.values()),
                'component_scores': {k: vr.score for k, vr in self.validation_results.items()},
                'issues': self.validation_issues or []
            }
        
        return result

class IngestionPipeline:
    """Pipeline completo de ingestão de documentos."""
    
    def __init__(self, config: Optional[IngestionConfig] = None):
        """
        Inicializa o pipeline de ingestão.
        
        Args:
            config: Configuração do pipeline
        """
        self.config = config or IngestionConfig()
        
        # Inicializa componentes
        self.parser = DocumentParser()
        
        chunk_config = ChunkConfig(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            strategy=self.config.chunking_strategy,
            min_chunk_size=self.config.min_chunk_size
        )
        self.chunker = ChunkingSystem(chunk_config)
        
        self.metadata_extractor = MetadataExtractor()
        
        # Versionamento opcional
        if self.config.enable_versioning:
            self.version_manager = DocumentVersionManager(self.config.storage_path)
        else:
            self.version_manager = None
        
        # Validação opcional
        if self.config.enable_validation:
            self.validator = ValidationManager(self.config.validation_level)
        else:
            self.validator = None
        
        logger.info("IngestionPipeline inicializado")
        logger.info(f"  - Versionamento: {'Habilitado' if self.config.enable_versioning else 'Desabilitado'}")
        logger.info(f"  - Validação: {'Habilitado' if self.config.enable_validation else 'Desabilitado'}")
        if self.config.enable_validation:
            logger.info(f"  - Nível de validação: {self.config.validation_level.value}")
        logger.info(f"  - Estratégia de chunking: {self.config.chunking_strategy}")
        logger.info(f"  - Tamanho do chunk: {self.config.chunk_size}")
    
    def ingest_document(self, file_content: bytes, filename: str, 
                       user_metadata: Optional[Dict[str, Any]] = None,
                       temp_file_path: Optional[str] = None) -> IngestionResult:
        """
        Processa um documento completo através do pipeline.
        
        Args:
            file_content: Conteúdo do arquivo em bytes
            filename: Nome do arquivo original
            user_metadata: Metadados fornecidos pelo usuário
            temp_file_path: Caminho temporário do arquivo (para versionamento)
            
        Returns:
            IngestionResult com todos os dados processados
        """
        start_time = time.time()
        
        try:
            logger.info(f"Iniciando ingestão de {filename}")
            
            # 1. Parse do documento
            parsed_data = self.parser.parse_document(file_content, filename)
            logger.info(f"Documento parseado: {len(parsed_data['text'])} caracteres")
            
            # 2. Verifica deduplicação se versionamento estiver habilitado
            document_version = None
            if self.version_manager and self.config.enable_deduplication:
                # Cria versão temporária para verificar hash
                if temp_file_path:
                    existing_version = self._check_for_duplicate(temp_file_path, filename)
                    if existing_version:
                        logger.info(f"Documento duplicado detectado: {existing_version.version_id}")
                        return self._create_duplicate_result(existing_version, start_time)
            
            # 3. Extrai metadados
            enhanced_metadata = self.metadata_extractor.extract_metadata(
                parsed_data['text'], 
                parsed_data['metadata'], 
                user_metadata
            )
            logger.info(f"Metadados extraídos: {len(enhanced_metadata)} campos")
            
            # 4. Chunking do documento
            chunks = self.chunker.chunk_document(parsed_data['text'], enhanced_metadata)
            logger.info(f"Documento dividido em {len(chunks)} chunks")
            
            # 5. Validação (se habilitada)
            validation_results = None
            validation_score = None
            validation_issues = None
            
            if self.validator:
                logger.info("Executando validação do pipeline")
                # Cria Path temporário se temp_file_path não existir
                if temp_file_path:
                    temp_path = Path(temp_file_path)
                else:
                    # Cria arquivo temporário para validação
                    import tempfile
                    temp_fd, temp_file_path = tempfile.mkstemp(suffix=Path(filename).suffix)
                    with os.fdopen(temp_fd, 'wb') as tmp_file:
                        tmp_file.write(file_content)
                    temp_path = Path(temp_file_path)
                
                validation_results = self.validator.validate_full_pipeline(
                    temp_path, parsed_data['text'], chunks, enhanced_metadata
                )
                
                validation_score = self.validator.get_overall_score(validation_results)
                is_pipeline_valid = self.validator.is_pipeline_valid(validation_results)
                
                # Coleta issues críticas para relatório
                critical_issues = self.validator.get_critical_issues(validation_results)
                validation_issues = [issue.message for issue in critical_issues]
                
                logger.info(f"Validação concluída - Score: {validation_score:.2f}, Válido: {is_pipeline_valid}")
                
                # Para ou continua baseado na configuração
                if not is_pipeline_valid and self.config.stop_on_validation_error:
                    error_message = f"Validação falhou com {len(critical_issues)} problemas críticos"
                    logger.error(error_message)
                    
                    processing_time = time.time() - start_time
                    return IngestionResult(
                        success=False,
                        document_version=None,
                        chunks=[],
                        metadata=enhanced_metadata,
                        processing_time=processing_time,
                        validation_results=validation_results,
                        validation_score=validation_score,
                        validation_issues=validation_issues,
                        error_message=error_message
                    )
            
            # 6. Enriquece metadados dos chunks
            enriched_chunks = []
            for chunk in chunks:
                enriched_metadata = self.metadata_extractor.enrich_chunk_metadata(
                    chunk.text, chunk.metadata, enhanced_metadata
                )
                
                # Atualiza metadados do chunk
                chunk.metadata.update(enriched_metadata)
                enriched_chunks.append(chunk)
            
            # 7. Cria versão do documento se versionamento estiver habilitado
            if self.version_manager and temp_file_path:
                document_version = self.version_manager.create_document_version(
                    temp_file_path, filename, enhanced_metadata
                )
                
                # Inclui resultados de validação nos metadados de processamento
                processing_metadata = {
                    'chunks_metadata': [chunk.metadata for chunk in enriched_chunks]
                }
                
                if validation_results:
                    processing_metadata['validation'] = {
                        'score': validation_score,
                        'is_valid': self.validator.is_pipeline_valid(validation_results),
                        'component_scores': {k: vr.score for k, vr in validation_results.items()},
                        'issues_count': len(validation_issues) if validation_issues else 0
                    }
                
                # Atualiza informações de processamento
                processing_result = ProcessingResult(
                    version_id=document_version.version_id,
                    chunks_count=len(enriched_chunks),
                    processing_time=time.time() - start_time,
                    success=True,
                    chunks_metadata=processing_metadata['chunks_metadata']
                )
                
                self.version_manager.update_processing_info(
                    document_version.version_id, processing_result
                )
                logger.info(f"Versão criada: {document_version.version_id}")
                
                # Limpa versões antigas se necessário
                if self.config.archive_old_versions:
                    self._cleanup_old_versions(document_version.document_id)
            
            processing_time = time.time() - start_time
            
            result = IngestionResult(
                success=True,
                document_version=document_version,
                chunks=enriched_chunks,
                metadata=enhanced_metadata,
                processing_time=processing_time,
                validation_results=validation_results,
                validation_score=validation_score,
                validation_issues=validation_issues
            )
            
            logger.info(f"Ingestão concluída em {processing_time:.2f}s")
            if validation_results:
                logger.info(f"  - Score de validação: {validation_score:.2f}")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = f"Erro durante ingestão: {str(e)}"
            logger.error(error_message)
            
            return IngestionResult(
                success=False,
                document_version=None,
                chunks=[],
                metadata={},
                processing_time=processing_time,
                error_message=error_message
            )
    
    def _check_for_duplicate(self, file_path: str, filename: str) -> Optional[DocumentVersion]:
        """Verifica se já existe uma versão com o mesmo conteúdo."""
        try:
            import hashlib
            
            # Calcula hash do arquivo
            with open(file_path, 'rb') as f:
                content = f.read()
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Busca versão existente
            return self.version_manager.find_version_by_hash(content_hash)
            
        except Exception as e:
            logger.warning(f"Erro ao verificar duplicação: {e}")
            return None
    
    def _create_duplicate_result(self, existing_version: DocumentVersion, start_time: float) -> IngestionResult:
        """Cria resultado para documento duplicado."""
        processing_time = time.time() - start_time
        
        # Recupera chunks se disponíveis
        chunks = []
        if existing_version.processing_info:
            chunks_metadata = existing_version.processing_info.get('chunks_metadata', [])
            # Reconstrói chunks básicos (sem texto completo)
            for i, chunk_meta in enumerate(chunks_metadata):
                chunks.append(Chunk(
                    text="[Chunk referenciado]",
                    start_index=0,
                    end_index=0,
                    chunk_id=f"{existing_version.version_id}_chunk_{i}",
                    metadata=chunk_meta
                ))
        
        return IngestionResult(
            success=True,
            document_version=existing_version,
            chunks=chunks,
            metadata=existing_version.metadata,
            processing_time=processing_time
        )
    
    def _cleanup_old_versions(self, document_id: str):
        """Limpa versões antigas de um documento."""
        try:
            self.version_manager.cleanup_old_versions(
                document_id, 
                keep_count=self.config.max_versions_per_document
            )
        except Exception as e:
            logger.warning(f"Erro ao limpar versões antigas: {e}")
    
    def ingest_file(self, file_path: str, 
                   user_metadata: Optional[Dict[str, Any]] = None) -> IngestionResult:
        """
        Processa um arquivo do sistema de arquivos.
        
        Args:
            file_path: Caminho para o arquivo
            user_metadata: Metadados fornecidos pelo usuário
            
        Returns:
            IngestionResult com todos os dados processados
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
            # Lê conteúdo do arquivo
            with open(file_path_obj, 'rb') as f:
                file_content = f.read()
            
            return self.ingest_document(
                file_content, 
                file_path_obj.name, 
                user_metadata, 
                str(file_path_obj)
            )
            
        except Exception as e:
            error_message = f"Erro ao processar arquivo {file_path}: {str(e)}"
            logger.error(error_message)
            
            return IngestionResult(
                success=False,
                document_version=None,
                chunks=[],
                metadata={},
                processing_time=0.0,
                error_message=error_message
            )
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas do pipeline de processamento."""
        stats = {
            'parser_formats': self.parser.get_supported_formats(),
            'chunking_strategy': self.config.chunking_strategy,
            'chunk_config': {
                'size': self.config.chunk_size,
                'overlap': self.config.chunk_overlap,
                'min_size': self.config.min_chunk_size
            },
            'versioning_enabled': self.config.enable_versioning
        }
        
        # Adiciona estatísticas de versionamento se disponível
        if self.version_manager:
            version_stats = self.version_manager.get_statistics()
            stats.update({
                'version_statistics': version_stats
            })
        
        return stats
    
    def search_documents(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca documentos baseado em query simples.
        
        Args:
            query: Termo de busca
            limit: Número máximo de resultados
            
        Returns:
            Lista de documentos que correspondem à busca
        """
        if not self.version_manager:
            return []
        
        results = []
        query_lower = query.lower()
        
        # Busca em todas as versões ativas
        for version in self.version_manager.versions.values():
            if version.status != VersionStatus.ACTIVE:
                continue
            
            # Busca no nome do arquivo
            if query_lower in version.original_filename.lower():
                score = 2.0
            else:
                score = 0.0
            
            # Busca em metadados
            for key, value in version.metadata.items():
                if isinstance(value, str) and query_lower in value.lower():
                    score += 1.0
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and query_lower in item.lower():
                            score += 0.5
            
            if score > 0:
                results.append({
                    'version_id': version.version_id,
                    'filename': version.original_filename,
                    'score': score,
                    'created_at': version.created_at,
                    'metadata': version.metadata
                })
        
        # Ordena por score e limita resultados
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    
    def get_document_history(self, document_id: str) -> Dict[str, Any]:
        """
        Obtém histórico completo de um documento.
        
        Args:
            document_id: ID do documento
            
        Returns:
            Histórico do documento com versões e processamento
        """
        if not self.version_manager:
            return {'error': 'Versionamento não habilitado'}
        
        try:
            versions = self.version_manager.get_document_versions(document_id)
            
            history = {
                'document_id': document_id,
                'total_versions': len(versions),
                'versions': []
            }
            
            for version in versions:
                version_info = {
                    'version_id': version.version_id,
                    'filename': version.original_filename,
                    'status': version.status.value,
                    'created_at': version.created_at,
                    'file_hash': version.content_hash,
                    'metadata': version.metadata
                }
                
                # Adiciona informações básicas do processamento se disponíveis nos metadados
                if hasattr(version, 'processing_info') and version.processing_info:
                    version_info['processing'] = version.processing_info
                
                history['versions'].append(version_info)
            
            return history
            
        except Exception as e:
            logger.error(f"Erro ao obter histórico de {document_id}: {str(e)}")
            return {'error': str(e)}
    
    def get_validation_report(self, validation_results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """
        Gera relatório detalhado de validação.
        
        Args:
            validation_results: Resultados de validação por componente
            
        Returns:
            Relatório detalhado de validação
        """
        if not self.validator or not validation_results:
            return {'error': 'Validação não disponível'}
        
        return self.validator.get_validation_report(validation_results) 