"""
Demonstração do Sistema Pinecone RAG
Exemplos práticos de uso do cliente e gerenciador de índices.
"""

import os
import sys
import time
import logging
from typing import List
import random

# Adiciona o diretório src ao path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from vector_db import (
    PineconeClient, PineconeConfig, VectorRecord, QueryResult,
    IndexManager, IndexType, create_index_manager, create_pinecone_client
)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_basic_client():
    """Demonstra uso básico do cliente Pinecone."""
    print("\n🔹 DEMO 1: Cliente Pinecone Básico")
    print("=" * 50)
    
    # Cria cliente usando o índice existente
    config = PineconeConfig(
        api_key=os.getenv("PINECONE_API_KEY"),
        index_name="rag-documentos",  # Usar o índice existente
        region="us-east-1"
    )
    client = PineconeClient(config)
    print(f"✅ Cliente criado - Modo mock: {client._mock_mode}")
    
    # Conecta ao índice existente em vez de criar um novo
    connected = client.connect_to_index("rag-documentos")
    print(f"✅ Conectado ao índice: {connected}")
    
    if not connected:
        print("❌ Não foi possível conectar ao índice. Verifique se ele existe.")
        return
    
    # Prepara dados de exemplo
    vectors = [
        VectorRecord(
            id="doc1",
            vector=[0.1] * 1024,  # 1024 dimensões para corresponder ao índice
            metadata={"title": "Documento 1", "category": "tecnologia", "author": "João"}
        ),
        VectorRecord(
            id="doc2",
            vector=[0.2] * 1024,  # 1024 dimensões
            metadata={"title": "Documento 2", "category": "ciência", "author": "Maria"}
        ),
        VectorRecord(
            id="doc3",
            vector=[0.3] * 1024,  # 1024 dimensões
            metadata={"title": "Documento 3", "category": "tecnologia", "author": "Pedro"}
        ),
        VectorRecord(
            id="doc4",
            vector=[0.4] * 1024,  # 1024 dimensões
            metadata={"title": "Documento 4", "category": "saúde", "author": "Ana"}
        )
    ]
    
    # Insere vetores
    success = client.upsert_vectors(vectors, namespace="demo")
    print(f"✅ {len(vectors)} vetores inseridos: {success}")
    
    # Consulta por similaridade
    query_vector = [0.1] * 1024  # 1024 dimensões, similar ao doc1
    results = client.query_vectors(
        query_vector=query_vector,
        top_k=3,
        namespace="demo",
        include_metadata=True
    )
    
    print(f"\n🔍 Resultados da busca (top 3):")
    for i, result in enumerate(results, 1):
        print(f"  {i}. ID: {result.id}")
        print(f"     Score: {result.score:.4f}")
        print(f"     Título: {result.metadata.get('title', 'N/A')}")
        print(f"     Categoria: {result.metadata.get('category', 'N/A')}")
        print()
    
    # Consulta com filtro
    filtered_results = client.query_vectors(
        query_vector=query_vector,
        top_k=10,
        namespace="demo",
        filter_dict={"category": "tecnologia"},
        include_metadata=True
    )
    
    print(f"🔍 Resultados filtrados (categoria=tecnologia): {len(filtered_results)}")
    for result in filtered_results:
        print(f"  - {result.metadata.get('title')} (score: {result.score:.4f})")
    
    # Estatísticas
    stats = client.get_index_stats()
    print(f"\n📊 Estatísticas do índice:")
    print(f"  Total de vetores: {stats.get('total_vector_count', 0)}")
    print(f"  Dimensão: {stats.get('dimension', 0)}")
    print(f"  Namespaces: {list(stats.get('namespaces', {}).keys())}")
    
    # Health check
    health = client.health_check()
    print(f"\n🏥 Status de saúde:")
    print(f"  Operacional: {health.get('operational', False)}")
    print(f"  Modo mock: {health.get('mock_mode', False)}")
    print(f"  Conectado: {health.get('connected', False)}")


