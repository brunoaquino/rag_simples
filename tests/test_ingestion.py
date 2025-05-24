"""
Testes para o sistema de ingestão de documentos.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.ingestion import DocumentParser, ChunkingSystem, MetadataExtractor
from src.ingestion.chunking_system import ChunkConfig


class TestDocumentParser:
    """Testes para o parser de documentos."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.parser = DocumentParser()
    
    def test_text_parser(self):
        """Testa o parser de texto simples."""
        content = "Este é um texto de teste.\nCom múltiplas linhas."
        result = self.parser.parse_document(content.encode('utf-8'), 'test.txt')
        
        assert result['text'] == content
        assert result['metadata']['filename'] == 'test.txt'
        assert result['metadata']['char_count'] == len(content)
        assert result['pages'] == 1
    
    def test_markdown_parser(self):
        """Testa o parser de Markdown."""
        content = "# Título\n\nEste é um **texto** em markdown."
        result = self.parser.parse_document(content.encode('utf-8'), 'test.md')
        
        assert result['text'] == content
        assert result['metadata']['format'] == 'markdown'
        assert result['pages'] == 1
    
    def test_unsupported_format(self):
        """Testa erro para formato não suportado."""
        with pytest.raises(ValueError, match="Formato não suportado"):
            self.parser.parse_document(b"content", "test.xyz")
    
    def test_get_supported_formats(self):
        """Testa listagem de formatos suportados."""
        formats = self.parser.get_supported_formats()
        expected = ['.txt', '.md', '.pdf', '.docx']
        
        for fmt in expected:
            assert fmt in formats


