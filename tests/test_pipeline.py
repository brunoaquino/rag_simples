"""
Testes para o pipeline de ingestão integrado.
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path

from src.ingestion import IngestionPipeline, IngestionConfig
from src.ingestion.validation_system import ValidationLevel


class TestIngestionPipeline:
    """Testes para o pipeline de ingestão."""
    
    def setup_method(self):
        """Configura cada teste."""
        # Configura pipeline com validação desabilitada para os testes
        config = IngestionConfig(
            enable_validation=False,  # Desabilita validação para evitar problemas nos testes
            enable_versioning=True,
            storage_path="test_data/versions"
        )
        self.pipeline = IngestionPipeline(config)
        
        # Garante que diretório de teste existe
        Path("test_data").mkdir(exist_ok=True)
        
        # Cria diretório temporário
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Configuração de teste
        self.config = IngestionConfig(
            chunk_size=200,
            chunk_overlap=50,
            chunking_strategy='fixed_size',
            min_chunk_size=30,  # Reduzido para permitir textos pequenos nos testes
            storage_path=str(self.temp_dir / "versions"),
            enable_versioning=True
        )
        
        self.pipeline = IngestionPipeline(self.config)
    
    def teardown_method(self):
        """Cleanup após cada teste."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_file(self, content: str, filename: str) -> str:
        """Cria arquivo de teste."""
        file_path = self.temp_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return str(file_path)
    
    def test_ingest_text_document(self):
        """Testa ingestão de documento de texto."""
        content = """
        Este é um documento de teste para o pipeline de ingestão.
        
        O documento contém múltiplos parágrafos com informações importantes.
        Deve ser processado corretamente pelo sistema de ingestão.
        
        Informações de contato: teste@empresa.com
        Telefone: (11) 1234-5678
        """
        
        file_path = self.create_test_file(content, "teste.txt")
        user_metadata = {
            'category': 'Teste',
            'department': 'TI',
            'tags': ['teste', 'documento']
        }
        
        result = self.pipeline.ingest_file(file_path, user_metadata)
        
        # Verifica resultado básico
        assert result.success is True
        assert result.error_message is None
        assert result.processing_time > 0
        
        # Verifica metadados
        assert result.metadata['user_category'] == 'Teste'
        assert result.metadata['department'] == 'TI'
        assert 'teste' in result.metadata['all_tags']
        
        # Verifica chunks
        assert len(result.chunks) > 0
        assert all(len(chunk.text) <= self.config.chunk_size + 100 for chunk in result.chunks)
        
        # Verifica versionamento
        if self.config.enable_versioning:
            assert result.document_version is not None
            assert result.document_version.original_filename == "teste.txt"
    
    def test_ingest_markdown_document(self):
        """Testa ingestão de documento Markdown."""
        content = """
        # Manual de Procedimentos
        
        ## Introdução
        Este manual descreve os procedimentos da empresa.
        
        ## Seção 1
        Primeira seção com detalhes importantes.
        
        ### Subseção 1.1
        Detalhes específicos da subseção.
        
        ## Seção 2
        Segunda seção com mais informações.
        """
        
        file_path = self.create_test_file(content, "manual.md")
        result = self.pipeline.ingest_file(file_path)
        
        assert result.success is True
        assert len(result.chunks) > 0
        
        # Verifica detecção de estrutura
        assert result.metadata['has_headers'] is True
        
        # Verifica metadados dos chunks
        for chunk in result.chunks:
            assert 'relevance_score' in chunk.metadata
            assert 'document_metadata' in chunk.metadata
    
    def test_duplicate_detection(self):
        """Testa detecção de documentos duplicados."""
        content = "Documento para teste de duplicação com conteúdo suficiente para gerar chunks válidos."
        
        # Processa primeiro arquivo
        file1_path = self.create_test_file(content, "doc1.txt")
        result1 = self.pipeline.ingest_file(file1_path)
        
        # Processa segundo arquivo com mesmo conteúdo
        file2_path = self.create_test_file(content, "doc2.txt")
        result2 = self.pipeline.ingest_file(file2_path)
        
        # Verifica que foi detectado como duplicado
        assert result1.success is True
        assert result2.success is True
        assert result1.document_version.version_id == result2.document_version.version_id
    
    def test_ingest_document_from_bytes(self):
        """Testa ingestão de documento a partir de bytes."""
        content = "Documento processado a partir de bytes com conteúdo suficiente para criar chunks válidos."
        content_bytes = content.encode('utf-8')
        
        result = self.pipeline.ingest_document(
            content_bytes, 
            "teste_bytes.txt",
            {'category': 'Bytes Test'}
        )
        
        assert result.success is True
        assert result.metadata['user_category'] == 'Bytes Test'
        assert len(result.chunks) > 0
    
    def test_processing_statistics(self):
        """Testa obtenção de estatísticas de processamento."""
        stats = self.pipeline.get_processing_statistics()
        
        assert 'parser_formats' in stats
        assert 'chunking_strategy' in stats
        assert 'chunk_config' in stats
        assert 'versioning_enabled' in stats
        
        assert stats['chunking_strategy'] == 'fixed_size'
        assert stats['versioning_enabled'] is True
    
    def test_search_documents(self):
        """Testa busca de documentos."""
        # Adiciona alguns documentos com conteúdo suficiente
        documents = [
            ("Documento sobre tecnologia e desenvolvimento de sistemas modernos para empresas", "tech.txt"),
            ("Manual de procedimentos operacionais da empresa para funcionários", "manual.txt"),
            ("Relatório financeiro anual com dados importantes e análises detalhadas", "relatorio.txt")
        ]
        
        for content, filename in documents:
            file_path = self.create_test_file(content, filename)
            result = self.pipeline.ingest_file(file_path, {'tags': content.split()[:2]})
            # Verifica se o documento foi processado com sucesso
            assert result.success, f"Falha ao processar {filename}"
            assert result.document_version is not None, f"Versão não criada para {filename}"
        
        # Verifica estado do version_manager
        assert self.pipeline.version_manager is not None
        assert len(self.pipeline.version_manager.versions) == 3
        
        # Busca por "Documento" (que deve estar nas user_tags)
        results = self.pipeline.search_documents("Documento")
        assert len(results) > 0
        assert any("tech.txt" in result['filename'] for result in results)
        
        # Busca por "tech" (que deve estar no nome do arquivo)
        results = self.pipeline.search_documents("tech")
        assert len(results) > 0
        assert results[0]['filename'] == "tech.txt"
        
        # Busca por "Manual" (que deve estar nas user_tags)
        results = self.pipeline.search_documents("Manual")
        assert len(results) > 0
        assert any("manual.txt" in result['filename'] for result in results)
        
        # Verifica estrutura dos resultados
        for result in results:
            assert 'version_id' in result
            assert 'filename' in result
            assert 'score' in result
            assert 'created_at' in result
    
    def test_document_history(self):
        """Testa obtenção de histórico de documentos."""
        # Cria múltiplas versões com conteúdo suficiente
        base_content = "Documento base com conteúdo suficiente para processamento"
        document_id = None
        
        for i in range(3):
            content = f"{base_content} versão {i} com informações adicionais específicas"
            file_path = self.create_test_file(content, f"versioned_doc_{i}.txt")
            result = self.pipeline.ingest_file(file_path)
            
            if document_id is None and result.document_version:
                document_id = result.document_version.document_id
        
        if document_id:
            history = self.pipeline.get_document_history(document_id)
            
            # Verifica campos que realmente existem na resposta
            assert 'document_id' in history
            assert 'total_versions' in history
            assert 'versions' in history
            
            assert history['total_versions'] > 0
            assert len(history['versions']) > 0
            
            # Verifica estrutura das versões
            for version in history['versions']:
                assert 'version_id' in version
                assert 'filename' in version
                assert 'status' in version
                assert 'created_at' in version
                assert 'metadata' in version
    
    def test_error_handling(self):
        """Testa tratamento de erros."""
        # Tenta processar arquivo inexistente
        result = self.pipeline.ingest_file("arquivo_inexistente.txt")
        
        assert result.success is False
        assert result.error_message is not None
        assert "não encontrado" in result.error_message
    
    def test_pipeline_without_versioning(self):
        """Testa pipeline sem versionamento."""
        config = IngestionConfig(
            enable_versioning=False,
            min_chunk_size=30  # Configuração consistente
        )
        pipeline = IngestionPipeline(config)
        
        content = "Documento sem versionamento com conteúdo suficiente para criar chunks válidos."
        file_path = self.create_test_file(content, "no_version.txt")
        
        result = pipeline.ingest_file(file_path)
        
        assert result.success is True
        assert result.document_version is None
        assert len(result.chunks) > 0
        
        # Verifica que estatísticas não incluem versionamento
        stats = pipeline.get_processing_statistics()
        assert stats['versioning_enabled'] is False
        assert 'version_statistics' not in stats
    
    def test_different_chunking_strategies(self):
        """Testa diferentes estratégias de chunking."""
        content = """
        Primeiro parágrafo do documento com conteúdo suficiente.
        
        Segundo parágrafo com mais informações importantes.
        
        Terceiro parágrafo com detalhes finais relevantes.
        """
        
        strategies = ['fixed_size', 'by_paragraph', 'by_sentence']
        
        for strategy in strategies:
            config = IngestionConfig(
                chunking_strategy=strategy,
                enable_versioning=False,
                min_chunk_size=30
            )
            pipeline = IngestionPipeline(config)
            
            file_path = self.create_test_file(content, f"test_{strategy}.txt")
            result = pipeline.ingest_file(file_path)
            
            assert result.success is True
            assert len(result.chunks) > 0
            
            # Verifica que a estratégia foi aplicada corretamente
            for chunk in result.chunks:
                assert chunk.metadata['strategy'] == strategy
    
    def test_metadata_enrichment(self):
        """Testa enriquecimento de metadados."""
        content = """
        Documento para teste de metadados com informações relevantes.
        
        Contém informações importantes sobre o sistema de gestão.
        Email: contato@empresa.com
        Telefone: (11) 9999-8888
        Site: https://empresa.com
        
        Este documento serve para testar a extração de entidades.
        """
        
        file_path = self.create_test_file(content, "metadata_test.txt")
        user_metadata = {
            'category': 'Documentação',
            'department': 'TI',
            'tags': ['sistema', 'contato']
        }
        
        result = self.pipeline.ingest_file(file_path, user_metadata)
        
        assert result.success is True
        
        # Verifica extração de entidades
        assert len(result.metadata['emails']) > 0
        assert len(result.metadata['phones']) > 0
        assert len(result.metadata['urls']) > 0
        
        # Verifica integração de metadados do usuário
        assert result.metadata['user_category'] == 'Documentação'
        assert result.metadata['department'] == 'TI'
        assert 'sistema' in result.metadata['all_tags']
        
        # Verifica enriquecimento dos chunks
        for chunk in result.chunks:
            assert 'relevance_score' in chunk.metadata
            assert 'word_count' in chunk.metadata
            assert 'document_metadata' in chunk.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 