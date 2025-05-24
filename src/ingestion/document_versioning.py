"""
Sistema de Versionamento de Documentos
Gerencia versões de documentos e suas derivações processadas.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class VersionStatus(Enum):
    """Status de uma versão de documento."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    PROCESSING = "processing"
    ERROR = "error"

@dataclass
class DocumentVersion:
    """Representa uma versão de documento."""
    version_id: str
    document_id: str
    version_number: str
    content_hash: str
    file_path: str
    original_filename: str
    file_size: int
    created_at: str
    status: VersionStatus
    metadata: Dict[str, Any]
    processing_info: Dict[str, Any]
    parent_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentVersion':
        """Cria instância a partir de dicionário."""
        data['status'] = VersionStatus(data['status'])
        return cls(**data)

@dataclass
class ProcessingResult:
    """Resultado do processamento de uma versão."""
    version_id: str
    chunks_count: int
    processing_time: float
    success: bool
    error_message: Optional[str] = None
    chunks_metadata: List[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)

class DocumentVersionManager:
    """Gerenciador de versões de documentos."""
    
    def __init__(self, storage_path: str = "data/versions"):
        """
        Inicializa o gerenciador de versões.
        
        Args:
            storage_path: Caminho para armazenar dados de versionamento
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de controle
        self.versions_file = self.storage_path / "versions.json"
        self.documents_file = self.storage_path / "documents.json"
        
        # Carrega dados existentes
        self.versions = self._load_versions()
        self.documents = self._load_documents()
        
        logger.info(f"DocumentVersionManager inicializado em {storage_path}")
    
    def _load_versions(self) -> Dict[str, DocumentVersion]:
        """Carrega versões existentes."""
        if not self.versions_file.exists():
            return {}
        
        try:
            with open(self.versions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            versions = {}
            for version_id, version_data in data.items():
                versions[version_id] = DocumentVersion.from_dict(version_data)
            
            logger.info(f"Carregadas {len(versions)} versões")
            return versions
        except Exception as e:
            logger.error(f"Erro ao carregar versões: {e}")
            return {}
    
    def _load_documents(self) -> Dict[str, Dict[str, Any]]:
        """Carrega informações de documentos."""
        if not self.documents_file.exists():
            return {}
        
        try:
            with open(self.documents_file, 'r', encoding='utf-8') as f:
                documents = json.load(f)
            
            logger.info(f"Carregados {len(documents)} documentos")
            return documents
        except Exception as e:
            logger.error(f"Erro ao carregar documentos: {e}")
            return {}
    
    def _save_versions(self):
        """Salva versões no arquivo."""
        try:
            data = {}
            for version_id, version in self.versions.items():
                data[version_id] = version.to_dict()
            
            with open(self.versions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug("Versões salvas com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar versões: {e}")
            raise
    
    def _save_documents(self):
        """Salva informações de documentos."""
        try:
            with open(self.documents_file, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, indent=2, ensure_ascii=False)
            
            logger.debug("Documentos salvos com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar documentos: {e}")
            raise
    
    def _generate_document_id(self, filename: str) -> str:
        """Gera ID único para documento baseado no nome."""
        # Remove extensão e normaliza
        base_name = Path(filename).stem.lower()
        # Adiciona timestamp para garantir unicidade
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{base_name}_{timestamp}"
    
    def _generate_version_id(self, document_id: str, content_hash: str) -> str:
        """Gera ID único para versão."""
        combined = f"{document_id}_{content_hash[:8]}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    def _calculate_content_hash(self, file_path: str) -> str:
        """Calcula hash do conteúdo do arquivo."""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error(f"Erro ao calcular hash de {file_path}: {e}")
            raise
    
    def _get_next_version_number(self, document_id: str) -> str:
        """Obtém próximo número de versão para um documento."""
        if document_id not in self.documents:
            return "1.0.0"
        
        # Encontra a versão mais alta
        versions = [v for v in self.versions.values() if v.document_id == document_id]
        if not versions:
            return "1.0.0"
        
        # Extrai números de versão e encontra o maior
        version_numbers = []
        for version in versions:
            try:
                parts = version.version_number.split('.')
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                version_numbers.append((major, minor, patch))
            except (ValueError, IndexError):
                continue
        
        if not version_numbers:
            return "1.0.0"
        
        # Incrementa versão patch
        max_version = max(version_numbers)
        return f"{max_version[0]}.{max_version[1]}.{max_version[2] + 1}"
    
    def create_document_version(self, file_path: str, original_filename: str,
                              metadata: Optional[Dict[str, Any]] = None,
                              parent_version: Optional[str] = None) -> DocumentVersion:
        """
        Cria nova versão de documento.
        
        Args:
            file_path: Caminho para o arquivo
            original_filename: Nome original do arquivo
            metadata: Metadados adicionais
            parent_version: ID da versão pai (para derivações)
            
        Returns:
            DocumentVersion criada
        """
        try:
            # Calcula hash do conteúdo
            content_hash = self._calculate_content_hash(file_path)
            
            # Verifica se já existe versão com mesmo hash
            existing_version = self.find_version_by_hash(content_hash)
            if existing_version:
                logger.info(f"Versão já existe para hash {content_hash[:8]}")
                return existing_version
            
            # Gera IDs
            document_id = self._generate_document_id(original_filename)
            version_id = self._generate_version_id(document_id, content_hash)
            version_number = self._get_next_version_number(document_id)
            
            # Obtém informações do arquivo
            file_stat = Path(file_path).stat()
            
            # Cria versão
            version = DocumentVersion(
                version_id=version_id,
                document_id=document_id,
                version_number=version_number,
                content_hash=content_hash,
                file_path=str(file_path),
                original_filename=original_filename,
                file_size=file_stat.st_size,
                created_at=datetime.now().isoformat(),
                status=VersionStatus.ACTIVE,
                metadata=metadata or {},
                processing_info={},
                parent_version=parent_version
            )
            
            # Armazena versão
            self.versions[version_id] = version
            
            # Atualiza informações do documento
            if document_id not in self.documents:
                self.documents[document_id] = {
                    'document_id': document_id,
                    'original_filename': original_filename,
                    'created_at': version.created_at,
                    'latest_version': version_id,
                    'version_count': 1
                }
            else:
                self.documents[document_id]['latest_version'] = version_id
                self.documents[document_id]['version_count'] += 1
            
            # Salva dados
            self._save_versions()
            self._save_documents()
            
            logger.info(f"Versão {version_id} criada para documento {document_id}")
            return version
            
        except Exception as e:
            logger.error(f"Erro ao criar versão: {e}")
            raise
    
    def find_version_by_hash(self, content_hash: str) -> Optional[DocumentVersion]:
        """Encontra versão pelo hash do conteúdo."""
        for version in self.versions.values():
            if version.content_hash == content_hash:
                return version
        return None
    
    def get_version(self, version_id: str) -> Optional[DocumentVersion]:
        """Obtém versão pelo ID."""
        return self.versions.get(version_id)
    
    def get_document_versions(self, document_id: str) -> List[DocumentVersion]:
        """Obtém todas as versões de um documento."""
        versions = [v for v in self.versions.values() if v.document_id == document_id]
        return sorted(versions, key=lambda x: x.created_at, reverse=True)
    
    def get_latest_version(self, document_id: str) -> Optional[DocumentVersion]:
        """Obtém a versão mais recente de um documento."""
        versions = self.get_document_versions(document_id)
        return versions[0] if versions else None
    
    def update_processing_info(self, version_id: str, processing_result: ProcessingResult):
        """Atualiza informações de processamento de uma versão."""
        if version_id not in self.versions:
            raise ValueError(f"Versão {version_id} não encontrada")
        
        version = self.versions[version_id]
        version.processing_info = processing_result.to_dict()
        
        # Atualiza status baseado no resultado
        if processing_result.success:
            version.status = VersionStatus.ACTIVE
        else:
            version.status = VersionStatus.ERROR
        
        self._save_versions()
        logger.info(f"Informações de processamento atualizadas para versão {version_id}")
    
    def archive_version(self, version_id: str):
        """Arquiva uma versão."""
        if version_id not in self.versions:
            raise ValueError(f"Versão {version_id} não encontrada")
        
        self.versions[version_id].status = VersionStatus.ARCHIVED
        self._save_versions()
        logger.info(f"Versão {version_id} arquivada")
    
    def deprecate_version(self, version_id: str):
        """Marca versão como depreciada."""
        if version_id not in self.versions:
            raise ValueError(f"Versão {version_id} não encontrada")
        
        self.versions[version_id].status = VersionStatus.DEPRECATED
        self._save_versions()
        logger.info(f"Versão {version_id} marcada como depreciada")
    
    def delete_version(self, version_id: str, delete_file: bool = False):
        """
        Remove uma versão.
        
        Args:
            version_id: ID da versão
            delete_file: Se deve deletar o arquivo físico
        """
        if version_id not in self.versions:
            raise ValueError(f"Versão {version_id} não encontrada")
        
        version = self.versions[version_id]
        
        # Remove arquivo físico se solicitado
        if delete_file and Path(version.file_path).exists():
            try:
                Path(version.file_path).unlink()
                logger.info(f"Arquivo {version.file_path} removido")
            except Exception as e:
                logger.warning(f"Erro ao remover arquivo {version.file_path}: {e}")
        
        # Remove versão
        del self.versions[version_id]
        
        # Atualiza informações do documento
        document_id = version.document_id
        if document_id in self.documents:
            self.documents[document_id]['version_count'] -= 1
            
            # Se era a versão mais recente, encontra nova versão mais recente
            if self.documents[document_id]['latest_version'] == version_id:
                remaining_versions = self.get_document_versions(document_id)
                if remaining_versions:
                    self.documents[document_id]['latest_version'] = remaining_versions[0].version_id
                else:
                    # Remove documento se não há mais versões
                    del self.documents[document_id]
        
        self._save_versions()
        self._save_documents()
        logger.info(f"Versão {version_id} removida")
    
    def get_version_diff(self, version_id1: str, version_id2: str) -> Dict[str, Any]:
        """
        Compara duas versões e retorna diferenças.
        
        Args:
            version_id1: ID da primeira versão
            version_id2: ID da segunda versão
            
        Returns:
            Dicionário com diferenças encontradas
        """
        version1 = self.get_version(version_id1)
        version2 = self.get_version(version_id2)
        
        if not version1 or not version2:
            raise ValueError("Uma ou ambas versões não encontradas")
        
        diff = {
            'version1': {
                'id': version1.version_id,
                'number': version1.version_number,
                'created_at': version1.created_at,
                'file_size': version1.file_size,
                'content_hash': version1.content_hash
            },
            'version2': {
                'id': version2.version_id,
                'number': version2.version_number,
                'created_at': version2.created_at,
                'file_size': version2.file_size,
                'content_hash': version2.content_hash
            },
            'differences': {
                'content_changed': version1.content_hash != version2.content_hash,
                'size_changed': version1.file_size != version2.file_size,
                'size_diff': version2.file_size - version1.file_size,
                'time_diff': version2.created_at > version1.created_at
            }
        }
        
        # Compara metadados
        metadata_diff = {}
        all_keys = set(version1.metadata.keys()) | set(version2.metadata.keys())
        
        for key in all_keys:
            val1 = version1.metadata.get(key)
            val2 = version2.metadata.get(key)
            
            if val1 != val2:
                metadata_diff[key] = {
                    'version1': val1,
                    'version2': val2
                }
        
        diff['metadata_differences'] = metadata_diff
        
        return diff
    
    def get_version_history(self, document_id: str) -> List[Dict[str, Any]]:
        """Obtém histórico completo de versões de um documento."""
        versions = self.get_document_versions(document_id)
        
        history = []
        for version in versions:
            history.append({
                'version_id': version.version_id,
                'version_number': version.version_number,
                'created_at': version.created_at,
                'status': version.status.value,
                'file_size': version.file_size,
                'has_processing_info': bool(version.processing_info),
                'parent_version': version.parent_version
            })
        
        return history
    
    def cleanup_old_versions(self, document_id: str, keep_count: int = 5):
        """
        Remove versões antigas, mantendo apenas as mais recentes.
        
        Args:
            document_id: ID do documento
            keep_count: Número de versões a manter
        """
        versions = self.get_document_versions(document_id)
        
        if len(versions) <= keep_count:
            logger.info(f"Documento {document_id} tem {len(versions)} versões, nenhuma remoção necessária")
            return
        
        # Remove versões mais antigas
        versions_to_remove = versions[keep_count:]
        
        for version in versions_to_remove:
            if version.status != VersionStatus.ACTIVE:
                self.delete_version(version.version_id, delete_file=True)
                logger.info(f"Versão antiga {version.version_id} removida")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas do sistema de versionamento."""
        total_versions = len(self.versions)
        total_documents = len(self.documents)
        
        # Conta por status
        status_counts = {}
        for status in VersionStatus:
            status_counts[status.value] = sum(
                1 for v in self.versions.values() if v.status == status
            )
        
        # Calcula tamanho total
        total_size = sum(v.file_size for v in self.versions.values())
        
        # Versões com processamento
        processed_versions = sum(
            1 for v in self.versions.values() if v.processing_info
        )
        
        return {
            'total_documents': total_documents,
            'total_versions': total_versions,
            'status_distribution': status_counts,
            'total_storage_size': total_size,
            'processed_versions': processed_versions,
            'processing_rate': processed_versions / total_versions if total_versions > 0 else 0
        } 