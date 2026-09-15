# План: Windows-primary runtime baseline (M4)

Статус: implementation-ready
Целевая стадия: перейти от текущего pre-beta MVP к воспроизводимому Windows-runtime baseline.

## 1. Текущее состояние проекта

### Стадия

Проект находится на стадии **functional MVP / pre-beta**:

- это уже не scaffold: есть рабочий слой сервисов, tray UI, фоновая транскрибация, настройки и хранение истории;
- это ещё не beta/release: нет Windows backend, полноценной кроссплатформенной проверки, packaging, CI, богатой истории, onboarding и стабильностного набора тестов;
- текущая документация частично опережает или отстаёт от кода.

Репозиторий чистый, основной код находится в корне проекта, хотя `docs/build-journal.md` и `docs/roadmap.md` продолжают называть путь `apps/gigaam-capture`.

### Уже реализовано

- PySide6 tray application shell и меню (`src/gigaam_capture/ui/tray.py`).
- Глобальный hotkey через `pynput`, с сигналом в Qt event loop.
- Запись короткого audio в WAV через `sounddevice`/`soundfile`.
- GigaAM transcription service и запуск inference в `QThread`.
- Settings dialog и JSON settings persistence.
- История в JSONL и отдельных TXT-файлах.
- Clipboard output target.
- macOS active-text-field backend через clipboard + synthetic `Cmd+V`, Accessibility permission check, focus-role validation и app profiles для Telegram/WhatsApp/browser bundles.
- Tray action `Inspect active target`.
- Базовые unit-тесты config/history/controller/macOS automation.

### Главные пробелы и риски

- `gigaam` импортируется, но отсутствует в `pyproject.toml` dependencies (`pyproject.toml:14-20`).
- `create_active_app_automation()` бросает `NotImplementedError` на Windows/Linux (`src/gigaam_capture/platform/automation.py:305-311`).
- Windows hotkey default сейчас macOS-специфичный `<cmd>+<shift>+r`.
- Ошибки history/delivery в `_on_transcription_completed()` не превращаются в управляемый fallback/state transition (`src/gigaam_capture/ui/tray.py:111-133`).
- Нет безопасного shutdown для активной записи/worker thread.
- Нет validation hotkey/model/target перед сохранением settings.
- Нет structured log/diagnostics bundle.
- Нет тестов recording/transcription/Windows backend/full capture flow.
- Нет packaging, CI, lockfile и release matrix.
- `docs/build-journal.md`, `docs/architecture.md` и `docs/roadmap.md` содержат устаревшие или противоречивые утверждения.

Тесты в этой planning-сессии не запускались: выполнение pytest было заблокировано правилами среды. Это нужно повторить на этапе реализации.

## 2. Принятые продуктовые решения для следующей вехи

1. Следующая веха — **M4: Windows-primary runtime baseline**, а не packaging.
2. Целевая среда: Windows 10/11 x64, Python >=3.10, чистый venv, запуск из исходников/editable install.
3. Linux остаётся экспериментальным: проверить запуск/clipboard там, где позволяет окружение, документировать ограничения; Linux не является acceptance gate этой вехи.
4. Windows active-text-field входит в M4 как **generic paste backend**: clipboard + synthetic `Ctrl+V`, без app-specific selectors и без полноценной UI Automation.
5. Если Windows paste падает: сохранить transcript в историю, скопировать его в clipboard и показать warning.
6. Hotkey defaults выбираются по ОС: macOS — `<cmd>+<shift>+r`, Windows/Linux — `<ctrl>+<shift>+r`.
7. GigaAM добавляется как pinned git submodule (рекомендуемый путь `third_party/gigaam`), с зафиксированным commit и проверенным API `load_model`/`transcribe`.
8. Smoke-test использует default-модель `v3_e2e_rnnt`; веса не коммитятся, а загружаются/хранятся в user cache.
9. Packaging, установщики, подпись, Linux full support, history viewer, long-form и app-specific adapters не входят в эту веху.

## 3. План работ

### Шаг 1. Зафиксировать dependency boundary GigaAM

- Добавить `third_party/gigaam` как git submodule и зафиксировать совместимый commit.
- Проверить в выбранном commit наличие `v3_e2e_rnnt`, API загрузки модели, inference API и способ cache/download весов.
- Добавить воспроизводимый bootstrap: установка GigaAM из submodule и затем `gigaam-capture` в тот же venv.
- Добавить runtime check с понятной ошибкой, если submodule/API отсутствует.
- Не коммитить model weights и не добавлять плавающую PyPI-зависимость.

Acceptance: чистая Windows-машина может установить обе части проекта по documented commands; версия GigaAM определяется зафиксированным SHA.

### Шаг 2. Ввести platform capability matrix

- Описать возможности по платформам: clipboard, active-text-field, global hotkey, audio, diagnostics.
- Реализовать platform-specific default hotkey и validation hotkey syntax.
- На Windows разрешить `clipboard` и generic `active-text-field`.
- На Linux оставить clipboard runtime path, а active-text-field явно marked unsupported с actionable сообщением.
- Обновить settings UI: недоступные режимы должны быть отключены или подписаны, а не падать только во время доставки.
- Обновить `PLANNED_AUTOMATION`, чтобы статус macOS отражал реализованный backend.

