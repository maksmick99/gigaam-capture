# GigaAM Capture — дорожная карта (Roadmap)

Документ описывает реалистичный план развития `gigaam-capture` от текущего MVP к beta/релизу и далее к кроссплатформенному продукту.

> Контекст: приложение выделено в отдельный репозиторий `gigaam-capture` и намеренно отделено от основной библиотеки `gigaam`, которая подключается как зависимость.

---

## 0. Видение и границы

### Vision
`GigaAM Capture` — утилита “говорю → получаю текст” с минимальным трением:
- глобальная горячая клавиша → запись → транскрибация → доставка результата (clipboard / вставка в активное поле),
- понятная диагностика (почему не вставилось / почему не записалось),
- история результатов и повторное использование.

### Non-goals (на ближайшие этапы)
- Не строим сразу большой “редактор транскриптов” — сначала стабильный capture-поток.
- Не делаем сложные app-specific селекторы для мессенджеров, пока не стабилизирован общий backend.
- Не оптимизируем инференс “до последнего миллисекунд” до появления реальных performance bottlenecks.

### Архитектурные принципы
- **UI отдельно от сервисов**: запись/транскрибация/доставка/история должны быть переиспользуемыми.
- **OutputTarget как стратегия**: любая доставка текста должна подключаться без “ветвления” UI-логики.
- **Платформенная автоматизация изолирована**: `platform/*` — единственное место для Accessibility/Automation.
- **Безопасность пользователя**: automation не должен “вслепую” вставлять в непонятный контекст; должен уметь валидировать и объяснять ошибки.

---

## 1. Milestones (крупные вехи)

Ниже — вехи, каждая заканчивается состоянием, которое можно показать пользователям/команде и измерить.

### M1 — Stable macOS MVP (Hardening)
**Цель:** стабильное ежедневное использование на macOS (clipboard и `active-text-field`).

**Deliverables**
- Улучшенный UX статусов (recording/transcribing/delivered/failed).
- Устойчивость state machine контроллера к гонкам.
- Улучшенная обработка ошибок (чёткие сообщения по правам Accessibility/микрофона).
- Фолбэк: если `active-text-field` не сработал — безопасное завершение + понятный fallback в clipboard (настраиваемый).
- Структурированное логирование (локальный файл) для диагностики.

**Definition of Done**
- 20+ последовательных попыток записи/вставки без зависаний UI.
- Все error paths дают actionable текст (что сделать пользователю).
- Набор unit-тестов покрывает ключевые переходы `idle → recording → transcribing → idle/error`.

**Риски**
- Accessibility/permissions сильно зависят от окружения пользователя.
- У разных приложений разные роли/контексты фокуса (`AXWebArea` и т.п.).

---

### M2 — Usability & History Viewer
**Цель:** сделать историю и повторное использование транскриптов “первоклассной функцией”.

**Deliverables**
- Окно/диалог “History” (последние N записей) с действиями:
  - открыть WAV/TXT,
  - скопировать текст,
  - повторить доставку (paste/copy).
- Хранение метаданных: модель, длительность, target_hint, статус доставки.
- Retention policy (лимит записей/размера, автоочистка WAV — configurable).

**Definition of Done**
- Пользователь может найти последнюю транскрибацию за 2 клика.
- История не растёт бесконтрольно.

---

### M3 — macOS Beta Packaging
**Цель:** сборка и распространение macOS версии, близкой к “первому публичному тесту”.

**Deliverables**
- Упакованное приложение (app bundle).
- Иконка, корректное поведение в tray/menu bar.
- Guided onboarding по правам Microphone/Accessibility.
- Экспорт diagnostics bundle (лог + версия + platform info).

**Definition of Done**
- “С нуля” установка и запуск на чистом macOS профиле без ручных правок.
- Ясный путь “почему не работает вставка” через Inspect + onboarding.

---

### M4 — Windows + Linux baseline (Clipboard-first)
**Цель:** кроссплатформенный baseline без обещаний сложной автоматизации.

**Deliverables**
- Windows: запись + транскрибация + clipboard target.
- Linux: запись + транскрибация + clipboard target (с оговорками по окружению).
- Единый capability matrix в документации.

**Definition of Done**
- Приложение запускается и делает транскрибацию на Windows/Linux в типовом окружении.

---

### M5 — Advanced product features
**Цель:** расширение продукта после стабилизации и первых релизов.

Кандидаты:
- Long-form режим (VAD сегментация, фоновые задачи, прогресс).
- “Preview before paste” (окно подтверждения/редактирования перед вставкой).
- App-specific adapters (Telegram/WhatsApp/web) при наличии реальных ограничений и репортов.
- Оптимизации: ONNX/ускорение для desktop-режима, прогрев модели, prefetch.

---

## 2. Workstreams (параллельные потоки работ)

Чтобы удобно рисовать roadmap/диаграмму, задачи лучше группировать по потокам:

1. **Capture Flow & UX**
   - статусы, уведомления, таймер записи, отмена, retries.
2. **Automation / Output Targets**
   - `clipboard`, `active-text-field`, inspect/validate/deliver/fallback.
3. **Data & History**
   - модель данных истории, просмотр, ретеншн.
4. **Packaging & Release**
   - сборка, подпись, дистрибуция, versioning.
5. **Quality**
   - тесты, регрессии, ручная матрица проверок.
6. **Docs & Support**
   - onboarding, troubleshooting, known issues.

---

## 3. Backlog (эпики → фичи)

### Epic A — Стабилизация state machine
- Зафиксировать и документировать допустимые переходы состояний.
- Добавить защиту от повторных нажатий и параллельных запусков worker.
- Покрыть тестами failure paths.

