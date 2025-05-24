"""
Cliente Pinecone para Sistema RAG
Sistema completo de banco de dados vetorial usando Pinecone.
"""

import os
import logging
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import numpy as np

# Pinecone imports
try:
    from pinecone import Pinecone, ServerlessSpec, PodSpec
    # from pinecone.grpc import PineconeGRPC  # Removido por problemas de dependência
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    logging.warning("Pinecone não está disponível. Usando implementação mock.")

logger = logging.getLogger(__name__)


@dataclass
class VectorRecord:
    """Representa um registro vetorial com metadados."""
    id: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    namespace: str = ""


@dataclass
class QueryResult:
    """Resultado de uma query vetorial."""
    id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    namespace: str = ""


@dataclass
class PineconeConfig:
    """Configuração do cliente Pinecone."""
    api_key: str
    environment: str = "us-east-1-aws"  # Default environment
    index_name: str = "rag-documents"
    dimension: int = 1024  # Default for sentence-transformers
    metric: str = "cosine"
    cloud: str = "aws"
    region: str = "us-east-1"  # Corrigido: região válida do AWS
    
    # Performance settings
    connection_pool_size: int = 10
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Index settings
    replicas: int = 1
    pods: int = 1
    pod_type: str = "p1.x1"
    shards: int = 1
    
    # Namespace settings
    default_namespace: str = "default"


@dataclass
class OperationMetrics:
    """Métricas de operações do Pinecone."""
    operation_type: str
    timestamp: datetime
    duration: float
    success: bool
    error_message: Optional[str] = None
    records_affected: int = 0
    namespace: str = ""


