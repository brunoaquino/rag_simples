"""
Sistema RAG Empresarial - Interface Streamlit
Interface principal para upload e processamento de documentos.
"""

import streamlit as st
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import time
import json
import hashlib
import sys

# Adiciona o diretório raiz do projeto ao Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Imports dos componentes de ingestão
from src.ingestion import (
    IngestionPipeline, 
    IngestionConfig,
    IngestionResult
)

# Configuração da página - DEVE SER A PRIMEIRA CHAMADA STREAMLIT
st.set_page_config(
    page_title="RAG Simples - Ingestão de Documentos",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Inicializa o estado da sessão."""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'chunk_settings' not in st.session_state:
        st.session_state.chunk_settings = {
            'chunk_size': 1000,
            'chunk_overlap': 200,
            'chunking_strategy': 'fixed_size'
        }

def render_sidebar():
    """Renderiza a barra lateral com configurações."""
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        st.subheader("📄 Chunking")
        chunk_size = st.slider(
            "Tamanho do chunk (caracteres)",
            min_value=100,
            max_value=2000,
            value=st.session_state.chunk_settings['chunk_size'],
            step=100,
            help="Número de caracteres por chunk"
        )
        
        chunk_overlap = st.slider(
            "Sobreposição (caracteres)",
            min_value=0,
            max_value=500,
            value=st.session_state.chunk_settings['chunk_overlap'],
            step=50,
            help="Número de caracteres de sobreposição entre chunks"
        )
        
        chunking_strategy = st.selectbox(
            "Estratégia de chunking",
            ['fixed_size', 'by_paragraph', 'by_sentence'],
            index=0,
            help="Método para dividir os documentos"
        )
        
        # Atualiza configurações na sessão
        st.session_state.chunk_settings.update({
            'chunk_size': chunk_size,
            'chunk_overlap': chunk_overlap,
            'chunking_strategy': chunking_strategy
        })
        
        st.subheader("🏷️ Metadados")
        category = st.selectbox(
            "Categoria",
            ["Documentos Gerais", "Políticas", "Procedimentos", "Manuais", "Relatórios"],
            help="Categoria do documento para organização"
        )
        
        department = st.selectbox(
            "Departamento",
            ["TI", "RH", "Financeiro", "Jurídico", "Operações", "Marketing"],
            help="Departamento responsável pelo documento"
        )
        
        tags = st.text_input(
            "Tags (separadas por vírgula)",
            placeholder="ex: política, segurança, procedimento",
            help="Tags para facilitar a busca"
        )
        
        return {
            'category': category,
            'department': department,
            'tags': [tag.strip() for tag in tags.split(',') if tag.strip()]
        }

def render_file_upload():
    """Renderiza a seção de upload de arquivos."""
    st.header("📁 Upload de Documentos")
    
    uploaded_files = st.file_uploader(
        "Escolha os arquivos",
        type=['pdf', 'docx', 'txt', 'md'],
        accept_multiple_files=True,
        help="Formatos suportados: PDF, DOCX, TXT, MD"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s)")
        
        # Exibe informações dos arquivos
        for i, file in enumerate(uploaded_files):
            with st.expander(f"📄 {file.name} ({file.size} bytes)", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Tipo:**", file.type)
                
                with col2:
                    st.write("**Tamanho:**", f"{file.size / 1024:.1f} KB")
                
                with col3:
                    st.write("**Status:**", "Pronto para processar")
    
    return uploaded_files

def get_file_preview(file) -> str:
    """Retorna uma prévia do conteúdo do arquivo."""
    try:
        if file.type == "text/plain":
            content = str(file.read(), "utf-8")
            return content[:500] + "..." if len(content) > 500 else content
        elif file.type == "text/markdown":
            content = str(file.read(), "utf-8")
            return content[:500] + "..." if len(content) > 500 else content
        else:
            return "Prévia não disponível para este tipo de arquivo"
    except Exception as e:
        return f"Erro ao ler arquivo: {str(e)}"
    finally:
        # Reset file pointer
        file.seek(0)

def render_processing_section(uploaded_files, metadata_config):
    """Renderiza a seção de processamento."""
    if not uploaded_files:
        st.info("📤 Faça upload de arquivos para começar o processamento")
        return
    
    st.header("⚙️ Processamento")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Resumo da Configuração")
        
        config_data = {
            "Arquivos": len(uploaded_files),
            "Tamanho do chunk": f"{st.session_state.chunk_settings['chunk_size']} caracteres",
            "Sobreposição": f"{st.session_state.chunk_settings['chunk_overlap']} caracteres",
            "Estratégia": st.session_state.chunk_settings['chunking_strategy'],
            "Categoria": metadata_config['category'],
            "Departamento": metadata_config['department'],
            "Tags": ", ".join(metadata_config['tags']) if metadata_config['tags'] else "Nenhuma"
        }
        
        for key, value in config_data.items():
            st.write(f"**{key}:** {value}")
    
    with col2:
        st.subheader("🚀 Ações")
        
        if st.button("🔄 Processar Documentos", type="primary", use_container_width=True):
            process_documents(uploaded_files, metadata_config)
        
        if st.button("👀 Prévia do Processamento", use_container_width=True):
            show_processing_preview(uploaded_files)

def process_documents(uploaded_files, metadata_config):
    """Processa os documentos carregados."""
    st.subheader("📊 Status do Processamento")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_files = len(uploaded_files)
    
    for i, file in enumerate(uploaded_files):
        # Atualiza status
        status_text.text(f"Processando {file.name}...")
        progress = (i + 1) / total_files
        progress_bar.progress(progress)
        
        # Simula processamento (aqui seria chamado o pipeline real)
        time.sleep(1)  # Simula tempo de processamento
        
        # Salva informações do processamento
        st.session_state.processing_status[file.name] = {
            'status': 'completed',
            'timestamp': datetime.now(),
            'metadata': metadata_config,
            'chunk_settings': st.session_state.chunk_settings.copy()
        }
    
    status_text.text("✅ Processamento concluído!")
    st.success(f"🎉 {total_files} arquivo(s) processado(s) com sucesso!")
    
    # Exibe resumo dos resultados
    render_results_summary()

def show_processing_preview(uploaded_files):
    """Mostra uma prévia do que será processado."""
    st.subheader("👀 Prévia do Processamento")
    
    for file in uploaded_files[:2]:  # Mostra apenas os primeiros 2 arquivos
        with st.expander(f"📄 Prévia: {file.name}"):
            preview = get_file_preview(file)
            st.text_area(
                "Conteúdo (primeiros 500 caracteres):",
                preview,
                height=150,
                disabled=True
            )
            
            # Simula chunks
            st.write("**Chunks estimados:**")
            chunk_size = st.session_state.chunk_settings['chunk_size']
            estimated_chunks = max(1, len(preview) // chunk_size)
            st.write(f"📊 Aproximadamente {estimated_chunks} chunk(s)")

def render_results_summary():
    """Renderiza o resumo dos resultados do processamento."""
    if not st.session_state.processing_status:
        return
    
    st.subheader("📈 Resultados do Processamento")
    
    processed_files = len(st.session_state.processing_status)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Arquivos Processados", processed_files)
    
    with col2:
        st.metric("Status", "✅ Completo")
    
    with col3:
        total_size = sum(
            len(get_file_preview(file)) 
            for file in st.session_state.get('uploaded_files', [])
        )
        st.metric("Dados Processados", f"{total_size} chars")
    
    # Tabela de arquivos processados
    if st.checkbox("🗂️ Mostrar detalhes dos arquivos"):
        for filename, info in st.session_state.processing_status.items():
            with st.expander(f"📄 {filename}"):
                st.write(f"**Status:** {info['status']}")
                st.write(f"**Processado em:** {info['timestamp'].strftime('%d/%m/%Y %H:%M:%S')}")
                st.write(f"**Categoria:** {info['metadata']['category']}")
                st.write(f"**Departamento:** {info['metadata']['department']}")
                if info['metadata']['tags']:
                    st.write(f"**Tags:** {', '.join(info['metadata']['tags'])}")

class DocumentIngestionInterface:
    """Interface principal para ingestão de documentos."""
    
    def __init__(self):
        """Inicializa a interface."""
        self.setup_pipeline()
        
    def setup_pipeline(self):
        """Configura o pipeline de ingestão."""
        # Configuração do pipeline
        self.config = IngestionConfig(
            chunk_size=1000,
            chunk_overlap=200,
            chunking_strategy='fixed_size',
            min_chunk_size=100,
            storage_path="data/versions",
            enable_versioning=True,
            enable_deduplication=True,
            archive_old_versions=True,
            max_versions_per_document=5
        )
        
        # Inicializa pipeline
        if 'pipeline' not in st.session_state:
            st.session_state.pipeline = IngestionPipeline(self.config)
        
        self.pipeline = st.session_state.pipeline
    
    def render_sidebar(self):
        """Renderiza a barra lateral com configurações."""
        st.sidebar.title("⚙️ Configurações")
        
        # Configurações de chunking
        st.sidebar.subheader("📝 Chunking")
        
        chunk_strategy = st.sidebar.selectbox(
            "Estratégia de Chunking",
            options=['fixed_size', 'by_paragraph', 'by_sentence'],
            index=['fixed_size', 'by_paragraph', 'by_sentence'].index(self.config.chunking_strategy)
        )
        
        chunk_size = st.sidebar.slider(
            "Tamanho do Chunk",
            min_value=200,
            max_value=2000,
            value=self.config.chunk_size,
            step=100
        )
        
        chunk_overlap = st.sidebar.slider(
            "Sobreposição do Chunk",
            min_value=0,
            max_value=500,
            value=self.config.chunk_overlap,
            step=50
        )
        
        # Configurações de versionamento
        st.sidebar.subheader("📦 Versionamento")
        
        enable_versioning = st.sidebar.checkbox(
            "Habilitar Versionamento",
            value=self.config.enable_versioning
        )
        
        enable_deduplication = st.sidebar.checkbox(
            "Detecção de Duplicados",
            value=self.config.enable_deduplication
        )
        
        max_versions = st.sidebar.slider(
            "Máximo de Versões por Documento",
            min_value=1,
            max_value=10,
            value=self.config.max_versions_per_document
        )
        
        # Atualiza configuração se houve mudanças
        new_config = IngestionConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_strategy=chunk_strategy,
            min_chunk_size=self.config.min_chunk_size,
            storage_path=self.config.storage_path,
            enable_versioning=enable_versioning,
            enable_deduplication=enable_deduplication,
            archive_old_versions=self.config.archive_old_versions,
            max_versions_per_document=max_versions
        )
        
        if (new_config.chunk_size != self.config.chunk_size or
            new_config.chunk_overlap != self.config.chunk_overlap or
            new_config.chunking_strategy != self.config.chunking_strategy or
            new_config.enable_versioning != self.config.enable_versioning or
            new_config.enable_deduplication != self.config.enable_deduplication or
            new_config.max_versions_per_document != self.config.max_versions_per_document):
            
            self.config = new_config
            st.session_state.pipeline = IngestionPipeline(self.config)
            self.pipeline = st.session_state.pipeline
            st.rerun()
        
        # Estatísticas do pipeline
        st.sidebar.subheader("📊 Estatísticas")
        stats = self.pipeline.get_processing_statistics()
        
        st.sidebar.write(f"**Estratégia atual:** {stats['chunking_strategy']}")
        st.sidebar.write(f"**Versionamento:** {'✅' if stats['versioning_enabled'] else '❌'}")
        
        if 'version_statistics' in stats:
            version_stats = stats['version_statistics']
            st.sidebar.write(f"**Documentos:** {version_stats['total_documents']}")
            st.sidebar.write(f"**Versões:** {version_stats['total_versions']}")
            st.sidebar.write(f"**Taxa de processamento:** {version_stats['processing_rate']:.1%}")
    
    def render_file_upload(self):
        """Renderiza a seção de upload de arquivos."""
        st.header("📤 Upload de Documentos")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_files = st.file_uploader(
                "Selecione os documentos para ingestão",
                type=['txt', 'md', 'pdf', 'docx'],
                accept_multiple_files=True,
                help="Formatos suportados: TXT, MD, PDF, DOCX"
            )
        
        with col2:
            st.subheader("🏷️ Metadados")
            category = st.selectbox(
                "Categoria",
                options=["Documentação", "Manual", "Relatório", "Política", "Procedimento", "Outro"]
            )
            
            department = st.selectbox(
                "Departamento",
                options=["TI", "RH", "Financeiro", "Operações", "Vendas", "Marketing", "Legal"]
            )
            
            tags = st.text_input(
                "Tags (separadas por vírgula)",
                placeholder="exemplo, documento, importante"
            )
            
            priority = st.selectbox(
                "Prioridade",
                options=["Alta", "Média", "Baixa"],
                index=1
            )
        
        if uploaded_files:
            user_metadata = {
                'category': category,
                'department': department,
                'tags': [tag.strip() for tag in tags.split(',') if tag.strip()],
                'priority': priority.lower()
            }
            
            return uploaded_files, user_metadata
        
        return None, None
    
    def render_processing_results(self, results: List[IngestionResult]):
        """Renderiza os resultados do processamento."""
        if not results:
            return
            
        st.header("📋 Resultados do Processamento")
        
        # Estatísticas gerais
        total_files = len(results)
        successful_files = sum(1 for r in results if r.success)
        failed_files = total_files - successful_files
        total_chunks = sum(len(r.chunks) for r in results)
        total_time = sum(r.processing_time for r in results)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📁 Arquivos", total_files)
        
        with col2:
            st.metric("✅ Sucessos", successful_files)
        
        with col3:
            st.metric("❌ Falhas", failed_files)
        
        with col4:
            st.metric("🧩 Chunks", total_chunks)
        
        st.metric("⏱️ Tempo Total", f"{total_time:.2f}s")
        
        # Detalhes de cada arquivo
        for i, result in enumerate(results):
            with st.expander(f"📄 Arquivo {i+1} - {'✅ Sucesso' if result.success else '❌ Erro'}"):
                
                if result.success:
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.write("**Informações Básicas:**")
                        if result.document_version:
                            st.write(f"- **ID da Versão:** `{result.document_version.version_id}`")
                            st.write(f"- **Nome do Arquivo:** {result.document_version.original_filename}")
                            st.write(f"- **Versão:** {result.document_version.version_number}")
                            st.write(f"- **Status:** {result.document_version.status.value}")
                            st.write(f"- **Tamanho:** {result.document_version.file_size} bytes")
                        
                        st.write(f"- **Chunks Gerados:** {len(result.chunks)}")
                        st.write(f"- **Tempo de Processamento:** {result.processing_time:.2f}s")
                    
                    with col2:
                        st.write("**Metadados Extraídos:**")
                        
                        # Metadados importantes
                        if 'emails' in result.metadata and result.metadata['emails']:
                            st.write(f"- **Emails:** {len(result.metadata['emails'])}")
                        
                        if 'phones' in result.metadata and result.metadata['phones']:
                            st.write(f"- **Telefones:** {len(result.metadata['phones'])}")
                        
                        if 'urls' in result.metadata and result.metadata['urls']:
                            st.write(f"- **URLs:** {len(result.metadata['urls'])}")
                        
                        if 'auto_category' in result.metadata:
                            st.write(f"- **Categoria Auto:** {result.metadata['auto_category']}")
                        
                        if 'language' in result.metadata:
                            st.write(f"- **Idioma:** {result.metadata['language']}")
                        
                        if 'word_count' in result.metadata:
                            st.write(f"- **Palavras:** {result.metadata['word_count']}")
                    
                    # Amostra de chunks
                    st.write("**Amostra de Chunks:**")
                    for j, chunk in enumerate(result.chunks[:3]):  # Mostra apenas os 3 primeiros
                        st.write(f"**Chunk {j+1}:** {chunk.text[:200]}{'...' if len(chunk.text) > 200 else ''}")
                    
                    if len(result.chunks) > 3:
                        st.write(f"... e mais {len(result.chunks) - 3} chunks")
                    
                    # Detalhes completos em JSON
                    if st.button(f"📄 Ver Detalhes Completos", key=f"details_{i}"):
                        st.json(result.to_dict())
                
                else:
                    st.error(f"**Erro:** {result.error_message}")
    
    def render_search_interface(self):
        """Renderiza a interface de busca de documentos."""
        st.header("🔍 Buscar Documentos")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_query = st.text_input(
                "Digite sua busca",
                placeholder="Ex: manual, procedimento, tecnologia..."
            )
        
        with col2:
            search_limit = st.number_input(
                "Limite de resultados",
                min_value=1,
                max_value=50,
                value=10
            )
        
        if search_query:
            with st.spinner("Buscando documentos..."):
                results = self.pipeline.search_documents(search_query, search_limit)
            
            if results:
                st.success(f"Encontrados {len(results)} documentos")
                
                for i, result in enumerate(results):
                    with st.expander(f"📄 {result['filename']} (Score: {result['score']:.1f})"):
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.write(f"**ID da Versão:** `{result['version_id']}`")
                            st.write(f"**Nome do Arquivo:** {result['filename']}")
                            st.write(f"**Score de Relevância:** {result['score']:.2f}")
                            st.write(f"**Criado em:** {result['created_at']}")
                        
                        with col2:
                            st.write("**Metadados:**")
                            metadata = result['metadata']
                            
                            if 'user_category' in metadata:
                                st.write(f"- **Categoria:** {metadata['user_category']}")
                            
                            if 'department' in metadata:
                                st.write(f"- **Departamento:** {metadata['department']}")
                            
                            if 'all_tags' in metadata and metadata['all_tags']:
                                st.write(f"- **Tags:** {', '.join(metadata['all_tags'][:5])}")
                            
                            if 'word_count' in metadata:
                                st.write(f"- **Palavras:** {metadata['word_count']}")
                        
                        # Botão para ver histórico
                        if st.button(f"📊 Ver Histórico", key=f"history_{i}"):
                            if result['version_id']:
                                # Extrai document_id da version_id
                                version_parts = result['version_id'].split('_')
                                if len(version_parts) >= 2:
                                    document_id = '_'.join(version_parts[:-1])
                                    history = self.pipeline.get_document_history(document_id)
                                    
                                    if history:
                                        st.write("**Histórico do Documento:**")
                                        st.write(f"- **Total de Versões:** {history['total_versions']}")
                                        
                                        if history['version_history']:
                                            st.write("**Versões:**")
                                            for version in history['version_history'][:5]:  # Mostra últimas 5
                                                st.write(f"  - {version['version_number']} ({version['status']}) - {version['created_at']}")
            else:
                st.warning("Nenhum documento encontrado para esta busca.")
    
    def render_documents_overview(self):
        """Renderiza uma visão geral dos documentos."""
        st.header("📚 Visão Geral dos Documentos")
        
        if not self.pipeline.version_manager:
            st.warning("Versionamento não está habilitado. Ative nas configurações para ver documentos.")
            return
        
        # Obtém estatísticas
        stats = self.pipeline.get_processing_statistics()
        
        if 'version_statistics' not in stats:
            st.info("Nenhum documento foi processado ainda. Faça upload de alguns documentos!")
            return
        
        version_stats = stats['version_statistics']
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📁 Total de Documentos", version_stats['total_documents'])
        
        with col2:
            st.metric("📦 Total de Versões", version_stats['total_versions'])
        
        with col3:
            st.metric("📊 Taxa de Processamento", f"{version_stats['processing_rate']:.1%}")
        
        with col4:
            storage_size = version_stats.get('total_storage_size', 0)
            storage_mb = storage_size / (1024 * 1024) if storage_size > 0 else 0
            st.metric("💾 Armazenamento", f"{storage_mb:.1f} MB")
        
        # Distribuição por status
        if 'status_distribution' in version_stats:
            st.subheader("📊 Distribuição por Status")
            status_dist = version_stats['status_distribution']
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("✅ Ativos", status_dist.get('active', 0))
            
            with col2:
                st.metric("📦 Arquivados", status_dist.get('archived', 0))
            
            with col3:
                st.metric("⚠️ Depreciados", status_dist.get('deprecated', 0))
        
        # Lista de documentos recentes
        st.subheader("📄 Documentos Recentes")
        
        # Obtém todas as versões e ordena por data
        all_versions = []
        for version in self.pipeline.version_manager.versions.values():
            all_versions.append(version)
        
        # Ordena por data de criação (mais recente primeiro)
        all_versions.sort(key=lambda v: v.created_at, reverse=True)
        
        # Mostra os 10 mais recentes
        for version in all_versions[:10]:
            with st.expander(f"📄 {version.original_filename} (v{version.version_number})"):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.write(f"**ID:** `{version.version_id}`")
                    st.write(f"**Status:** {version.status.value}")
                    st.write(f"**Tamanho:** {version.file_size} bytes")
                    st.write(f"**Criado:** {version.created_at}")
                
                with col2:
                    if version.metadata:
                        st.write("**Metadados:**")
                        
                        if 'user_category' in version.metadata:
                            st.write(f"- Categoria: {version.metadata['user_category']}")
                        
                        if 'department' in version.metadata:
                            st.write(f"- Departamento: {version.metadata['department']}")
                        
                        if 'word_count' in version.metadata:
                            st.write(f"- Palavras: {version.metadata['word_count']}")
                
                # Informações de processamento
                if version.processing_info:
                    st.write("**Processamento:**")
                    proc_info = version.processing_info
                    
                    if 'chunks_count' in proc_info:
                        st.write(f"- Chunks: {proc_info['chunks_count']}")
                    
                    if 'processing_time' in proc_info:
                        st.write(f"- Tempo: {proc_info['processing_time']:.2f}s")
    
    def run(self):
        """Executa a aplicação principal."""
        st.title("📄 RAG Simples - Sistema de Ingestão de Documentos")
        st.markdown("Sistema completo para processamento e ingestão de documentos com versionamento e chunking inteligente.")
        
        # Renderiza barra lateral
        self.render_sidebar()
        
        # Tabs principais
        tab1, tab2, tab3 = st.tabs(["📤 Upload", "🔍 Buscar", "📚 Documentos"])
        
        with tab1:
            # Upload e processamento
            uploaded_files, user_metadata = self.render_file_upload()
            
            if uploaded_files and user_metadata:
                if st.button("🚀 Processar Documentos", type="primary"):
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = []
                    
                    for i, uploaded_file in enumerate(uploaded_files):
                        # Atualiza progresso
                        progress = (i + 1) / len(uploaded_files)
                        progress_bar.progress(progress)
                        status_text.text(f"Processando {uploaded_file.name} ({i+1}/{len(uploaded_files)})")
                        
                        # Cria arquivo temporário
                        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        try:
                            # Processa arquivo
                            result = self.pipeline.ingest_file(tmp_file_path, user_metadata)
                            results.append(result)
                            
                        finally:
                            # Remove arquivo temporário
                            os.unlink(tmp_file_path)
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Mostra resultados
                    self.render_processing_results(results)
        
        with tab2:
            self.render_search_interface()
        
        with tab3:
            self.render_documents_overview()


def main():
    """Função principal da aplicação."""
    app = DocumentIngestionInterface()
    app.run()


if __name__ == "__main__":
    main() 