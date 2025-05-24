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
from .progress_tracking import ProgressTracker, ProcessingStage, ProcessingStatus

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
    
    # Configurações de tracking de progresso
    enable_progress_tracking: bool = True
    progress_storage_path: Optional[str] = None
    
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
    # Adicionados campos de tracking
    document_id: Optional[str] = None
    tracking_id: Optional[str] = None
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
            'metadata': self.metadata,
            'document_id': self.document_id,
            'tracking_id': self.tracking_id
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
        
        # Progress tracking opcional
        if self.config.enable_progress_tracking:
            progress_path = Path(self.config.progress_storage_path) if self.config.progress_storage_path else None
            self.progress_tracker = ProgressTracker(progress_path)
        else:
            self.progress_tracker = None
        
        logger.info("IngestionPipeline inicializado")
        logger.info(f"  - Versionamento: {'Habilitado' if self.config.enable_versioning else 'Desabilitado'}")
        logger.info(f"  - Validação: {'Habilitado' if self.config.enable_validation else 'Desabilitado'}")
        logger.info(f"  - Progress Tracking: {'Habilitado' if self.config.enable_progress_tracking else 'Desabilitado'}")
        if self.config.enable_validation:
            logger.info(f"  - Nível de validação: {self.config.validation_level.value}")
        logger.info(f"  - Estratégia de chunking: {self.config.chunking_strategy}")
        logger.info(f"  - Tamanho do chunk: {self.config.chunk_size}")
    
    def ingest_document(self, file_content: bytes, filename: str, 
                       user_metadata: Optional[Dict[str, Any]] = None,
                       temp_file_path: Optional[str] = None,
                       batch_id: Optional[str] = None) -> IngestionResult:
        """
        Processa um documento completo através do pipeline.
        
        Args:
            file_content: Conteúdo do arquivo em bytes
            filename: Nome do arquivo original
            user_metadata: Metadados fornecidos pelo usuário
            temp_file_path: Caminho temporário do arquivo (para versionamento)
            batch_id: ID do lote (para tracking)
            
        Returns:
            IngestionResult com todos os dados processados
        """
        start_time = time.time()
        tracking_id = None
        
        try:
            logger.info(f"Iniciando ingestão de {filename}")
            
            # Inicia tracking se habilitado
            if self.progress_tracker:
                tracking_id = self.progress_tracker.start_document_processing(
                    filename, batch_id, len(file_content)
                )
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.PARSING, 0.0
                )
            
            # 1. Parse do documento
            parsed_data = self.parser.parse_document(file_content, filename)
            logger.info(f"Documento parseado: {len(parsed_data['text'])} caracteres")
            
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.PARSING, 100.0, 
                    {"text_length": len(parsed_data['text'])}, ProcessingStatus.COMPLETED
                )
            
            # 2. Verifica deduplicação se versionamento estiver habilitado
            document_version = None
            if self.version_manager and self.config.enable_deduplication:
                # Cria versão temporária para verificar hash
                if temp_file_path:
                    existing_version = self._check_for_duplicate(temp_file_path, filename)
                    if existing_version:
                        logger.info(f"Documento duplicado detectado: {existing_version.version_id}")
                        
                        if self.progress_tracker:
                            self.progress_tracker.update_document_progress(
                                tracking_id, ProcessingStage.COMPLETED, 100.0,
                                {"duplicate": True, "existing_version": existing_version.version_id},
                                ProcessingStatus.COMPLETED
                            )
                        
                        result = self._create_duplicate_result(existing_version, start_time)
                        result.tracking_id = tracking_id
                        return result
            
            # 3. Extrai metadados
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.METADATA_EXTRACTION, 0.0
                )
            
            enhanced_metadata = self.metadata_extractor.extract_metadata(
                parsed_data['text'], 
                parsed_data['metadata'], 
                user_metadata
            )
            logger.info(f"Metadados extraídos: {len(enhanced_metadata)} campos")
            
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.METADATA_EXTRACTION, 100.0,
                    {"metadata_fields": len(enhanced_metadata)}, ProcessingStatus.COMPLETED
                )
            
            # 4. Chunking do documento
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.CHUNKING, 0.0
                )
            
            chunks = self.chunker.chunk_document(parsed_data['text'], enhanced_metadata)
            logger.info(f"Documento dividido em {len(chunks)} chunks")
            
            # 4.1. Enriquecimento dos metadados dos chunks
            enriched_chunks = []
            for chunk in chunks:
                enriched_metadata = self.metadata_extractor.enrich_chunk_metadata(
                    chunk.text, chunk.metadata, enhanced_metadata
                )
                # Cria novo chunk com metadados enriquecidos
                enriched_chunk = Chunk(
                    text=chunk.text,
                    start_index=chunk.start_index,
                    end_index=chunk.end_index,
                    chunk_id=chunk.chunk_id,
                    metadata=enriched_metadata
                )
                enriched_chunks.append(enriched_chunk)
            
            chunks = enriched_chunks
            
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.CHUNKING, 100.0,
                    {"chunks_created": len(chunks)}, ProcessingStatus.COMPLETED
                )
                # Atualiza métricas
                self.progress_tracker.update_document_metrics(
                    tracking_id, chunks_created=len(chunks)
                )
            
            # 5. Validação (se habilitada)
            validation_results = None
            validation_score = None
            validation_issues = None
            
            if self.validator:
                if self.progress_tracker:
                    self.progress_tracker.update_document_progress(
                        tracking_id, ProcessingStage.VALIDATION, 0.0
                    )
                
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
                
                if self.progress_tracker:
                    self.progress_tracker.update_document_progress(
                        tracking_id, ProcessingStage.VALIDATION, 100.0,
                        {"validation_score": validation_score, "is_valid": is_pipeline_valid},
                        ProcessingStatus.COMPLETED
                    )
                    # Atualiza métricas de validação
                    self.progress_tracker.update_document_metrics(
                        tracking_id, validation_score=validation_score
                    )
                
                # Para processamento se validação crítica falhar
                if self.config.stop_on_validation_error and not is_pipeline_valid:
                    error_msg = f"Validação crítica falhou para {filename}"
                    logger.error(error_msg)
                    
                    if self.progress_tracker:
                        self.progress_tracker.update_document_progress(
                            tracking_id, ProcessingStage.FAILED, 100.0,
                            {"error": error_msg}, ProcessingStatus.FAILED
                        )
                    
                    return IngestionResult(
                        success=False,
                        document_version=None,
                        chunks=[],
                        metadata=enhanced_metadata,
                        processing_time=time.time() - start_time,
                        tracking_id=tracking_id,
                        validation_results=validation_results,
                        validation_score=validation_score,
                        validation_issues=validation_issues,
                        error_message=error_msg
                    )
                
                # Remove arquivo temporário se foi criado
                if temp_file_path and not self.config.enable_versioning:
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass
            
            # 6. Versionamento (se habilitado)
            if self.version_manager:
                if self.progress_tracker:
                    self.progress_tracker.update_document_progress(
                        tracking_id, ProcessingStage.VERSIONING, 0.0
                    )
                
                logger.info("Criando versão do documento")
                
                # Se não temos arquivo temporário, cria um para versionamento
                if not temp_file_path:
                    import tempfile
                    temp_fd, temp_file_path = tempfile.mkstemp(suffix=Path(filename).suffix)
                    with os.fdopen(temp_fd, 'wb') as tmp_file:
                        tmp_file.write(file_content)
                
                # Cria versão do documento
                document_version = self.version_manager.create_document_version(
                    temp_file_path, Path(filename).name, enhanced_metadata
                )
                
                # Processa resultado da versão
                processing_result = ProcessingResult(
                    version_id=document_version.version_id,
                    chunks_count=len(chunks),
                    processing_time=time.time() - start_time,
                    success=True
                )
                
                self.version_manager.update_processing_info(
                    document_version.version_id, processing_result
                )
                
                logger.info(f"Versão criada: {document_version.version_id}")
                
                if self.progress_tracker:
                    self.progress_tracker.update_document_progress(
                        tracking_id, ProcessingStage.VERSIONING, 100.0,
                        {"version_id": document_version.version_id}, ProcessingStatus.COMPLETED
                    )
                
                # Limpeza opcional de versões antigas
                if self.config.archive_old_versions:
                    self._cleanup_old_versions(document_version.document_id)
            
            # 7. Armazenamento final
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.STORAGE, 50.0
                )
            
            # Aqui seria onde salvamos os chunks no banco vetorial
            # Por enquanto, apenas simulamos o armazenamento
            logger.info("Simulando armazenamento de chunks...")
            
            if self.progress_tracker:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.STORAGE, 100.0, 
                    {"stored_chunks": len(chunks)}, ProcessingStatus.COMPLETED
                )
                
                # Finaliza o processamento
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.COMPLETED, 100.0,
                    {"total_time": time.time() - start_time}, ProcessingStatus.COMPLETED
                )
            
            processing_time = time.time() - start_time
            logger.info(f"Ingestão de {filename} concluída em {processing_time:.2f}s")
            
            return IngestionResult(
                success=True,
                document_version=document_version,
                chunks=chunks,
                metadata=enhanced_metadata,
                processing_time=processing_time,
                document_id=document_version.document_id if document_version else None,
                tracking_id=tracking_id,
                validation_results=validation_results,
                validation_score=validation_score,
                validation_issues=validation_issues
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Erro durante ingestão de {filename}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if self.progress_tracker and tracking_id:
                self.progress_tracker.update_document_progress(
                    tracking_id, ProcessingStage.FAILED, 100.0,
                    {"error": str(e)}, ProcessingStatus.FAILED
                )
            
            return IngestionResult(
                success=False,
                document_version=None,
                chunks=[],
                metadata=user_metadata or {},
                processing_time=processing_time,
                tracking_id=tracking_id,
                error_message=error_msg
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
            # Reconstrói chunks básicos (sem texto completo) se chunks_metadata existir
            if chunks_metadata:
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
    
    def get_validation_report(self, validation_results: Dict[str, ValidationResult]) -> Dict[str, Any]:
        """
        Cria relatório detalhado de validação.
        
        Args:
            validation_results: Resultados de validação
            
        Returns:
            Relatório formatado da validação
        """
        if not validation_results:
            return {'error': 'Nenhum resultado de validação disponível'}
        
        report = {
            'overall_score': self.validator.get_overall_score(validation_results) if self.validator else 0,
            'is_valid': self.validator.is_pipeline_valid(validation_results) if self.validator else False,
            'components': {},
            'critical_issues': [],
            'warnings': [],
            'summary': {}
        }
        
        total_issues = 0
        total_warnings = 0
        
        for component_name, result in validation_results.items():
            component_report = {
                'score': result.score,
                'is_valid': result.is_valid,
                'issues_count': len(result.issues),
                'warnings_count': len([issue for issue in result.issues 
                                     if issue.severity.value in ['warning', 'info']]),
                'errors_count': len([issue for issue in result.issues 
                                   if issue.severity.value in ['error', 'critical']])
            }
            
            report['components'][component_name] = component_report
            
            # Coleta issues críticas
            for issue in result.issues:
                if issue.severity.value in ['critical', 'error']:
                    report['critical_issues'].append({
                        'component': component_name,
                        'rule': issue.rule_name,
                        'severity': issue.severity.value,
                        'message': issue.message,
                        'location': issue.location
                    })
                    total_issues += 1
                elif issue.severity.value in ['warning', 'info']:
                    report['warnings'].append({
                        'component': component_name,
                        'rule': issue.rule_name,
                        'severity': issue.severity.value,
                        'message': issue.message,
                        'location': issue.location
                    })
                    total_warnings += 1
        
        # Summary
        report['summary'] = {
            'total_components': len(validation_results),
            'valid_components': sum(1 for result in validation_results.values() if result.is_valid),
            'total_critical_issues': total_issues,
            'total_warnings': total_warnings
        }
        
        return report
    
    # Métodos para Progress Tracking
    
    def start_batch_processing(self, filenames: List[str]) -> Optional[str]:
        """
        Inicia processamento em lote com tracking.
        
        Args:
            filenames: Lista de nomes de arquivos
            
        Returns:
            ID do lote ou None se tracking desabilitado
        """
        if not self.progress_tracker:
            logger.warning("Progress tracking não está habilitado")
            return None
        
        return self.progress_tracker.start_batch(filenames)
    
    def get_document_progress(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém progresso de um documento específico.
        
        Args:
            document_id: ID do documento
            
        Returns:
            Progresso do documento em formato dict
        """
        if not self.progress_tracker:
            return None
        
        progress = self.progress_tracker.get_document_progress(document_id)
        if not progress:
            return None
        
        return {
            'document_id': progress.document_id,
            'filename': progress.filename,
            'status': progress.status.value,
            'current_stage': progress.current_stage.value,
            'overall_progress': progress.overall_progress,
            'created_at': progress.created_at,
            'updated_at': progress.updated_at,
            'stages': {
                stage.value: {
                    'progress': stage_prog.progress_percentage,
                    'status': stage_prog.status.value,
                    'duration': stage_prog.duration,
                    'details': stage_prog.details
                }
                for stage, stage_prog in progress.stages.items()
            }
        }
    
    def get_batch_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém progresso de um lote específico.
        
        Args:
            batch_id: ID do lote
            
        Returns:
            Progresso do lote em formato dict
        """
        if not self.progress_tracker:
            return None
        
        batch = self.progress_tracker.get_batch_progress(batch_id)
        if not batch:
            return None
        
        return {
            'batch_id': batch.batch_id,
            'total_documents': batch.total_documents,
            'completed_documents': batch.completed_documents,
            'failed_documents': batch.failed_documents,
            'in_progress_documents': batch.in_progress_documents,
            'overall_progress': batch.overall_progress,
            'is_completed': batch.is_completed,
            'started_at': batch.started_at,
            'completed_at': batch.completed_at,
            'documents': list(batch.documents.keys())
        }
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas gerais de processamento.
        
        Returns:
            Estatísticas do sistema
        """
        base_stats = {
            # Campos no nível raiz para compatibilidade com testes existentes
            'versioning_enabled': self.config.enable_versioning,
            'validation_enabled': self.config.enable_validation,
            'parser_formats': self.parser.get_supported_formats(),
            'chunking_strategy': self.config.chunking_strategy,
            'chunk_size': self.config.chunk_size,
            'chunk_config': {
                'chunk_size': self.config.chunk_size,
                'chunk_overlap': self.config.chunk_overlap,
                'strategy': self.config.chunking_strategy,
                'min_chunk_size': self.config.min_chunk_size
            },
            
            # Configuração detalhada agrupada
            'pipeline_config': {
                'versioning_enabled': self.config.enable_versioning,
                'validation_enabled': self.config.enable_validation,
                'progress_tracking_enabled': self.config.enable_progress_tracking,
                'chunking_strategy': self.config.chunking_strategy,
                'chunk_size': self.config.chunk_size,
                'validation_level': self.config.validation_level.value if self.config.enable_validation else None
            }
        }
        
        if self.progress_tracker:
            tracking_stats = self.progress_tracker.get_overall_statistics()
            base_stats.update(tracking_stats)
        else:
            # Se tracking não estiver habilitado, adiciona campos padrão
            base_stats.update({
                'total_documents': 0,
                'completed_documents': 0,
                'failed_documents': 0,
                'in_progress_documents': 0,
                'success_rate': 0.0,
                'average_processing_time': 0.0,
                'average_processing_speed': 0.0,
                'total_batches': 0,
                'active_batches': 0
            })
        
        # Adiciona estatísticas de versionamento se disponíveis
        if self.version_manager:
            try:
                # Simula estatísticas de versão (método não implementado no DocumentVersionManager atual)
                base_stats['versioning'] = {
                    'storage_path': self.config.storage_path,
                    'deduplication_enabled': self.config.enable_deduplication
                }
            except:
                pass
        
        return base_stats
    
    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Obtém atividade recente de processamento.
        
        Args:
            limit: Número máximo de documentos
            
        Returns:
            Lista de documentos recentes
        """
        if not self.progress_tracker:
            return []
        
        recent_docs = self.progress_tracker.get_recent_documents(limit)
        
        return [
            {
                'document_id': doc.document_id,
                'filename': doc.filename,
                'status': doc.status.value,
                'current_stage': doc.current_stage.value,
                'overall_progress': doc.overall_progress,
                'updated_at': doc.updated_at,
                'file_size': doc.file_size
            }
            for doc in recent_docs
        ]
    
    def get_notifications(self, unread_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtém notificações do sistema.
        
        Args:
            unread_only: Apenas notificações não lidas
            limit: Número máximo de notificações
            
        Returns:
            Lista de notificações
        """
        if not self.progress_tracker:
            return []
        
        notifications = self.progress_tracker.get_notifications(unread_only, limit)
        
        return [
            {
                'id': notif.id,
                'type': notif.type.value,
                'title': notif.title,
                'message': notif.message,
                'timestamp': notif.timestamp,
                'read': notif.read,
                'document_id': notif.document_id,
                'batch_id': notif.batch_id
            }
            for notif in notifications
        ]
    
    def mark_notification_read(self, notification_id: str) -> bool:
        """
        Marca uma notificação como lida.
        
        Args:
            notification_id: ID da notificação
            
        Returns:
            True se marcada com sucesso
        """
        if not self.progress_tracker:
            return False
        
        self.progress_tracker.mark_notification_read(notification_id)
        return True
    
    def clear_old_tracking_data(self, days: int = 30):
        """
        Remove dados antigos de tracking.
        
        Args:
            days: Número de dias para manter os dados
        """
        if self.progress_tracker:
            self.progress_tracker.clear_old_data(days)
    
    def search_documents(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Busca documentos baseado em uma query.
        
        Args:
            query: Termo de busca
            limit: Número máximo de resultados
            
        Returns:
            Lista de documentos encontrados
        """
        if not self.version_manager:
            logger.warning("Busca não disponível sem versionamento habilitado")
            return []
        
        try:
            results = []
            query_lower = query.lower()
            
            # Busca em todas as versões
            for version in self.version_manager.versions.values():
                score = 0.0
                
                # Busca no nome do arquivo
                if query_lower in version.original_filename.lower():
                    score += 10.0
                
                # Busca nos metadados
                if version.metadata:
                    # Busca em tags do usuário
                    user_tags = version.metadata.get('user_tags', [])
                    if any(query_lower in str(tag).lower() for tag in user_tags):
                        score += 5.0
                    
                    # Busca em todas as tags
                    all_tags = version.metadata.get('all_tags', [])
                    if any(query_lower in str(tag).lower() for tag in all_tags):
                        score += 3.0
                    
                    # Busca na categoria
                    auto_category = version.metadata.get('auto_category', '')
                    if query_lower in str(auto_category).lower():
                        score += 4.0
                    
                    # Busca em keywords extraídas
                    keywords = version.metadata.get('extracted_keywords', [])
                    if any(query_lower in str(keyword).lower() for keyword in keywords):
                        score += 2.0
                
                # Se encontrou alguma correspondência, adiciona aos resultados
                if score > 0:
                    # Formata data de criação
                    created_at_str = None
                    if version.created_at:
                        if hasattr(version.created_at, 'isoformat'):
                            created_at_str = version.created_at.isoformat()
                        else:
                            created_at_str = str(version.created_at)
                    
                    results.append({
                        'version_id': version.version_id,
                        'filename': version.original_filename,
                        'score': score,
                        'created_at': created_at_str,
                        'status': version.status.value if version.status else 'active',
                        'metadata': version.metadata
                    })
            
            # Ordena por score (maior primeiro) e limita resultados
            results.sort(key=lambda x: x['score'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Erro na busca de documentos: {e}")
            return []
    
    def get_document_history(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém o histórico de versões de um documento.
        
        Args:
            document_id: ID do documento
            
        Returns:
            Histórico do documento
        """
        if not self.version_manager:
            logger.warning("Histórico não disponível sem versionamento habilitado")
            return None
        
        try:
            # Busca todas as versões do documento
            versions = self.version_manager.get_document_versions(document_id)
            
            if not versions:
                return None
            
            # Formata o histórico
            versions_list = []
            for version in versions:
                # Formata data de criação
                created_at_str = None
                if version.created_at:
                    if hasattr(version.created_at, 'isoformat'):
                        created_at_str = version.created_at.isoformat()
                    else:
                        created_at_str = str(version.created_at)
                
                version_info = {
                    'version_id': version.version_id,
                    'filename': version.original_filename,
                    'status': version.status.value if version.status else 'active',
                    'created_at': created_at_str,
                    'metadata': version.metadata or {},
                    'size': version.file_size,
                    'content_hash': version.content_hash
                }
                
                # Adiciona informações de processamento se disponíveis
                if version.processing_info:
                    version_info['processing'] = {
                        'chunks_count': version.processing_info.get('chunks_count', 0),
                        'processing_time': version.processing_info.get('processing_time', 0),
                        'success': version.processing_info.get('success', True)
                    }
                
                versions_list.append(version_info)
            
            # Ordena por data de criação (mais recente primeiro)
            versions_list.sort(
                key=lambda x: x['created_at'] or '1970-01-01T00:00:00',
                reverse=True
            )
            
            return {
                'document_id': document_id,
                'total_versions': len(versions_list),
                'versions': versions_list,
                'latest_version': versions_list[0] if versions_list else None
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter histórico do documento: {e}")
            return None
    
    def shutdown(self):
        """Finaliza o pipeline e seus componentes."""
        if self.progress_tracker:
            self.progress_tracker.shutdown()
        
        logger.info("Pipeline de ingestão finalizado") 