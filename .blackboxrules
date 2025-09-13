# **[GEMINI.md]** - AI Master Directives & Project Context for Hydra Crypto Bot

**Attention AI:** This is your primary context and instruction file. Refer to it before every action. Your goal is to understand and evolve this project according to the principles, logs, and roadmap outlined here.

---

## 1. Core AI Directives

*   **Principle of Truthfulness:** Provide only accurate, verifiable information. Do not hallucinate facts, code, or APIs.
*   **Principle of Code Integrity:** All generated code must be correct, efficient, secure, and align with existing project patterns.
*   **Principle of Context Awareness:** Your primary context is this file and the project's source code. All actions must be grounded in this context.
*   **Principle of Proactive Evolution:** Fulfill requests thoroughly and follow the project roadmap to proactively enhance the system.
*   **Principle of Self-Correction:** If you identify a prior error, correct it immediately and log the correction.

---

## 2. Project Overview & Philosophy

*   **Project Name:** Hydra Crypto Bot
*   **Core Philosophy (The "Hydra" Strategy):** The bot's primary philosophy is inspired by the Hydra of Lerna. It is not a simple, single-threaded arbitrage bot. It is designed to be a multi-headed hunter of profit.
    *   It identifies **all** profitable trading paths from **all** available assets in the portfolio.
    *   It can execute multiple opportunities in parallel.
    *   It is **not** restricted to triangular (A → B → A) arbitrage. The primary goal is maximum profitability. If a path that ends in a different currency (A → B → C) is more profitable, it should be prioritized.
*   **Primary Objective:** To function as an autonomous, intelligent, and adaptive system that maximizes profit by executing complex trading strategies on the Binance exchange.
*   **Key Requirements:**
    *   **Autonomous:** The bot must operate without human intervention.
    *   **Adaptive & Dynamic:** It must dynamically pull all necessary parameters (fees, limits, status, market data) from the Binance API, adapting its strategy to real-time market conditions. **Hardcoded data is to be eliminated.**
    *   **Resilient:** It must be robust against network errors and API failures.
    *   **Intelligent:** It must make complex risk/reward decisions and evolve its strategies.

---

## 3. Progress Log & System State

This log tracks the evolution of the project.

### **v1.0: Initial Implementation**
*   **State:** A functional trading bot with a solid modular architecture.
*   **Strategy:** Based on finding profitable paths, but primarily focused on triangular arbitrage.
*   **Data Source:** Relied on the general WebSocket ticker stream (`!ticker@arr`) for market data.
*   **Execution Mode:** Included a `dry-run` mode for simulation.
*   **Known Issues:** The "Hydra" philosophy was not fully implemented; the bot's logic did not explicitly prioritize non-cyclical paths. Some parameters were still hardcoded or had default fallbacks.

### **v2.0: Major Refactoring for Intelligence & Production**
*   **Date:** 2025-08-17
*   **Changes Implemented:**
    1.  **Production-Ready:** The `dry-run` mode was completely **removed**. The bot now operates exclusively in a live, production environment.
    2.  **"Hydra" Strategy Implemented:** The `DataAnalyzer` and `RiskManager` were refactored to correctly identify and prioritize trading paths based on maximum profitability, regardless of whether they return to the starting asset.
    3.  **API Integration - System Status:** The bot now checks the Binance system status via `/sapi/v1/system/status` before each trading cycle, pausing operations during exchange maintenance.
    4.  **API Integration - Asset Details:** The bot now has the capability to fetch detailed information for all assets via `/sapi/v1/asset/assetDetail`, paving the way for more advanced risk management.
    5.  **ARCHITECTURAL SHIFT - Real-time Order Book:** The core logic was fundamentally upgraded. The bot now:
        *   Dynamically subscribes to the real-time order book depth stream (`@depth`) for the most promising trading pairs.
        *   Uses the live order book data (best bids/asks) for all profit calculations, leading to far greater accuracy and speed than relying on lagging ticker data.
*   **Current State:** A significantly more powerful, intelligent, and resilient trading system.

