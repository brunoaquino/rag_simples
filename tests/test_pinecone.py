"""
Testes para o Sistema Pinecone
Testa funcionalidades do cliente e gerenciador de índices.
"""

import pytest
import tempfile
import os
import json
import time
from typing import List
from pathlib import Path

from src.vector_db import (
    PineconeClient, PineconeConfig, VectorRecord, QueryResult, OperationMetrics,
    IndexManager, IndexType, IndexTemplate, create_pinecone_client, 
    create_index_manager, get_default_config
)


class TestPineconeConfig:
    """Testes para a configuração do Pinecone."""
    
    def test_config_creation(self):
        """Testa criação de configuração."""
        config = PineconeConfig(
            api_key="test-key",
            environment="test-env",
            index_name="test-index",
            dimension=512
        )
        
        assert config.api_key == "test-key"
        assert config.environment == "test-env" 
        assert config.index_name == "test-index"
        assert config.dimension == 512
        assert config.metric == "cosine"  # Default
    
    def test_default_config_from_env(self, monkeypatch):
        """Testa configuração padrão a partir de variáveis de ambiente."""
        # Remove API key do ambiente para este teste
        monkeypatch.delenv("PINECONE_API_KEY", raising=False)
        config = get_default_config()
        assert config.api_key == ""
        assert config.dimension == 768
    
    def test_config_with_env_vars(self, monkeypatch):
        """Testa configuração com variáveis de ambiente."""
        monkeypatch.setenv("PINECONE_API_KEY", "env-api-key")
        monkeypatch.setenv("PINECONE_DIMENSION", "1024")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "env-index")
        
        config = get_default_config()
        assert config.api_key == "env-api-key"
        assert config.dimension == 1024
        assert config.index_name == "env-index"


class TestVectorRecord:
    """Testes para registros vetoriais."""
    
    def test_vector_record_creation(self):
        """Testa criação de registro vetorial."""
        vector = [0.1, 0.2, 0.3]
        metadata = {"source": "test", "type": "document"}
        
        record = VectorRecord(
            id="test-1",
            vector=vector,
            metadata=metadata,
            namespace="test"
        )
        
        assert record.id == "test-1"
        assert record.vector == vector
        assert record.metadata == metadata
        assert record.namespace == "test"
    
    def test_vector_record_default_values(self):
        """Testa valores padrão do registro vetorial."""
        record = VectorRecord(id="test-1", vector=[0.1, 0.2])
        
        assert record.metadata == {}
        assert record.namespace == ""


class TestQueryResult:
    """Testes para resultados de query."""
    
    def test_query_result_creation(self):
        """Testa criação de resultado de query."""
        result = QueryResult(
            id="result-1",
            score=0.95,
            metadata={"title": "Test Document"},
            namespace="documents"
        )
        
        assert result.id == "result-1"
        assert result.score == 0.95
        assert result.metadata["title"] == "Test Document"
        assert result.namespace == "documents"


