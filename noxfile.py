import nox
import os
import shutil

# Define os diretórios a serem verificados
LOCATIONS = [
    "api_client.py",
    "config.py",
    "dashboard.py",
    "data_analyzer.py",
    "logging_config.py",
    "main.py",
    "order_executor.py",
    "performance_monitor.py",
    "resilience.py",
    "risk_manager.py",
    "security.py",
    # "tests/" # Adicionar quando o diretório de testes for criado
]

# Opções padrão do nox
nox.options.sessions = ["lint", "security"]
nox.options.reuse_existing_virtualenvs = True


@nox.session(python=["3.13"])
def tests(session):
    """Executa todos os testes (unit, integration, etc.)."""
    session.install(".[dev]")
    session.run("pytest", *session.posargs)


@nox.session(python="3.13")
def lint(session):
    """Executa linting e formatação."""
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", ".")


@nox.session(python="3.13")
def security(session):
    """Executa verificações de segurança."""
    session.install("bandit", "safety")
    # Filtra para rodar bandit apenas em arquivos .py
    py_files = [loc for loc in LOCATIONS if loc.endswith(".py")]
    session.run("bandit", "-r", *py_files)
    session.run("safety", "check")


@nox.session(python="3.13")
def quality_report(session):
    """Gera relatórios de qualidade (cobertura, etc.)."""
    session.install(".[dev]")
    session.run("pytest", "--cov=.", "--cov-report=html", "--cov-report=term-missing")


@nox.session(python=False)
def clean(session):
    """Remove arquivos temporários e caches."""
    shutil.rmtree(".pytest_cache", ignore_errors=True)
    shutil.rmtree("htmlcov", ignore_errors=True)
    shutil.rmtree(".nox", ignore_errors=True)
    if os.path.exists("coverage.xml"):
        os.remove("coverage.xml")
    print("Cache e arquivos temporários removidos.")
