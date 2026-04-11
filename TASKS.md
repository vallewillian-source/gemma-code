# Proposta: Sistema de Orquestração em Dois Níveis

## Visão Geral da Arquitetura

```
 Usuário / CI/CD
      │
      ▼
[overnight.py]  ──────────────── único entry point overnight
      │
      ├── 1. Constrói RepoMap (já existe)
      │
      ├── 2. OrchestratorAgent (DeepSeek V3.2)
      │         └── Recebe: tarefa + RepoMap + Heurísticas
      │         └── Devolve: lista de SubtaskSpec (JSON estruturado)
      │
      └── 3. Para cada SubtaskSpec:
                └── SubtaskRunner (Gemma / Qwen via Ollama)
                          ├── Acesso restrito a arquivos listados
                          ├── Contexto pré-injetado
                          └── Loop: implementa → roda tests → para quando passa
```

## O Que Precisa Ser Criado

### Estrutura de Arquivos Novos

```
src/gemmacode/
├── orchestrator/
│   ├── __init__.py
│   ├── schema.py           # Pydantic: SubtaskSpec, DecompositionPlan
│   ├── heuristics.py       # Carrega e compõe heurísticas em prompt
│   ├── ordering.py         # Topological sort de dependências
│   └── heuristics/         # YAMLs com padrões pré-definidos
│       ├── python_project.yaml
│       ├── testing_patterns.yaml
│       └── file_structure.yaml
├── agents/
│   ├── orchestrator.py     # NOVO: agente DeepSeek single-shot
│   └── subtask_runner.py   # NOVO: agente executor c/ loop de testes
├── environments/
│   └── restricted.py       # NOVO: wrapper com allowlist de arquivos
└── run/
    └── overnight.py        # NOVO: entry point do pipeline completo
```

## Contexto Técnico

### 1. Task Decomposition Schema

O contrato central — tudo gira em torno dele:

- **TestCriterion**: descrição + comando pytest
- **SubtaskSpec**: id, título, descrição, files_to_read/write, contexto, dependências, testes de aceite, complexidade estimada
- **DecompositionPlan**: tarefa original + lista de subtasks + contexto global + heurísticas aplicadas
- **SubtaskResult**: result da execução (status, erro, outputs dos testes)
- **SubtaskStatus**: enum (pending | running | passed | failed | timeout)

### 2. Sistema de Heurísticas

Padrões pré-definidos que o DeepSeek **deve** aplicar mecanicamente:

- **python_project.yaml**: localização de testes, fixtures, naming, pathlib, ausência de mocks desnecessários
- **testing_patterns.yaml**: estrutura pytest, parametrize para edge cases, assert inline, test-before-implement
- **file_structure.yaml**: single responsibility, tamanho máximo de arquivo, `__init__.py`, padrão `extra/`

### 3. OrchestratorAgent (DeepSeek)

Single-shot call estruturado:
- Recebe: tarefa + repo_map completo + heurísticas injetadas + schema JSON como exemplo
- Retorna: JSON válido conforme `DecompositionPlan`
- Retry com erro do Pydantic se JSON inválido
- Não precisa de loop — é um call único bem-pensado

### 4. RestrictedEnvironment

Wrapper sobre `LocalEnvironment` com allowlist de arquivos:
- Intercepta comandos que tentam ler/escrever fora da allowlist
- Retorna erro explicativo (não bloqueia silenciosamente)
- Objetivo: economizar tokens (modelo menor não fica explorando) e evitar colisões entre subtasks

### 5. SubtaskRunner

Executor de uma SubtaskSpec com modelo menor (Gemma/Qwen):
- Usa `DefaultAgent` com `RestrictedEnvironment`
- Injeta contexto pré-compilado no prompt
- Após agent finalizar: roda testes de aceite independentemente
- Se testes falham: re-entra no agent com outputs (até max_retries)
- Retorna `SubtaskResult` com status

### 6. Pipeline Overnight