def demo_index_manager():
    """Demonstra uso do gerenciador de índices."""
    print("\n🔹 DEMO 2: Gerenciador de Índices")
    print("=" * 50)
    
    # Cria gerenciador
    manager = create_index_manager(
        api_key=os.getenv("PINECONE_API_KEY", "demo-mock-key"),
        project_prefix="demo-rag"
    )
    print("✅ Gerenciador criado")
    
    # Configura ambiente com diferentes tipos de índice
    index_types = [IndexType.DOCUMENTS, IndexType.CODE]
    setup_status = manager.setup_complete_environment(index_types)
    
    print(f"\n🏗️ Setup do ambiente:")
    for index_type, success in setup_status.items():
        status = "✅" if success else "❌"
        print(f"  {status} {index_type.value}: {success}")
    
    # Demonstra uso de diferentes tipos
    print(f"\n📚 Usando índice de DOCUMENTOS:")
    docs_client = manager.get_client(IndexType.DOCUMENTS)
    if docs_client:
        # Dados de exemplo para documentos
        doc_vectors = [
            VectorRecord(
                id="report1",
                vector=[0.1] * 768,  # Vetor de 768 dimensões (padrão)
                metadata={
                    "document_type": "report",
                    "category": "financial",
                    "title": "Relatório Financeiro Q1",
                    "author": "Equipe Financeira"
                }
            ),
            VectorRecord(
                id="manual1",
                vector=[0.2] * 768,
                metadata={
                    "document_type": "manual",
                    "category": "technical",
                    "title": "Manual do Usuário",
                    "author": "Equipe Técnica"
                }
            )
        ]
        
        success = docs_client.upsert_vectors(doc_vectors, namespace="documents")
        print(f"  ✅ Inseridos {len(doc_vectors)} documentos: {success}")
        
        # Busca em documentos
        results = docs_client.query_vectors(
            query_vector=[0.15] * 768,
            top_k=2,
            namespace="documents",
            filter_dict={"document_type": "report"},
            include_metadata=True
        )
        print(f"  🔍 Encontrados {len(results)} relatórios similares")
    
    print(f"\n💻 Usando índice de CÓDIGO:")
    code_client = manager.get_client(IndexType.CODE)
    if code_client:
        # Dados de exemplo para código
        code_vectors = [
            VectorRecord(
                id="func1",
                vector=[0.3] * 768,
                metadata={
                    "language": "python",
                    "function_type": "utility",
                    "file_path": "utils/helpers.py",
                    "line_numbers": "10-25"
                }
            ),
            VectorRecord(
                id="class1",
                vector=[0.4] * 768,
                metadata={
                    "language": "python",
                    "function_type": "class",
                    "file_path": "models/user.py",
                    "line_numbers": "1-50"
                }
            )
        ]
        
        success = code_client.upsert_vectors(code_vectors, namespace="code")
        print(f"  ✅ Inseridos {len(code_vectors)} trechos de código: {success}")
        
        # Busca em código
        results = code_client.query_vectors(
            query_vector=[0.35] * 768,
            top_k=2,
            namespace="code",
            filter_dict={"language": "python"},
            include_metadata=True
        )
        print(f"  🔍 Encontrados {len(results)} trechos de Python similares")
    
    # Recomendação automática de tipo
    print(f"\n🤖 Recomendação automática de tipos:")
    test_descriptions = [
        "Python functions and classes in a repository",
        "PDF documents with financial reports",
        "Images with object detection metadata",
        "Audio transcripts from meetings",
        "Mixed content including text and images"
    ]
    
    for desc in test_descriptions:
        recommended = manager.get_recommended_type(desc)
        print(f"  '{desc}' → {recommended.value}")
    
    # Estatísticas gerais
    print(f"\n📊 Estatísticas gerais:")
    all_stats = manager.get_all_stats()
    
    for index_type, stats in all_stats.items():
        print(f"  {index_type.value}:")
        if "error" in stats:
            print(f"    ❌ Erro: {stats['error']}")
        else:
            index_stats = stats.get("index_stats", {})
            print(f"    Vetores: {index_stats.get('total_vector_count', 0)}")
            print(f"    Dimensão: {index_stats.get('dimension', 0)}")
    
    # Health check geral
    health = manager.health_check_all()
    print(f"\n🏥 Status de saúde geral:")
    print(f"  Clientes totais: {health['total_clients']}")
    print(f"  Clientes operacionais: {health['operational_clients']}")
    print(f"  Saúde geral: {health['overall_health']:.2%}")


