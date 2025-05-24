"""
Schemas de Índices Pinecone para Sistema RAG
Define configurações padrão e templates para diferentes tipos de índices.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class IndexEnvironment(Enum):
    """Ambientes de deployment do Pinecone."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EmbeddingModel(Enum):
    """Modelos de embedding suportados."""
    # Hugging Face - 1024 dimensões (recomendados)
    E5_LARGE_V2 = "intfloat/e5-large-v2"
    BGE_LARGE_EN = "BAAI/bge-large-en-v1.5"
    MULTILINGUAL_E5_LARGE = "intfloat/multilingual-e5-large"
    
    # OpenAI
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"  # 3072 dim
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"  # 1536 dim
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"  # 1536 dim
    
    # Custom
    CUSTOM_1024 = "custom-1024"


@dataclass
class MetadataField:
    """Definição de um campo de metadados."""
    name: str
    type: str  # "string", "number", "boolean", "list"
    description: str
    required: bool = False
    indexed: bool = True  # Se deve ser indexado para filtros


@dataclass
class IndexSchema:
    """Schema completo de um índice Pinecone."""
    name: str
    description: str
    dimension: int
    metric: str
    embedding_model: EmbeddingModel
    metadata_fields: List[MetadataField]
    
    # Configurações Pinecone
    cloud: str = "aws"
    region: str = "us-east-1"
    serverless: bool = True
    
    # Configurações de performance
    replicas: int = 1
    pods: int = 1
    pod_type: str = "p1.x1"
    shards: int = 1
    
    # Configurações de namespace
    default_namespace: str = "default"
    namespaces: List[str] = field(default_factory=lambda: ["default"])
    
    def get_pinecone_spec(self) -> Dict[str, Any]:
        """Retorna especificação para criação do índice."""
        if self.serverless:
            return {
                "cloud": self.cloud,
                "region": self.region
            }
        else:
            return {
                "environment": f"{self.region}-{self.cloud}",
                "replicas": self.replicas,
                "shards": self.shards,
                "pods": self.pods,
                "pod_type": self.pod_type
            }
    
    def get_metadata_config(self) -> Dict[str, Dict[str, Any]]:
        """Retorna configuração de metadados."""
        return {
            field.name: {
                "type": field.type,
                "description": field.description,
                "required": field.required,
                "indexed": field.indexed
            }
            for field in self.metadata_fields
        }


