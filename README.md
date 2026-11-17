# FilmCraft Starter

**Стартовый пакет для FilmCraft: MCP, правила для AI-агентов, официальная документация, конфигурации клиентов и реальные проверки на Linux.**

Независимый проект для управления ArtCraft FilmCraft через штатный MCP-сервер, `filmcraft-cli` и desktop bridge. Подходит для Kimi Code, Codex, Claude Code, Copilot, Cursor, Gemini CLI, OpenCode и других stdio-совместимых клиентов.

> Это не официальный релиз ArtCraft. Исходные документы FilmCraft сохранены с лицензиями и атрибуцией; файлы стартового пакета распространяются по MIT. Подробности: `NOTICE.md`.

## Быстрый старт

Требования: Linux, FilmCraft и `filmcraft-cli`, Python 3.11+, а для полного export-теста — `ffmpeg` и `ffprobe`.

```sh
git clone https://github.com/i4w7w4a/filmcraft-starter.git
cd filmcraft-starter
bash scripts/bootstrap.sh
```

`bootstrap.sh` определяет вашу установку FilmCraft, создаёт локальные проектные MCP-конфиги и живой каталог команд, затем запускает статические и unit-проверки. Глобальные настройки в домашнем каталоге он не изменяет.

Для нестандартных путей:

```sh
bash scripts/bootstrap.sh \
  --app /absolute/path/to/filmcraft \
  --cli /absolute/path/to/filmcraft-cli
```

Готовый пакет находится в `dist/filmcraft-agent.skill`. Его SHA-256: `ee5e0e30890331fb20c87c8cfceda80dfa742b761ff46e28fb1bfa1ffc28e215`. Проверка из каталога `dist/`: `sha256sum -c SHA256SUMS.txt`.

## Проверка

```sh
python3 scripts/check_project.py
bash scripts/smoke-headless.sh
bash scripts/smoke-bridge.sh
```

- Headless: MCP initialize, 17 tools, resources, inspect, живой каталог, обратимый монтаж и undo, PNG, короткий H.264 export, `offlineMedia`, ffprobe, полный decode и RGB-проверка кадра.
- Bridge: изолированный демопроект, UI state, automation elements и screenshot.
- Пользовательские проекты тесты не открывают.

После обновления FilmCraft или изменении путей:

```sh
bash scripts/bootstrap.sh --refresh
```

## Запуск агента

### Headless

Откройте корень репозитория в нужном клиенте, проверьте launch target и доверие проекту, затем начните новую сессию.

- Kimi Code и Codex: `/mcp`.
- OpenCode: `opencode mcp list`.
- Другой stdio-клиент: `config/mcp.json`.

Для конкретной рабочей копии:

```sh
python3 scripts/filmcraft_agent.py configure \
  --project /absolute/path/to/working-copy.fcproj
```

### Desktop bridge

```sh
bash scripts/start-bridge.sh --agent kimi
bash scripts/start-bridge.sh --agent codex
bash scripts/start-bridge.sh --agent claude
bash scripts/start-bridge.sh --agent opencode
bash scripts/start-bridge.sh --agent gemini
bash scripts/start-bridge.sh --agent code
```

Для другого клиента:

```sh
bash scripts/start-bridge.sh -- /absolute/path/to/agent
```

Wrapper создаёт временный `FILMCRAFT_CONTROL_TOKEN` только в окружении процессов и не записывает его в файлы. Запущенный FilmCraft по умолчанию остаётся открытым после выхода агента.

## Что входит

- `AGENTS.md` — обязательные правила для всех агентов.
- `SKILL.md` — компактный переносимый навык FilmCraft.
- `references/safety.md` — token, записи, подтверждения и параллельные сессии.
- `references/workflow.md` — монтаж, UI, сохранение и экспорт.
- `references/recipes.md` — проверяемые командные цепочки.
- `references/clients.md` — конфигурации и запуск клиентов.
- `references/troubleshooting.md` — диагностика.
- `references/upstream/` — официальная документация FilmCraft v0.20.1.
- `references/commands-v0.20.1.json` — baseline из 718 команд.
- `dist/` — готовый `filmcraft-agent.skill` и SHA-256.
- `tests/results/baseline-v0.20.1.json` — обезличенный отчёт проверки.
- `tests/baseline/` — изображения реальных MCP-проверок.

Главный принцип: после команды агент повторно читает состояние, а визуальное изменение проверяет по PNG. Успешный ответ команды не доказывает правильность монтажа или экспорта.

## Context7

Context7 не требуется для управления FilmCraft. Это отдельный необязательный сервер документации: шаблон `assets/templates/context7.mcpServers.json`, библиотека `/storytold/filmcraft`. Локальные документы нужного тега и живой каталог команд имеют приоритет.

## Обновление документации

```sh
bash scripts/bootstrap.sh --refresh
bash scripts/update-upstream.sh --yes
bash scripts/smoke-headless.sh
bash scripts/smoke-bridge.sh
```

Поддерживается также проверенное офлайн-зеркало с явным `--repo` и полным `--commit`. Неизвестные зеркала не используйте.

## Проверено на FilmCraft 0.20.1

- Официальный Linux x86_64-архив прошёл SHA-256.
- 69 файлов документации и их хэши проверены.
- MCP 2025-06-18: 17 tools и оба resources.
- Headless и bridge прошли на изолированном демопроекте.
- H.264: 13 кадров, `offlineMedia: []`, полный decode и визуальная RGB-проверка.
- OpenCode v2 прошёл официальную JSON Schema без ошибок.
- Merge, backup, managed replacement и конфликтная остановка проверены автотестами.
- После упаковки `.skill` был заново распакован, и тесты повторены на нём.

Приложения Kimi Code, Codex, Claude Code, Cursor, Gemini CLI, VS Code и OpenCode в среде сборки не были установлены. Их конфиги проверены по актуальным официальным форматам, но клиентские approvals, показ PNG и переподключение нужно проверить локально. Не все 718 команд, кодеки и GPU-пути тестировались.

## Лицензии

Файлы проекта — MIT (`LICENSE`). Документы и изображения FilmCraft сохраняют исходные лицензии и атрибуцию (`NOTICE.md`, `references/upstream/`, `references/provenance.md`).