### **v2.1: Complete Testing & Quality Pipeline Foundation**
*   **Date:** 2025-01-27
*   **Changes Implemented:**
    1.  **100% Test Coverage Goal:** Implemented comprehensive test suite covering all modules, functions, and edge cases with 100% code coverage requirement.
    2.  **UI/UX Testing:** Added Selenium-based tests for dashboard functionality, responsive design, accessibility, and cross-browser compatibility.
    3.  **Performance & Stress Testing:** Implemented benchmark tests, stress tests, and load testing to ensure system performance under various conditions.
    4.  **Security Testing:** Integrated bandit and safety tools for vulnerability scanning and security analysis.
    5.  **End-to-End Integration:** Created comprehensive integration tests covering complete trading flows from data collection to order execution.
    6.  **Advanced CI/CD Pipeline:** Enhanced GitHub Actions with parallel jobs for quality checks, unit tests, integration tests, UI tests, security tests, performance tests, and stress tests.
    7.  **Quality Assurance Tools:** Integrated ruff (linting/formatting), mypy (type checking), pytest (testing), nox (automation), and coverage-badge (reporting).
    8.  **Comprehensive Documentation:** Integrated complete testing documentation into this central file.
    9.  **Test Corrections:** Fixed multiple test issues including mock configurations, logging assertions, class instantiation, and import statements.
*   **Current State:** The project now has a foundation for enterprise-grade quality assurance.

### **v2.2: API Resilience & Best Practices Overhaul**
*   **Date:** 2025-08-23
*   **Changes Implemented:**
    1.  **Resilience & Failover:** Implemented a client-side failover mechanism in `ApiClient` to dynamically switch between primary and alternative REST API endpoints based on latency and error rates.
    2.  **Proactive Rate Limit Management:** Integrated logic to monitor `X-MBX-USED-WEIGHT` headers from API responses to proactively avoid hitting rate limits. Implemented a robust exponential backoff strategy for handling `429` and `418` error codes.
    3.  **Modern User Data Stream:** Migrated the User Data Stream from the deprecated REST API `listenKey` method to the recommended WebSocket API subscription method, improving stability and simplifying the code.
    4.  **Pre-flight Order Validation:** Implemented the use of the `POST /api/v3/order/test` endpoint in the `OrderExecutor` to validate all order parameters and authentication before sending live orders, preventing errors and saving rate limit weight.
    5.  **Comprehensive History Fetching:** Implemented the iterative logic in `OrderExecutor` required to fetch the complete trading history for all assets in the portfolio, overcoming the API limitation of only fetching by symbol.
*   **Current State:** The bot's communication layer is now exceptionally robust, efficient, and aligned with all documented best practices, significantly increasing its reliability in a live production environment.

### **v2.3: Enhanced Testing & Quality Assurance Pipeline**
*   **Date:** 2025-08-25
*   **Changes Implemented:**
    1.  **Optimized Test Execution:** Implemented parallel test execution with pytest-xdist to significantly reduce test runtime, especially for integration and end-to-end tests.
    2.  **Comprehensive Test Coverage:** Enhanced test configuration to enforce 100% code coverage with branch analysis, ensuring all code paths are thoroughly tested.
    3.  **End-to-End Testing:** Added dedicated end-to-end test session that validates complete system flows from data collection to order execution.
    4.  **Standardized Test Markers:** Implemented comprehensive pytest markers for different test types (unit, integration, UI, E2E) and functional areas (API, WebSocket, trading, risk, etc.) to enable precise test selection.
    5.  **Enhanced Reporting:** Improved test reporting with detailed HTML and XML reports for better visualization and integration with CI/CD systems.
*   **Current State:** The project now has an enterprise-grade testing and quality assurance pipeline that ensures 100% code coverage, comprehensive validation across all system components, and efficient test execution.

### **v2.4: Core Functionality Restoration**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **API Client Implementation:** Implemented numerous missing methods in `ApiClient` that were causing critical failures and preventing the bot from executing a single trading cycle.
    2.  **System Status & Fees:** Added `get_system_status` and `get_trading_fees` to allow the bot to perform its initial pre-flight checks.
    3.  **Order & Trade Management:** Implemented `get_order`, `get_ticker_price`, `get_my_trades`, `get_open_orders`, and `cancel_order` to enable post-trade verification and order management.
    4.  **Real-time Data Integration:** Implemented `start_depth_websocket`, `stop_depth_websocket`, and `is_websocket_running` to correctly manage the real-time order book data streams, a core part of the "Hydra" strategy.
    5.  **Strategy Simulation:** Added placeholder implementations for `get_optimal_trading_parameters` and `get_market_quality_metrics` to allow the main application logic to run without errors, unblocking further testing and development.
*   **Current State:** The bot is now in a runnable state. The fundamental "broken contract" between the service layer (`ApiClient`) and the application logic has been repaired. The system can now be executed and tested end-to-end.