Entry point que orquestra tudo:
1. Constrói RepoMap
2. Decompõe com DeepSeek
3. Executa subtasks em sequência (topological sort de dependências)
4. Retorna resumo com status de cada subtask

## O Que Não Mudar

- `DefaultAgent` e `InteractiveAgent` ficam intactos — reutilizados como dependência
- Sistema de config YAML permanece — overnight.py adiciona suas próprias configs
- RepoMap existente é reutilizado diretamente
- `runtime/model_policy.py` já expõe `get_validator_settings()` — usar para DeepSeek

---

# Divisão de Tarefas

## Tarefa 1 — Schema central (`orchestrator/schema.py`)

**Arquivo:** `src/gemmacode/orchestrator/schema.py` (criar) + `src/gemmacode/orchestrator/__init__.py`

**O que implementar:**
- `TestCriterion`: campos `description: str` e `test_command: str`
- `SubtaskSpec`: `id`, `title`, `description`, `files_to_read: list[str]`, `files_to_write: list[str]`, `context`, `dependencies: list[str]`, `acceptance_tests: list[TestCriterion]`, `estimated_complexity: Literal["low", "medium", "high"]`
- `DecompositionPlan`: `original_task`, `subtasks: list[SubtaskSpec]`, `global_context`, `heuristics_applied: list[str]`
- `SubtaskStatus`: enum `pending | running | passed | failed | timeout`
- `SubtaskResult`: `spec: SubtaskSpec`, `status: SubtaskStatus`, `error: str | None`, `test_outputs: list[str]`

**Testes que devem passar (`tests/orchestrator/test_schema.py`):**
- `DecompositionPlan.model_validate(dict)` aceita JSON válido com subtasks aninhadas
- `DecompositionPlan.model_validate_json(json_str)` faz round-trip sem perda
- Validação levanta `ValidationError` quando `estimated_complexity` tem valor inválido
- `SubtaskSpec` com `dependencies=[]` e `acceptance_tests=[]` é válido
- `SubtaskResult` com `status=SubtaskStatus.passed` e `error=None` serializa corretamente

---

## Tarefa 2 — Arquivos YAML de heurísticas

**Arquivos a criar:**
- `src/gemmacode/orchestrator/heuristics/python_project.yaml`
- `src/gemmacode/orchestrator/heuristics/testing_patterns.yaml`
- `src/gemmacode/orchestrator/heuristics/file_structure.yaml`

**Schema de cada YAML:**
```yaml
name: str
description: str
rules:
  - id: str          # slug único, ex: "test-location"
    description: str  # instrução em linguagem natural, 1-3 frases
    example: str | null
```

**Conteúdo mínimo:**
- `python_project.yaml`: ao menos 5 regras cobrindo localização de testes, fixtures, naming de funções, uso de pathlib, ausência de mocks desnecessários
- `testing_patterns.yaml`: ao menos 5 regras cobrindo estrutura pytest, parametrize para edge cases, assert inline, test-before-implement, critério de "done" via testes
- `file_structure.yaml`: ao menos 4 regras cobrindo single responsibility, tamanho máximo de arquivo, estrutura de `__init__.py`, padrão de `extra/` para código específico

**Testes que devem passar (`tests/orchestrator/test_heuristics_yaml.py`):**
- Cada YAML carrega sem erro via `yaml.safe_load`
- Cada YAML tem `name`, `description`, `rules` presentes
- Cada item em `rules` tem `id` e `description`
- Nenhum `id` está duplicado dentro do mesmo arquivo

---

## Tarefa 3 — Loader de heurísticas (`orchestrator/heuristics.py`)

**Arquivo:** `src/gemmacode/orchestrator/heuristics.py`

