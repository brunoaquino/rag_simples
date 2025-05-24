"""
Sistema de Chunking - Divisão inteligente de documentos
Divide documentos em chunks menores mantendo contexto e semântica.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ChunkConfig:
    """Configuração para o sistema de chunking."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    strategy: str = 'fixed_size'  # 'fixed_size', 'by_paragraph', 'by_sentence'
    preserve_structure: bool = True
    min_chunk_size: int = 100

@dataclass 
class Chunk:
    """Representa um chunk de texto."""
    text: str
    start_index: int
    end_index: int
    chunk_id: str
    metadata: Dict[str, Any]
    
    def __len__(self) -> int:
        return len(self.text)

class BaseChunker(ABC):
    """Classe base para estratégias de chunking."""
    
    def __init__(self, config: ChunkConfig):
        self.config = config
    
    @abstractmethod
    def chunk_text(self, text: str, doc_metadata: Dict[str, Any]) -> List[Chunk]:
        """Divide o texto em chunks usando a estratégia específica."""
        pass
    
    def _create_chunk_id(self, doc_filename: str, chunk_index: int) -> str:
        """Cria um ID único para o chunk."""
        return f"{doc_filename}__chunk_{chunk_index:04d}"
    
    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """Adiciona sobreposição entre chunks consecutivos."""
        if len(chunks) <= 1 or self.config.chunk_overlap <= 0:
            return chunks
        
        overlapped_chunks = []
        
        for i, chunk in enumerate(chunks):
            if i == 0:
                # Primeiro chunk - sem sobreposição anterior
                overlapped_chunks.append(chunk)
            else:
                # Pega sobreposição do chunk anterior
                prev_chunk = chunks[i-1]
                overlap_text = prev_chunk[-self.config.chunk_overlap:]
                
                # Remove quebras de linha do início da sobreposição
                overlap_text = overlap_text.lstrip('\n')
                
                # Combina sobreposição com chunk atual
                combined_chunk = overlap_text + "\n" + chunk
                overlapped_chunks.append(combined_chunk)
        
        return overlapped_chunks

class FixedSizeChunker(BaseChunker):
    """Chunker que divide texto em tamanhos fixos."""
    
    def chunk_text(self, text: str, doc_metadata: Dict[str, Any]) -> List[Chunk]:
        """Divide texto em chunks de tamanho fixo."""
        chunks = []
        text_length = len(text)
        
        # Se o texto é menor que o tamanho do chunk, retorna como um único chunk
        if text_length <= self.config.chunk_size:
            chunk = Chunk(
                text=text,
                start_index=0,
                end_index=text_length,
                chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), 0),
                metadata={
                    'strategy': 'fixed_size',
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'doc_metadata': doc_metadata
                }
            )
            return [chunk]
        
        chunk_index = 0
        start_index = 0
        
        while start_index < text_length:
            # Calcula fim do chunk
            end_index = min(start_index + self.config.chunk_size, text_length)
            
            # Se não é o último chunk, tenta quebrar em uma fronteira de palavra
            if end_index < text_length and self.config.preserve_structure:
                # Procura pela última quebra de linha ou espaço
                last_newline = text.rfind('\n', start_index, end_index)
                last_space = text.rfind(' ', start_index, end_index)
                
                break_point = max(last_newline, last_space)
                
                # Só usa a quebra se ela não for muito próxima do início
                if break_point > start_index + self.config.min_chunk_size:
                    end_index = break_point + 1
            
            chunk_text = text[start_index:end_index].strip()
            
            # Só cria chunk se tiver conteúdo significativo
            if len(chunk_text) >= self.config.min_chunk_size:
                chunk = Chunk(
                    text=chunk_text,
                    start_index=start_index,
                    end_index=end_index,
                    chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), chunk_index),
                    metadata={
                        'strategy': 'fixed_size',
                        'chunk_index': chunk_index,
                        'doc_metadata': doc_metadata
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Move para o próximo chunk com sobreposição
            start_index = max(end_index - self.config.chunk_overlap, start_index + 1)
        
        # Atualiza metadados com total de chunks
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)
        
        logger.info(f"Texto dividido em {len(chunks)} chunks usando estratégia fixed_size")
        return chunks

