"""
Sistema de Tracking de Progresso para Pipeline de Ingestão
Monitora e reporta o status de processamento de documentos em tempo real.
"""

import time
import logging
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import queue

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Estágios do pipeline de processamento."""
    UPLOAD = "upload"
    PARSING = "parsing"
    CHUNKING = "chunking"
    METADATA_EXTRACTION = "metadata_extraction"
    VALIDATION = "validation"
    VERSIONING = "versioning"
    STORAGE = "storage"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStatus(Enum):
    """Status de processamento de um documento."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(Enum):
    """Tipos de notificação."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ProcessingMetrics:
    """Métricas de processamento de um documento."""
    document_id: str
    filename: str
    file_size: int
    start_time: float
    end_time: Optional[float] = None
    stage_timings: Dict[str, float] = field(default_factory=dict)
    stage_durations: Dict[str, float] = field(default_factory=dict)
    chunks_created: int = 0
    validation_score: Optional[float] = None
    error_count: int = 0
    warnings_count: int = 0
    
    @property
    def total_duration(self) -> Optional[float]:
        """Duração total do processamento."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def processing_speed(self) -> Optional[float]:
        """Velocidade de processamento em chars/segundo."""
        if self.total_duration and self.file_size > 0:
            return self.file_size / self.total_duration
        return None


@dataclass
class StageProgress:
    """Progresso de um estágio específico."""
    stage: ProcessingStage
    started_at: float
    completed_at: Optional[float] = None
    progress_percentage: float = 0.0
    status: ProcessingStatus = ProcessingStatus.IN_PROGRESS
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Duração do estágio."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return None


@dataclass
class DocumentProgress:
    """Progresso de processamento de um documento."""
    document_id: str
    filename: str
    file_size: int
    status: ProcessingStatus
    current_stage: ProcessingStage
    stages: Dict[ProcessingStage, StageProgress] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def overall_progress(self) -> float:
        """Progresso geral do documento (0-100)."""
        completed_stages = sum(1 for stage in self.stages.values() 
                             if stage.status == ProcessingStatus.COMPLETED)
        total_stages = len(ProcessingStage) - 2  # Excluindo COMPLETED e FAILED
        return (completed_stages / total_stages) * 100 if total_stages > 0 else 0
    
    def update_stage(self, stage: ProcessingStage, progress: float = 0.0, 
                    details: Optional[Dict] = None, status: Optional[ProcessingStatus] = None):
        """Atualiza o progresso de um estágio."""
        self.updated_at = time.time()
        self.current_stage = stage
        
        if stage not in self.stages:
            self.stages[stage] = StageProgress(stage=stage, started_at=time.time())
        
        stage_progress = self.stages[stage]
        stage_progress.progress_percentage = progress
        
        if details:
            stage_progress.details.update(details)
        
        if status:
            stage_progress.status = status
            if status == ProcessingStatus.COMPLETED:
                stage_progress.completed_at = time.time()
                stage_progress.progress_percentage = 100.0


@dataclass
class BatchProgress:
    """Progresso de processamento em lote."""
    batch_id: str
    total_documents: int
    documents: Dict[str, DocumentProgress] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    @property
    def completed_documents(self) -> int:
        """Número de documentos completados."""
        return sum(1 for doc in self.documents.values() 
                  if doc.status == ProcessingStatus.COMPLETED)
    
    @property
    def failed_documents(self) -> int:
        """Número de documentos que falharam."""
        return sum(1 for doc in self.documents.values() 
                  if doc.status == ProcessingStatus.FAILED)
    
    @property
    def in_progress_documents(self) -> int:
        """Número de documentos em processamento."""
        return sum(1 for doc in self.documents.values() 
                  if doc.status == ProcessingStatus.IN_PROGRESS)
    
    @property
    def overall_progress(self) -> float:
        """Progresso geral do lote (0-100)."""
        if self.total_documents == 0:
            return 100.0
        return (self.completed_documents / self.total_documents) * 100
    
    @property
    def is_completed(self) -> bool:
        """Verifica se o lote foi completado."""
        return (self.completed_documents + self.failed_documents) >= self.total_documents


