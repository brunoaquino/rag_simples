"""
Configurações centralizadas do sistema RAG empresarial.
"""

from typing import Optional, List
from pydantic import BaseSettings, Field
import os


class DatabaseSettings(BaseSettings):
    """Configurações do banco de dados."""
    url: str = Field(default="sqlite:///./data/rag_system.db", env="DATABASE_URL")
    echo: bool = Field(default=False, env="DATABASE_ECHO")


class PineconeSettings(BaseSettings):
    """Configurações do Pinecone."""
    api_key: str = Field(..., env="PINECONE_API_KEY")
    environment: str = Field(default="us-west1-gcp-free", env="PINECONE_ENVIRONMENT")
    index_name: str = Field(default="rag-embeddings", env="PINECONE_INDEX_NAME")
    dimension: int = Field(default=1536, env="PINECONE_DIMENSION")


class OpenAISettings(BaseSettings):
    """Configurações do OpenAI."""
    api_key: str = Field(..., env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    max_tokens: int = Field(default=2048, env="OPENAI_MAX_TOKENS")


class HuggingFaceSettings(BaseSettings):
    """Configurações do Hugging Face."""
    model_name: str = Field(default="sentence-transformers/all-mpnet-base-v2", env="HF_MODEL_NAME")
    cache_dir: str = Field(default="./data/models", env="HF_CACHE_DIR")


class IngestionSettings(BaseSettings):
    """Configurações do sistema de ingestão."""
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    max_file_size: int = Field(default=50 * 1024 * 1024, env="MAX_FILE_SIZE")  # 50MB
    allowed_extensions: List[str] = Field(
        default=[".pdf", ".docx", ".txt", ".md"], 
        env="ALLOWED_EXTENSIONS"
    )


class UISettings(BaseSettings):
    """Configurações das interfaces."""
    streamlit_port: int = Field(default=8501, env="STREAMLIT_PORT")
    fastapi_port: int = Field(default=8000, env="FASTAPI_PORT")
    debug: bool = Field(default=False, env="DEBUG")


class LoggingSettings(BaseSettings):
    """Configurações de logging."""
    level: str = Field(default="INFO", env="LOG_LEVEL")
    file_path: str = Field(default="./logs/rag_system.log", env="LOG_FILE_PATH")
    max_file_size: int = Field(default=10 * 1024 * 1024, env="LOG_MAX_FILE_SIZE")  # 10MB
    backup_count: int = Field(default=5, env="LOG_BACKUP_COUNT")


class SecuritySettings(BaseSettings):
    """Configurações de segurança."""
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")


class Settings(BaseSettings):
    """Configurações principais do sistema."""
    
    # Informações do projeto
    project_name: str = "RAG Sistema Empresarial"
    version: str = "0.1.0"
    description: str = "Sistema RAG empresarial inteligente"
    
    # Configurações específicas
    database: DatabaseSettings = DatabaseSettings()
    pinecone: PineconeSettings = PineconeSettings()
    openai: OpenAISettings = OpenAISettings()
    huggingface: HuggingFaceSettings = HuggingFaceSettings()
    ingestion: IngestionSettings = IngestionSettings()
    ui: UISettings = UISettings()
    logging: LoggingSettings = LoggingSettings()
    security: SecuritySettings = SecuritySettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instância global das configurações
settings = Settings() 