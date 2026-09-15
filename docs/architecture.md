# Architecture

## Intent

`gigaam-capture` is a standalone desktop application project that can later be
split into its own repository or forked independently from the core GigaAM
library.

## Layers

- `gigaam_capture.config`: app paths, directory bootstrap, settings persistence
  with validation and defaults for unknown or corrupted values
- `gigaam_capture.log`: rotating file logging and the application logger
- `gigaam_capture.models`: plain dataclasses and state models
- `gigaam_capture.history`: append-only JSONL and text history storage
- `gigaam_capture.services.recording`: microphone capture with progress,
  automatic stop, and an injectable recorder for tests
- `gigaam_capture.services.transcription`: GigaAM model loading and inference
  (the `gigaam` import is lazy, so the rest of the app runs without it)
- `gigaam_capture.services.hotkeys`: global hotkey backend plus hotkey validation
- `gigaam_capture.output_targets`: transcript delivery strategies, platform
  gating, and the startup target fallback
- `gigaam_capture.platform`: platform capabilities and OS-specific automation
  backends
- `gigaam_capture.inspect`: diagnostics entry point
  (`python -m gigaam_capture.inspect`)
- `gigaam_capture.ui`: tray app and user interaction shell

## Why this structure

- UI is separated from core services so the same services can later back a
  Windows tray app, Linux tray app, or a richer desktop shell.
- Output delivery is abstracted so clipboard output can be replaced or extended
  by active-input insertion.
- Platform automation is isolated because Telegram, WhatsApp Desktop, browser
  messengers, and native chat apps require OS-specific focus handling.

## Platform layer

`gigaam_capture.platform` is the only place that knows about OS automation:

- `platform/__init__.py` reports capabilities: for every output target it
  exposes availability, backend name, and the reason a target is unavailable.
  The registration table lists a platform only when its backend exists, so the
  capability report can never promise delivery that the runtime cannot perform.
- `platform/targets.py` holds platform-neutral types: `ActiveAppAutomation`
  (protocol), `ActiveTargetInfo`, `AppProfile`, and `AutomationPermissionError`.
  `ActiveTargetInfo` carries macOS bundle/role data as well as Windows
  process/class/control-type data, so history metadata and diagnostics share one
  shape.
- `platform/macos.py` implements `MacOSPasteAutomation`: Accessibility trust
  checks, frontmost app/window/role lookup, bundle-aware role policy, synthetic
  `Cmd+V`.
- `platform/windows.py` implements `WindowsPasteAutomation`: a `ctypes`-based
  Win32 adapter (foreground window, window text, class name, focused window,
  process image name), per-process app profiles, and optional UI Automation
  focus inspection; paste is `Ctrl+V` through `pynput`.
- `platform/windows_uia.py` reads the focused UI Automation element through COM
  (`comtypes`) and maps control type ids to readable names.
- `platform/automation.py` remains a thin facade: it re-exports shared types and
  dispatches `create_active_app_automation()` by `sys.platform`, keeping the
  backend classes importable from the historical module path.

Focus-validation policy on both platforms follows the same idea: strict generic
rules, relaxed rules only for recognized application profiles, and rejection
messages that name the frontmost target plus an actionable focus hint.

## Delivery behavior

- `clipboard` is the default and the only target available everywhere.
- `active-text-field` is validated before paste and falls back to the clipboard
  when `fallback_to_clipboard` is enabled.
- Delivery always produces a `DeliveryOutcome` (`delivered`,
  `fallback-clipboard`, or `failed`) that is written into the history record and
  reported through tray notifications. A failed delivery moves the controller to
  the `error` state, so the app can never get stuck in `transcribing`.
- A target that is not supported on the current platform is replaced by
  clipboard delivery at startup with a warning, and the settings dialog only
  offers supported targets.

## Recording behavior

`RecordingService` collects microphone chunks through an injectable recorder
interface, which keeps it testable without audio hardware:

- `elapsed_seconds` / `remaining_seconds` drive the tray countdown
- `poll()` finishes the capture once the configured limit is reached, which the
  controller calls from a `QTimer` tick
- `stop()` writes only the frames that were actually captured, so the reported
  duration matches the audio file
- shutdown stops an in-flight capture instead of leaving the stream open

## Observability

Every layer logs through `gigaam_capture.log` into
`<user data dir>/logs/app.log` (rotating, 1 MB x 3). The stream handler is
limited to warnings and errors so CLI tools and the tray app stay quiet during
normal operation.

`python -m gigaam_capture.inspect` renders the same capability and target
information that the tray menu reports, in text or JSON form.

## Planned platform backends

- Linux: separate backend strategy for X11 and Wayland, clipboard-first fallback
  likely required for some environments.

## Expected future split

When this project is mature enough to move into a separate repository, the
intended boundary is:

- keep `gigaam` as the model library dependency (installed from source, because
  PyPI only hosts a stale release)
- publish a dedicated app package and desktop build pipeline

## Roadmap documents

- [`docs/roadmap.md`](./roadmap.md)
- [`docs/platform-notes.md`](./platform-notes.md)
- [`docs/build-journal.md`](./build-journal.md)