**O que implementar:**
- `load_heuristics(categories: list[str] | None = None) -> list[dict]` — carrega todos os YAMLs da pasta `heuristics/`, filtra por `name` se `categories` fornecido
- `build_heuristics_prompt(categories: list[str] | None = None) -> str` — formata as regras como bloco de texto estruturado pronto para injeção em prompt. Formato: uma seção por categoria, cada regra numerada com seu `id` e `description`
- `HEURISTICS_DIR: Path` — constante apontando para `orchestrator/heuristics/`

**Testes que devem passar (`tests/orchestrator/test_heuristics.py`):**
- `load_heuristics()` retorna lista com 3 categorias quando chamado sem filtro
- `load_heuristics(["python_project"])` retorna exatamente 1 categoria
- `load_heuristics(["nonexistent"])` retorna lista vazia (sem erro)
- `build_heuristics_prompt()` retorna string contendo os `id`s de todas as regras
- `build_heuristics_prompt(["testing_patterns"])` não contém regras de `python_project`

---

## Tarefa 4 — OrchestratorAgent (`agents/orchestrator.py`)

**Arquivo:** `src/gemmacode/agents/orchestrator.py`

**O que implementar:**
- `OrchestratorAgent(model: Model, heuristics_categories: list[str] | None = None, max_retries: int = 3)`
- `decompose(task: str, repo_map: str) -> DecompositionPlan` — método principal:
  1. Chama `build_heuristics_prompt()` para obter as regras
  2. Monta system prompt com: papel do agente + heurísticas + schema JSON de `DecompositionPlan` como exemplo
  3. Monta user message com: tarefa + repo_map + instrução de retornar JSON válido
  4. Chama `self.model.query(messages)` (messages no formato padrão do projeto)
  5. Extrai JSON da resposta e valida com `DecompositionPlan.model_validate_json()`
  6. Se `ValidationError`: adiciona erro ao histórico de mensagens e re-tenta (até `max_retries`)
  7. Levanta `OrchestratorError` após esgotar retries
- `OrchestratorError(Exception)` — erro customizado

**Testes que devem passar (`tests/agents/test_orchestrator.py`):**
- Com `DeterministicModel` retornando JSON válido: `decompose()` retorna `DecompositionPlan` correto
- Prompt enviado ao modelo contém a string da `task`
- Prompt enviado ao modelo contém ao menos um `id` de heurística de `python_project`
- Com `DeterministicModel` retornando JSON inválido na 1ª call e válido na 2ª: `decompose()` retorna sucesso após retry
- Com `DeterministicModel` sempre retornando JSON inválido: `decompose()` levanta `OrchestratorError`

---

## Tarefa 5 — RestrictedEnvironment (`environments/restricted.py`)

**Arquivo:** `src/gemmacode/environments/restricted.py`

**O que implementar:**
- `RestrictedEnvironment(allowed_files: list[str], base_env: LocalEnvironment | None = None)`
- `execute(action: dict, ...) -> dict` — wrapper sobre `base_env.execute()`:
  - Extrai paths mencionados no `action["command"]` via regex simples (strings que terminam com extensão conhecida ou precedidas de `cat`/`open`/`>>`/`>`/`echo.*>`)
  - Se algum path detectado **não** está em `allowed_files` (comparação por sufixo absoluto): retorna dict de erro com mensagem explicando quais arquivos são permitidos — sem executar o comando
  - Caso contrário: delega para `base_env.execute()`
- `get_template_vars()` — retorna `{"allowed_files": self.allowed_files}`
- Registro em `environments/__init__.py` com key `"restricted"`

**Testes que devem passar (`tests/environments/test_restricted.py`):**
- `execute({"command": "cat allowed_file.py"})` executa normalmente quando arquivo está na allowlist
- `execute({"command": "cat /etc/passwd"})` retorna dict com `returncode != 0` e mensagem de erro mencionando "allowed files"
- `execute({"command": "echo foo > not_allowed.py"})` é bloqueado
- `execute({"command": "ls -la"})` passa (sem paths de arquivo específicos)
- `execute({"command": "pytest tests/"})` passa (pytest não referencia arquivos diretamente no comando)
- `get_template_vars()["allowed_files"]` contém os arquivos passados no construtor