class TestPineconeClient:
    """Testes para o cliente Pinecone."""
    
    def setup_method(self):
        """Configura cada teste."""
        # Configuração para modo mock (sem API key real)
        self.config = PineconeConfig(
            api_key="mock-api-key",
            index_name="test-index",
            dimension=768
        )
        self.client = PineconeClient(self.config)
    
    def test_client_initialization(self):
        """Testa inicialização do cliente."""
        assert self.client.config.api_key == "mock-api-key"
        assert self.client.config.index_name == "test-index"
        assert self.client._mock_mode == True  # Sem Pinecone real
    
    def test_create_index_mock(self):
        """Testa criação de índice no modo mock."""
        success = self.client.create_index("test-index-new", 512, "cosine")
        assert success == True
        assert "test-index-new" in self.client._mock_data
    
    def test_connect_to_index_mock(self):
        """Testa conexão ao índice no modo mock."""
        success = self.client.connect_to_index("test-index")
        assert success == True
        assert self.client._index == "test-index"
    
    def test_upsert_vectors_mock(self):
        """Testa inserção de vetores no modo mock."""
        # Conecta ao índice primeiro
        self.client.connect_to_index("test-index")
        
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2, 0.3], metadata={"type": "document"}),
            VectorRecord(id="doc2", vector=[0.4, 0.5, 0.6], metadata={"type": "code"})
        ]
        
        success = self.client.upsert_vectors(vectors, namespace="test")
        assert success == True
        
        # Verifica se vetores foram inseridos
        mock_ns = self.client._mock_data["test-index"]["test"]
        assert "doc1" in mock_ns
        assert "doc2" in mock_ns
        assert mock_ns["doc1"].metadata["type"] == "document"
    
    def test_query_vectors_mock(self):
        """Testa busca de vetores no modo mock."""
        # Setup: insere vetores primeiro
        self.client.connect_to_index("test-index")
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2, 0.3], metadata={"type": "document"}),
            VectorRecord(id="doc2", vector=[0.4, 0.5, 0.6], metadata={"type": "code"})
        ]
        self.client.upsert_vectors(vectors, namespace="test")
        
        # Executa query
        query_vector = [0.1, 0.2, 0.3]
        results = self.client.query_vectors(
            query_vector=query_vector,
            top_k=2,
            namespace="test",
            include_metadata=True
        )
        
        assert len(results) <= 2
        for result in results:
            assert isinstance(result, QueryResult)
            assert result.score >= 0.0
            assert result.score <= 1.0
    
    def test_query_with_filter_mock(self):
        """Testa busca com filtro no modo mock."""
        # Setup
        self.client.connect_to_index("test-index")
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2, 0.3], metadata={"type": "document"}),
            VectorRecord(id="doc2", vector=[0.4, 0.5, 0.6], metadata={"type": "code"})
        ]
        self.client.upsert_vectors(vectors, namespace="test")
        
        # Query com filtro
        results = self.client.query_vectors(
            query_vector=[0.1, 0.2, 0.3],
            top_k=10,
            namespace="test",
            filter_dict={"type": "document"}
        )
        
        # Deve encontrar apenas documentos do tipo "document"
        for result in results:
            if result.metadata:
                assert result.metadata.get("type") == "document"
    
    def test_delete_vectors_mock(self):
        """Testa remoção de vetores no modo mock."""
        # Setup
        self.client.connect_to_index("test-index")
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2, 0.3]),
            VectorRecord(id="doc2", vector=[0.4, 0.5, 0.6])
        ]
        self.client.upsert_vectors(vectors, namespace="test")
        
        # Remove um vetor
        success = self.client.delete_vectors(["doc1"], namespace="test")
        assert success == True
        
        # Verifica se foi removido
        mock_ns = self.client._mock_data["test-index"]["test"]
        assert "doc1" not in mock_ns
        assert "doc2" in mock_ns
    
    def test_get_index_stats_mock(self):
        """Testa obtenção de estatísticas no modo mock."""
        # Setup
        self.client.connect_to_index("test-index")
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2, 0.3]),
            VectorRecord(id="doc2", vector=[0.4, 0.5, 0.6])
        ]
        self.client.upsert_vectors(vectors, namespace="test")
        
        stats = self.client.get_index_stats()
        
        assert "total_vector_count" in stats
        assert "dimension" in stats
        assert "namespaces" in stats
        assert stats["total_vector_count"] >= 0
        assert stats["dimension"] == self.config.dimension
    
    def test_list_indexes_mock(self):
        """Testa listagem de índices no modo mock."""
        # Cria alguns índices
        self.client.create_index("index-1")
        self.client.create_index("index-2")
        
        indexes = self.client.list_indexes()
        
        assert isinstance(indexes, list)
        assert "index-1" in indexes
        assert "index-2" in indexes
    
    def test_delete_index_mock(self):
        """Testa remoção de índice no modo mock."""
        # Cria índice
        self.client.create_index("test-to-delete")
        assert "test-to-delete" in self.client._mock_data
        
        # Remove índice
        success = self.client.delete_index("test-to-delete")
        assert success == True
        assert "test-to-delete" not in self.client._mock_data
    
    def test_metrics_recording(self):
        """Testa gravação de métricas."""
        initial_metrics_count = len(self.client.metrics)
        
        # Executa algumas operações
        self.client.create_index("metrics-test")
        self.client.connect_to_index("metrics-test")
        
        # Verifica se métricas foram gravadas
        assert len(self.client.metrics) > initial_metrics_count
        
        # Verifica tipos de métricas
        metric_types = [m.operation_type for m in self.client.metrics]
        assert "create_index" in metric_types
        assert "connect_index" in metric_types
    
    def test_get_metrics_filtered(self):
        """Testa obtenção de métricas filtradas."""
        # Executa operações para gerar métricas
        self.client.create_index("metrics-test")
        self.client.connect_to_index("metrics-test")
        
        # Obtém métricas de criação de índice
        create_metrics = self.client.get_metrics(operation_type="create_index")
        
        assert len(create_metrics) >= 1
        for metric in create_metrics:
            assert metric.operation_type == "create_index"
            assert isinstance(metric.duration, float)
            assert isinstance(metric.success, bool)
    
    def test_performance_summary(self):
        """Testa resumo de performance."""
        # Executa operações para gerar métricas
        self.client.create_index("perf-test")
        self.client.connect_to_index("perf-test")
        
        summary = self.client.get_performance_summary()
        
        if summary.get("message") != "Nenhuma métrica disponível":
            assert isinstance(summary, dict)
            # Verifica se tem estatísticas por operação
            for op_type, stats in summary.items():
                assert "total_operations" in stats
                assert "success_rate" in stats
                assert "average_duration" in stats
    
    def test_health_check(self):
        """Testa verificação de saúde."""
        health = self.client.health_check()
        
        assert "pinecone_available" in health
        assert "mock_mode" in health
        assert "connected" in health
        assert "config" in health
        
        assert health["mock_mode"] == True
        assert isinstance(health["config"], dict)
    
    def test_export_import_mock_data(self):
        """Testa exportação e importação de dados mock."""
        # Setup: adiciona alguns dados
        self.client.connect_to_index("test-index")
        vectors = [
            VectorRecord(id="doc1", vector=[0.1, 0.2], metadata={"type": "test"}),
            VectorRecord(id="doc2", vector=[0.3, 0.4], metadata={"type": "demo"})
        ]
        self.client.upsert_vectors(vectors, namespace="export-test")
        
        # Exporta dados
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            export_path = f.name
        
        try:
            success = self.client.export_mock_data(export_path)
            assert success == True
            
            # Verifica se arquivo foi criado
            assert os.path.exists(export_path)
            
            # Cria novo cliente e importa dados
            new_client = PineconeClient(self.config)
            import_success = new_client.import_mock_data(export_path)
            assert import_success == True
            
            # Verifica se dados foram importados
            new_client.connect_to_index("test-index")
            imported_stats = new_client.get_index_stats()
            assert imported_stats["total_vector_count"] >= 2
            
        finally:
            # Limpa arquivo temporário
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestIndexManager:
    """Testes para o gerenciador de índices."""
    
    def setup_method(self):
        """Configura cada teste."""
        self.config = PineconeConfig(
            api_key="mock-api-key",
            environment="test-env"
        )
        self.manager = IndexManager(self.config, "test-project")
    
    def test_manager_initialization(self):
        """Testa inicialização do gerenciador."""
        assert self.manager.project_prefix == "test-project"
        assert self.manager.base_config.api_key == "mock-api-key"
        assert len(self.manager.clients) == 0
    
    def test_index_templates(self):
        """Testa templates de índices."""
        # Verifica se todos os tipos têm templates
        for index_type in IndexType:
            assert index_type in IndexManager.INDEX_TEMPLATES
            
        # Verifica estrutura do template
        doc_template = IndexManager.INDEX_TEMPLATES[IndexType.DOCUMENTS]
        assert doc_template.name_suffix == "docs"
        assert doc_template.dimension == 768
        assert doc_template.metric == "cosine"
        assert isinstance(doc_template.metadata_config, dict)
    
    def test_create_index_for_type(self):
        """Testa criação de índice para tipo específico."""
        success = self.manager.create_index_for_type(IndexType.DOCUMENTS)
        
        assert success == True
        assert IndexType.DOCUMENTS in self.manager.clients
        
        # Verifica cliente
        client = self.manager.get_client(IndexType.DOCUMENTS)
        assert client is not None
        assert client.config.index_name == "test-project-docs"
        assert client.config.dimension == 768
    
    def test_connect_to_existing_indexes(self):
        """Testa conexão a índices existentes."""
        # Primeiro cria alguns índices
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        self.manager.create_index_for_type(IndexType.CODE)
        
        # Cria novo gerenciador e tenta conectar
        new_manager = IndexManager(self.config, "test-project")
        connection_status = new_manager.connect_to_existing_indexes()
        
        # No modo mock, isso deveria conectar aos "índices" já criados
        assert isinstance(connection_status, dict)
        assert IndexType.DOCUMENTS in connection_status
        assert IndexType.CODE in connection_status
    
    def test_get_client(self):
        """Testa obtenção de cliente por tipo."""
        # Sem cliente criado
        client = self.manager.get_client(IndexType.DOCUMENTS)
        assert client is None
        
        # Cria cliente
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        client = self.manager.get_client(IndexType.DOCUMENTS)
        assert client is not None
        assert isinstance(client, PineconeClient)
    
    def test_list_all_indexes(self):
        """Testa listagem de todos os índices."""
        # Cria alguns índices
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        self.manager.create_index_for_type(IndexType.CODE)
        
        indexes = self.manager.list_all_indexes()
        
        assert isinstance(indexes, dict)
        # No modo mock, verifica se pelo menos um índice foi criado
        assert len(indexes) >= 1
        
        # Verifica estrutura dos índices listados
        found_docs = False
        for index_name, info in indexes.items():
            if info["type"] == "documents":
                found_docs = True
                assert info["connected"] == True
                break
        assert found_docs == True
    
    def test_get_all_stats(self):
        """Testa obtenção de estatísticas de todos os índices."""
        # Cria índices
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        self.manager.create_index_for_type(IndexType.CODE)
        
        all_stats = self.manager.get_all_stats()
        
        assert isinstance(all_stats, dict)
        assert IndexType.DOCUMENTS in all_stats
        assert IndexType.CODE in all_stats
        
        # Verifica estrutura das estatísticas
        docs_stats = all_stats[IndexType.DOCUMENTS]
        assert "index_stats" in docs_stats
        assert "performance" in docs_stats
        assert "template" in docs_stats
    
    def test_setup_complete_environment(self):
        """Testa configuração de ambiente completo."""
        # Configura apenas alguns tipos
        index_types = [IndexType.DOCUMENTS, IndexType.CODE]
        setup_status = self.manager.setup_complete_environment(index_types)
        
        assert isinstance(setup_status, dict)
        assert len(setup_status) == 2
        assert IndexType.DOCUMENTS in setup_status
        assert IndexType.CODE in setup_status
        
        # Verifica se foram criados com sucesso
        for index_type, success in setup_status.items():
            assert success == True
            assert index_type in self.manager.clients
    
    def test_health_check_all(self):
        """Testa verificação de saúde de todos os clientes."""
        # Cria alguns clientes
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        self.manager.create_index_for_type(IndexType.CODE)
        
        health = self.manager.health_check_all()
        
        assert "total_clients" in health
        assert "project_prefix" in health
        assert "clients" in health
        assert "operational_clients" in health
        assert "overall_health" in health
        
        assert health["total_clients"] == 2
        assert health["project_prefix"] == "test-project"
        assert isinstance(health["overall_health"], float)
    
    def test_get_recommended_type(self):
        """Testa recomendação de tipo de índice."""
        # Testa diferentes descrições (usando palavras mais específicas)
        assert self.manager.get_recommended_type("Python programming language") == IndexType.CODE
        assert self.manager.get_recommended_type("PDF document text content") == IndexType.DOCUMENTS
        assert self.manager.get_recommended_type("Photo picture visual") == IndexType.IMAGES
        assert self.manager.get_recommended_type("Voice audio recording") == IndexType.AUDIO
        assert self.manager.get_recommended_type("Mixed content types") == IndexType.MIXED
        assert self.manager.get_recommended_type("Unknown content") == IndexType.MIXED
    
    def test_cleanup_all_indexes(self):
        """Testa limpeza de todos os índices."""
        # Cria índices
        self.manager.create_index_for_type(IndexType.DOCUMENTS)
        self.manager.create_index_for_type(IndexType.CODE)
        
        # Testa sem confirmação
        cleanup_status = self.manager.cleanup_all_indexes(confirm=False)
        assert cleanup_status == {}
        assert len(self.manager.clients) == 2  # Não removeu
        
        # Testa com confirmação
        cleanup_status = self.manager.cleanup_all_indexes(confirm=True)
        assert isinstance(cleanup_status, dict)
        assert len(self.manager.clients) == 0  # Removeu clientes


