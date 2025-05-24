"""
Gerenciador de Índices Pinecone
Sistema para criar e gerenciar múltiplos índices com diferentes configurações.
"""

import logging
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from .pinecone_client import PineconeClient, PineconeConfig

logger = logging.getLogger(__name__)


class IndexType(Enum):
    """Tipos de índices pré-configurados."""
    DOCUMENTS = "documents"  # Para documentos gerais
    CODE = "code"           # Para código fonte
    IMAGES = "images"       # Para descrições de imagens
    AUDIO = "audio"         # Para transcrições de áudio
    MIXED = "mixed"         # Para conteúdo misto


@dataclass
class IndexTemplate:
    """Template de configuração para tipos de índice."""
    name_suffix: str
    dimension: int
    metric: str
    description: str
    default_namespace: str
    recommended_batch_size: int = 100
    metadata_config: Dict[str, Any] = None


class IndexManager:
    """Gerenciador de múltiplos índices Pinecone."""
    
    # Templates pré-configurados
    INDEX_TEMPLATES = {
        IndexType.DOCUMENTS: IndexTemplate(
            name_suffix="docs",
            dimension=768,  # sentence-transformers padrão
            metric="cosine",
            description="Índice para documentos de texto geral",
            default_namespace="documents",
            recommended_batch_size=100,
            metadata_config={
                "indexed": ["document_type", "category", "language"],
                "stored": ["title", "author", "created_at", "file_path"]
            }
        ),
        IndexType.CODE: IndexTemplate(
            name_suffix="code",
            dimension=768,
            metric="cosine", 
            description="Índice para código fonte e documentação técnica",
            default_namespace="code",
            recommended_batch_size=50,
            metadata_config={
                "indexed": ["language", "function_type", "complexity"],
                "stored": ["file_path", "line_numbers", "repository"]
            }
        ),
        IndexType.IMAGES: IndexTemplate(
            name_suffix="images",
            dimension=512,  # Menor dimensão para descrições de imagem
            metric="cosine",
            description="Índice para descrições e metadados de imagens",
            default_namespace="images",
            recommended_batch_size=200,
            metadata_config={
                "indexed": ["image_type", "category", "quality"],
                "stored": ["file_path", "size", "resolution", "description"]
            }
        ),
        IndexType.AUDIO: IndexTemplate(
            name_suffix="audio",
            dimension=768,
            metric="cosine",
            description="Índice para transcrições e metadados de áudio",
            default_namespace="audio",
            recommended_batch_size=75,
            metadata_config={
                "indexed": ["audio_type", "language", "duration_category"],
                "stored": ["file_path", "duration", "speaker", "transcript"]
            }
        ),
        IndexType.MIXED: IndexTemplate(
            name_suffix="mixed",
            dimension=1024,  # Dimensão maior para conteúdo misto
            metric="cosine",
            description="Índice para conteúdo misto e multimodal",
            default_namespace="mixed",
            recommended_batch_size=50,
            metadata_config={
                "indexed": ["content_type", "category", "modality"],
                "stored": ["source", "created_at", "file_path", "summary"]
            }
        )
    }
    
    def __init__(self, base_config: PineconeConfig, project_prefix: str = "rag"):
        """
        Inicializa o gerenciador de índices.
        
        Args:
            base_config: Configuração base do Pinecone
            project_prefix: Prefixo para nomes dos índices
        """
        self.base_config = base_config
        self.project_prefix = project_prefix
        self.clients: Dict[IndexType, PineconeClient] = {}
        
    def create_index_for_type(self, 
                             index_type: IndexType,
                             custom_config: Optional[Dict[str, Any]] = None,
                             serverless: bool = True) -> bool:
        """
        Cria um índice para um tipo específico de conteúdo.
        
        Args:
            index_type: Tipo do índice
            custom_config: Configurações personalizadas
            serverless: Se deve usar Serverless
            
        Returns:
            True se criado com sucesso
        """
        try:
            template = self.INDEX_TEMPLATES[index_type]
            
            # Cria nome do índice
            index_name = f"{self.project_prefix}-{template.name_suffix}"
            
            # Configura cliente específico
            config = PineconeConfig(
                api_key=self.base_config.api_key,
                environment=self.base_config.environment,
                index_name=index_name,
                dimension=template.dimension,
                metric=template.metric,
                cloud=self.base_config.cloud,
                region=self.base_config.region,
                default_namespace=template.default_namespace
            )
            
            # Aplica configurações personalizadas
            if custom_config:
                for key, value in custom_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            
            # Cria cliente e índice
            client = PineconeClient(config)
            
            success = client.create_index(
                index_name=index_name,
                dimension=config.dimension,
                metric=config.metric,
                serverless=serverless
            )
            
            if success:
                # Conecta ao índice
                client.connect_to_index(index_name)
                self.clients[index_type] = client
                
                logger.info(f"Índice '{index_name}' criado e conectado para tipo {index_type.value}")
                return True
            else:
                logger.error(f"Falha ao criar índice para tipo {index_type.value}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao criar índice para tipo {index_type.value}: {e}")
            return False
    
    def connect_to_existing_indexes(self) -> Dict[IndexType, bool]:
        """
        Conecta a índices existentes para todos os tipos.
        
        Returns:
            Dicionário com status de conexão por tipo
        """
        connection_status = {}
        
        for index_type, template in self.INDEX_TEMPLATES.items():
            try:
                index_name = f"{self.project_prefix}-{template.name_suffix}"
                
                config = PineconeConfig(
                    api_key=self.base_config.api_key,
                    environment=self.base_config.environment,
                    index_name=index_name,
                    dimension=template.dimension,
                    metric=template.metric,
                    default_namespace=template.default_namespace
                )
                
                client = PineconeClient(config)
                success = client.connect_to_index(index_name)
                
                if success:
                    self.clients[index_type] = client
                    connection_status[index_type] = True
                    logger.info(f"Conectado ao índice {index_name}")
                else:
                    connection_status[index_type] = False
                    logger.warning(f"Falha ao conectar ao índice {index_name}")
                    
            except Exception as e:
                connection_status[index_type] = False
                logger.error(f"Erro ao conectar ao índice {index_type.value}: {e}")
        
        return connection_status
    
    def get_client(self, index_type: IndexType) -> Optional[PineconeClient]:
        """
        Obtém cliente para um tipo específico de índice.
        
        Args:
            index_type: Tipo do índice
            
        Returns:
            Cliente Pinecone ou None se não conectado
        """
        return self.clients.get(index_type)
    
    def list_all_indexes(self) -> Dict[str, Any]:
        """
        Lista todos os índices do projeto.
        
        Returns:
            Informações sobre todos os índices
        """
        # Usa qualquer cliente para listar (todos compartilham mesmo ambiente)
        if not self.clients:
            # Cria cliente temporário apenas para listar
            temp_client = PineconeClient(self.base_config)
            all_indexes = temp_client.list_indexes()
        else:
            client = next(iter(self.clients.values()))
            all_indexes = client.list_indexes()
        
        # Filtra índices do projeto
        project_indexes = [
            idx for idx in all_indexes 
            if idx.startswith(self.project_prefix)
        ]
        
        # Mapeia para tipos conhecidos
        mapped_indexes = {}
        for index_name in project_indexes:
            suffix = index_name.replace(f"{self.project_prefix}-", "")
            
            # Encontra tipo correspondente
            index_type = None
            for itype, template in self.INDEX_TEMPLATES.items():
                if template.name_suffix == suffix:
                    index_type = itype
                    break
            
            mapped_indexes[index_name] = {
                "type": index_type.value if index_type else "unknown",
                "connected": index_type in self.clients if index_type else False,
                "template": self.INDEX_TEMPLATES.get(index_type) if index_type else None
            }
        
        return mapped_indexes
    
    def get_all_stats(self) -> Dict[IndexType, Dict[str, Any]]:
        """
        Obtém estatísticas de todos os índices conectados.
        
        Returns:
            Estatísticas por tipo de índice
        """
        all_stats = {}
        
        for index_type, client in self.clients.items():
            try:
                stats = client.get_index_stats()
                performance = client.get_performance_summary()
                
                all_stats[index_type] = {
                    "index_stats": stats,
                    "performance": performance,
                    "template": self.INDEX_TEMPLATES[index_type]
                }
                
            except Exception as e:
                logger.error(f"Erro ao obter stats para {index_type.value}: {e}")
                all_stats[index_type] = {"error": str(e)}
        
        return all_stats
    
    def setup_complete_environment(self, 
                                  index_types: List[IndexType] = None,
                                  serverless: bool = True) -> Dict[IndexType, bool]:
        """
        Configura ambiente completo criando todos os índices necessários.
        
        Args:
            index_types: Tipos de índices a criar (padrão: todos)
            serverless: Se deve usar Serverless
            
        Returns:
            Status de criação por tipo
        """
        if index_types is None:
            index_types = list(IndexType)
        
        setup_status = {}
        
        logger.info(f"Configurando ambiente com {len(index_types)} tipos de índice")
        
        for index_type in index_types:
            logger.info(f"Criando índice para tipo: {index_type.value}")
            
            success = self.create_index_for_type(
                index_type=index_type,
                serverless=serverless
            )
            
            setup_status[index_type] = success
            
            if success:
                logger.info(f"✅ Índice {index_type.value} criado com sucesso")
            else:
                logger.error(f"❌ Falha ao criar índice {index_type.value}")
                
            # Pequeno delay entre criações para evitar rate limiting
            time.sleep(2)
        
        successful_setups = sum(1 for success in setup_status.values() if success)
        logger.info(f"Setup concluído: {successful_setups}/{len(index_types)} índices criados")
        
        return setup_status
    
    def health_check_all(self) -> Dict[str, Any]:
        """
        Verifica saúde de todos os clientes conectados.
        
        Returns:
            Status de saúde geral
        """
        health_status = {
            "total_clients": len(self.clients),
            "project_prefix": self.project_prefix,
            "clients": {}
        }
        
        operational_count = 0
        
        for index_type, client in self.clients.items():
            try:
                client_health = client.health_check()
                health_status["clients"][index_type.value] = client_health
                
                if client_health.get("operational", False):
                    operational_count += 1
                    
            except Exception as e:
                health_status["clients"][index_type.value] = {
                    "error": str(e),
                    "operational": False
                }
        
        health_status["operational_clients"] = operational_count
        health_status["overall_health"] = operational_count / len(self.clients) if self.clients else 0
        
        return health_status
    
    def cleanup_all_indexes(self, confirm: bool = False) -> Dict[IndexType, bool]:
        """
        Remove todos os índices do projeto (USE COM CUIDADO).
        
        Args:
            confirm: Confirmação de que deseja realmente deletar
            
        Returns:
            Status de remoção por tipo
        """
        if not confirm:
            logger.warning("cleanup_all_indexes requer confirm=True para executar")
            return {}
        
        cleanup_status = {}
        
        for index_type, client in self.clients.items():
            try:
                template = self.INDEX_TEMPLATES[index_type]
                index_name = f"{self.project_prefix}-{template.name_suffix}"
                
                success = client.delete_index(index_name)
                cleanup_status[index_type] = success
                
                if success:
                    logger.info(f"Índice {index_name} removido")
                else:
                    logger.error(f"Falha ao remover índice {index_name}")
                    
            except Exception as e:
                logger.error(f"Erro ao remover índice {index_type.value}: {e}")
                cleanup_status[index_type] = False
        
        # Limpa clientes
        self.clients.clear()
        
        return cleanup_status
    
    def get_recommended_type(self, content_description: str) -> IndexType:
        """
        Recomenda tipo de índice baseado na descrição do conteúdo.
        
        Args:
            content_description: Descrição do tipo de conteúdo
            
        Returns:
            Tipo recomendado de índice
        """
        content_lower = content_description.lower()
        
        # Palavras-chave para cada tipo
        keywords = {
            IndexType.CODE: ["code", "programming", "script", "function", "class", "api", "github", "repository"],
            IndexType.IMAGES: ["image", "photo", "picture", "visual", "graphic", "diagram", "chart"],
            IndexType.AUDIO: ["audio", "speech", "voice", "sound", "music", "transcript", "podcast"],
            IndexType.DOCUMENTS: ["document", "text", "pdf", "word", "article", "report", "paper"]
        }
        
        # Conta matches para cada tipo
        scores = {}
        for index_type, type_keywords in keywords.items():
            score = sum(1 for keyword in type_keywords if keyword in content_lower)
            scores[index_type] = score
        
        # Retorna tipo com maior score, ou MIXED se empate/baixo score
        if not scores or max(scores.values()) == 0:
            return IndexType.MIXED
        
        return max(scores, key=scores.get)


def create_index_manager(api_key: str, 
                        project_prefix: str = "rag",
                        environment: str = "us-east1-aws") -> IndexManager:
    """
    Cria um gerenciador de índices com configuração básica.
    
    Args:
        api_key: Chave API do Pinecone
        project_prefix: Prefixo para nomes dos índices
        environment: Ambiente Pinecone
        
    Returns:
        Gerenciador de índices configurado
    """
    base_config = PineconeConfig(
        api_key=api_key,
        environment=environment,
        index_name="temp",  # Será sobrescrito
        dimension=768,      # Será sobrescrito
    )
    
    return IndexManager(base_config, project_prefix) 