---

## Tarefa 6 — SubtaskRunner (`agents/subtask_runner.py`)

**Arquivo:** `src/gemmacode/agents/subtask_runner.py`

**O que implementar:**
- `SubtaskRunner(local_model: Model, base_env: LocalEnvironment | None = None, max_test_retries: int = 2)`
- `run(spec: SubtaskSpec) -> SubtaskResult` — pipeline de execução:
  1. Cria `RestrictedEnvironment(spec.files_to_read + spec.files_to_write)`
  2. Monta task prompt a partir da `SubtaskSpec`:
     - Título, descrição, contexto
     - Lista de arquivos autorizados
     - Critérios de aceite em linguagem natural
     - Instrução: "implemente, rode os testes abaixo e finalize com `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` apenas quando todos passarem"
  3. Instancia `DefaultAgent` com step_limit proporcional à complexity (`low=20, medium=40, high=60`)
  4. Chama `agent.run(prompt)`
  5. Roda cada `criterion.test_command` via `base_env.execute()` (sem restrição — pytest precisa de acesso amplo)
  6. Se todos passam: retorna `SubtaskResult(status=passed)`
  7. Se algum falha: re-entra no agent com output dos testes como mensagem adicional (até `max_test_retries`)
  8. Se ainda falha: retorna `SubtaskResult(status=failed, error=...)`
- `_build_task_prompt(spec: SubtaskSpec) -> str`
- `_run_tests(spec: SubtaskSpec) -> tuple[bool, list[str]]` — retorna `(all_passed, outputs)`

**Testes que devem passar (`tests/agents/test_subtask_runner.py`):**
- Com `DeterministicModel` que emite `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` e todos os testes passando: `result.status == SubtaskStatus.passed`
- Prompt gerado contém `spec.description`, `spec.context`, e os `description` de cada `TestCriterion`
- Prompt gerado lista os `files_to_write` da spec
- Com testes falhando na 1ª rodada e passando na 2ª: `result.status == SubtaskStatus.passed` e agent foi chamado 2 vezes
- Com testes sempre falhando (além de `max_test_retries`): `result.status == SubtaskStatus.failed`

---

## Tarefa 7 — Topological sort para sequenciamento (`orchestrator/ordering.py`)

**Arquivo:** `src/gemmacode/orchestrator/ordering.py`

**O que implementar:**
- `topological_sort(subtasks: list[SubtaskSpec]) -> list[SubtaskSpec]` — ordena respeitando o campo `dependencies` de cada subtask
- Levanta `CyclicDependencyError(Exception)` se detectar ciclo
- Subtasks sem dependências vêm primeiro; dentro do mesmo "nível", preserva a ordem original

**Testes que devem passar (`tests/orchestrator/test_ordering.py`):**
- Lista sem dependências retorna mesma ordem
- `[B depends on A, A, C depends on B]` retorna `[A, B, C]`
- Ciclo `A→B→A` levanta `CyclicDependencyError`
- Dependência em `id` inexistente levanta `ValueError` com mensagem clara
- 10 subtasks em ordem aleatória com dependências em cadeia: resultado é topologicamente válido

---

## Tarefa 8 — Entry point overnight (`run/overnight.py`)

**Arquivo:** `src/gemmacode/run/overnight.py`