@dataclass
class Notification:
    """Notificação do sistema."""
    id: str
    type: NotificationType
    title: str
    message: str
    document_id: Optional[str] = None
    batch_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    read: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProgressTracker:
    """Sistema principal de tracking de progresso."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Inicializa o tracker de progresso.
        
        Args:
            storage_path: Caminho para armazenar dados de progresso
        """
        self.storage_path = storage_path or Path("data/progress")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Estado interno
        self.batches: Dict[str, BatchProgress] = {}
        self.documents: Dict[str, DocumentProgress] = {}
        self.notifications: Dict[str, Notification] = {}
        self.metrics: Dict[str, ProcessingMetrics] = {}
        
        # Callbacks para notificações
        self.notification_callbacks: List[Callable[[Notification], None]] = []
        
        # Thread-safe queue para atualizações
        self.update_queue = queue.Queue()
        self.running = True
        
        # Thread para processar atualizações
        self.update_thread = threading.Thread(target=self._process_updates, daemon=True)
        self.update_thread.start()
        
        # Carrega dados persistidos
        self._load_state()
    
    def start_batch(self, document_filenames: List[str]) -> str:
        """
        Inicia um novo lote de processamento.
        
        Args:
            document_filenames: Lista de nomes de arquivos
            
        Returns:
            ID do lote criado
        """
        batch_id = str(uuid.uuid4())
        batch = BatchProgress(
            batch_id=batch_id,
            total_documents=len(document_filenames)
        )
        
        self.batches[batch_id] = batch
        
        # Cria documentos no lote
        for filename in document_filenames:
            doc_id = self.start_document_processing(filename, batch_id)
            batch.documents[doc_id] = self.documents[doc_id]
        
        self._notify(NotificationType.INFO, 
                    f"Lote iniciado",
                    f"Processamento de {len(document_filenames)} documentos iniciado",
                    batch_id=batch_id)
        
        self._save_state()
        return batch_id
    
    def start_document_processing(self, filename: str, batch_id: Optional[str] = None, 
                                file_size: int = 0) -> str:
        """
        Inicia o processamento de um documento.
        
        Args:
            filename: Nome do arquivo
            batch_id: ID do lote (opcional)
            file_size: Tamanho do arquivo em bytes
            
        Returns:
            ID do documento criado
        """
        doc_id = str(uuid.uuid4())
        doc_progress = DocumentProgress(
            document_id=doc_id,
            filename=filename,
            file_size=file_size,
            status=ProcessingStatus.QUEUED,
            current_stage=ProcessingStage.UPLOAD
        )
        
        if batch_id:
            doc_progress.metadata['batch_id'] = batch_id
        
        self.documents[doc_id] = doc_progress
        
        # Cria métricas
        self.metrics[doc_id] = ProcessingMetrics(
            document_id=doc_id,
            filename=filename,
            file_size=file_size,
            start_time=time.time()
        )
        
        self._save_state()
        return doc_id
    
    def update_document_progress(self, document_id: str, stage: ProcessingStage, 
                               progress: float = 0.0, details: Optional[Dict] = None,
                               status: Optional[ProcessingStatus] = None):
        """
        Atualiza o progresso de um documento.
        
        Args:
            document_id: ID do documento
            stage: Estágio atual
            progress: Progresso (0-100)
            details: Detalhes adicionais
            status: Status do estágio
        """
        if document_id not in self.documents:
            logger.warning(f"Documento {document_id} não encontrado")
            return
        
        doc = self.documents[document_id]
        old_stage = doc.current_stage
        
        # Atualiza estágio
        doc.update_stage(stage, progress, details, status)
        
        # Atualiza métricas
        metrics = self.metrics.get(document_id)
        if metrics:
            # Marca timing do estágio
            if old_stage != stage:
                stage_name = stage.value
                metrics.stage_timings[stage_name] = time.time()
                
                # Calcula duração do estágio anterior
                if old_stage and old_stage.value in metrics.stage_timings:
                    old_stage_name = old_stage.value
                    if old_stage_name in metrics.stage_timings:
                        duration = time.time() - metrics.stage_timings[old_stage_name]
                        metrics.stage_durations[old_stage_name] = duration
        
        # Atualiza status geral se necessário
        if status == ProcessingStatus.COMPLETED and stage == ProcessingStage.COMPLETED:
            doc.status = ProcessingStatus.COMPLETED
            if metrics:
                metrics.end_time = time.time()
            
            self._notify(NotificationType.SUCCESS,
                        f"Documento processado",
                        f"'{doc.filename}' foi processado com sucesso",
                        document_id=document_id)
        
        elif status == ProcessingStatus.FAILED:
            doc.status = ProcessingStatus.FAILED
            if metrics:
                metrics.end_time = time.time()
                metrics.error_count += 1
            
            self._notify(NotificationType.ERROR,
                        f"Falha no processamento",
                        f"Erro ao processar '{doc.filename}'",
                        document_id=document_id)
        
        elif doc.status == ProcessingStatus.QUEUED and stage != ProcessingStage.UPLOAD:
            doc.status = ProcessingStatus.IN_PROGRESS
        
        # Verifica se o lote foi completado
        batch_id = doc.metadata.get('batch_id')
        if batch_id and batch_id in self.batches:
            batch = self.batches[batch_id]
            if batch.is_completed and not batch.completed_at:
                batch.completed_at = time.time()
                
                self._notify(NotificationType.SUCCESS,
                            f"Lote completado",
                            f"Processamento do lote concluído: {batch.completed_documents} sucessos, {batch.failed_documents} falhas",
                            batch_id=batch_id)
        
        self.update_queue.put(('save_state', None))
    
    def update_document_metrics(self, document_id: str, **kwargs):
        """
        Atualiza métricas específicas de um documento.
        
        Args:
            document_id: ID do documento
            **kwargs: Métricas a atualizar
        """
        if document_id in self.metrics:
            metrics = self.metrics[document_id]
            for key, value in kwargs.items():
                if hasattr(metrics, key):
                    setattr(metrics, key, value)
    
    def get_document_progress(self, document_id: str) -> Optional[DocumentProgress]:
        """Obtém o progresso de um documento específico."""
        return self.documents.get(document_id)
    
    def get_batch_progress(self, batch_id: str) -> Optional[BatchProgress]:
        """Obtém o progresso de um lote específico."""
        return self.batches.get(batch_id)
    
    def get_document_metrics(self, document_id: str) -> Optional[ProcessingMetrics]:
        """Obtém as métricas de um documento específico."""
        return self.metrics.get(document_id)
    
    def get_overall_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas gerais do sistema.
        
        Returns:
            Dicionário com estatísticas do sistema
        """
        total_docs = len(self.documents)
        completed_docs = sum(1 for doc in self.documents.values() 
                           if doc.status == ProcessingStatus.COMPLETED)
        failed_docs = sum(1 for doc in self.documents.values() 
                        if doc.status == ProcessingStatus.FAILED)
        in_progress_docs = sum(1 for doc in self.documents.values() 
                             if doc.status == ProcessingStatus.IN_PROGRESS)
        
        # Métricas de performance
        completed_metrics = [m for m in self.metrics.values() if m.end_time]
        avg_processing_time = (sum(m.total_duration for m in completed_metrics) / 
                             len(completed_metrics)) if completed_metrics else 0
        
        avg_processing_speed = (sum(m.processing_speed for m in completed_metrics 
                                  if m.processing_speed) / 
                              len([m for m in completed_metrics if m.processing_speed])) if completed_metrics else 0
        
        return {
            'total_documents': total_docs,
            'completed_documents': completed_docs,
            'failed_documents': failed_docs,
            'in_progress_documents': in_progress_docs,
            'success_rate': (completed_docs / total_docs * 100) if total_docs > 0 else 0,
            'average_processing_time': avg_processing_time,
            'average_processing_speed': avg_processing_speed,
            'total_batches': len(self.batches),
            'active_batches': sum(1 for batch in self.batches.values() if not batch.is_completed)
        }
    
    def get_recent_documents(self, limit: int = 20) -> List[DocumentProgress]:
        """
        Obtém os documentos mais recentes.
        
        Args:
            limit: Número máximo de documentos
            
        Returns:
            Lista de progressos de documentos ordenados por data
        """
        sorted_docs = sorted(self.documents.values(), 
                           key=lambda x: x.updated_at, reverse=True)
        return sorted_docs[:limit]
    
    def get_notifications(self, unread_only: bool = False, limit: int = 50) -> List[Notification]:
        """
        Obtém notificações do sistema.
        
        Args:
            unread_only: Apenas notificações não lidas
            limit: Número máximo de notificações
            
        Returns:
            Lista de notificações
        """
        notifications = list(self.notifications.values())
        
        if unread_only:
            notifications = [n for n in notifications if not n.read]
        
        # Ordena por timestamp (mais recentes primeiro)
        notifications.sort(key=lambda x: x.timestamp, reverse=True)
        
        return notifications[:limit]
    
    def mark_notification_read(self, notification_id: str):
        """Marca uma notificação como lida."""
        if notification_id in self.notifications:
            self.notifications[notification_id].read = True
            self._save_state()
    
    def add_notification_callback(self, callback: Callable[[Notification], None]):
        """Adiciona callback para notificações."""
        self.notification_callbacks.append(callback)
    
    def clear_old_data(self, days: int = 30):
        """
        Remove dados antigos do sistema.
        
        Args:
            days: Número de dias para manter os dados
        """
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        # Remove documentos antigos
        old_docs = [doc_id for doc_id, doc in self.documents.items() 
                   if doc.updated_at < cutoff_time]
        
        for doc_id in old_docs:
            del self.documents[doc_id]
            if doc_id in self.metrics:
                del self.metrics[doc_id]
        
        # Remove lotes antigos
        old_batches = [batch_id for batch_id, batch in self.batches.items() 
                      if batch.started_at < cutoff_time]
        
        for batch_id in old_batches:
            del self.batches[batch_id]
        
        # Remove notificações antigas
        old_notifications = [notif_id for notif_id, notif in self.notifications.items() 
                           if notif.timestamp < cutoff_time]
        
        for notif_id in old_notifications:
            del self.notifications[notif_id]
        
        logger.info(f"Removidos {len(old_docs)} documentos, {len(old_batches)} lotes, "
                   f"{len(old_notifications)} notificações antigas")
        
        self._save_state()
    
    def _notify(self, type_: NotificationType, title: str, message: str, 
               document_id: Optional[str] = None, batch_id: Optional[str] = None):
        """Cria e dispara uma notificação."""
        notification = Notification(
            id=str(uuid.uuid4()),
            type=type_,
            title=title,
            message=message,
            document_id=document_id,
            batch_id=batch_id
        )
        
        self.notifications[notification.id] = notification
        
        # Chama callbacks
        for callback in self.notification_callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Erro em callback de notificação: {e}")
    
    def _process_updates(self):
        """Processa atualizações em background."""
        while self.running:
            try:
                action, data = self.update_queue.get(timeout=1.0)
                
                if action == 'save_state':
                    self._save_state()
                
                self.update_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro ao processar atualização: {e}")
    
    def _save_state(self):
        """Salva o estado atual em arquivo."""
        try:
            # Garante que o diretório existe
            self.storage_path.mkdir(parents=True, exist_ok=True)
            
            state = {
                'batches': {bid: self._batch_to_dict(batch) 
                           for bid, batch in self.batches.items()},
                'documents': {did: self._document_to_dict(doc) 
                             for did, doc in self.documents.items()},
                'notifications': {nid: self._notification_to_dict(notif) 
                                for nid, notif in self.notifications.items()},
                'metrics': {mid: self._metrics_to_dict(metrics) 
                           for mid, metrics in self.metrics.items()},
                'last_saved': time.time()
            }
            
            state_file = self.storage_path / 'progress_state.json'
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def _load_state(self):
        """Carrega o estado de arquivo."""
        try:
            state_file = self.storage_path / 'progress_state.json'
            if not state_file.exists():
                return
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Carrega lotes
            for bid, batch_data in state.get('batches', {}).items():
                self.batches[bid] = self._dict_to_batch(batch_data)
            
            # Carrega documentos
            for did, doc_data in state.get('documents', {}).items():
                self.documents[did] = self._dict_to_document(doc_data)
            
            # Carrega notificações
            for nid, notif_data in state.get('notifications', {}).items():
                self.notifications[nid] = self._dict_to_notification(notif_data)
            
            # Carrega métricas
            for mid, metrics_data in state.get('metrics', {}).items():
                self.metrics[mid] = self._dict_to_metrics(metrics_data)
            
            logger.info("Estado carregado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
    
    def _batch_to_dict(self, batch: BatchProgress) -> Dict:
        """Converte BatchProgress para dicionário."""
        return {
            'batch_id': batch.batch_id,
            'total_documents': batch.total_documents,
            'started_at': batch.started_at,
            'completed_at': batch.completed_at,
            'documents': list(batch.documents.keys())
        }
    
    def _dict_to_batch(self, data: Dict) -> BatchProgress:
        """Converte dicionário para BatchProgress."""
        batch = BatchProgress(
            batch_id=data['batch_id'],
            total_documents=data['total_documents'],
            started_at=data['started_at'],
            completed_at=data.get('completed_at')
        )
        
        # Reconecta documentos
        for doc_id in data.get('documents', []):
            if doc_id in self.documents:
                batch.documents[doc_id] = self.documents[doc_id]
        
        return batch
    
    def _document_to_dict(self, doc: DocumentProgress) -> Dict:
        """Converte DocumentProgress para dicionário."""
        return {
            'document_id': doc.document_id,
            'filename': doc.filename,
            'file_size': doc.file_size,
            'status': doc.status.value,
            'current_stage': doc.current_stage.value,
            'created_at': doc.created_at,
            'updated_at': doc.updated_at,
            'metadata': doc.metadata,
            'stages': {stage.value: {
                'stage': stage_prog.stage.value,
                'started_at': stage_prog.started_at,
                'completed_at': stage_prog.completed_at,
                'progress_percentage': stage_prog.progress_percentage,
                'status': stage_prog.status.value,
                'details': stage_prog.details,
                'error_message': stage_prog.error_message
            } for stage, stage_prog in doc.stages.items()}
        }
    
    def _dict_to_document(self, data: Dict) -> DocumentProgress:
        """Converte dicionário para DocumentProgress."""
        doc = DocumentProgress(
            document_id=data['document_id'],
            filename=data['filename'],
            file_size=data['file_size'],
            status=ProcessingStatus(data['status']),
            current_stage=ProcessingStage(data['current_stage']),
            created_at=data['created_at'],
            updated_at=data['updated_at'],
            metadata=data.get('metadata', {})
        )
        
        # Reconstrói estágios
        for stage_name, stage_data in data.get('stages', {}).items():
            stage = ProcessingStage(stage_name)
            stage_progress = StageProgress(
                stage=ProcessingStage(stage_data['stage']),
                started_at=stage_data['started_at'],
                completed_at=stage_data.get('completed_at'),
                progress_percentage=stage_data['progress_percentage'],
                status=ProcessingStatus(stage_data['status']),
                details=stage_data.get('details', {}),
                error_message=stage_data.get('error_message')
            )
            doc.stages[stage] = stage_progress
        
        return doc
    
    def _notification_to_dict(self, notif: Notification) -> Dict:
        """Converte Notification para dicionário."""
        return {
            'id': notif.id,
            'type': notif.type.value,
            'title': notif.title,
            'message': notif.message,
            'document_id': notif.document_id,
            'batch_id': notif.batch_id,
            'timestamp': notif.timestamp,
            'read': notif.read,
            'metadata': notif.metadata
        }
    
    def _dict_to_notification(self, data: Dict) -> Notification:
        """Converte dicionário para Notification."""
        return Notification(
            id=data['id'],
            type=NotificationType(data['type']),
            title=data['title'],
            message=data['message'],
            document_id=data.get('document_id'),
            batch_id=data.get('batch_id'),
            timestamp=data['timestamp'],
            read=data.get('read', False),
            metadata=data.get('metadata', {})
        )
    
    def _metrics_to_dict(self, metrics: ProcessingMetrics) -> Dict:
        """Converte ProcessingMetrics para dicionário."""
        return {
            'document_id': metrics.document_id,
            'filename': metrics.filename,
            'file_size': metrics.file_size,
            'start_time': metrics.start_time,
            'end_time': metrics.end_time,
            'stage_timings': metrics.stage_timings,
            'stage_durations': metrics.stage_durations,
            'chunks_created': metrics.chunks_created,
            'validation_score': metrics.validation_score,
            'error_count': metrics.error_count,
            'warnings_count': metrics.warnings_count
        }
    
    def _dict_to_metrics(self, data: Dict) -> ProcessingMetrics:
        """Converte dicionário para ProcessingMetrics."""
        return ProcessingMetrics(
            document_id=data['document_id'],
            filename=data['filename'],
            file_size=data['file_size'],
            start_time=data['start_time'],
            end_time=data.get('end_time'),
            stage_timings=data.get('stage_timings', {}),
            stage_durations=data.get('stage_durations', {}),
            chunks_created=data.get('chunks_created', 0),
            validation_score=data.get('validation_score'),
            error_count=data.get('error_count', 0),
            warnings_count=data.get('warnings_count', 0)
        )
    
    def shutdown(self):
        """Finaliza o tracker de progresso."""
        self.running = False
        self._save_state()
        if self.update_thread.is_alive():
            self.update_thread.join(timeout=2.0)


# Instância global opcional
_global_tracker: Optional[ProgressTracker] = None


def get_global_tracker() -> ProgressTracker:
    """Obtém a instância global do tracker de progresso."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ProgressTracker()
    return _global_tracker


def set_global_tracker(tracker: ProgressTracker):
    """Define a instância global do tracker de progresso."""
    global _global_tracker
    _global_tracker = tracker 