"""
Testes para o sistema de versionamento de documentos.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import json

from src.ingestion.document_versioning import (
    DocumentVersionManager, DocumentVersion, ProcessingResult, VersionStatus
)


class TestDocumentVersionManager:
    """Testes para o gerenciador de versões de documentos."""
    
    def setup_method(self):
        """Setup para cada teste."""
        # Cria diretório temporário para testes
        self.temp_dir = Path(tempfile.mkdtemp())
        self.storage_path = self.temp_dir / "versions"
        self.version_manager = DocumentVersionManager(str(self.storage_path))
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_file(self, content: str, filename: str) -> str:
        """Cria um arquivo de teste."""
        file_path = self.temp_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(file_path)
    
    def test_create_document_version(self):
        """Testa criação de versão de documento."""
        # Cria arquivo de teste
        content = "Este é um documento de teste."
        file_path = self.create_test_file(content, "test.txt")
        
        # Cria versão
        version = self.version_manager.create_document_version(
            file_path, "test.txt", {"author": "test"}
        )
        
        assert version is not None
        assert version.original_filename == "test.txt"
        assert version.version_number == "1.0.0"
        assert version.status == VersionStatus.ACTIVE
        assert version.metadata["author"] == "test"
        assert len(version.content_hash) == 64  # SHA-256 hash
    
    def test_duplicate_content_detection(self):
        """Testa detecção de conteúdo duplicado."""
        content = "Mesmo conteúdo para ambos arquivos."
        
        # Cria primeiro arquivo
        file1_path = self.create_test_file(content, "file1.txt")
        version1 = self.version_manager.create_document_version(file1_path, "file1.txt")
        
        # Cria segundo arquivo com mesmo conteúdo
        file2_path = self.create_test_file(content, "file2.txt")
        version2 = self.version_manager.create_document_version(file2_path, "file2.txt")
        
        # Deve retornar a mesma versão
        assert version1.version_id == version2.version_id
        assert version1.content_hash == version2.content_hash
    
    def test_version_numbering(self):
        """Testa numeração sequencial de versões."""
        base_content = "Conteúdo base do documento"
        
        # Cria múltiplas versões do mesmo documento base
        versions = []
        for i in range(3):
            content = f"{base_content} - versão {i}"
            file_path = self.create_test_file(content, "document.txt")
            version = self.version_manager.create_document_version(file_path, "document.txt")
            versions.append(version)
        
        # Verifica numeração
        version_numbers = [v.version_number for v in versions]
        assert "1.0.0" in version_numbers
        assert "1.0.1" in version_numbers  
        assert "1.0.2" in version_numbers
    
    def test_find_version_by_hash(self):
        """Testa busca de versão por hash."""
        content = "Conteúdo para busca por hash"
        file_path = self.create_test_file(content, "search_test.txt")
        
        version = self.version_manager.create_document_version(file_path, "search_test.txt")
        found_version = self.version_manager.find_version_by_hash(version.content_hash)
        
        assert found_version is not None
        assert found_version.version_id == version.version_id
    
    def test_get_document_versions(self):
        """Testa obtenção de todas as versões de um documento."""
        base_content = "Documento com múltiplas versões"
        document_id = None
        
        # Cria várias versões
        for i in range(3):
            content = f"{base_content} {i}"
            file_path = self.create_test_file(content, "multi_version.txt")
            version = self.version_manager.create_document_version(file_path, "multi_version.txt")
            
            if document_id is None:
                document_id = version.document_id
        
        # Obtém todas as versões
        versions = self.version_manager.get_document_versions(document_id)
        
        assert len(versions) == 3
        # Verifica se estão ordenadas por data (mais recente primeiro)
        for i in range(len(versions) - 1):
            assert versions[i].created_at >= versions[i + 1].created_at
    
    def test_get_latest_version(self):
        """Testa obtenção da versão mais recente."""
        base_content = "Documento para teste de versão mais recente"
        document_id = None
        latest_version = None
        
        # Cria várias versões
        for i in range(3):
            content = f"{base_content} {i}"
            file_path = self.create_test_file(content, f"latest_test_{i}.txt")
            version = self.version_manager.create_document_version(file_path, "latest_test.txt")
            
            if document_id is None:
                document_id = version.document_id
            latest_version = version
        
        # Obtém versão mais recente
        found_latest = self.version_manager.get_latest_version(document_id)
        
        assert found_latest is not None
        assert found_latest.version_id == latest_version.version_id
    
    def test_update_processing_info(self):
        """Testa atualização de informações de processamento."""
        content = "Documento para teste de processamento"
        file_path = self.create_test_file(content, "processing_test.txt")
        
        version = self.version_manager.create_document_version(file_path, "processing_test.txt")
        
        # Cria resultado de processamento
        processing_result = ProcessingResult(
            version_id=version.version_id,
            chunks_count=5,
            processing_time=1.23,
            success=True,
            chunks_metadata=[{"chunk_1": "metadata"}]
        )
        
        # Atualiza informações
        self.version_manager.update_processing_info(version.version_id, processing_result)
        
        # Verifica atualização
        updated_version = self.version_manager.get_version(version.version_id)
        assert updated_version.processing_info["chunks_count"] == 5
        assert updated_version.processing_info["success"] is True
        assert updated_version.status == VersionStatus.ACTIVE
    
    def test_archive_version(self):
        """Testa arquivamento de versão."""
        content = "Documento para teste de arquivamento"
        file_path = self.create_test_file(content, "archive_test.txt")
        
        version = self.version_manager.create_document_version(file_path, "archive_test.txt")
        
        # Arquiva versão
        self.version_manager.archive_version(version.version_id)
        
        # Verifica status
        archived_version = self.version_manager.get_version(version.version_id)
        assert archived_version.status == VersionStatus.ARCHIVED
    
    def test_deprecate_version(self):
        """Testa depreciação de versão."""
        content = "Documento para teste de depreciação"
        file_path = self.create_test_file(content, "deprecate_test.txt")
        
        version = self.version_manager.create_document_version(file_path, "deprecate_test.txt")
        
        # Deprecia versão
        self.version_manager.deprecate_version(version.version_id)
        
        # Verifica status
        deprecated_version = self.version_manager.get_version(version.version_id)
        assert deprecated_version.status == VersionStatus.DEPRECATED
    
    def test_delete_version(self):
        """Testa remoção de versão."""
        content = "Documento para teste de remoção"
        file_path = self.create_test_file(content, "delete_test.txt")
        
        version = self.version_manager.create_document_version(file_path, "delete_test.txt")
        version_id = version.version_id
        
        # Remove versão
        self.version_manager.delete_version(version_id)
        
        # Verifica remoção
        deleted_version = self.version_manager.get_version(version_id)
        assert deleted_version is None
    
    def test_get_version_diff(self):
        """Testa comparação entre versões."""
        # Cria primeira versão
        content1 = "Primeira versão do documento"
        file1_path = self.create_test_file(content1, "diff_test1.txt")
        version1 = self.version_manager.create_document_version(
            file1_path, "diff_test.txt", {"author": "user1"}
        )
        
        # Cria segunda versão
        content2 = "Segunda versão do documento com mais conteúdo"
        file2_path = self.create_test_file(content2, "diff_test2.txt")
        version2 = self.version_manager.create_document_version(
            file2_path, "diff_test.txt", {"author": "user2"}
        )
        
        # Compara versões
        diff = self.version_manager.get_version_diff(version1.version_id, version2.version_id)
        
        assert diff["differences"]["content_changed"] is True
        assert diff["differences"]["size_changed"] is True
        assert diff["differences"]["size_diff"] > 0
        assert "author" in diff["metadata_differences"]
    
    def test_get_version_history(self):
        """Testa obtenção do histórico de versões."""
        base_content = "Documento com histórico"
        document_id = None
        
        # Cria várias versões
        for i in range(3):
            content = f"{base_content} versão {i}"
            file_path = self.create_test_file(content, f"history_test_{i}.txt")
            version = self.version_manager.create_document_version(file_path, "history_test.txt")
            
            if document_id is None:
                document_id = version.document_id
        
        # Obtém histórico
        history = self.version_manager.get_version_history(document_id)
        
        assert len(history) == 3
        assert all("version_id" in entry for entry in history)
        assert all("created_at" in entry for entry in history)
        assert all("status" in entry for entry in history)
    
    def test_cleanup_old_versions(self):
        """Testa limpeza de versões antigas."""
        base_content = "Documento para teste de limpeza"
        document_id = None
        
        # Cria muitas versões
        for i in range(10):
            content = f"{base_content} versão {i}"
            file_path = self.create_test_file(content, f"cleanup_test_{i}.txt")
            version = self.version_manager.create_document_version(file_path, "cleanup_test.txt")
            
            if document_id is None:
                document_id = version.document_id
            
            # Marca versões antigas como não ativas
            if i < 7:
                self.version_manager.archive_version(version.version_id)
        
        # Faz limpeza mantendo apenas 3 versões
        self.version_manager.cleanup_old_versions(document_id, keep_count=3)
        
        # Verifica resultado
        remaining_versions = self.version_manager.get_document_versions(document_id)
        assert len(remaining_versions) <= 3
    
    def test_get_statistics(self):
        """Testa obtenção de estatísticas."""
        # Cria algumas versões
        for i in range(3):
            content = f"Documento {i} para estatísticas"
            file_path = self.create_test_file(content, f"stats_test_{i}.txt")
            version = self.version_manager.create_document_version(file_path, f"stats_test_{i}.txt")
            
            # Adiciona informação de processamento para algumas
            if i % 2 == 0:
                processing_result = ProcessingResult(
                    version_id=version.version_id,
                    chunks_count=2,
                    processing_time=0.5,
                    success=True
                )
                self.version_manager.update_processing_info(version.version_id, processing_result)
        
        # Obtém estatísticas
        stats = self.version_manager.get_statistics()
        
        assert stats["total_documents"] >= 3
        assert stats["total_versions"] >= 3
        assert "status_distribution" in stats
        assert "total_storage_size" in stats
        assert stats["processed_versions"] >= 2
        assert 0 <= stats["processing_rate"] <= 1
    
    def test_persistence(self):
        """Testa persistência de dados."""
        content = "Documento para teste de persistência"
        file_path = self.create_test_file(content, "persistence_test.txt")
        
        # Cria versão
        version = self.version_manager.create_document_version(file_path, "persistence_test.txt")
        original_version_id = version.version_id
        
        # Cria novo gerenciador com o mesmo storage path
        new_manager = DocumentVersionManager(str(self.storage_path))
        
        # Verifica se os dados foram carregados
        loaded_version = new_manager.get_version(original_version_id)
        assert loaded_version is not None
        assert loaded_version.original_filename == "persistence_test.txt"


class TestDocumentVersion:
    """Testes para a classe DocumentVersion."""
    
    def test_to_dict_and_from_dict(self):
        """Testa conversão para dicionário e de volta."""
        version = DocumentVersion(
            version_id="test_id",
            document_id="doc_id",
            version_number="1.0.0",
            content_hash="hash123",
            file_path="/path/to/file.txt",
            original_filename="file.txt",
            file_size=1024,
            created_at=datetime.now().isoformat(),
            status=VersionStatus.ACTIVE,
            metadata={"author": "test"},
            processing_info={}
        )
        
        # Converte para dict
        version_dict = version.to_dict()
        assert version_dict["status"] == "active"
        assert version_dict["metadata"]["author"] == "test"
        
        # Converte de volta
        restored_version = DocumentVersion.from_dict(version_dict)
        assert restored_version.version_id == version.version_id
        assert restored_version.status == VersionStatus.ACTIVE
        assert restored_version.metadata["author"] == "test"


class TestProcessingResult:
    """Testes para a classe ProcessingResult."""
    
    def test_to_dict(self):
        """Testa conversão para dicionário."""
        result = ProcessingResult(
            version_id="test_version",
            chunks_count=5,
            processing_time=2.5,
            success=True,
            error_message=None,
            chunks_metadata=[{"chunk_1": "data"}]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["version_id"] == "test_version"
        assert result_dict["chunks_count"] == 5
        assert result_dict["processing_time"] == 2.5
        assert result_dict["success"] is True
        assert result_dict["chunks_metadata"] == [{"chunk_1": "data"}]


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 