**O que implementar:**
- CLI com Typer: `gemma-code-overnight`
- Argumentos: `task: str` (option `-t`), `output_dir: Path` (option `-o`, default `~/.config/gemma-code/overnight/`), `heuristics: list[str]` (option `-H`, default todas), `dry_run: bool` (flag `--dry-run` — roda só o orchestrator, imprime o plano e sai)
- Pipeline:
  1. Constrói RepoMap via `build_repo_map(Path.cwd())` (reutiliza código existente)
  2. Instancia model DeepSeek via `get_validator_settings()` + `LitellmModel`
  3. Instancia `OrchestratorAgent` e chama `decompose(task, repo_map_full)`
  4. Salva `plan.json` em `output_dir` (serialização do `DecompositionPlan`)
  5. Se `--dry-run`: imprime plano com Rich e sai
  6. Ordena subtasks com `topological_sort()`
  7. Para cada subtask: instancia `SubtaskRunner` com modelo local via `get_local_model_name()`, chama `run(spec)`, salva resultado parcial
  8. Ao final: imprime tabela resumo (Rich) com status de cada subtask
  9. Salva `summary.json` em `output_dir`
- `load_plan(path: Path) -> DecompositionPlan` — função auxiliar para recarregar plano salvo

**Testes que devem passar (`tests/run/test_overnight.py`):**
- `load_plan(path)` faz round-trip com `plan.json` gerado pelo pipeline
- `--dry-run` não chama `SubtaskRunner.run()`
- Com mocks de `OrchestratorAgent.decompose` e `SubtaskRunner.run`: pipeline executa subtasks na ordem correta retornada por `topological_sort`
- Se uma subtask retorna `status=failed`: pipeline continua com as demais (comportamento não-bloqueante por padrão)
- `summary.json` contém status de todas as subtasks

---

## Tarefa 9 — Config YAML e registro no pyproject

**Arquivos a modificar/criar:**
- `src/gemmacode/config/overnight.yaml` (criar)
- `pyproject.toml` (modificar)

**`overnight.yaml`:**
```yaml
agent:
  step_limit: 40
  cost_limit: 0.0
  mode: yolo

model:
  model_kwargs:
    num_ctx: 40960
  cost_tracking: ignore_errors

environment:
  timeout: 60
```

**`pyproject.toml`** — adicionar em `[project.scripts]`:
```toml
gemma-code-overnight = "gemmacode.run.overnight:app"
```

**Testes que devem passar:**
- `overnight.yaml` carrega via `get_config_from_spec("overnight.yaml")` sem erro
- `get_config_from_spec("overnight.yaml")` retorna dict com `agent.mode == "yolo"`
- `gemma-code-overnight --help` executa sem erro (smoke test via `subprocess.run`)

---

## Tarefa 10 — Teste de integração ponta a ponta

**Arquivo:** `tests/integration/test_overnight_pipeline.py`

**O que implementar:**
- Fixture `deterministic_plan` — `DecompositionPlan` com 3 subtasks (A sem deps, B depende de A, C depende de A), cada uma com 1 `TestCriterion` cujo `test_command` é `echo ok` (sempre passa)
- `MockOrchestratorAgent` — retorna `deterministic_plan` sem chamar API
- `MockSubtaskRunner` — registra ordem de chamadas e retorna `SubtaskResult(status=passed)`
- Testa o pipeline completo do `overnight.py` com os mocks injetados

**Testes que devem passar:**
- Subtask A é executada antes de B e C
- Subtask B só é executada após A estar com status `passed`
- `summary.json` tem exatamente 3 entradas, todas `passed`
- Re-carregar `plan.json` com `load_plan()` produz objeto idêntico ao original
- Pipeline com uma subtask falhando não interrompe as demais independentes

---

# Ordem de Execução

```
1 → 2 → 3 → 4   (schema, heurísticas, loader, orchestrator: sem deps de runtime)
          ↓
          5       (restricted env: deps só de LocalEnvironment)
          ↓
          6       (subtask runner: deps 1+5)
          ↓
          7       (ordering: deps só de 1)
          ↓
          8       (overnight: deps de tudo)
          ↓
          9       (config + pyproject: deps de 8)
          ↓
         10       (integração: deps de tudo)
```

**Tarefas que podem ser desenvolvidas em paralelo:**
- Tarefas 2 e 5 podem ser desenvolvidas em paralelo com 4, pois não dependem entre si
- As demais precisam de forma linear, conforme o diagrama acima
