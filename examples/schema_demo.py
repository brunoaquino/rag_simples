#!/usr/bin/env python3
"""
Demonstração dos Schemas de Índices Pinecone
Mostra como usar o sistema de schemas para definir e validar índices.
"""

import os
import sys
import json
from typing import Dict, Any

# Adiciona src ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from vector_db.schemas import (
    SchemaRegistry,
    IndexEnvironment,
    EmbeddingModel,
    validate_schema,
    get_embedding_dimensions,
    create_migration_plan,
    IndexSchema,
    MetadataField
)


def print_separator(title: str):
    """Imprime separador com título."""
    print(f"\n{'='*60}")
    print(f"🔹 {title}")
    print("="*60)


def demo_schema_registry():
    """Demonstra o uso do registro de schemas."""
    print_separator("DEMO 1: Registro de Schemas")
    
    # Lista todos os schemas disponíveis
    environments = [IndexEnvironment.DEVELOPMENT, IndexEnvironment.STAGING, IndexEnvironment.PRODUCTION]
    
    for env in environments:
        print(f"\n📊 Ambiente: {env.value.upper()}")
        schemas = SchemaRegistry.get_all_schemas(env)
        
        for schema in schemas:
            print(f"  ✅ {schema.name}")
            print(f"     📏 Dimensões: {schema.dimension}")
            print(f"     📊 Modelo: {schema.embedding_model.value}")
            print(f"     📋 Metadados: {len(schema.metadata_fields)} campos")
            print(f"     🔖 Namespaces: {', '.join(schema.namespaces)}")


def demo_specific_schemas():
    """Demonstra schemas específicos em detalhes."""
    print_separator("DEMO 2: Schemas Específicos")
    
    # Schema de documentos RAG
    doc_schema = SchemaRegistry.get_rag_documents_schema(IndexEnvironment.PRODUCTION)
    print(f"📋 Schema: {doc_schema.name}")
    print(f"📝 Descrição: {doc_schema.description}")
    print(f"📏 Dimensões: {doc_schema.dimension}")
    print(f"📊 Métrica: {doc_schema.metric}")
    
    print(f"\n🏷️  Campos de Metadados ({len(doc_schema.metadata_fields)}):")
    for field in doc_schema.metadata_fields[:10]:  # Mostra só os primeiros 10
        required = "🔴" if field.required else "🟡"
        indexed = "📇" if field.indexed else "📄"
        print(f"  {required} {indexed} {field.name}: {field.type} - {field.description}")
    
    if len(doc_schema.metadata_fields) > 10:
        print(f"  ... e mais {len(doc_schema.metadata_fields) - 10} campos")
    
    # Configuração Pinecone
    print(f"\n⚙️  Configuração Pinecone:")
    pinecone_spec = doc_schema.get_pinecone_spec()
    for key, value in pinecone_spec.items():
        print(f"  {key}: {value}")


def demo_validation():
    """Demonstra validação de schemas."""
    print_separator("DEMO 3: Validação de Schemas")
    
    # Schema válido
    valid_schema = SchemaRegistry.get_code_schema()
    errors = validate_schema(valid_schema)
    print(f"✅ Schema válido '{valid_schema.name}': {len(errors)} erros")
    
    # Schema inválido (dimensão incompatível)
    invalid_schema = IndexSchema(
        name="teste-invalido",
        description="Schema inválido para teste",
        dimension=512,  # Incompatível com E5_LARGE_V2
        metric="cosine",
        embedding_model=EmbeddingModel.E5_LARGE_V2,
        metadata_fields=[
            MetadataField("id", "string", "ID", required=True),
            MetadataField("id", "number", "Outro ID", required=True)  # Nome duplicado
        ]
    )
    
    errors = validate_schema(invalid_schema)
    print(f"\n❌ Schema inválido '{invalid_schema.name}': {len(errors)} erros")
    for i, error in enumerate(errors, 1):
        print(f"  {i}. {error}")


