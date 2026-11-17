# Рабочий процесс FilmCraft

## Содержание

- Выбор режима
- Discovery и inspect
- Монтаж и проверка
- UI-автоматизация
- Сохранение и экспорт
- CLI fallback

## Выбор режима

| Задача | Режим | Запуск |
|---|---|---|
| Собрать или изменить проект без окна | Headless | `filmcraft-cli mcp --project /abs/copy.fcproj` |
| Проверить MCP на синтетическом проекте | Headless demo | `filmcraft-cli mcp --demo` |
| Управлять открытым приложением | Bridge | `filmcraft-cli mcp --bridge 127.0.0.1:9876` |
| Агент не поддерживает MCP | CLI | `filmcraft-cli --project /abs/copy.fcproj ...` |

Headless создаёт собственную in-process сессию. Bridge подключается к desktop, запущенному с `--control`. UI-only инструменты требуют bridge, даже если их схемы видны клиенту в списке инструментов.

## Discovery и inspect

1. Проверь версии: `filmcraft --version`, `filmcraft-cli --version`.
2. Получи MCP tools/resources и сравни с ожидаемыми возможностями, не с зашитым числом из чужой версии.
3. Вызови `doc_inspect`. Он возвращает `project` и активную `sequence`.
4. Для bridge вызови `ui_inspect`; для поиска виджетов — `ui_elements` с `prefix`.
5. Найди команду:

```json
{"name": "command_list", "arguments": {"filter": "razor", "enabled_only": true}}
```

CLI-эквиваленты:

```sh
filmcraft-cli commands razor
filmcraft-cli describe timeline.razor
filmcraft-cli commands --json
```

`references/commands-v0.20.1.json` — обезличенный baseline, полученный из проверенного бинарника v0.20.1. `references/commands.local.json` — снимок вашей локальной установки, созданный bootstrap. После обновления FilmCraft создай local-файл заново; baseline не используй как живой каталог.

## Монтаж и проверка

Используй цикл:

```text
inspect → найти команду → явные ID → малый edit → inspect → PNG → следующий шаг
```

- Не полагайся на текущее выделение, если команда принимает `clip`, `clips`, `item` или `items`.
- После `file.newSequence` или `sequence.open` заново проверь активную последовательность.
- Для связанных видео и аудио проверь оба клипа и `link`.
- Время в inspect представлено ticks; команды также могут принимать `seconds`, `frame` и `timecode`. Для точного кадра предпочитай `frame`/`timecode`.
- `effects.setParam` с `keyframes: 0` может быть успешным статическим изменением, а не ошибкой.
- `effects.addKeyframe` переключает ключ: читай `added`, чтобы отличить добавление от удаления.
- Не считай `null` или отсутствие ошибки доказательством правильного монтажа.

Визуальная проверка:

```json
{"name": "render_frame", "arguments": {"seconds": 1.0, "max_side": 960}}
```

MCP возвращает PNG как image content. Открой изображение доступным клиенту средством. Если клиент не показывает изображения, сохрани их через `scripts/mcp_client.py` либо используй `file.exportFrame` и прочитай файл.

## UI-автоматизация

1. Запусти desktop через `scripts/start-bridge.sh`.
2. Получи `ui_elements` и выбери automation ID.
3. Используй `ui_click`, `ui_drag`, `ui_key`, `ui_type`; координаты — только если ID отсутствует.
4. После layout-изменения заново получи элементы: прежний ID или rect мог относиться к старому кадру.
5. Проверь `ui_inspect`, `sequence_inspect` и `ui_screenshot`.

`render_frame` в bridge временно перемещает playhead для кадра и восстанавливает его. Не выполняй параллельно другие действия, зависящие от playhead/selection.

## Сохранение и экспорт

Для существующего проекта используй рабочую копию. Команды `file.saveCopy` и `file.saveAs` имеют разное поведение: первая сохраняет копию без смены текущего пути, вторая принимает новый путь как текущий.

Перед экспортом:

```text
doc_inspect → media.status / media.findMissing → диапазон → новый полный path → export
```

Короткий блокирующий экспорт допустим с `wait: true`. Для длительного:

1. Вызови `file.exportMedia` с `wait: false`.
2. Сохрани `job`, `path`, `poll`, `cancel` из результата.
3. Опрашивай `jobs.list`.
4. Проверяй `progress`, `etaSeconds`, `finished`, `result`.
5. При необходимости отмени `jobs.cancel`.

Для последовательности изображений результат может содержать `path`, `lastPath` и `basePath`: используй их вместо предположения об именах файлов.

`offlineMedia: []` обязателен для нормальной сдачи. Непустой список означает, что экспорт мог завершиться с placeholder-кадрами. Остановись и устрани причину.

Независимая проверка:

```sh
python3 scripts/filmcraft_agent.py verify-export /abs/output.mp4 --decode --visual
```

## CLI fallback

Примеры только после получения актуальных схем:

```sh
filmcraft-cli --project /abs/copy.fcproj inspect sequence
filmcraft-cli --project /abs/copy.fcproj --save exec timeline.razor seconds=3.5
filmcraft-cli --project /abs/copy.fcproj export /abs/exports/out.mp4
filmcraft-cli --bridge 127.0.0.1:9876 exec window.workspace.color
```

`--save` перезаписывает открытый проект; используй его только для рабочей копии. Блокировка CLI `--save` не распространяется на desktop и MCP-сессии. Поэтому общий принцип «один писатель» остаётся обязательным.

Полный справочник: `upstream/docs/agents.md`, `upstream/docs/control-protocol.md`, `upstream/docs/project-files.md`.