Acceptance: на каждой ОС factory возвращает поддерживаемый target или понятную capability error; настройки не сохраняют заведомо недоступную комбинацию.

### Шаг 3. Реализовать Windows generic paste backend

- Добавить `WindowsPasteAutomation` в `platform/automation.py`.
- Использовать clipboard для передачи transcript и synthetic `Ctrl+V` для вставки.
- Сохранять и восстанавливать предыдущее содержимое clipboard.
- Проверять наличие foreground window и корректно обрабатывать отсутствие фокуса/ошибки keyboard injection.
- Не добавлять Telegram/WhatsApp/browser selectors в этой вехе.
- Добавить `describe_target()` с названием foreground app/window, насколько это надёжно доступно.
- Реализовать fallback на clipboard в controller при любой delivery failure.

Acceptance: в Notepad/другом обычном text field Windows transcript вставляется одним hotkey flow; при simulated backend failure transcript остаётся в clipboard и пользователь получает warning.

### Шаг 4. Укрепить capture state machine и lifecycle

- Явно описать переходы `idle -> recording -> transcribing -> idle/error` и запретить повторные запуски.
- Обработать исключения recording, history append, transcription и delivery без зависания в `transcribing`.
- Освобождать worker/thread в `finally`-подобном lifecycle и корректно завершать их при quit.
- Добавить безопасный cancel/stop для активной записи и очистку partial WAV при ошибке.
- Проверить enforcement max duration и отсутствие утечек audio handles.
- Сделать update settings транзакционным: validation -> apply in memory -> save; откат при ошибке.
- Добавить structured local log в user data dir с основными state transitions и delivery errors.

Acceptance: 20 последовательных capture attempts на Windows не зависают, не создают параллельные workers и всегда возвращаются в `idle` или управляемый `error`.

### Шаг 5. Расширить тестовую пирамиду

- Unit-тесты platform factory и platform-specific hotkey defaults.
- Unit-тесты Windows backend с fake clipboard/key injection и fallback.
- Unit-тесты recording service с patched `sounddevice`/`soundfile`.
- Unit-тесты transcription service с fake `gigaam.load_model`/model.
- Controller tests для success, transcription failure, history failure, delivery failure, fallback и shutdown.
- Settings validation/persistence tests, включая malformed JSON и unsupported target.
- Один integration/smoke test с реальной моделью `v3_e2e_rnnt` на Windows; качество текста не является критерием, критерий — model load + inference без исключения на коротком WAV.
- Не включать model weights в repository или CI artifacts.

Acceptance: обычный `pytest` быстрый и не требует модели/OS permissions; real-model smoke запускается отдельной командой/маркером и документируется.

### Шаг 6. Обновить документацию и operational flow

- Исправить путь проекта в docs: текущий repo root, а не `apps/gigaam-capture`.
- Обновить README install/run для Windows venv и pinned submodule.
- Добавить capability matrix и отдельные секции macOS/Windows/Linux limitations.
- Описать hotkey defaults, Accessibility/Microphone permissions, clipboard fallback и inspect action.
- Описать model cache, smoke-test command и troubleshooting.
- Привести `architecture.md`, `roadmap.md` и `build-journal.md` в соответствие с фактическим кодом; отметить выполненные и будущие вехи.

Acceptance: новый разработчик может установить проект и понять, что работает на Windows, что экспериментально на Linux и что требует macOS permissions.

### Шаг 7. Финальная Windows validation

На чистой Windows 10/11 x64:

1. Создать новый venv Python >=3.10.
2. Инициализировать pinned GigaAM submodule и установить GigaAM + app.
3. Запустить `pytest`, compile check и app launch.
4. Проверить default `<ctrl>+<shift>+r`, recording, transcription, clipboard delivery.
5. Проверить generic active-field paste в обычном text field.
6. Проверить fallback при simulated/real delivery failure.
7. Проверить settings persistence, inspect action, shutdown и отсутствие зависаний.
8. Запустить real-model smoke с `v3_e2e_rnnt` и коротким WAV.
9. Сохранить результаты и известные ограничения в docs.

Acceptance: все обязательные проверки выше проходят без ручных изменений кода; packaging/installer не требуется.

## 4. Definition of Done для M4

- Windows runtime устанавливается из чистого venv по документации.
- Windows clipboard и generic active-field delivery работают или дают безопасный clipboard fallback.
- GigaAM pinned и воспроизводим; веса не хранятся в repo.
- Реальный `v3_e2e_rnnt` smoke проходит на Windows.
- State machine не зависает и корректно обрабатывает failure paths.
- Hotkey defaults platform-specific и валидируются.
- Linux описан как experimental; отсутствие full Linux automation не блокирует M4.
- Документация не содержит утверждений, противоречащих коду.
- Packaging, signing, history viewer, long-form и app-specific adapters явно остаются вне этой вехи.

## 5. Последующий backlog после M4

1. M1 hardening: richer status/timer, cancellation, diagnostics bundle, broader error messages.
2. M2 history viewer: список записей, open/copy/retry, metadata delivery status, retention policy.
3. M3 macOS packaging: app bundle, icon, permissions onboarding, clean-profile smoke test.
4. Linux baseline: отдельная веха для X11/Wayland hotkey/audio/clipboard capability.
5. Advanced features: long-form/VAD, preview before paste, app-specific adapters, model warmup/optimization.