def demo_embedding_models():
    """Demonstra informações sobre modelos de embedding."""
    print_separator("DEMO 4: Modelos de Embedding")
    
    print("📊 Modelos Suportados:")
    for model in EmbeddingModel:
        dimensions = get_embedding_dimensions(model)
        provider = "🤗 Hugging Face" if "intfloat" in model.value or "BAAI" in model.value else "🤖 OpenAI"
        if "custom" in model.value.lower():
            provider = "⚙️ Custom"
        
        print(f"  {provider}")
        print(f"    📝 Modelo: {model.value}")
        print(f"    📏 Dimensões: {dimensions}")
        print(f"    🎯 Recomendado: {'✅' if dimensions == 1024 else '⚠️'}")
        print()


def demo_migration_planning():
    """Demonstra planejamento de migrações."""
    print_separator("DEMO 5: Planejamento de Migrações")
    
    # Schema antigo (simplificado)
    old_schema = IndexSchema(
        name="rag-documents-old",
        description="Schema antigo",
        dimension=768,
        metric="cosine",
        embedding_model=EmbeddingModel.CUSTOM_1024,  # Inconsistente intencionalmente
        metadata_fields=[
            MetadataField("id", "string", "ID", required=True),
            MetadataField("title", "string", "Título"),
            MetadataField("old_field", "string", "Campo antigo")
        ],
        namespaces=["default", "old_namespace"]
    )
    
    # Schema novo
    new_schema = SchemaRegistry.get_rag_documents_schema()
    
    # Plano de migração
    migration_plan = create_migration_plan(old_schema, new_schema)
    
    print("📋 Plano de Migração:")
    print(f"  🔄 Requer reindexação: {'✅ Sim' if migration_plan['requires_reindex'] else '❌ Não'}")
    print(f"  📏 Mudança de dimensão: {'✅' if migration_plan['dimension_change'] else '❌'}")
    print(f"  📊 Mudança de métrica: {'✅' if migration_plan['metric_change'] else '❌'}")
    
    if migration_plan['new_fields']:
        print(f"\n➕ Novos campos ({len(migration_plan['new_fields'])}):")
        for field in migration_plan['new_fields'][:5]:  # Mostra só os primeiros 5
            print(f"    + {field}")
        if len(migration_plan['new_fields']) > 5:
            print(f"    ... e mais {len(migration_plan['new_fields']) - 5} campos")
    
    if migration_plan['removed_fields']:
        print(f"\n➖ Campos removidos:")
        for field in migration_plan['removed_fields']:
            print(f"    - {field}")
    
    namespace_changes = migration_plan['namespace_changes']
    if namespace_changes['added'] or namespace_changes['removed']:
        print(f"\n🔖 Mudanças em Namespaces:")
        for ns in namespace_changes['added']:
            print(f"    + {ns}")
        for ns in namespace_changes['removed']:
            print(f"    - {ns}")