class ParagraphChunker(BaseChunker):
    """Chunker que divide texto por parágrafos."""
    
    def chunk_text(self, text: str, doc_metadata: Dict[str, Any]) -> List[Chunk]:
        """Divide texto por parágrafos, respeitando tamanho máximo."""
        # Divide em parágrafos
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # Se não há parágrafos separados, trata o texto inteiro como um parágrafo
        if not paragraphs:
            paragraphs = [text.strip()] if text.strip() else []
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        start_index = 0
        
        for paragraph in paragraphs:
            # Verifica se adicionar este parágrafo excederia o tamanho do chunk
            potential_chunk = current_chunk + "\n\n" + paragraph if current_chunk else paragraph
            
            if len(potential_chunk) <= self.config.chunk_size:
                # Adiciona parágrafo ao chunk atual
                current_chunk = potential_chunk
            else:
                # Finaliza chunk atual se não estiver vazio
                if current_chunk and len(current_chunk.strip()) >= self.config.min_chunk_size:
                    chunk = self._create_paragraph_chunk(
                        current_chunk, start_index, doc_metadata, chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    start_index += len(current_chunk) + 2  # +2 para \n\n
                
                # Se o parágrafo sozinho é maior que o tamanho do chunk, divide ele
                if len(paragraph) > self.config.chunk_size:
                    para_chunks = self._split_large_paragraph(
                        paragraph, start_index, doc_metadata, chunk_index
                    )
                    chunks.extend(para_chunks)
                    chunk_index += len(para_chunks)
                    start_index += len(paragraph) + 2
                    current_chunk = ""
                else:
                    # Inicia novo chunk com este parágrafo
                    current_chunk = paragraph
        
        # Adiciona último chunk se não estiver vazio
        if current_chunk and len(current_chunk.strip()) >= self.config.min_chunk_size:
            chunk = self._create_paragraph_chunk(
                current_chunk, start_index, doc_metadata, chunk_index
            )
            chunks.append(chunk)
        
        # Se não há chunks válidos, cria um chunk único com todo o texto
        if not chunks and text.strip():
            chunk = Chunk(
                text=text.strip(),
                start_index=0,
                end_index=len(text),
                chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), 0),
                metadata={
                    'strategy': 'by_paragraph',
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'doc_metadata': doc_metadata
                }
            )
            chunks.append(chunk)
        
        # Atualiza metadados
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)
        
        logger.info(f"Texto dividido em {len(chunks)} chunks usando estratégia by_paragraph")
        return chunks
    
    def _create_paragraph_chunk(self, text: str, start_index: int, doc_metadata: Dict[str, Any], chunk_index: int) -> Chunk:
        """Cria um chunk a partir de texto de parágrafo."""
        return Chunk(
            text=text,
            start_index=start_index,
            end_index=start_index + len(text),
            chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), chunk_index),
            metadata={
                'strategy': 'by_paragraph',
                'chunk_index': chunk_index,
                'doc_metadata': doc_metadata
            }
        )
    
    def _split_large_paragraph(self, paragraph: str, start_index: int, doc_metadata: Dict[str, Any], chunk_index: int) -> List[Chunk]:
        """Divide um parágrafo muito grande em chunks menores."""
        # Usa o chunker de tamanho fixo para dividir o parágrafo
        fixed_chunker = FixedSizeChunker(self.config)
        para_chunks = fixed_chunker.chunk_text(paragraph, doc_metadata)
        
        # Ajusta metadados e índices
        for i, chunk in enumerate(para_chunks):
            chunk.chunk_id = self._create_chunk_id(doc_metadata.get('filename', 'unknown'), chunk_index + i)
            chunk.start_index += start_index
            chunk.end_index += start_index
            chunk.metadata['strategy'] = 'by_paragraph_split'
            chunk.metadata['chunk_index'] = chunk_index + i
        
        return para_chunks