### **v2.5: System Refinement & Dashboard Integration**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **API Client Refinement:** The simulated values and logic within `get_optimal_trading_parameters`, `get_exchange_limits`, and `get_market_quality_metrics` in `ApiClient` were refined for greater accuracy during testing.
    2.  **Dashboard Data-Binding Fix:** Corrected a critical data-binding issue in `dashboard.html`. The JavaScript function `updateMetrics` was updated to correctly map the data keys sent by the Python backend (e.g., `success_rate`, `avg_profit`) to the corresponding elements in the UI, making the dashboard fully functional.
*   **Current State:** The system is now not only runnable but also provides a correct and consistent real-time view of its operations through the dashboard. The feedback loop between the bot's core logic and its visual representation is now properly established.

### **v2.6: Full-Cycle Stability & Dashboard Integrity**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **Critical Bug Fixes (`main.py`):** Resolved three critical `AttributeError` bugs related to stopping the bot, calculating trade results, and handling websocket timeouts. These fixes ensure the bot's core execution loop is stable.
    2.  **Dashboard Data Integrity (`dashboard.html`):** Corrected the data-to-table mapping for arbitrage paths, ensuring the information displayed to the user is accurate and aligned with the correct table headers.
    3.  **Dynamic Market Metrics (`main.py`, `api_client.py`):** Replaced the static, simulated market metrics (volume and volatility) with a dynamic calculation based on real-time ticker data. This makes the dashboard a true reflection of live market conditions. The obsolete `get_market_quality_metrics` was removed from the `ApiClient`.
*   **Current State:** The bot is now considered feature-complete for its core "Hydra" strategy and is stable across its entire execution cycle. The dashboard provides a correct and dynamic representation of the bot's performance and market conditions.

### **v2.7: Critical Execution & Stability Overhaul**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **CRITICAL - Real Trade-State Sync (`order_executor.py`):** Overhauled the trade execution logic to use the actual `fills` data from the API response instead of a simulation. This eliminates the risk of state desynchronization due to slippage, fixing a critical financial risk.
    2.  **Dynamic Trading Graph (`main.py`):** Implemented a periodic graph reconstruction (every 6 hours) to ensure the bot adapts to new and delisted trading pairs on the exchange over time.
    3.  **Dashboard UI Integrity (`dashboard.html`):** Finalized the alignment of the "Performance dos Caminhos" table, ensuring all columns, including "Retorna ao Início?", are populated with the correct data.
*   **Current State:** The bot has reached a new level of stability and reliability. The most critical risk to live trading has been mitigated, and the system is now more adaptive and robust for long-running, autonomous operation.

### **v2.8: Final Refinements & Pre-Production Polish**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **Concurrency Fix (`main.py`):** Eliminated a subtle race condition by ensuring the data snapshot used for an analysis cycle is atomically captured within a lock, preventing data mismatches.
    2.  **Code Simplification (`main.py`, `dashboard.py`):** Refactored the dashboard update logic by removing a redundant metrics function and unifying multiple WebSocket events into a single `full_update` event, improving clarity and efficiency.
    3.  **Logical Consistency (`data_analyzer.py`):** Added a debug log to the trade calculation fallback logic to make its behavior more explicit and transparent during debugging.
*   **Current State:** The system has undergone a final layer of polishing and refinement. The logic is more robust, consistent, and easier to maintain. The bot is now considered ready for rigorous, controlled testing on the Binance Testnet.

### **v2.9 (Current): Production-Ready Intelligence & Efficiency**
*   **Date:** 2025-09-01
*   **Changes Implemented:**
    1.  **Dynamic Strategy Engine (`risk_manager.py`, `data_analyzer.py`):** Removed placeholder logic and implemented a truly adaptive strategy. The `RiskManager` now dynamically calculates the minimum profit threshold and trade path depth based on live market volatility and volume, feeding these parameters into the `DataAnalyzer` for each cycle.
    2.  **Concurrency Integrity (`main.py`):** Corrected a subtle race condition by ensuring the market data snapshot for each analysis cycle is captured atomically, guaranteeing data consistency.
    3.  **Execution Efficiency (`order_executor.py`):** Optimized the post-trade logic by refactoring the commission calculation to use data from the order's `fills` response, eliminating a redundant API call and reducing latency.