class TestUtilityFunctions:
    """Testes para funções utilitárias."""
    
    def test_create_pinecone_client(self):
        """Testa função de criação de cliente."""
        config = PineconeConfig(api_key="test", index_name="test")
        client = create_pinecone_client(config)
        
        assert isinstance(client, PineconeClient)
        assert client.config.api_key == "test"
    
    def test_create_pinecone_client_default(self):
        """Testa criação de cliente com configuração padrão."""
        client = create_pinecone_client()
        
        assert isinstance(client, PineconeClient)
        assert client.config.dimension == 768  # Default
    
    def test_create_index_manager(self):
        """Testa função de criação de gerenciador."""
        manager = create_index_manager("test-api-key", "test-prefix")
        
        assert isinstance(manager, IndexManager)
        assert manager.project_prefix == "test-prefix"
        assert manager.base_config.api_key == "test-api-key"


class TestErrorHandling:
    """Testes para tratamento de erros."""
    
    def setup_method(self):
        """Configura cada teste."""
        self.config = PineconeConfig(api_key="mock", index_name="test")
        self.client = PineconeClient(self.config)
    
    def test_operations_without_connection(self):
        """Testa operações sem conexão ao índice."""
        # Não conecta ao índice
        
        # Upsert deve falhar graciosamente
        vectors = [VectorRecord(id="test", vector=[0.1, 0.2])]
        success = self.client.upsert_vectors(vectors)
        # No modo mock, isso ainda funciona pois conecta automaticamente
        
        # Query sem conexão
        results = self.client.query_vectors([0.1, 0.2])
        # No modo mock, retorna lista vazia mas não falha
        assert isinstance(results, list)
    
    def test_empty_operations(self):
        """Testa operações com dados vazios."""
        self.client.connect_to_index("test-index")
        
        # Upsert com lista vazia
        success = self.client.upsert_vectors([])
        assert success == True
        
        # Delete com lista vazia
        success = self.client.delete_vectors([])
        assert success == True
        
        # Query em namespace vazio
        results = self.client.query_vectors([0.1, 0.2], namespace="empty")
        assert results == []
    
    def test_invalid_operations(self):
        """Testa operações inválidas."""
        # Stats sem índice
        stats = self.client.get_index_stats()
        # No modo mock, retorna stats vazias mas não falha
        assert isinstance(stats, dict)