class SentenceChunker(BaseChunker):
    """Chunker que divide texto por frases."""
    
    def chunk_text(self, text: str, doc_metadata: Dict[str, Any]) -> List[Chunk]:
        """Divide texto por frases, respeitando tamanho máximo."""
        # Regex mais sofisticada para detectar fim de frases
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Se não há frases separadas, trata o texto inteiro como uma frase
        if not sentences:
            sentences = [text.strip()] if text.strip() else []
        
        chunks = []
        current_chunk = ""
        chunk_index = 0
        start_index = 0
        
        for sentence in sentences:
            # Verifica se adicionar esta frase excederia o tamanho do chunk
            potential_chunk = current_chunk + " " + sentence if current_chunk else sentence
            
            if len(potential_chunk) <= self.config.chunk_size:
                # Adiciona frase ao chunk atual
                current_chunk = potential_chunk
            else:
                # Finaliza chunk atual se não estiver vazio
                if current_chunk and len(current_chunk.strip()) >= self.config.min_chunk_size:
                    chunk = self._create_sentence_chunk(
                        current_chunk, start_index, doc_metadata, chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    start_index += len(current_chunk) + 1
                
                # Se a frase sozinha é maior que o tamanho do chunk, divide ela
                if len(sentence) > self.config.chunk_size:
                    # Usa chunker de tamanho fixo para frases muito longas
                    fixed_chunker = FixedSizeChunker(self.config)
                    sentence_chunks = fixed_chunker.chunk_text(sentence, doc_metadata)
                    
                    for i, sent_chunk in enumerate(sentence_chunks):
                        sent_chunk.chunk_id = self._create_chunk_id(
                            doc_metadata.get('filename', 'unknown'), chunk_index + i
                        )
                        sent_chunk.metadata['strategy'] = 'by_sentence_split'
                        sent_chunk.metadata['chunk_index'] = chunk_index + i
                    
                    chunks.extend(sentence_chunks)
                    chunk_index += len(sentence_chunks)
                    start_index += len(sentence) + 1
                    current_chunk = ""
                else:
                    # Inicia novo chunk com esta frase
                    current_chunk = sentence
        
        # Adiciona último chunk se não estiver vazio
        if current_chunk and len(current_chunk.strip()) >= self.config.min_chunk_size:
            chunk = self._create_sentence_chunk(
                current_chunk, start_index, doc_metadata, chunk_index
            )
            chunks.append(chunk)
        
        # Se não há chunks válidos, cria um chunk único com todo o texto
        if not chunks and text.strip():
            chunk = Chunk(
                text=text.strip(),
                start_index=0,
                end_index=len(text),
                chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), 0),
                metadata={
                    'strategy': 'by_sentence',
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'doc_metadata': doc_metadata
                }
            )
            chunks.append(chunk)
        
        # Atualiza metadados
        for chunk in chunks:
            chunk.metadata['total_chunks'] = len(chunks)
        
        logger.info(f"Texto dividido em {len(chunks)} chunks usando estratégia by_sentence")
        return chunks
    
    def _create_sentence_chunk(self, text: str, start_index: int, doc_metadata: Dict[str, Any], chunk_index: int) -> Chunk:
        """Cria um chunk a partir de texto de frases."""
        return Chunk(
            text=text,
            start_index=start_index,
            end_index=start_index + len(text),
            chunk_id=self._create_chunk_id(doc_metadata.get('filename', 'unknown'), chunk_index),
            metadata={
                'strategy': 'by_sentence',
                'chunk_index': chunk_index,
                'doc_metadata': doc_metadata
            }
        )

class ChunkingSystem:
    """Sistema principal de chunking."""
    
    def __init__(self, config: Optional[ChunkConfig] = None):
        """Inicializa o sistema de chunking."""
        self.config = config or ChunkConfig()
        
        # Mapeamento de estratégias para classes
        self.chunkers = {
            'fixed_size': FixedSizeChunker,
            'by_paragraph': ParagraphChunker,
            'by_sentence': SentenceChunker
        }
        
        logger.info(f"ChunkingSystem inicializado com estratégia: {self.config.strategy}")
    
    def chunk_document(self, text: str, doc_metadata: Dict[str, Any]) -> List[Chunk]:
        """
        Divide um documento em chunks usando a estratégia configurada.
        
        Args:
            text: Texto do documento
            doc_metadata: Metadados do documento
            
        Returns:
            Lista de chunks
            
        Raises:
            ValueError: Se a estratégia não for suportada
        """
        if self.config.strategy not in self.chunkers:
            available = list(self.chunkers.keys())
            raise ValueError(
                f"Estratégia '{self.config.strategy}' não suportada. "
                f"Disponíveis: {available}"
            )
        
        # Valida entrada
        if not text or not text.strip():
            logger.warning("Texto vazio fornecido para chunking")
            return []
        
        # Cria o chunker apropriado
        chunker_class = self.chunkers[self.config.strategy]
        chunker = chunker_class(self.config)
        
        # Executa chunking
        try:
            chunks = chunker.chunk_text(text, doc_metadata)
            
            # Valida resultado
            chunks = [chunk for chunk in chunks if len(chunk.text.strip()) >= self.config.min_chunk_size]
            
            logger.info(
                f"Documento '{doc_metadata.get('filename', 'unknown')}' "
                f"dividido em {len(chunks)} chunks válidos"
            )
            
            return chunks
            
        except Exception as e:
            logger.error(f"Erro durante chunking: {str(e)}")
            raise
    
    def get_chunk_stats(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """Retorna estatísticas dos chunks gerados."""
        if not chunks:
            return {
                'total_chunks': 0,
                'avg_chunk_size': 0,
                'min_chunk_size': 0,
                'max_chunk_size': 0,
                'total_text_length': 0
            }
        
        chunk_sizes = [len(chunk.text) for chunk in chunks]
        total_text = sum(chunk_sizes)
        
        return {
            'total_chunks': len(chunks),
            'avg_chunk_size': total_text / len(chunks),
            'min_chunk_size': min(chunk_sizes),
            'max_chunk_size': max(chunk_sizes),
            'total_text_length': total_text
        } 