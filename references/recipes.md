# Проверяемые рецепты

Эти цепочки основаны на официальной документации и тестах FilmCraft v0.20.1. Перед применением к другой версии повтори discovery. Не переноси ID из примеров в реальный проект.

## Безопасный headless smoke

Запуск: `filmcraft-cli mcp --demo`.

### Inspect

```json
{"name": "doc_inspect", "arguments": {}}
```

Ожидай объект с `project` и непустой `sequence` для demo.

### Найти команду

```json
{"name": "command_list", "arguments": {"filter": "timeline.razor"}}
```

### Обратимый edit на demo

```json
{
  "name": "command_run",
  "arguments": {"id": "sequence.addEditAllTracks", "params": {"seconds": 2.0}}
}
```

Проверь `cuts >= 1`, затем:

```json
{"name": "command_run", "arguments": {"id": "edit.undo", "params": {}}}
```

Не выполняй этот рецепт на пользовательском проекте как тест.

### PNG

```json
{"name": "render_frame", "arguments": {"seconds": 1.0, "max_side": 320}}
```

Сохрани image content и открой PNG.

### Короткий H.264

```json
{
  "name": "command_run",
  "arguments": {
    "id": "file.exportMedia",
    "params": {
      "path": "/absolute/new-directory/smoke.mp4",
      "format": "h264",
      "width": 640,
      "height": 360,
      "audio": false,
      "range": "custom",
      "startSeconds": 1.0,
      "endSeconds": 1.5,
      "wait": true
    }
  }
}
```

Проверь `offlineMedia: []`, фактический `path`, файл и длительность. Весь сценарий автоматизирован:

```sh
bash scripts/smoke-headless.sh
```

## Bridge read-only smoke

Запуск через wrapper на изолированном demo:

```sh
bash scripts/smoke-bridge.sh
```

Проверяются:

```json
{"name": "ui_inspect", "arguments": {}}
{"name": "ui_elements", "arguments": {"prefix": "tools."}}
{"name": "ui_screenshot", "arguments": {"max_side": 800}}
```

## Реальный монтаж — только с живыми ID

1. Создай рабочую копию `.fcproj` и настрой headless с `--project`.
2. Вызови `doc_inspect`.
3. Импортируй по абсолютным путям:

```json
{
  "name": "media_import",
  "arguments": {"paths": ["/absolute/media/example.mp4"]}
}
```

4. Повтори `project_inspect`, получи новый `item` ID.
5. Найди параметры `timeline.place` через `command_list`.
6. Размести клип, повтори `sequence_inspect`, проверь связанные video/audio ID.
7. Выполни один монтажный шаг и снова inspect + PNG.
8. Сохрани через `file.saveCopy` либо в согласованный новый путь.

Не используй `item: 1`, `clip: 87` и похожие значения из документации: они относятся к другому проекту.

## Длительный экспорт

Запусти `file.exportMedia` с `wait: false`. Ответ содержит подсказки `poll: "jobs.list"` и `cancel: "jobs.cancel"`.

```json
{"name": "command_run", "arguments": {"id": "jobs.list", "params": {}}}
```

После `finished: true` проверь `result`, `offlineMedia`, `warnings` и файл. Отмена:

```json
{
  "name": "command_run",
  "arguments": {"id": "jobs.cancel", "params": {"job": 123}}
}
```

`123` — placeholder: используй реальный ID задания из первого ответа.

## Проверка готового файла

```sh
python3 scripts/filmcraft_agent.py verify-export /absolute/output.mp4 --decode --visual
python3 scripts/mcp_client.py --mode demo call render_frame '{"seconds":1,"max_side":320}' --images workspace/previews
```

## Что не считается рецептом

- Команда, найденная только в старом community skill.
- Цепочка, которая завершилась без ошибки, но не проверена inspect/PNG.
- Экспорт, для которого не проверен `offlineMedia`.
- Команда из актуального каталога, если её поведение на текущем кодеке/GPU не проверено.
