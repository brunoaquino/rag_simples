"""
Extrator de Metadados - Extração automática de metadados de documentos
Analisa documentos para extrair informações estruturadas e contextuais.
"""

import re
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

class MetadataExtractor:
    """Extrator de metadados de documentos."""
    
    def __init__(self):
        """Inicializa o extrator de metadados."""
        # Patterns para diferentes tipos de conteúdo
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'(?:\+\d{1,3}[-.\s]?)?\(?(?:\d{2})\)?[-.\s]?(?:\d{4,5})[-.\s]?(?:\d{4})')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.date_pattern = re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b')
        
        # Keywords para categorização automática
        self.category_keywords = {
            'política': ['política', 'policy', 'procedimento', 'norma', 'regulamento', 'diretrizes'],
            'financeiro': ['orçamento', 'financeiro', 'custo', 'receita', 'despesa', 'contabilidade'],
            'rh': ['recursos humanos', 'rh', 'funcionário', 'colaborador', 'benefícios', 'salário'],
            'técnico': ['desenvolvimento', 'sistema', 'api', 'código', 'tecnologia', 'infraestrutura'],
            'jurídico': ['contrato', 'legal', 'jurídico', 'compliance', 'regulamentação'],
            'operacional': ['processo', 'operação', 'workflow', 'procedimento', 'manual']
        }
        
        # Stop words para análise de keywords
        self.stop_words = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'da', 'do', 'das', 'dos',
            'em', 'na', 'no', 'nas', 'nos', 'por', 'para', 'com', 'sem', 'que', 'se', 'como',
            'mas', 'ou', 'e', 'é', 'são', 'foi', 'foram', 'será', 'serão', 'tem', 'têm',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'between', 'among', 'that', 'this', 'these', 'those'
        }
        
        logger.info("MetadataExtractor inicializado")
    
    def extract_metadata(self, text: str, doc_metadata: Dict[str, Any], 
                        user_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extrai metadados completos de um documento.
        
        Args:
            text: Texto do documento
            doc_metadata: Metadados básicos do documento (do parser)
            user_metadata: Metadados fornecidos pelo usuário
            
        Returns:
            Dict com metadados extraídos e enriquecidos
        """
        metadata = {
            # Metadados básicos
            'filename': doc_metadata.get('filename', 'unknown'),
            'file_size': doc_metadata.get('file_size', 0),
            'extraction_timestamp': datetime.now().isoformat(),
            
            # Hash do conteúdo para deduplicação
            'content_hash': self._generate_content_hash(text),
            
            # Estatísticas do texto
            **self._extract_text_stats(text),
            
            # Entidades extraídas
            **self._extract_entities(text),
            
            # Categorização automática
            'auto_category': self._classify_document(text),
            
            # Keywords extraídas
            'extracted_keywords': self._extract_keywords(text),
            
            # Estrutura do documento
            **self._analyze_document_structure(text),
            
            # Metadados do parser original
            'parser_metadata': doc_metadata
        }
        
        # Incorpora metadados fornecidos pelo usuário
        if user_metadata:
            metadata.update({
                'user_category': user_metadata.get('category'),
                'department': user_metadata.get('department'),
                'user_tags': user_metadata.get('tags', []),
                'custom_metadata': user_metadata
            })
        
        # Combina todas as tags
        all_tags = set()
        if metadata.get('user_tags'):
            all_tags.update(metadata['user_tags'])
        if metadata.get('extracted_keywords'):
            all_tags.update(metadata['extracted_keywords'][:5])  # Top 5 keywords
        
        metadata['all_tags'] = list(all_tags)
        
        logger.info(f"Metadados extraídos para {metadata['filename']}")
        return metadata
    
    def _generate_content_hash(self, text: str) -> str:
        """Gera hash SHA-256 do conteúdo para deduplicação."""
        normalized_text = re.sub(r'\s+', ' ', text.strip().lower())
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
    
    def _extract_text_stats(self, text: str) -> Dict[str, Any]:
        """Extrai estatísticas básicas do texto."""
        lines = text.splitlines()
        words = text.split()
        
        # Contagem de caracteres sem espaços
        char_count_no_spaces = len(re.sub(r'\s', '', text))
        
        # Contagem de parágrafos (assumindo parágrafos separados por linha vazia)
        paragraphs = re.split(r'\n\s*\n', text.strip())
        paragraph_count = len([p for p in paragraphs if p.strip()])
        
        return {
            'char_count': len(text),
            'char_count_no_spaces': char_count_no_spaces,
            'word_count': len(words),
            'line_count': len(lines),
            'paragraph_count': paragraph_count,
            'avg_words_per_paragraph': len(words) / max(paragraph_count, 1),
            'reading_time_minutes': max(1, len(words) // 200)  # ~200 WPM
        }
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extrai entidades como emails, telefones, URLs, datas."""
        entities = {
            'emails': list(set(self.email_pattern.findall(text))),
            'phones': list(set(self.phone_pattern.findall(text))),
            'urls': list(set(self.url_pattern.findall(text))),
            'dates': list(set(self.date_pattern.findall(text)))
        }
        
        # Conta total de entidades
        entities['total_entities'] = sum(len(v) for v in entities.values())
        
        return entities
    
    def _classify_document(self, text: str) -> Optional[str]:
        """Classifica automaticamente o documento baseado em keywords."""
        text_lower = text.lower()
        category_scores = {}
        
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                # Conta ocorrências da keyword (case-insensitive)
                count = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text_lower))
                score += count
            
            if score > 0:
                category_scores[category] = score
        
        # Retorna a categoria com maior score
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return None
    
    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extrai keywords mais frequentes do texto."""
        # Normaliza texto
        text_clean = re.sub(r'[^\w\s]', ' ', text.lower())
        words = text_clean.split()
        
        # Remove stop words e palavras muito curtas
        filtered_words = [
            word for word in words 
            if len(word) >= 3 and word not in self.stop_words
        ]
        
        # Conta frequência
        word_freq = {}
        for word in filtered_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Retorna palavras mais frequentes
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:max_keywords] if freq >= 2]
    
    def _analyze_document_structure(self, text: str) -> Dict[str, Any]:
        """Analisa a estrutura do documento."""
        structure = {
            'has_headers': False,
            'has_lists': False,
            'has_tables': False,
            'has_code_blocks': False,
            'language': 'pt'  # Padrão português, poderia usar langdetect
        }
        
        # Verifica headers (linhas que começam com #, ou são seguidas por ===, ---)
        header_patterns = [
            r'^#{1,6}\s+',  # Markdown headers
            r'^.+\n[=]{3,}',  # Underlined headers with =
            r'^.+\n[-]{3,}'   # Underlined headers with -
        ]
        
        for pattern in header_patterns:
            if re.search(pattern, text, re.MULTILINE):
                structure['has_headers'] = True
                break
        
        # Verifica listas
        list_patterns = [
            r'^\s*[-*+]\s+',  # Markdown lists
            r'^\s*\d+\.\s+',  # Numbered lists
            r'^\s*[a-z]\)\s+' # Lettered lists
        ]
        
        for pattern in list_patterns:
            if re.search(pattern, text, re.MULTILINE):
                structure['has_lists'] = True
                break
        
        # Verifica tabelas (markdown style ou pipe-separated)
        if re.search(r'\|.*\|.*\|', text):
            structure['has_tables'] = True
        
        # Verifica blocos de código
        code_patterns = [
            r'```[\s\S]*?```',  # Markdown code blocks
            r'`[^`]+`',         # Inline code
            r'^\s{4,}',         # Indented code blocks
        ]
        
        for pattern in code_patterns:
            if re.search(pattern, text, re.MULTILINE):
                structure['has_code_blocks'] = True
                break
        
        return structure
    
    def enrich_chunk_metadata(self, chunk_text: str, chunk_metadata: Dict[str, Any], 
                             doc_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece metadados de um chunk específico.
        
        Args:
            chunk_text: Texto do chunk
            chunk_metadata: Metadados básicos do chunk
            doc_metadata: Metadados do documento pai
            
        Returns:
            Metadados enriquecidos do chunk
        """
        enriched = chunk_metadata.copy()
        
        # Estatísticas do chunk
        enriched.update(self._extract_text_stats(chunk_text))
        
        # Entidades no chunk
        enriched.update(self._extract_entities(chunk_text))
        
        # Keywords específicas do chunk
        enriched['chunk_keywords'] = self._extract_keywords(chunk_text, max_keywords=5)
        
        # Estrutura do chunk
        enriched.update(self._analyze_document_structure(chunk_text))
        
        # Relaciona com metadados do documento
        enriched['document_metadata'] = {
            'filename': doc_metadata.get('filename'),
            'document_category': doc_metadata.get('auto_category'),
            'document_tags': doc_metadata.get('all_tags', [])
        }
        
        # Calcula relevância do chunk (baseado em keywords e entidades)
        enriched['relevance_score'] = self._calculate_chunk_relevance(
            chunk_text, doc_metadata
        )
        
        return enriched
    
    def _calculate_chunk_relevance(self, chunk_text: str, doc_metadata: Dict[str, Any]) -> float:
        """Calcula score de relevância do chunk baseado em keywords e entidades."""
        score = 0.0
        
        # Score baseado em keywords do documento
        doc_keywords = doc_metadata.get('extracted_keywords', [])
        chunk_text_lower = chunk_text.lower()
        
        for keyword in doc_keywords:
            if keyword.lower() in chunk_text_lower:
                score += 1.0
        
        # Score baseado em entidades
        entities = self._extract_entities(chunk_text)
        entity_count = entities.get('total_entities', 0)
        score += entity_count * 0.5
        
        # Score baseado em estrutura
        structure = self._analyze_document_structure(chunk_text)
        if structure.get('has_headers'):
            score += 2.0
        if structure.get('has_lists'):
            score += 1.0
        
        # Normaliza pelo tamanho do chunk
        chunk_size = len(chunk_text.split())
        normalized_score = score / max(chunk_size / 100, 1)  # Por 100 palavras
        
        return min(normalized_score, 10.0)  # Cap em 10.0
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Valida e limpa metadados extraídos."""
        validated = {}
        
        # Campos obrigatórios
        required_fields = ['filename', 'extraction_timestamp', 'content_hash']
        for field in required_fields:
            if field in metadata:
                validated[field] = metadata[field]
            else:
                logger.warning(f"Campo obrigatório ausente: {field}")
        
        # Campos numéricos
        numeric_fields = ['char_count', 'word_count', 'line_count', 'file_size']
        for field in numeric_fields:
            if field in metadata:
                try:
                    validated[field] = max(0, int(metadata[field]))
                except (ValueError, TypeError):
                    logger.warning(f"Valor inválido para {field}: {metadata[field]}")
                    validated[field] = 0
        
        # Listas
        list_fields = ['emails', 'phones', 'urls', 'dates', 'extracted_keywords', 'all_tags']
        for field in list_fields:
            if field in metadata:
                if isinstance(metadata[field], list):
                    validated[field] = metadata[field]
                else:
                    validated[field] = []
        
        # Strings
        string_fields = ['auto_category', 'department', 'language']
        for field in string_fields:
            if field in metadata:
                validated[field] = str(metadata[field]) if metadata[field] else None
        
        # Copia outros campos
        for key, value in metadata.items():
            if key not in validated:
                validated[key] = value
        
        return validated 