class PineconeClient:
    """Cliente completo para operações com Pinecone."""
    
    def __init__(self, config: Optional[PineconeConfig] = None):
        """
        Inicializa o cliente Pinecone.
        
        Args:
            config: Configuração do Pinecone
        """
        self.config = config or self._load_config_from_env()
        self.metrics: List[OperationMetrics] = []
        self._client = None
        self._index = None
        
        # Validação inicial
        if not PINECONE_AVAILABLE:
            logger.warning("Pinecone SDK não disponível. Usando modo mock.")
            self._mock_mode = True
            self._mock_data: Dict[str, Dict[str, VectorRecord]] = {}
        else:
            self._mock_mode = False
            self._initialize_client()
    
    def _load_config_from_env(self) -> PineconeConfig:
        """Carrega configuração a partir de variáveis de ambiente."""
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            logger.warning("PINECONE_API_KEY não encontrada. Usando modo mock.")
            api_key = "mock-api-key"
        
        return PineconeConfig(
            api_key=api_key,
            environment=os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws"),
            index_name=os.getenv("PINECONE_INDEX_NAME", "rag-documents"),
            dimension=int(os.getenv("PINECONE_DIMENSION", "768")),
            metric=os.getenv("PINECONE_METRIC", "cosine"),
            default_namespace=os.getenv("PINECONE_NAMESPACE", "default")
        )
    
    def _initialize_client(self):
        """Inicializa o cliente Pinecone."""
        try:
            if not self._mock_mode:
                # Inicializa cliente Pinecone
                self._client = Pinecone(api_key=self.config.api_key)
                logger.info("Cliente Pinecone inicializado com sucesso")
            else:
                logger.info("Cliente Pinecone em modo mock")
                
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Pinecone: {e}")
            self._mock_mode = True
            self._mock_data = {}
    
    def _record_metric(self, operation_type: str, start_time: float, 
                      success: bool, records_affected: int = 0,
                      error_message: Optional[str] = None,
                      namespace: str = ""):
        """Registra métricas de operação."""
        duration = time.time() - start_time
        metric = OperationMetrics(
            operation_type=operation_type,
            timestamp=datetime.now(),
            duration=duration,
            success=success,
            error_message=error_message,
            records_affected=records_affected,
            namespace=namespace
        )
        self.metrics.append(metric)
        
        # Limita histórico de métricas a 1000 entradas
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def create_index(self, 
                    index_name: Optional[str] = None,
                    dimension: Optional[int] = None,
                    metric: Optional[str] = None,
                    serverless: bool = True) -> bool:
        """
        Cria um índice no Pinecone.
        
        Args:
            index_name: Nome do índice
            dimension: Dimensão dos vetores
            metric: Métrica de similaridade
            serverless: Se deve usar Serverless (True) ou Pod (False)
            
        Returns:
            True se criado com sucesso
        """
        start_time = time.time()
        index_name = index_name or self.config.index_name
        dimension = dimension or self.config.dimension
        metric = metric or self.config.metric
        
        try:
            if self._mock_mode:
                if index_name not in self._mock_data:
                    self._mock_data[index_name] = {}
                logger.info(f"Índice mock '{index_name}' criado")
                self._record_metric("create_index", start_time, True)
                return True
            
            # Verifica se índice já existe
            existing_indexes = self._client.list_indexes()
            index_names = [idx.name for idx in existing_indexes.indexes]
            
            if index_name in index_names:
                logger.info(f"Índice '{index_name}' já existe")
                self._record_metric("create_index", start_time, True)
                return True
            
            # Cria especificação do índice
            if serverless:
                spec = ServerlessSpec(
                    cloud=self.config.cloud,
                    region=self.config.region
                )
            else:
                spec = PodSpec(
                    environment=self.config.environment,
                    replicas=self.config.replicas,
                    shards=self.config.shards,
                    pods=self.config.pods,
                    pod_type=self.config.pod_type
                )
            
            # Cria o índice
            self._client.create_index(
                name=index_name,
                dimension=dimension,
                metric=metric,
                spec=spec
            )
            
            # Aguarda o índice ficar pronto
            self._wait_for_index_ready(index_name)
            
            logger.info(f"Índice '{index_name}' criado com sucesso")
            self._record_metric("create_index", start_time, True)
            return True
            
        except Exception as e:
            error_msg = f"Erro ao criar índice '{index_name}': {e}"
            logger.error(error_msg)
            self._record_metric("create_index", start_time, False, error_message=str(e))
            return False
    
    def _wait_for_index_ready(self, index_name: str, timeout: int = 300):
        """Aguarda o índice ficar pronto."""
        if self._mock_mode:
            return True
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                index_stats = self._client.describe_index(index_name)
                if index_stats.status.ready:
                    return True
                time.sleep(5)
            except Exception as e:
                logger.warning(f"Erro ao verificar status do índice: {e}")
                time.sleep(5)
        
        raise TimeoutError(f"Índice '{index_name}' não ficou pronto em {timeout}s")
    
    def connect_to_index(self, index_name: Optional[str] = None) -> bool:
        """
        Conecta a um índice específico.
        
        Args:
            index_name: Nome do índice
            
        Returns:
            True se conectado com sucesso
        """
        start_time = time.time()
        index_name = index_name or self.config.index_name
        
        try:
            if self._mock_mode:
                if index_name not in self._mock_data:
                    self._mock_data[index_name] = {}
                self._index = index_name  # Simula conexão
                logger.info(f"Conectado ao índice mock '{index_name}'")
                self._record_metric("connect_index", start_time, True)
                return True
            
            self._index = self._client.Index(index_name)
            logger.info(f"Conectado ao índice '{index_name}'")
            self._record_metric("connect_index", start_time, True)
            return True
            
        except Exception as e:
            error_msg = f"Erro ao conectar ao índice '{index_name}': {e}"
            logger.error(error_msg)
            self._record_metric("connect_index", start_time, False, error_message=str(e))
            return False
    
    def upsert_vectors(self, 
                      vectors: List[VectorRecord],
                      namespace: Optional[str] = None,
                      batch_size: int = 100) -> bool:
        """
        Insere ou atualiza vetores no índice.
        
        Args:
            vectors: Lista de registros vetoriais
            namespace: Namespace para os vetores
            batch_size: Tamanho do lote para operações
            
        Returns:
            True se inserido com sucesso
        """
        start_time = time.time()
        namespace = namespace or self.config.default_namespace
        
        try:
            if not vectors:
                logger.warning("Lista de vetores vazia")
                return True
            
            if self._mock_mode:
                index_name = self._index or self.config.index_name
                if index_name not in self._mock_data:
                    self._mock_data[index_name] = {}
                if namespace not in self._mock_data[index_name]:
                    self._mock_data[index_name][namespace] = {}
                
                for vector in vectors:
                    self._mock_data[index_name][namespace][vector.id] = vector
                
                logger.info(f"Upsert mock: {len(vectors)} vetores no namespace '{namespace}'")
                self._record_metric("upsert", start_time, True, len(vectors), namespace=namespace)
                return True
            
            if not self._index:
                raise ValueError("Não conectado a um índice")
            
            # Processa em lotes
            total_upserted = 0
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                
                # Prepara dados para upsert
                upsert_data = [
                    {
                        "id": vec.id,
                        "values": vec.vector,
                        "metadata": vec.metadata
                    }
                    for vec in batch
                ]
                
                # Executa upsert
                self._index.upsert(vectors=upsert_data, namespace=namespace)
                total_upserted += len(batch)
                
                logger.debug(f"Lote {i//batch_size + 1}: {len(batch)} vetores")
            
            logger.info(f"Upsert concluído: {total_upserted} vetores no namespace '{namespace}'")
            self._record_metric("upsert", start_time, True, total_upserted, namespace=namespace)
            return True
            
        except Exception as e:
            error_msg = f"Erro no upsert de vetores: {e}"
            logger.error(error_msg)
            self._record_metric("upsert", start_time, False, error_message=str(e), namespace=namespace)
            return False
    
    def query_vectors(self,
                     query_vector: List[float],
                     top_k: int = 10,
                     namespace: Optional[str] = None,
                     filter_dict: Optional[Dict[str, Any]] = None,
                     include_metadata: bool = True,
                     include_values: bool = False) -> List[QueryResult]:
        """
        Busca vetores similares.
        
        Args:
            query_vector: Vetor de consulta
            top_k: Número de resultados
            namespace: Namespace para busca
            filter_dict: Filtros de metadados
            include_metadata: Incluir metadados
            include_values: Incluir valores dos vetores
            
        Returns:
            Lista de resultados ordenados por similaridade
        """
        start_time = time.time()
        namespace = namespace or self.config.default_namespace
        
        try:
            if self._mock_mode:
                index_name = self._index or self.config.index_name
                if (index_name not in self._mock_data or 
                    namespace not in self._mock_data[index_name]):
                    logger.info(f"Namespace '{namespace}' vazio no modo mock")
                    self._record_metric("query", start_time, True, 0, namespace=namespace)
                    return []
                
                # Simulação simples de busca no modo mock
                mock_vectors = self._mock_data[index_name][namespace]
                results = []
                
                for vec_id, vector_record in list(mock_vectors.items())[:top_k]:
                    # Simula score aleatório para o mock
                    score = np.random.uniform(0.8, 0.95)
                    
                    # Aplica filtros se especificados
                    if filter_dict:
                        metadata_match = all(
                            vector_record.metadata.get(k) == v 
                            for k, v in filter_dict.items()
                        )
                        if not metadata_match:
                            continue
                    
                    results.append(QueryResult(
                        id=vec_id,
                        score=score,
                        metadata=vector_record.metadata if include_metadata else {},
                        namespace=namespace
                    ))
                
                logger.info(f"Query mock: {len(results)} resultados no namespace '{namespace}'")
                self._record_metric("query", start_time, True, len(results), namespace=namespace)
                return results
            
            if not self._index:
                raise ValueError("Não conectado a um índice")
            
            # Executa query
            response = self._index.query(
                vector=query_vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter_dict,
                include_metadata=include_metadata,
                include_values=include_values
            )
            
            # Processa resultados
            results = []
            for match in response.matches:
                results.append(QueryResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata or {},
                    namespace=namespace
                ))
            
            logger.info(f"Query concluída: {len(results)} resultados no namespace '{namespace}'")
            self._record_metric("query", start_time, True, len(results), namespace=namespace)
            return results
            
        except Exception as e:
            error_msg = f"Erro na query de vetores: {e}"
            logger.error(error_msg)
            self._record_metric("query", start_time, False, error_message=str(e), namespace=namespace)
            return []
    
    def delete_vectors(self,
                      vector_ids: List[str],
                      namespace: Optional[str] = None) -> bool:
        """
        Remove vetores do índice.
        
        Args:
            vector_ids: IDs dos vetores a remover
            namespace: Namespace dos vetores
            
        Returns:
            True se removido com sucesso
        """
        start_time = time.time()
        namespace = namespace or self.config.default_namespace
        
        try:
            if not vector_ids:
                logger.warning("Lista de IDs vazia")
                return True
            
            if self._mock_mode:
                index_name = self._index or self.config.index_name
                if (index_name in self._mock_data and 
                    namespace in self._mock_data[index_name]):
                    
                    deleted_count = 0
                    for vec_id in vector_ids:
                        if vec_id in self._mock_data[index_name][namespace]:
                            del self._mock_data[index_name][namespace][vec_id]
                            deleted_count += 1
                    
                    logger.info(f"Delete mock: {deleted_count} vetores removidos do namespace '{namespace}'")
                    self._record_metric("delete", start_time, True, deleted_count, namespace=namespace)
                return True
            
            if not self._index:
                raise ValueError("Não conectado a um índice")
            
            # Remove vetores
            self._index.delete(ids=vector_ids, namespace=namespace)
            
            logger.info(f"Delete concluído: {len(vector_ids)} vetores removidos do namespace '{namespace}'")
            self._record_metric("delete", start_time, True, len(vector_ids), namespace=namespace)
            return True
            
        except Exception as e:
            error_msg = f"Erro ao deletar vetores: {e}"
            logger.error(error_msg)
            self._record_metric("delete", start_time, False, error_message=str(e), namespace=namespace)
            return False
    
    def get_index_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas do índice.
        
        Args:
            namespace: Namespace específico
            
        Returns:
            Dicionário com estatísticas
        """
        start_time = time.time()
        
        try:
            if self._mock_mode:
                index_name = self._index or self.config.index_name
                if index_name not in self._mock_data:
                    return {"total_vector_count": 0, "namespaces": {}}
                
                stats = {"namespaces": {}}
                total_count = 0
                
                for ns, vectors in self._mock_data[index_name].items():
                    count = len(vectors)
                    stats["namespaces"][ns] = {"vector_count": count}
                    total_count += count
                
                stats["total_vector_count"] = total_count
                stats["dimension"] = self.config.dimension
                stats["index_fullness"] = 0.0  # Mock
                
                self._record_metric("stats", start_time, True)
                return stats
            
            if not self._index:
                raise ValueError("Não conectado a um índice")
            
            # Obtém estatísticas
            stats = self._index.describe_index_stats()
            
            logger.info("Estatísticas do índice obtidas com sucesso")
            self._record_metric("stats", start_time, True)
            
            return {
                "total_vector_count": stats.total_vector_count,
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "namespaces": stats.namespaces or {}
            }
            
        except Exception as e:
            error_msg = f"Erro ao obter estatísticas: {e}"
            logger.error(error_msg)
            self._record_metric("stats", start_time, False, error_message=str(e))
            return {}
    
    def list_indexes(self) -> List[str]:
        """
        Lista todos os índices disponíveis.
        
        Returns:
            Lista com nomes dos índices
        """
        start_time = time.time()
        
        try:
            if self._mock_mode:
                indexes = list(self._mock_data.keys())
                logger.info(f"Índices mock: {indexes}")
                self._record_metric("list_indexes", start_time, True)
                return indexes
            
            # Lista índices
            response = self._client.list_indexes()
            indexes = [idx.name for idx in response.indexes]
            
            logger.info(f"Índices encontrados: {indexes}")
            self._record_metric("list_indexes", start_time, True)
            return indexes
            
        except Exception as e:
            error_msg = f"Erro ao listar índices: {e}"
            logger.error(error_msg)
            self._record_metric("list_indexes", start_time, False, error_message=str(e))
            return []
    
    def delete_index(self, index_name: Optional[str] = None) -> bool:
        """
        Remove um índice.
        
        Args:
            index_name: Nome do índice a remover
            
        Returns:
            True se removido com sucesso
        """
        start_time = time.time()
        index_name = index_name or self.config.index_name
        
        try:
            if self._mock_mode:
                if index_name in self._mock_data:
                    del self._mock_data[index_name]
                    logger.info(f"Índice mock '{index_name}' removido")
                else:
                    logger.warning(f"Índice mock '{index_name}' não encontrado")
                self._record_metric("delete_index", start_time, True)
                return True
            
            # Remove índice
            self._client.delete_index(index_name)
            
            logger.info(f"Índice '{index_name}' removido com sucesso")
            self._record_metric("delete_index", start_time, True)
            return True
            
        except Exception as e:
            error_msg = f"Erro ao remover índice '{index_name}': {e}"
            logger.error(error_msg)
            self._record_metric("delete_index", start_time, False, error_message=str(e))
            return False
    
    def get_metrics(self, 
                   operation_type: Optional[str] = None,
                   last_hours: int = 24) -> List[OperationMetrics]:
        """
        Obtém métricas de operações.
        
        Args:
            operation_type: Tipo de operação específica
            last_hours: Número de horas passadas
            
        Returns:
            Lista de métricas
        """
        cutoff_time = datetime.now() - timedelta(hours=last_hours)
        
        filtered_metrics = [
            metric for metric in self.metrics
            if metric.timestamp >= cutoff_time
        ]
        
        if operation_type:
            filtered_metrics = [
                metric for metric in filtered_metrics
                if metric.operation_type == operation_type
            ]
        
        return filtered_metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Obtém resumo de performance.
        
        Returns:
            Dicionário com métricas de performance
        """
        recent_metrics = self.get_metrics(last_hours=24)
        
        if not recent_metrics:
            return {"message": "Nenhuma métrica disponível"}
        
        # Agrupa por tipo de operação
        by_operation = {}
        for metric in recent_metrics:
            op_type = metric.operation_type
            if op_type not in by_operation:
                by_operation[op_type] = {
                    "total_operations": 0,
                    "successful_operations": 0,
                    "total_duration": 0.0,
                    "total_records": 0
                }
            
            stats = by_operation[op_type]
            stats["total_operations"] += 1
            if metric.success:
                stats["successful_operations"] += 1
            stats["total_duration"] += metric.duration
            stats["total_records"] += metric.records_affected
        
        # Calcula médias
        summary = {}
        for op_type, stats in by_operation.items():
            summary[op_type] = {
                "total_operations": stats["total_operations"],
                "success_rate": stats["successful_operations"] / stats["total_operations"],
                "average_duration": stats["total_duration"] / stats["total_operations"],
                "total_records_processed": stats["total_records"]
            }
        
        return summary
    
    def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde da conexão.
        
        Returns:
            Status de saúde do sistema
        """
        health_status = {
            "pinecone_available": PINECONE_AVAILABLE,
            "mock_mode": self._mock_mode,
            "connected": bool(self._index),
            "index_name": self._index if self._mock_mode else (self.config.index_name if self._index else None),
            "config": {
                "dimension": self.config.dimension,
                "metric": self.config.metric,
                "default_namespace": self.config.default_namespace
            }
        }
        
        if self._index:
            try:
                stats = self.get_index_stats()
                health_status["index_stats"] = stats
                health_status["operational"] = True
            except Exception as e:
                health_status["operational"] = False
                health_status["error"] = str(e)
        else:
            health_status["operational"] = False
            health_status["error"] = "Não conectado a um índice"
        
        return health_status
    
    def export_mock_data(self, file_path: str) -> bool:
        """
        Exporta dados mock para arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se exportado com sucesso
        """
        if not self._mock_mode:
            logger.warning("Export só disponível no modo mock")
            return False
        
        try:
            # Converte VectorRecord para dict serializável
            export_data = {}
            for index_name, namespaces in self._mock_data.items():
                export_data[index_name] = {}
                for namespace, vectors in namespaces.items():
                    export_data[index_name][namespace] = {
                        vec_id: {
                            "id": vec.id,
                            "vector": vec.vector,
                            "metadata": vec.metadata,
                            "namespace": vec.namespace
                        }
                        for vec_id, vec in vectors.items()
                    }
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Dados mock exportados para {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao exportar dados mock: {e}")
            return False
    
    def import_mock_data(self, file_path: str) -> bool:
        """
        Importa dados mock de arquivo.
        
        Args:
            file_path: Caminho do arquivo
            
        Returns:
            True se importado com sucesso
        """
        if not self._mock_mode:
            logger.warning("Import só disponível no modo mock")
            return False
        
        try:
            with open(file_path, 'r') as f:
                import_data = json.load(f)
            
            # Converte dict para VectorRecord
            self._mock_data = {}
            for index_name, namespaces in import_data.items():
                self._mock_data[index_name] = {}
                for namespace, vectors in namespaces.items():
                    self._mock_data[index_name][namespace] = {
                        vec_id: VectorRecord(
                            id=vec_data["id"],
                            vector=vec_data["vector"],
                            metadata=vec_data["metadata"],
                            namespace=vec_data["namespace"]
                        )
                        for vec_id, vec_data in vectors.items()
                    }
            
            logger.info(f"Dados mock importados de {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao importar dados mock: {e}")
            return False


# Funções de conveniência
def create_pinecone_client(config: Optional[PineconeConfig] = None) -> PineconeClient:
    """
    Cria e retorna um cliente Pinecone configurado.
    
    Args:
        config: Configuração personalizada
        
    Returns:
        Cliente Pinecone inicializado
    """
    return PineconeClient(config)


def get_default_config() -> PineconeConfig:
    """
    Retorna configuração padrão do Pinecone.
    
    Returns:
        Configuração padrão
    """
    return PineconeConfig(
        api_key=os.getenv("PINECONE_API_KEY", ""),
        environment=os.getenv("PINECONE_ENVIRONMENT", "us-east-1-aws"),
        index_name=os.getenv("PINECONE_INDEX_NAME", "rag-documents"),
        dimension=int(os.getenv("PINECONE_DIMENSION", "768"))
    ) 