# Диагностика

## `filmcraft-cli not found`

Проверь:

```sh
command -v filmcraft filmcraft-cli
filmcraft --version
filmcraft-cli --version
```

Для deb/rpm официальная документация указывает `/usr/bin/filmcraft-cli`. Для AppImage, Flatpak и portable-пакета не угадывай внутренний путь: передай реальные исполняемые файлы через `--app` и `--cli`. Если пакет содержит только desktop, MCP через `filmcraft-cli` из него не появится автоматически.

## Версия docs не совпадает

Сравни `workspace/runtime/probe.json` и `references/upstream-manifest.json`. Выполни `bash scripts/update-upstream.sh --yes`, затем `dump-commands` и оба smoke-теста. Не заменяй правила автоматически.

## Bridge не запускается

- Нужен token длиной 64 hex; используй wrapper, а не ручной статический token.
- Desktop и MCP должны находиться в одном наследуемом окружении.
- Адрес должен быть loopback и совпадать с `--control`.
- Если порт занят неизвестным процессом, не подключайся вслепую и не убивай его. Выбери другой `--address 127.0.0.1:<port>` и заново выполни configure.
- Проверь desktop log в `workspace/runtime/bridge-data/agent-logs/` или каталоге конкретного smoke-теста. Не публикуй его с приватными путями.

## Нет окна или screenshot зависает

Проверь `DISPLAY`/`WAYLAND_DISPLAY` в `probe`. UI screenshot требует представленного кадра; скрытое окно или sleeping display могут вызвать ошибку. Для CI используй реальный/virtual display и `--graphics software`, если аппаратный путь нестабилен. Headless рендер окна не требует.

## Клиент не видит новый MCP

После изменения конфига начни новую сессию. Проверь workspace trust. В Kimi Code используй `/mcp`, в Codex — `/mcp`. Не повторяй запуск с одним и тем же неверным путём: исправь `--cli` и перегенерируй конфиг.

## MCP отвечает `unknown argument`

Аргументы MCP-инструментов строгие. Проверь `inputSchema` через `tools/list`. Не путай аргумент инструмента с `command_run.params`: внутренние параметры команды передаются дальше в engine и имеют собственную схему из `command_list`.

## `no sequence`, `no clips selected`

Сделай `doc_inspect`: headless без `--demo` и `--project` начинает пустым. Открой или создай последовательность. По возможности передай явные `clip`/`clips`/`item`, а не полагайся на selection.

## Export создал неожиданное имя

Используй фактические `path`, `lastPath`, `basePath` результата. Для image sequence переданное имя может стать базой для нумерованных файлов. Не удаляй файлы по маске, пока не сверишь эти поля.

## Export успешен, но кадры с placeholder

Проверь `offlineMedia` и `media.status`. Успешная запись файла не отменяет placeholder. Устрани missing/offline/unreadable media и повтори экспорт в новый путь.

## Длительный export оборвался по timeout клиента

Используй `wait: false`, затем `jobs.list`. Не увеличивай timeout безгранично. При отмене применяй `jobs.cancel` и проверяй, что задание завершилось, прежде чем использовать выходной файл.

## `ffprobe`/`ffmpeg` отсутствуют

Проект продолжит работать, но независимая проверка будет неполной. Отчёт явно содержит warning. Не заменяй отсутствующую проверку фразой «файл корректный»: можно подтвердить только существование, размер и хэш.

## Не удалось получить документы из GitHub

Сохрани текущую версию `references/upstream/`; не подменяй её Context7. Повтори официальный `update-docs` позже. Команда использует sparse checkout только нужных файлов, сверяет commit релиза и создаёт backup перед заменой. Для заранее проверенного офлайн-зеркала передай `--repo /absolute/mirror --commit <полный-SHA>`; не используй неизвестный репозиторий как источник документации.
