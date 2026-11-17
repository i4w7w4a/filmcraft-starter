# Подключение агентов

## Единая подготовка

В корне проекта выполни:

```sh
bash scripts/bootstrap.sh
```

Для нестандартной установки передай `--app` и `--cli`. Для конкретной рабочей копии добавь `--project /absolute/path/copy.fcproj`.

Генератор создаёт серверы:

- `filmcraft` — bridge на `127.0.0.1:9876`;
- `filmcraft-headless` — пустой headless или указанный `--project`.

Он не сохраняет token и не меняет глобальные пользовательские конфиги.

## Kimi Code

Файл: `.kimi-code/mcp.json`.

1. Открой корень проекта в Kimi Code.
2. Проверь launch target в workspace trust prompt. Доверяй только собственную копию проекта.
3. Начни новую сессию после добавления MCP.
4. Выполни `/mcp` и проверь оба сервера.
5. Для bridge запускай Kimi через `bash scripts/start-bridge.sh --agent kimi`.

Не используй режим, в котором MCP-вызовы автоматически одобряются без разбора. Сохрани подтверждения записывающих операций.

## Codex

Файл: `.codex/config.toml`.

- Конфиг действует для trusted project.
- Bridge наследует `FILMCRAFT_CONTROL_TOKEN` через `env_vars`.
- `default_tools_approval_mode = "writes"` запрашивает подтверждение для не-read-only инструментов.
- Проверь `/mcp`; для bridge используй `bash scripts/start-bridge.sh --agent codex`.

## Claude Code

Файл: `.mcp.json`.

Запусти `bash scripts/start-bridge.sh --agent claude` либо обычный `claude` для headless. Проверь и подтверди project MCP servers при запросе. Для headless-only регистрации вручную используй абсолютный путь CLI.

## Cursor

Файл: `.cursor/mcp.json`. Открой настройки MCP, проверь оба локальных сервера и запускай агента из окружения bridge, если требуется desktop.

## Gemini CLI

Файл: `.gemini/settings.json`. Проверь MCP после новой сессии. Используй `--agent gemini` в bridge-wrapper.

## VS Code и Copilot

По умолчанию используется современный корневой `.mcp.json` с `mcpServers` и `type: stdio`. Этот файл совместно создаётся адаптерами Claude Code и Copilot; токен в него не записывается. После загрузки workspace проверь доверие и статус MCP. Для desktop bridge VS Code и его MCP-процессы должны наследовать токен: используй `bash scripts/start-bridge.sh --agent code`.

Для старого editor-managed Local harness можно отдельно выполнить `python3 scripts/filmcraft_agent.py configure --clients vscode`; будет создан `.vscode/mcp.json` с секцией `servers`. Для новой конфигурации Copilot этот устаревший путь не нужен.

## OpenCode

Файл: `opencode.json`. Для актуальной v2 генератор использует `mcp.servers`, тип `local`; сервер подключается автоматически без поля `enabled`. Проверка: `opencode mcp list`. Используй `bash scripts/start-bridge.sh --agent opencode` для desktop.

Для старой схемы с серверами непосредственно в `mcp` выполни отдельно `python3 scripts/filmcraft_agent.py configure --clients opencode-legacy`. Не создавай v2 и legacy-конфигурацию одновременно.

## Другой MCP-клиент

Используй `config/mcp.json`, если клиент принимает формат `mcpServers`. Иначе перенеси из него два stdio-описания:

```json
{
  "command": "/absolute/path/filmcraft-cli",
  "args": ["mcp", "--bridge", "127.0.0.1:9876"]
}
```

Headless: `args: ["mcp"]`. Если клиент не умеет MCP resources или image content, командные инструменты всё равно могут работать; проверяй фактические возможности и сохраняй PNG через CLI fallback.

## Агент без MCP

Используй `filmcraft-cli` через shell. Сначала `commands`/`describe`, затем `inspect`, `exec`, `export`. Правила `AGENTS.md` остаются обязательными.

## Context7

Это отдельный необязательный сервер документации, не требуемый для управления FilmCraft. Библиотека: `/storytold/filmcraft`.

Шаблон сервера: `assets/templates/context7.mcpServers.json`. Объедини его с конфигом клиента только если нужен онлайн-поиск по документации. Не помещай API key в проект; если ключ требуется, используй собственный механизм окружения клиента.

Приоритет остаётся за локальными документами нужного тега и живым каталогом команд.

## Проверка матрицы

Для каждого клиента отметь:

- подключение stdio;
- tools/list и resources/list;
- вызов read-only;
- запрос подтверждения записи;
- получение/сохранение PNG;
- длительный export через `wait: false` и polling;
- переподключение после перезапуска.

Результаты сохраняй отдельно в `tests/results/<client>.local.json`, без token и приватных путей проекта.
