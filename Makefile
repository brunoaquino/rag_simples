.PHONY: help install test lint format clean run-streamlit run-api docs check-env check-vars

# Variáveis
PYTHON = python
PIP = pip
VENV = venv
SRC_DIR = src
TESTS_DIR = tests

# Comando padrão
help:
	@echo "🚀 Sistema RAG Empresarial - Comandos Disponíveis:"
	@echo ""
	@echo "📦 Setup & Instalação:"
	@echo "  make install     - Instalar dependências"
	@echo "  make install-dev - Instalar dependências de desenvolvimento"
	@echo "  make clean       - Limpar arquivos temporários"
	@echo ""
	@echo "🧪 Testes & Qualidade:"
	@echo "  make test        - Executar todos os testes"
	@echo "  make test-unit   - Executar apenas testes unitários"
	@echo "  make test-cov    - Executar testes com cobertura"
	@echo "  make lint        - Verificar qualidade do código"
	@echo "  make format      - Formatar código automaticamente"
	@echo ""
	@echo "🔧 Ambiente & Configuração:"
	@echo "  make check-env   - Verificar dependências instaladas"
	@echo "  make check-vars  - Verificar variáveis de ambiente"
	@echo "  make setup-env   - Criar arquivo .env de exemplo"
	@echo ""
	@echo "🚀 Execução:"
	@echo "  make run-streamlit - Iniciar interface Streamlit"
	@echo "  make run-api       - Iniciar API FastAPI"
	@echo "  make run-dev       - Modo desenvolvimento (hot reload)"
	@echo ""
	@echo "📚 Documentação:"
	@echo "  make docs        - Gerar documentação"
	@echo "  make docs-serve  - Servir documentação localmente"

# Instalação
install:
	@echo "📦 Instalando dependências..."
	$(PIP) install -r requirements.txt

install-dev:
	@echo "📦 Instalando dependências de desenvolvimento..."
	$(PIP) install -r requirements/core.txt
	$(PIP) install -r requirements/ai.txt
	$(PIP) install -r requirements/web.txt
	$(PIP) install isort mypy flake8 coverage

# Testes
test:
	@echo "🧪 Executando todos os testes..."
	$(PYTHON) -m pytest $(TESTS_DIR) -v

test-unit:
	@echo "🧪 Executando testes unitários..."
	$(PYTHON) -m pytest $(TESTS_DIR) -v -m "unit"

test-cov:
	@echo "🧪 Executando testes com cobertura..."
	$(PYTHON) -m pytest $(TESTS_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term

# Qualidade de código
lint:
	@echo "🔍 Verificando qualidade do código..."
	$(PYTHON) -m flake8 $(SRC_DIR) $(TESTS_DIR)
	$(PYTHON) -m mypy $(SRC_DIR)
	$(PYTHON) -m black --check $(SRC_DIR) $(TESTS_DIR)
	$(PYTHON) -m isort --check-only $(SRC_DIR) $(TESTS_DIR)

format:
	@echo "✨ Formatando código..."
	$(PYTHON) -m black $(SRC_DIR) $(TESTS_DIR)
	$(PYTHON) -m isort $(SRC_DIR) $(TESTS_DIR)

# Verificações de ambiente
check-env:
	@echo "🔍 Verificando ambiente..."
	$(PYTHON) scripts/test_env.py

check-vars:
	@echo "🔍 Verificando variáveis de ambiente..."
	$(PYTHON) scripts/check_env.py

setup-env:
	@echo "⚙️  Configurando arquivo .env..."
	@if [ ! -f .env ]; then \
		cp config/env_example.txt .env; \
		echo "✅ Arquivo .env criado. Edite com suas configurações reais."; \
	else \
		echo "⚠️  Arquivo .env já existe."; \
	fi

# Execução
run-streamlit:
	@echo "🎨 Iniciando interface Streamlit..."
	$(PYTHON) -m streamlit run src/ui/streamlit_app.py

run-api:
	@echo "🚀 Iniciando API FastAPI..."
	$(PYTHON) -m uvicorn src.ui.fastapi_app:app --reload --host 0.0.0.0 --port 8000

run-dev:
	@echo "🔧 Iniciando modo desenvolvimento..."
	$(PYTHON) -m uvicorn src.ui.fastapi_app:app --reload --host 0.0.0.0 --port 8000 &
	$(PYTHON) -m streamlit run src/ui/streamlit_app.py --server.port 8501

# Limpeza
clean:
	@echo "🧹 Limpando arquivos temporários..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/

# Documentação
docs:
	@echo "📚 Gerando documentação..."
	@echo "Documentação disponível no README.md"

docs-serve:
	@echo "📚 Servindo documentação..."
	$(PYTHON) -m http.server 8080 -d docs/ 