### Epic B — Устойчивое delivery поведение
- Unified delivery result: success/failure + reason.
- Fallback политика (настройка):
  - `active-text-field` failed → copy to clipboard + toast.
- Улучшение восстановления clipboard (особенно при исключениях).

### Epic C — Улучшение UX записи
- Таймер записи.
- Индикатор (tooltip/menu status) с оставшимся временем.
- Ясный сигнал начала/окончания записи.

### Epic D — Диагностика и логирование
- Локальный лог-файл в user data dir.
- Кнопка “Export diagnostics”.
- Расширить `Inspect active target`: показывать capability + permissions.

### Epic E — История и viewer
- UI viewer.
- Действия над элементом истории.
- Retention.

### Epic F — Packaging
- macOS: app bundle pipeline.
- Windows/Linux: позже, после baseline.

---

## 4. Release criteria (что считать “готово”)

### Для Beta (macOS)
- Нет зависаний UI.
- Понятные ошибки по permissions.
- `clipboard` режим работает всегда.
- `active-text-field` либо работает, либо корректно объясняет и делает fallback.
- Есть минимальная диагностика (лог + inspect).

### Для v1.0
- История с viewer.
- Packaging и onboarding.
- Стабильность на “реальной” матрице приложений (Telegram/WhatsApp/браузеры).

---

## 5. Предложение по таймлайну (6–8 недель)

Это примерный план, который удобно “нарисовать” на диаграмме.

### Sprint 1 (M1)
- Stabilize controller state machine + тесты.
- Улучшить тексты ошибок и уведомления.
- Fallback delivery политика.

### Sprint 2 (M1)
- Таймер/индикатор записи.
- Структурированный лог.
- Улучшить Inspect, чтобы в 1 шаг диагностировать permissions и фокус.

### Sprint 3 (M2)
- History viewer (минимальный).
- Actions: copy/open/retry.
- Retention policy.

### Sprint 4 (M3)
- Onboarding permissions.
- Packaging scaffold для macOS.
- Smoke тесты на реальных приложениях.

Дальше (после Beta): Windows/Linux baseline + advanced features.

---

## 6. Параллельный трек: библиотека `gigaam`

Чтобы не смешивать цели:
- `gigaam` развивается по своим задачам (качество моделей, инференс, ONNX/Triton, longform).
- `gigaam-capture` потребляет `gigaam` как зависимость и прежде всего требует **стабильных API**:
  - `gigaam.load_model(...)`
  - `model.transcribe(...)`
  - (опционально) warmup / прогресс / отмена в будущем.

Если появятся требования “модель грузится слишком долго / нужен прогресс”, это оформляется как отдельный epic на стороне `gigaam`.

---

## 7. Отметка о состоянии (обновлено)

### Сделано

- **Воспроизводимость:** `pythonpath = ["src"]` для pytest, extras `dev`/`windows`/`macos`/`asr`,
  ленивый импорт `gigaam` (тесты идут без ASR-рантайма), CI-матрица
  `ubuntu`/`macos`/`windows` x Python 3.10/3.12 с ruff и coverage.
- **Стабилизация capture-потока (эпики A, B):** доставка обёрнута в `DeliveryOutcome`
  (`delivered` / `fallback-clipboard` / `failed`), при сбое — переход в `error`,
  а не «залипание» в `transcribing`; настраиваемый fallback в clipboard;
  настройки применяются только после успешной валидации target'а.
- **Платформенные возможности:** `platform/__init__.py` отдаёт capabilities
  (доступность, backend, причина), диалог настроек показывает только доступные
  режимы, при старте неподдерживаемый target заменяется на clipboard с предупреждением.
- **Запись (эпик C):** корректная длительность (по реально записанным кадрам),
  автостоп по лимиту через `poll()` + `QTimer`, таймер/остаток времени в tray,
  остановка захвата при выходе, никаких `sd.wait()` в UI-потоке.
- **Диагностика (эпик D):** ротируемый лог `<user data dir>/logs/app.log`,
  CLI `python -m gigaam_capture.inspect` (текст и `--json`), tray-пункт
  `Inspect active target`, сообщения об ошибках с указанием frontmost-таргета.
- **Windows-паритет (этап M4 из раздела 3):** backend `active-text-field` для Windows —
  Win32 через `ctypes` (foreground/focus/class/process) + инспекция фокуса через
  UI Automation (`comtypes`), профили процессов для Telegram/WhatsApp/Discord/Slack
  и браузеров, `Ctrl+V` через `pynput`, отдельное сообщение про UIPI (UAC/elevation).
- **Общие ценности:** единые типы `ActiveTargetInfo`/`AppProfile` в `platform/targets.py`,
  macOS-backend вынесен в `platform/macos.py`, `platform/automation.py` — тонкий фасад
  с диспетчеризацией.
- **Конфиг:** устойчивость к битому/расширенному `settings.json` (неизвестные ключи
  игнорируются, невалидные значения → defaults), валидация хоткея, платформенные
  дефолты хоткея (`<cmd>+<shift>+r` на macOS, `<ctrl>+<alt>+r` на Windows/Linux).

### Осталось

- **M1 (macOS hardening):** явная state machine с документированными переходами,
  onboarding по разрешениям (микрофон + Accessibility), экспорт diagnostics bundle.
- **M2:** viewer истории (окно со списком, действия copy/open/retry/delete),
  retention policy и автоочистка WAV.
- **M3:** упаковка (app bundle/установщик), иконка, подпись/нотаризация, CHANGELOG.
- **Linux:** backend для X11/Wayland или явная политика clipboard-only.
- **Ручная матрица проверок** на реальных мессенджерах (см. `docs/platform-notes.md`).