def demo_advanced_features():
    """Demonstra funcionalidades avançadas."""
    print("\n🔹 DEMO 3: Funcionalidades Avançadas")
    print("=" * 50)
    
    # Cria cliente usando o índice existente
    config = PineconeConfig(
        api_key=os.getenv("PINECONE_API_KEY"),
        index_name="rag-documentos",  # Usar o índice existente
        dimension=1024,  # Dimensão do índice existente
        metric="cosine",
        region="us-east-1"
    )
    
    client = create_pinecone_client(config)
    connected = client.connect_to_index("rag-documentos")
    
    if not connected:
        print("❌ Não foi possível conectar ao índice existente")
        return
    
    # Dados com metadados ricos (vetores de 1024 dimensões)
    random.seed(42)  # Para resultados reproduzíveis
    
    vectors = [
        VectorRecord(
            id=f"demo_item_{i}",
            vector=[random.random() for _ in range(1024)],  # 1024 dimensões aleatórias
            metadata={
                "index": i,
                "category": "A" if i % 2 == 0 else "B",
                "score": i * 0.1,
                "tags": ["tag1", "tag2"] if i < 5 else ["tag3", "tag4"],
                "created_at": f"2024-01-{i+1:02d}",
                "is_active": True
            }
        )
        for i in range(10)
    ]
    
    # Insere em lotes
    batch_size = 3
    total_inserted = 0
    
    print(f"📦 Inserindo {len(vectors)} vetores em lotes de {batch_size}:")
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i+batch_size]
        success = client.upsert_vectors(batch, namespace="advanced")
        if success:
            total_inserted += len(batch)
            print(f"  ✅ Lote {i//batch_size + 1}: {len(batch)} vetores")
    
    print(f"Total inserido: {total_inserted} vetores")
    
    # Consultas avançadas com filtros complexos
    print(f"\n🔍 Consultas avançadas:")
    
    # Filtro por categoria
    results = client.query_vectors(
        query_vector=[random.random() for _ in range(1024)],  # 1024 dimensões
        top_k=5,
        namespace="advanced",
        filter_dict={"category": "A"},
        include_metadata=True
    )
    print(f"  Categoria A: {len(results)} resultados")
    
    # Consulta com múltiplos vetores de query (1024 dimensões)
    query_vectors = [
        [random.random() for _ in range(1024)],
        [random.random() for _ in range(1024)]
    ]
    
    for i, qv in enumerate(query_vectors):
        results = client.query_vectors(
            query_vector=qv,
            top_k=3,
            namespace="advanced",
            include_metadata=True
        )
        # Corrige divisão por zero
        avg_score = sum(r.score for r in results) / len(results) if results else 0.0
        print(f"  Query {i+1}: {len(results)} resultados (média score: {avg_score:.4f})")
    
    # Métricas de performance
    print(f"\n📈 Métricas de performance:")
    
    # Gera algumas operações para métricas
    for _ in range(3):
        client.query_vectors([random.random() for _ in range(1024)], top_k=2, namespace="advanced")
    
    # Obtém métricas
    metrics = client.get_metrics(operation_type="query", last_hours=1)
    print(f"  Queries realizadas: {len(metrics)}")
    
    if metrics:
        avg_duration = sum(m.duration for m in metrics) / len(metrics)
        success_rate = sum(1 for m in metrics if m.success) / len(metrics)
        print(f"  Duração média: {avg_duration:.4f}s")
        print(f"  Taxa de sucesso: {success_rate:.2%}")
    
    # Summary de performance
    summary = client.get_performance_summary()
    if summary and "message" not in summary:
        print(f"  Resumo de performance:")
        for op_type, stats in summary.items():
            print(f"    {op_type}: {stats['total_operations']} ops, "
                  f"{stats['success_rate']:.2%} sucesso, "
                  f"{stats['average_duration']:.4f}s média")
    
    # Operações de limpeza
    print(f"\n🧹 Operações de limpeza:")
    
    # Remove alguns vetores específicos
    ids_to_delete = ["item_0", "item_1", "item_2"]
    success = client.delete_vectors(ids_to_delete, namespace="advanced")
    print(f"  ✅ Removidos {len(ids_to_delete)} vetores: {success}")
    
    # Estatísticas finais
    final_stats = client.get_index_stats()
    print(f"  📊 Estatísticas finais:")
    print(f"    Total de vetores: {final_stats.get('total_vector_count', 0)}")
    
    # Export de dados (só no modo mock)
    if client._mock_mode:
        print(f"\n💾 Export de dados mock:")
        export_path = "/tmp/demo_export.json"
        success = client.export_mock_data(export_path)
        if success and os.path.exists(export_path):
            file_size = os.path.getsize(export_path)
            print(f"  ✅ Dados exportados para {export_path} ({file_size} bytes)")
            
            # Cleanup
            os.unlink(export_path)
            print(f"  🗑️ Arquivo temporário removido")


def main():
    """Executa todas as demonstrações."""
    print("🚀 DEMONSTRAÇÃO DO SISTEMA PINECONE RAG")
    print("=" * 60)
    
    print("Este demo mostra como usar o sistema completo de banco de dados")
    print("vetorial com Pinecone para aplicações RAG (Retrieval-Augmented Generation).")
    print()
    
    # Verifica se há API key real
    has_api_key = bool(os.getenv("PINECONE_API_KEY"))
    if has_api_key:
        print("🔑 API Key do Pinecone detectada - operações reais serão executadas")
    else:
        print("🎭 Sem API Key - executando em modo mock (demonstração)")
    print()
    
    try:
        # Executa demos
        demo_basic_client()
        demo_index_manager()
        demo_advanced_features()
        
        print("\n" + "=" * 60)
        print("✅ TODAS AS DEMONSTRAÇÕES CONCLUÍDAS COM SUCESSO!")
        print()
        print("📚 Para usar em produção:")
        print("  1. Configure PINECONE_API_KEY com sua chave real")
        print("  2. Ajuste as configurações de dimensão conforme seu modelo de embeddings")
        print("  3. Use IndexManager para gerenciar múltiplos tipos de conteúdo")
        print("  4. Monitore métricas de performance regularmente")
        print()
        print("🔗 Documentação completa em: src/vector_db/")
        
    except Exception as e:
        print(f"\n❌ Erro durante a demonstração: {e}")
        logger.exception("Erro detalhado:")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 