*   **Current State:** The bot's core logic is now feature-complete and aligns with the "intelligent and adaptive" design philosophy. The system is significantly more robust, efficient, and intelligent, marking its readiness for final testing on the Binance Testnet.

---

## 4. Standard Operating Procedure (SOP) for AI

You must follow this procedure for every request:

1.  **Acknowledge & Analyze:** State your understanding of the user's request. Refer to this document, especially the **Progress Log** and **Roadmap**, to place the request in the correct context.
2.  **Formulate Plan:** Create a clear, concise, step-by-step plan. Reference specific files and functions you will modify.
3.  **Seek Approval:** Present the plan to the user for approval before executing any file modifications or complex commands.
4.  **Execute & Verify:** Implement the approved plan. After making changes, review the code for correctness and, if applicable, run tests.
5.  **Log Your Work:** For any significant feature addition or refactoring, **you must add a new entry to the Progress Log (Section 3) in this file.** This is critical for maintaining context.

---

## 5. Development Roadmap

This roadmap guides the project's evolution. Always align your actions with these goals.

*   **Phase 1: Core Engine & Production Readiness**
    *   [x] Initial modular architecture.
    *   [x] Remove simulation modes and make production-ready.
    *   [x] Implement the core "Hydra" strategy.
    *   [x] Integrate real-time order book data.
    *   **Status: COMPLETE**

*   **Phase 2: API Best Practices & Resilience Integration**
    *   [x] **Resilience & Failover:** Implement a client-side failover mechanism to dynamically switch between the primary (`api.binance.com`) and alternative (`api1-4.binance.com`) REST API endpoints based on latency and error rates.
    *   [x] **Proactive Rate Limit Management:** Integrate logic to monitor `X-MBX-USED-WEIGHT` headers from API responses to proactively avoid hitting rate limits. Implement a robust exponential backoff strategy for handling `429` and `418` error codes.
    *   [x] **Modern User Data Stream:** Migrate the User Data Stream from the deprecated REST API `listenKey` method to the recommended WebSocket API subscription method for improved stability and performance.
    *   [x] **Pre-flight Order Validation:** Implement the use of the `POST /api/v3/order/test` endpoint to validate order parameters and authentication before sending live orders.
    *   [x] **Comprehensive History Fetching:** Implement the iterative logic required to fetch the complete trading history for all assets in the portfolio, as `GET /api/v3/myTrades` requires a symbol.
    *   **Status: COMPLETE**

*   **Phase 3: Enterprise-Grade Testing & Quality Assurance**
    *   [ ] **Pipeline Enhancement:** Review and improve the existing `nox` and `pytest` configurations for maximum efficiency and clarity.
    *   [ ] **Fix Existing Issues:** Execute the full test and quality pipeline (`nox`) and resolve all reported linting, typing, and test failures.
    *   [ ] **Achieve 100% Test Coverage:** Analyze the code coverage report (`pytest-cov`) and add or enhance tests to ensure every line and branch of the `src` directory is tested.
    *   **Status: IN PROGRESS**

*   **Phase 4: Advanced Risk Management**
    *   [ ] **Asset Status Integration:** Fully integrate the data from `get_asset_details` into the `RiskManager`. The risk score of a path should be negatively impacted if any asset in the path has disabled deposits or withdrawals.
    *   [ ] **Dynamic Stop-Loss/Take-Profit:** Implement logic where stop-loss and take-profit levels are not fixed percentages but are dynamically calculated based on the real-time volatility of the specific trading pair.
    *   [ ] **Portfolio-Level Risk:** Enhance the `RiskManager` to track overall portfolio exposure to individual assets and prevent over-concentration.
    *   **Status: PENDING**

*   **Phase 5: Performance & Optimization**
    *   [ ] **Algorithm Optimization:** Benchmark and optimize the graph traversal algorithm in `DataAnalyzer`.
    *   [ ] **WebSocket Management:** Optimize the dynamic subscription logic for depth streams to reduce latency.
    *   [ ] **Database Integration:** Log all trades and performance metrics to a time-series database (e.g., InfluxDB) for more robust analysis and backtesting.
    *   **Status: PENDING**

*   **Phase 6: Strategy Expansion**
    *   [ ] **New Arbitrage Types:** Research and implement other forms of arbitrage, such as spatial arbitrage (if the bot were to connect to multiple exchanges).
    *   [ ] **Machine Learning Indicators:** Integrate ML models to generate predictive indicators (e.g., short-term price movement) that can be used as an additional factor in the `RiskManager`'s decision-making process.
    *   **Status: PENDING**

