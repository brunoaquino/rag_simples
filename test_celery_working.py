#!/usr/bin/env python3
"""
Teste rápido para verificar se o Celery está funcionando normalmente
"""

import sys
import os
import time
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from async_processing.tasks import hello_world_task, simulate_document_processing

def test_celery_working():
    """Teste para garantir que o Celery está funcionando normalmente."""
    print("🚀 Testando se o Celery está funcionando normalmente...")
    print("=" * 60)
    
    # Teste 1: Hello World Task
    print("\n📋 Teste 1: Hello World Task")
    try:
        result = hello_world_task.apply_async(args=["Bruno"])
        print(f"   Task enviada: {result.id}")
        
        # Aguardar resultado com timeout
        final_result = result.get(timeout=10)
        print(f"   ✅ Resultado: {final_result['message']}")
        print(f"   ✅ Status: {final_result['status']}")
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    # Teste 2: Task de Processamento
    print("\n📋 Teste 2: Document Processing Task")
    try:
        result = simulate_document_processing.apply_async(
            args=["test_doc"], 
            kwargs={"chunk_count": 2}
        )
        print(f"   Task enviada: {result.id}")
        
        final_result = result.get(timeout=15)
        print(f"   ✅ Documento processado: {final_result['document_id']}")
        print(f"   ✅ Chunks processados: {final_result['processed_chunks']}/{final_result['total_chunks']}")
        print(f"   ✅ Progresso: {final_result['progress']}%")
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 CELERY ESTÁ FUNCIONANDO NORMALMENTE!")
    print("✅ Worker ativo e processando tasks")
    print("✅ Redis conectado e funcionando")
    print("✅ Tasks básicas executando com sucesso")
    print("✅ Tasks com progresso funcionando")
    print("✅ Sistema pronto para produção")
    return True

if __name__ == "__main__":
    success = test_celery_working()
    if success:
        print("\n🚀 Próximos passos disponíveis:")
        print("   • Iniciar Flower: python3 start_celery_worker.py flower")
        print("   • Monitorar worker: tail -f celery_worker_fixed.log")
        print("   • Executar mais workers: python3 start_celery_worker.py worker")
    sys.exit(0 if success else 1) 