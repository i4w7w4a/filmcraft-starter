---
name: filmcraft-agent
description: Operate ArtCraft FilmCraft through its native MCP server, filmcraft-cli or the desktop control bridge. Use for FilmCraft, .fcproj, filmcraft-cli, FilmCraft MCP, video editing, sequence construction, trimming, effects, captions, colour, rendering, UI automation, export and verification. Supports safe headless and bridge workflows on Linux, live command discovery, client configuration for coding agents, offline official documentation and smoke testing.
---

# FilmCraft Agent

Управляй установленным FilmCraft через штатный MCP и обязательный цикл обратной связи. Не создавай второй MCP-сервер и не угадывай параметры по памяти.

## Обязательные правила

Прочитай `AGENTS.md` перед первым редактированием, экспортом, UI-автоматизацией или настройкой нового клиента. Для любых записывающих операций соблюдай `references/safety.md`.

## Подготовь локальную установку

Если `workspace/runtime/probe.json` отсутствует, устарел или путь к FilmCraft изменился:

```sh
bash scripts/bootstrap.sh
```

Если FilmCraft установлен в нестандартном месте:

```sh
bash scripts/bootstrap.sh \
  --app /absolute/path/filmcraft \
  --cli /absolute/path/filmcraft-cli
```

Bootstrap только определяет установку, генерирует проектные конфиги и получает каталог команд. Он не устанавливает FilmCraft, не меняет пользовательские глобальные конфиги и не запускает редактирование.

Если bundled docs не совпадают с версией CLI, получи документы её тега после проверки доступности релиза:

```sh
bash scripts/update-upstream.sh --yes
```

Команда создаёт резервную копию предыдущих документов и не обновляет правила проекта автоматически.

## Выбери режим

### Headless

Используй сервер `filmcraft-headless` для неинтерактивной обработки. Он запускается как `filmcraft-cli mcp`; без `--demo` или `--project` открывается пустой проект.

Для существующего проекта сгенерируй выделенную конфигурацию:

```sh
python3 scripts/filmcraft_agent.py configure --project /absolute/path/working-copy.fcproj
```

Работай только с одним активным писателем `.fcproj`.

### Bridge

Используй сервер `filmcraft` для текущего desktop и UI. Запускай агента через wrapper, чтобы desktop и MCP унаследовали один токен:

```sh
bash scripts/start-bridge.sh --agent kimi
# или: bash scripts/start-bridge.sh --agent codex
# или: bash scripts/start-bridge.sh --agent claude
```

Для другого клиента передай команду после `--`:

```sh
bash scripts/start-bridge.sh -- /absolute/path/to/agent
```

Не выводи и не сохраняй токен. Desktop, запущенный wrapper, по умолчанию остаётся открытым после выхода агента, чтобы не потерять несохранённую работу.

## Выполняй работу

1. Получи `doc_inspect`; в bridge также `ui_inspect`.
2. Найди команду через `command_list`; не полагайся на статический список.
3. Прочитай реальные ID и параметры.
4. Выполни малый шаг с явными целями.
5. Повтори inspect.
6. Открой `render_frame` или `ui_screenshot`.
7. Исправь ошибку через `edit.undo`, если это безопасно, либо остановись и сообщи.
8. Перед экспортом проверь media, диапазон и путь; после экспорта проверь результат независимо.

Следуй `references/workflow.md`. Для конкретных JSON-цепочек используй только `references/recipes.md` с учётом локальной версии. Для форматов и ограничений обращайся к `references/formats.md` и связанным upstream-документам.

## Ищи в официальной документации

Основные файлы:

- MCP, CLI и рабочий цикл: `references/upstream/docs/agents.md`.
- Control channel и UI: `references/upstream/docs/control-protocol.md`.
- Сохранение, recovery, offline media: `references/upstream/docs/project-files.md`.
- Поддержка форматов: `references/upstream/docs/file-format-parity.md` и `codec-parity.md`.
- Известные ограничения: `references/upstream/docs/gaps.md`.

Большие документы читай точечно. Например:

```sh
grep -n -A 20 -B 5 'file.exportMedia' references/upstream/docs/agents.md
grep -n -A 12 -B 4 'ui.screenshot' references/upstream/docs/control-protocol.md
```

Не загружай весь каталог upstream в контекст без необходимости. Полный живой каталог команд после bootstrap находится в `references/commands.local.json`; `references/commands-v0.20.1.json` — только обезличенный baseline проверенного релиза.

## Проверяй установку

Запускай тесты на изолированном демопроекте:

```sh
bash scripts/smoke-headless.sh
bash scripts/smoke-bridge.sh
python3 scripts/check_project.py
```

Headless проверяет handshake, tools/resources, inspect, живой каталог, обратимый монтажный шаг + undo, PNG и короткий H.264 export. Bridge проверяет UI state, automation elements и screenshot. Они не открывают пользовательский проект.

Если тест не прошёл, не сообщай об успехе. Сохрани точную ошибку и используй `references/troubleshooting.md`.

## Настраивай клиентов

`configure` сохраняет сторонние секции JSON и заменяет только записи `filmcraft` и `filmcraft-headless`. В Codex изменяется только managed block. Резервные копии находятся в `workspace/runtime/config-backup/`.

Поддерживаемые генераторы: Kimi Code, Codex, Claude Code, Cursor, Gemini CLI, VS Code, OpenCode и generic `mcpServers`. Пути и особенности запуска: `references/clients.md`.

Context7 — отдельный необязательный сервер документации. Используй библиотеку `/storytold/filmcraft`; не подменяй ею локальную версию документов.