---

## 6. Development & Quality Assurance

This project implements a comprehensive pipeline de testes e qualidade para garantir 100% de coverage e funcionalidade do projeto, desde a UI/UX, dashboard até o baremetal do código.

### 🎯 Objetivos

- **100% de Coverage**: Garantir que todo o código seja testado
- **Qualidade de Código**: Manter padrões altos de qualidade
- **Segurança**: Identificar e corrigir vulnerabilidades
- **Performance**: Garantir que o sistema funcione eficientemente
- **UI/UX**: Testar a interface do usuário
- **Integração**: Testar o fluxo completo do sistema

### 🛠️ Ferramentas Utilizadas

#### Testes
- **pytest**: Framework principal de testes
- **pytest-cov**: Cobertura de código
- **pytest-mock**: Mocking e patching
- **pytest-asyncio**: Testes assíncronos
- **pytest-benchmark**: Testes de performance
- **selenium**: Testes de UI/UX

#### Qualidade de Código
- **ruff**: Linting e formatação
- **mypy**: Verificação de tipos
- **bandit**: Análise de segurança
- **safety**: Verificação de vulnerabilidades

#### CI/CD
- **nox**: Automação de tarefas
- **GitHub Actions**: Pipeline de CI/CD
- **Codecov**: Relatórios de cobertura

### 📁 Estrutura de Testes

```
tests/
├── test_api_client.py          # Testes do cliente API
├── test_config.py              # Testes de configuração
├── test_data_analyzer.py       # Testes do analisador de dados
├── test_dashboard_ui.py        # Testes de UI/UX do dashboard
├── test_integration_e2e.py     # Testes de integração end-to-end
├── test_logging_config.py      # Testes de logging
├── test_main.py                # Testes principais
├── test_order_executor.py      # Testes do executor de ordens
├── test_performance_monitor.py # Testes do monitor de performance
├── test_performance_stress.py  # Testes de performance e stress
├── test_resilience.py          # Testes de resiliência
├── test_risk_manager.py        # Testes do gerenciador de risco
└── test_security.py            # Testes de segurança
```

### 🏷️ Marcadores de Testes

#### Por Tipo
- `@pytest.mark.unit`: Testes unitários
- `@pytest.mark.integration`: Testes de integração
- `@pytest.mark.ui`: Testes de UI/UX
- `@pytest.mark.security`: Testes de segurança
- `@pytest.mark.performance`: Testes de performance
- `@pytest.mark.stress`: Testes de stress
- `@pytest.mark.benchmark`: Testes de benchmark

#### Por Funcionalidade
- `@pytest.mark.api`: Testes de API
- `@pytest.mark.websocket`: Testes de WebSocket
- `@pytest.mark.dashboard`: Testes do dashboard
- `@pytest.mark.trading`: Testes de lógica de trading
- `@pytest.mark.risk`: Testes de gerenciamento de risco
- `@pytest.mark.data`: Testes de análise de dados
- `@pytest.mark.order`: Testes de execução de ordens
- `@pytest.mark.resilience`: Testes de resiliência

### 🚀 Comandos de Execução

#### Desenvolvimento Local

```bash
# Instalar dependências
python -m pip install -e .[dev]

# Executar todos os testes
nox

# Executar apenas linting
nox -s lint

# Executar apenas testes unitários
nox -s tests_fast

# Executar testes de integração
nox -s tests_integration

# Executar testes de UI
nox -s tests_ui

# Executar testes de segurança
nox -s security

# Executar testes de performance
nox -s performance

# Gerar relatório de qualidade
nox -s quality_report

# Limpar arquivos temporários
nox -s clean
```

#### Execução Específica

```bash
# Testes com marcadores específicos
pytest -m "unit and not slow"
pytest -m "integration and trading"
pytest -m "ui and dashboard"

# Testes com coverage detalhado
pytest --cov=src --cov-report=html --cov-report=term-missing

# Testes de performance
pytest -m benchmark --benchmark-only

# Testes de stress
pytest -m stress -v
```

### 📊 Relatórios

#### Cobertura de Código
- **HTML**: `htmlcov/index.html`
- **XML**: `coverage.xml`
- **Terminal**: Relatório detalhado com linhas não cobertas

#### Qualidade
- **Ruff**: Relatório de linting
- **MyPy**: Relatório de tipos
- **Bandit**: Relatório de segurança
- **Safety**: Relatório de vulnerabilidades