class TestChunkingSystem:
    """Testes para o sistema de chunking."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.config = ChunkConfig(
            chunk_size=100,
            chunk_overlap=20,
            strategy='fixed_size'
        )
        self.chunker = ChunkingSystem(self.config)
    
    def test_fixed_size_chunking(self):
        """Testa chunking de tamanho fixo."""
        text = "Este é um texto longo que será dividido em chunks menores. " * 10
        doc_metadata = {'filename': 'test.txt'}
        
        chunks = self.chunker.chunk_document(text, doc_metadata)
        
        assert len(chunks) > 1
        assert all(len(chunk.text) <= self.config.chunk_size + 50 for chunk in chunks)  # Margem para quebras
        assert chunks[0].metadata['strategy'] == 'fixed_size'
    
    def test_paragraph_chunking(self):
        """Testa chunking por parágrafos."""
        config = ChunkConfig(strategy='by_paragraph', chunk_size=200, min_chunk_size=10)
        chunker = ChunkingSystem(config)
        
        text = "Primeiro parágrafo.\n\nSegundo parágrafo muito longo que pode ser dividido.\n\nTerceiro parágrafo."
        doc_metadata = {'filename': 'test.txt'}
        
        chunks = chunker.chunk_document(text, doc_metadata)
        
        assert len(chunks) >= 1
        assert chunks[0].metadata['strategy'] == 'by_paragraph'
    
    def test_sentence_chunking(self):
        """Testa chunking por frases."""
        config = ChunkConfig(strategy='by_sentence', chunk_size=100, min_chunk_size=10)
        chunker = ChunkingSystem(config)
        
        text = "Primeira frase. Segunda frase mais longa. Terceira frase."
        doc_metadata = {'filename': 'test.txt'}
        
        chunks = chunker.chunk_document(text, doc_metadata)
        
        assert len(chunks) >= 1
        assert chunks[0].metadata['strategy'] == 'by_sentence'
    
    def test_empty_text(self):
        """Testa comportamento com texto vazio."""
        chunks = self.chunker.chunk_document("", {'filename': 'empty.txt'})
        assert len(chunks) == 0
    
    def test_chunk_stats(self):
        """Testa estatísticas dos chunks."""
        text = "Texto de teste para estatísticas."
        chunks = self.chunker.chunk_document(text, {'filename': 'test.txt'})
        
        stats = self.chunker.get_chunk_stats(chunks)
        
        assert 'total_chunks' in stats
        assert 'avg_chunk_size' in stats
        assert stats['total_chunks'] == len(chunks)


class TestMetadataExtractor:
    """Testes para o extrator de metadados."""
    
    def setup_method(self):
        """Setup para cada teste."""
        self.extractor = MetadataExtractor()
    
    def test_basic_metadata_extraction(self):
        """Testa extração básica de metadados."""
        text = "Este é um documento de teste com email@exemplo.com e telefone (11) 99999-9999."
        doc_metadata = {'filename': 'test.txt', 'file_size': len(text)}
        
        metadata = self.extractor.extract_metadata(text, doc_metadata)
        
        assert metadata['filename'] == 'test.txt'
        assert metadata['word_count'] > 0
        assert metadata['char_count'] == len(text)
        assert 'content_hash' in metadata
        assert 'extraction_timestamp' in metadata
    
    def test_entity_extraction(self):
        """Testa extração de entidades."""
        text = "Contato: joao@empresa.com, telefone (11) 1234-5678, site https://exemplo.com"
        doc_metadata = {'filename': 'test.txt'}
        
        metadata = self.extractor.extract_metadata(text, doc_metadata)
        
        assert len(metadata['emails']) > 0
        assert len(metadata['phones']) > 0
        assert len(metadata['urls']) > 0
    
    def test_keyword_extraction(self):
        """Testa extração de keywords."""
        text = "desenvolvimento sistema tecnologia código programação desenvolvimento sistema"
        doc_metadata = {'filename': 'test.txt'}
        
        metadata = self.extractor.extract_metadata(text, doc_metadata)
        
        assert 'extracted_keywords' in metadata
        assert len(metadata['extracted_keywords']) > 0
    
    def test_document_classification(self):
        """Testa classificação automática de documentos."""
        text = "Este documento contém políticas e procedimentos da empresa sobre desenvolvimento de sistemas."
        doc_metadata = {'filename': 'test.txt'}
        
        metadata = self.extractor.extract_metadata(text, doc_metadata)
        
        # Deve classificar como técnico ou política
        assert metadata['auto_category'] in ['técnico', 'política', None]
    
    def test_user_metadata_integration(self):
        """Testa integração com metadados do usuário."""
        text = "Documento de teste."
        doc_metadata = {'filename': 'test.txt'}
        user_metadata = {
            'category': 'Manual',
            'department': 'TI',
            'tags': ['teste', 'documentação']
        }
        
        metadata = self.extractor.extract_metadata(text, doc_metadata, user_metadata)
        
        assert metadata['user_category'] == 'Manual'
        assert metadata['department'] == 'TI'
        assert 'teste' in metadata['all_tags']
    
    def test_content_hash_consistency(self):
        """Testa consistência do hash de conteúdo."""
        text = "Mesmo conteúdo"
        doc_metadata = {'filename': 'test.txt'}
        
        hash1 = self.extractor._generate_content_hash(text)
        hash2 = self.extractor._generate_content_hash(text)
        
        assert hash1 == hash2
        
        # Texto diferente deve gerar hash diferente
        hash3 = self.extractor._generate_content_hash("Conteúdo diferente")
        assert hash1 != hash3


class TestIntegration:
    """Testes de integração entre os componentes."""
    
    def test_full_pipeline(self):
        """Testa pipeline completo de ingestão."""
        # Cria um documento de teste
        text = """
        # Manual de Procedimentos
        
        Este é um manual de procedimentos da empresa.
        
        ## Seção 1
        Primeira seção com informações importantes.
        
        ## Seção 2  
        Segunda seção com mais detalhes.
        
        Contato: suporte@empresa.com
        """
        
        # Parse do documento
        parser = DocumentParser()
        parsed = parser.parse_document(text.encode('utf-8'), 'manual.md')
        
        # Chunking
        config = ChunkConfig(chunk_size=200, strategy='by_paragraph')
        chunker = ChunkingSystem(config)
        chunks = chunker.chunk_document(parsed['text'], parsed['metadata'])
        
        # Extração de metadados
        extractor = MetadataExtractor()
        user_metadata = {'category': 'Manual', 'department': 'TI'}
        metadata = extractor.extract_metadata(
            parsed['text'], 
            parsed['metadata'], 
            user_metadata
        )
        
        # Verificações
        assert len(chunks) > 0
        assert metadata['user_category'] == 'Manual'
        assert metadata['department'] == 'TI'
        assert len(metadata['emails']) > 0  # Deve encontrar o email
        assert metadata['has_headers'] is True  # Deve detectar headers markdown
        
        # Enriquece metadados dos chunks
        for chunk in chunks:
            enriched = extractor.enrich_chunk_metadata(
                chunk.text, 
                chunk.metadata, 
                metadata
            )
            assert 'relevance_score' in enriched
            assert 'document_metadata' in enriched


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 