class SchemaRegistry:
    """Registro central de schemas de índices."""
    
    @staticmethod
    def get_rag_documents_schema(environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> IndexSchema:
        """Schema para documentos RAG gerais."""
        env_suffix = f"-{environment.value}" if environment != IndexEnvironment.PRODUCTION else ""
        
        return IndexSchema(
            name=f"rag-documents{env_suffix}",
            description="Índice principal para documentos RAG com embeddings de 1024 dimensões",
            dimension=1024,
            metric="cosine",
            embedding_model=EmbeddingModel.E5_LARGE_V2,
            metadata_fields=[
                MetadataField("document_id", "string", "ID único do documento", required=True),
                MetadataField("chunk_id", "string", "ID do chunk dentro do documento", required=True),
                MetadataField("document_title", "string", "Título do documento"),
                MetadataField("document_type", "string", "Tipo do documento (pdf, docx, txt, etc.)"),
                MetadataField("category", "string", "Categoria do conteúdo"),
                MetadataField("tags", "list", "Tags associadas ao conteúdo"),
                MetadataField("language", "string", "Idioma do conteúdo"),
                MetadataField("author", "string", "Autor do documento"),
                MetadataField("created_at", "string", "Data de criação (ISO format)"),
                MetadataField("updated_at", "string", "Data de atualização (ISO format)"),
                MetadataField("source_url", "string", "URL de origem se aplicável"),
                MetadataField("page_number", "number", "Número da página"),
                MetadataField("chunk_size", "number", "Tamanho do chunk em caracteres"),
                MetadataField("chunk_overlap", "number", "Sobreposição com chunk anterior"),
                MetadataField("confidence_score", "number", "Score de confiança do processamento"),
                MetadataField("is_sensitive", "boolean", "Se contém informação sensível"),
                MetadataField("access_level", "string", "Nível de acesso (public, internal, confidential)"),
                MetadataField("department", "string", "Departamento responsável"),
                MetadataField("keywords", "list", "Palavras-chave extraídas"),
                MetadataField("summary", "string", "Resumo do chunk")
            ],
            namespaces=["default", "public", "internal", "confidential"]
        )
    
    @staticmethod
    def get_code_schema(environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> IndexSchema:
        """Schema para código e documentação técnica."""
        env_suffix = f"-{environment.value}" if environment != IndexEnvironment.PRODUCTION else ""
        
        return IndexSchema(
            name=f"rag-code{env_suffix}",
            description="Índice especializado para código e documentação técnica",
            dimension=1024,
            metric="cosine",
            embedding_model=EmbeddingModel.E5_LARGE_V2,
            metadata_fields=[
                MetadataField("file_path", "string", "Caminho do arquivo", required=True),
                MetadataField("function_name", "string", "Nome da função/método"),
                MetadataField("class_name", "string", "Nome da classe"),
                MetadataField("language", "string", "Linguagem de programação", required=True),
                MetadataField("file_type", "string", "Tipo do arquivo (source, test, doc)"),
                MetadataField("line_start", "number", "Linha inicial do código"),
                MetadataField("line_end", "number", "Linha final do código"),
                MetadataField("complexity", "number", "Score de complexidade"),
                MetadataField("repository", "string", "Nome do repositório"),
                MetadataField("branch", "string", "Branch do código"),
                MetadataField("commit_hash", "string", "Hash do commit"),
                MetadataField("author", "string", "Autor do código"),
                MetadataField("last_modified", "string", "Data da última modificação"),
                MetadataField("test_coverage", "number", "Cobertura de testes"),
                MetadataField("dependencies", "list", "Dependências do código"),
                MetadataField("docstring", "string", "Documentação do código"),
                MetadataField("is_public_api", "boolean", "Se é API pública"),
                MetadataField("deprecated", "boolean", "Se está deprecated"),
                MetadataField("version", "string", "Versão do código")
            ],
            namespaces=["source", "tests", "docs", "examples"]
        )
    
    @staticmethod
    def get_media_schema(environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> IndexSchema:
        """Schema para conteúdo multimídia (imagens, áudio, vídeo)."""
        env_suffix = f"-{environment.value}" if environment != IndexEnvironment.PRODUCTION else ""
        
        return IndexSchema(
            name=f"rag-media{env_suffix}",
            description="Índice para conteúdo multimídia com embeddings de descrições",
            dimension=1024,
            metric="cosine",
            embedding_model=EmbeddingModel.MULTILINGUAL_E5_LARGE,
            metadata_fields=[
                MetadataField("media_id", "string", "ID único da mídia", required=True),
                MetadataField("media_type", "string", "Tipo de mídia (image, audio, video)", required=True),
                MetadataField("file_name", "string", "Nome do arquivo"),
                MetadataField("file_size", "number", "Tamanho do arquivo em bytes"),
                MetadataField("duration", "number", "Duração em segundos (para áudio/vídeo)"),
                MetadataField("resolution", "string", "Resolução (para imagem/vídeo)"),
                MetadataField("format", "string", "Formato do arquivo"),
                MetadataField("title", "string", "Título da mídia"),
                MetadataField("description", "string", "Descrição do conteúdo"),
                MetadataField("transcript", "string", "Transcrição (para áudio/vídeo)"),
                MetadataField("alt_text", "string", "Texto alternativo (para imagens)"),
                MetadataField("objects_detected", "list", "Objetos detectados na mídia"),
                MetadataField("scene_description", "string", "Descrição da cena"),
                MetadataField("mood", "string", "Tom/humor do conteúdo"),
                MetadataField("created_at", "string", "Data de criação"),
                MetadataField("location", "string", "Local onde foi criada"),
                MetadataField("camera_model", "string", "Modelo da câmera/dispositivo"),
                MetadataField("quality_score", "number", "Score de qualidade da mídia")
            ],
            namespaces=["images", "audio", "video", "documents"]
        )
    
    @staticmethod
    def get_conversations_schema(environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> IndexSchema:
        """Schema para conversas e interações."""
        env_suffix = f"-{environment.value}" if environment != IndexEnvironment.PRODUCTION else ""
        
        return IndexSchema(
            name=f"rag-conversations{env_suffix}",
            description="Índice para conversas, chat logs e interações",
            dimension=1024,
            metric="cosine",
            embedding_model=EmbeddingModel.MULTILINGUAL_E5_LARGE,
            metadata_fields=[
                MetadataField("conversation_id", "string", "ID da conversa", required=True),
                MetadataField("message_id", "string", "ID da mensagem", required=True),
                MetadataField("user_id", "string", "ID do usuário"),
                MetadataField("user_role", "string", "Papel do usuário (user, assistant, system)"),
                MetadataField("timestamp", "string", "Timestamp da mensagem"),
                MetadataField("session_id", "string", "ID da sessão"),
                MetadataField("channel", "string", "Canal da conversa"),
                MetadataField("intent", "string", "Intenção detectada"),
                MetadataField("sentiment", "string", "Sentimento da mensagem"),
                MetadataField("confidence", "number", "Confiança na resposta"),
                MetadataField("feedback_score", "number", "Score de feedback do usuário"),
                MetadataField("response_time", "number", "Tempo de resposta"),
                MetadataField("tokens_used", "number", "Tokens utilizados"),
                MetadataField("model_used", "string", "Modelo utilizado para resposta"),
                MetadataField("context_retrieved", "boolean", "Se contexto foi recuperado"),
                MetadataField("sources_cited", "list", "Fontes citadas na resposta")
            ],
            namespaces=["support", "general", "technical", "sales"]
        )
    
    @staticmethod
    def get_all_schemas(environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> List[IndexSchema]:
        """Retorna todos os schemas disponíveis."""
        return [
            SchemaRegistry.get_rag_documents_schema(environment),
            SchemaRegistry.get_code_schema(environment),
            SchemaRegistry.get_media_schema(environment),
            SchemaRegistry.get_conversations_schema(environment)
        ]
    
    @staticmethod
    def get_schema_by_name(name: str, environment: IndexEnvironment = IndexEnvironment.DEVELOPMENT) -> Optional[IndexSchema]:
        """Retorna schema por nome."""
        schemas = SchemaRegistry.get_all_schemas(environment)
        for schema in schemas:
            if schema.name == name or schema.name.replace(f"-{environment.value}", "") == name:
                return schema
        return None


def get_embedding_dimensions(model: EmbeddingModel) -> int:
    """Retorna o número de dimensões para um modelo de embedding."""
    dimensions_map = {
        EmbeddingModel.E5_LARGE_V2: 1024,
        EmbeddingModel.BGE_LARGE_EN: 1024,
        EmbeddingModel.MULTILINGUAL_E5_LARGE: 1024,
        EmbeddingModel.TEXT_EMBEDDING_3_LARGE: 3072,
        EmbeddingModel.TEXT_EMBEDDING_3_SMALL: 1536,
        EmbeddingModel.TEXT_EMBEDDING_ADA_002: 1536,
        EmbeddingModel.CUSTOM_1024: 1024
    }
    return dimensions_map.get(model, 1024)


def validate_schema(schema: IndexSchema) -> List[str]:
    """Valida um schema e retorna lista de erros."""
    errors = []
    
    # Validação básica
    if not schema.name:
        errors.append("Nome do índice é obrigatório")
    
    if schema.dimension <= 0:
        errors.append("Dimensão deve ser maior que zero")
    
    if schema.metric not in ["cosine", "euclidean", "dotproduct"]:
        errors.append("Métrica deve ser 'cosine', 'euclidean' ou 'dotproduct'")
    
    # Validação de dimensões do modelo
    expected_dim = get_embedding_dimensions(schema.embedding_model)
    if schema.dimension != expected_dim:
        errors.append(f"Dimensão {schema.dimension} não compatível com modelo {schema.embedding_model.value} (esperado: {expected_dim})")
    
    # Validação de metadados
    field_names = [f.name for f in schema.metadata_fields]
    if len(field_names) != len(set(field_names)):
        errors.append("Nomes de campos de metadados devem ser únicos")
    
    # Validação de namespaces
    if not schema.namespaces:
        errors.append("Pelo menos um namespace deve ser definido")
    
    return errors


# Utilitários para migração
def create_migration_plan(old_schema: IndexSchema, new_schema: IndexSchema) -> Dict[str, Any]:
    """Cria plano de migração entre schemas."""
    plan = {
        "requires_reindex": False,
        "dimension_change": old_schema.dimension != new_schema.dimension,
        "metric_change": old_schema.metric != new_schema.metric,
        "new_fields": [],
        "removed_fields": [],
        "renamed_fields": [],
        "namespace_changes": []
    }
    
    # Detecta mudanças que requerem reindexação
    if plan["dimension_change"] or plan["metric_change"]:
        plan["requires_reindex"] = True
    
    # Analisa campos de metadados
    old_fields = {f.name: f for f in old_schema.metadata_fields}
    new_fields = {f.name: f for f in new_schema.metadata_fields}
    
    plan["new_fields"] = [name for name in new_fields if name not in old_fields]
    plan["removed_fields"] = [name for name in old_fields if name not in new_fields]
    
    # Analisa namespaces
    old_ns = set(old_schema.namespaces)
    new_ns = set(new_schema.namespaces)
    
    plan["namespace_changes"] = {
        "added": list(new_ns - old_ns),
        "removed": list(old_ns - new_ns)
    }
    
    return plan 