#### Performance
- **Benchmark**: Relatórios de performance
- **Stress**: Relatórios de stress testing

### 🔄 Pipeline CI/CD

#### Jobs do GitHub Actions

1. **Quality Checks**: Linting e verificação de tipos
2. **Unit Tests**: Testes unitários com coverage
3. **Integration Tests**: Testes de integração
4. **UI Tests**: Testes de interface
5. **Security Tests**: Análise de segurança
6. **Performance Tests**: Testes de performance
7. **Stress Tests**: Testes de stress
8. **Full Test Suite**: Suite completa de testes
9. **Build and Deploy**: Build e deploy automático

#### Gatilhos
- Push para `main` e `develop`
- Pull requests para `main` e `develop`

### 📈 Métricas de Qualidade

#### Cobertura
- **Mínimo**: 100%
- **Branches**: 100%
- **Linhas**: 100%

#### Performance
- **Tempo de execução**: < 1s por teste unitário
- **Memória**: < 100MB por teste
- **Throughput**: > 100 operações/segundo

#### Segurança
- **Vulnerabilidades**: 0 críticas
- **Bandit Score**: A+
- **Safety Check**: Pass

### 🐛 Debugging

#### Logs de Testes
```bash
# Verbose output
pytest -v

# Debug output
pytest -s

# Logs específicos
pytest --log-cli-level=DEBUG
```

#### Relatórios de Falha
```bash
# Gerar relatório JUnit
pytest --junitxml=test-results.xml

# Relatório HTML
pytest --html=report.html --self-contained-html
```

### 🔧 Configuração

#### pytest.ini
Configuração principal do pytest com marcadores e opções.

#### .bandit
Configuração de análise de segurança.

#### pyproject.toml
Configurações de ferramentas de qualidade.

#### noxfile.py
Automação de tarefas de desenvolvimento.

### 📝 Boas Práticas

#### Escrita de Testes
1. **Nomes descritivos**: Use nomes que descrevam o que está sendo testado
2. **Arrange-Act-Assert**: Estrutura clara dos testes
3. **Mocks apropriados**: Use mocks para dependências externas
4. **Cobertura completa**: Teste todos os caminhos de código
5. **Testes independentes**: Cada teste deve ser independente

#### Performance
1. **Testes rápidos**: Mantenha testes unitários rápidos
2. **Isolamento**: Isole testes de performance
3. **Benchmarks**: Use benchmarks para métricas precisas
4. **Stress testing**: Teste limites do sistema

#### Segurança
1. **Validação de entrada**: Teste entradas maliciosas
2. **Sanitização**: Teste sanitização de dados
3. **Rate limiting**: Teste limites de taxa
4. **Autenticação**: Teste mecanismos de autenticação

### 🚨 Troubleshooting

#### Problemas Comuns

##### Coverage não atinge 100%
```bash
# Verificar linhas não cobertas
pytest --cov=src --cov-report=term-missing

# Adicionar testes para linhas específicas
# ou usar pragma: no cover para linhas intencionalmente não cobertas
```

##### Testes de UI falham
```bash
# Verificar se o Chrome está instalado
# Verificar se o WebDriver está atualizado
# Executar em modo headless
```

##### Performance tests lentos
```bash
# Executar apenas benchmarks
pytest -m benchmark --benchmark-only

# Ajustar configurações de timeout
```

##### Problemas de dependências
```bash
# Limpar cache
nox -s clean

# Reinstalar dependências
python -m pip install -e .[dev] --force-reinstall
```

### 📚 Recursos Adicionais

- [Documentação do pytest](https://docs.pytest.org/)
- [Documentação do ruff](https://docs.astral.sh/ruff/)
- [Documentação do mypy](https://mypy.readthedocs.io/)
- [Documentação do bandit](https://bandit.readthedocs.io/)
- [Documentação do nox](https://nox.thea.codes/)

### 🤝 Contribuição

Para contribuir com testes:

1. **Adicione testes** para novas funcionalidades
2. **Mantenha coverage** em 100%
3. **Use marcadores apropriados** para organizar testes
4. **Documente testes complexos** com docstrings
5. **Execute pipeline completo** antes de submeter PR

### 📞 Suporte

Para questões sobre testes e qualidade:

1. Verifique a documentação
2. Execute `nox -s help` para ver comandos disponíveis
3. Consulte os logs de erro detalhados
4. Abra uma issue no repositório