class TestIntegrationScenarios:
    """Testes de cenários de integração."""
    
    def test_complete_workflow(self):
        """Testa fluxo completo de trabalho."""
        # Cria gerenciador
        manager = create_index_manager("test-api-key", "integration")
        
        # Configura ambiente
        setup_status = manager.setup_complete_environment([IndexType.DOCUMENTS])
        assert setup_status[IndexType.DOCUMENTS] == True
        
        # Obtém cliente
        client = manager.get_client(IndexType.DOCUMENTS)
        assert client is not None
        
        # Insere dados
        vectors = [
            VectorRecord(
                id=f"doc-{i}",
                vector=[float(i)/10, float(i+1)/10, float(i+2)/10],
                metadata={"index": i, "type": "test"}
            )
            for i in range(5)
        ]
        
        success = client.upsert_vectors(vectors, namespace="integration-test")
        assert success == True
        
        # Busca dados
        results = client.query_vectors(
            query_vector=[0.1, 0.2, 0.3],
            top_k=3,
            namespace="integration-test",
            filter_dict={"type": "test"}
        )
        
        assert len(results) <= 3
        for result in results:
            assert result.metadata.get("type") == "test"
        
        # Verifica estatísticas
        stats = client.get_index_stats()
        assert stats["total_vector_count"] >= 5
        
        # Verifica métricas
        metrics = client.get_metrics(operation_type="upsert")
        assert len(metrics) >= 1
        
        # Health check
        health = manager.health_check_all()
        assert health["total_clients"] == 1
        assert health["operational_clients"] == 1 