def demo_custom_schema():
    """Demonstra criação de schema customizado."""
    print_separator("DEMO 6: Schema Customizado")
    
    # Cria schema para e-commerce
    ecommerce_schema = IndexSchema(
        name="rag-ecommerce-development",
        description="Índice para produtos de e-commerce",
        dimension=1024,
        metric="cosine",
        embedding_model=EmbeddingModel.MULTILINGUAL_E5_LARGE,
        metadata_fields=[
            MetadataField("product_id", "string", "ID do produto", required=True),
            MetadataField("name", "string", "Nome do produto", required=True),
            MetadataField("category", "string", "Categoria do produto"),
            MetadataField("brand", "string", "Marca do produto"),
            MetadataField("price", "number", "Preço do produto"),
            MetadataField("discount", "number", "Desconto aplicado"),
            MetadataField("in_stock", "boolean", "Se está em estoque"),
            MetadataField("tags", "list", "Tags do produto"),
            MetadataField("description", "string", "Descrição detalhada"),
            MetadataField("specifications", "string", "Especificações técnicas"),
            MetadataField("rating", "number", "Avaliação média"),
            MetadataField("review_count", "number", "Número de avaliações"),
            MetadataField("created_at", "string", "Data de criação"),
            MetadataField("updated_at", "string", "Data de atualização")
        ],
        namespaces=["electronics", "clothing", "books", "home", "sports"]
    )
    
    print(f"🛒 Schema E-commerce: {ecommerce_schema.name}")
    print(f"📝 Descrição: {ecommerce_schema.description}")
    
    # Valida o schema
    errors = validate_schema(ecommerce_schema)
    print(f"\n✅ Validação: {len(errors)} erros")
    
    # Mostra configuração de metadados
    metadata_config = ecommerce_schema.get_metadata_config()
    print(f"\n📋 Configuração de Metadados:")
    for field_name, config in list(metadata_config.items())[:5]:  # Primeiros 5
        print(f"  {field_name}:")
        print(f"    tipo: {config['type']}")
        print(f"    obrigatório: {config['required']}")
        print(f"    indexado: {config['indexed']}")


def demo_json_export():
    """Demonstra exportação de schemas para JSON."""
    print_separator("DEMO 7: Exportação JSON")
    
    # Obtém schema de documentos
    schema = SchemaRegistry.get_rag_documents_schema(IndexEnvironment.PRODUCTION)
    
    # Converte para dict (simulando serialização JSON)
    schema_dict = {
        "name": schema.name,
        "description": schema.description,
        "dimension": schema.dimension,
        "metric": schema.metric,
        "embedding_model": schema.embedding_model.value,
        "cloud": schema.cloud,
        "region": schema.region,
        "serverless": schema.serverless,
        "namespaces": schema.namespaces,
        "metadata_fields": [
            {
                "name": field.name,
                "type": field.type,
                "description": field.description,
                "required": field.required,
                "indexed": field.indexed
            }
            for field in schema.metadata_fields
        ],
        "pinecone_spec": schema.get_pinecone_spec(),
        "metadata_config": schema.get_metadata_config()
    }
    
    print("📄 Schema exportado para JSON:")
    print(json.dumps({
        "name": schema_dict["name"],
        "description": schema_dict["description"],
        "dimension": schema_dict["dimension"],
        "metric": schema_dict["metric"],
        "embedding_model": schema_dict["embedding_model"],
        "total_metadata_fields": len(schema_dict["metadata_fields"]),
        "namespaces": schema_dict["namespaces"]
    }, indent=2, ensure_ascii=False))


def main():
    """Executa todas as demonstrações."""
    print("🚀 Sistema de Schemas Pinecone - Demonstração Completa")
    print("=" * 60)
    
    try:
        demo_schema_registry()
        demo_specific_schemas()
        demo_validation()
        demo_embedding_models()
        demo_migration_planning()
        demo_custom_schema()
        demo_json_export()
        
        print_separator("RESUMO")
        print("✅ Todas as demonstrações executadas com sucesso!")
        print("\n📊 Recursos demonstrados:")
        print("  🏗️  Sistema de registro de schemas")
        print("  📋 Schemas pré-definidos para diferentes casos de uso")
        print("  ✅ Validação automática de configurações")
        print("  🤖 Suporte a múltiplos modelos de embedding")
        print("  🔄 Planejamento de migrações")
        print("  ⚙️  Criação de schemas customizados")
        print("  📄 Exportação para JSON")
        
        print("\n🎯 Próximos passos recomendados:")
        print("  1. Implementar criação automática de índices usando schemas")
        print("  2. Integrar com sistema de embeddings")
        print("  3. Adicionar monitoramento e métricas")
        print("  4. Implementar sistema de backup/restore")
        
    except Exception as e:
        print(f"\n❌ Erro na demonstração: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 