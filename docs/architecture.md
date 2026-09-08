# Architecture

## Intent

`gigaam-capture` is a standalone desktop application project that can later be split into its own repository or forked independently from the core GigaAM library.

## Layers

- `gigaam_capture.config`: app paths, directory bootstrap, settings persistence
- `gigaam_capture.models`: plain dataclasses and state models
- `gigaam_capture.history`: append-only JSONL and text history storage
- `gigaam_capture.services.recording`: audio capture abstraction
- `gigaam_capture.services.transcription`: GigaAM model loading and inference
- `gigaam_capture.services.hotkeys`: global hotkey backend
- `gigaam_capture.output_targets`: transcript delivery strategies
- `gigaam_capture.platform`: OS-specific automation planning and future adapters
- `gigaam_capture.ui`: tray app and user interaction shell

## Why this structure

- UI is separated from core services so the same services can later back a Windows tray app, Linux tray app, or a richer desktop shell.
- Output delivery is abstracted so clipboard output can be replaced or extended by active-input insertion.
- Platform automation is isolated because Telegram, WhatsApp Desktop, browser messengers, and native chat apps require OS-specific focus and accessibility handling.

## Planned output targets

- `clipboard`: default, safest MVP path
- `active-text-field`: inject transcript into the currently focused text input
- `app-specific`: app adapters for Telegram Desktop, WhatsApp Desktop, browsers, and Electron apps

Current macOS implementation detail:

- `active-text-field` is implemented as clipboard population followed by synthetic `Cmd+V`
- this keeps the first backend generic across messenger windows without hardcoding app-specific selectors
- later macOS work can add richer Accessibility inspection for focused-control validation
- the backend now explicitly checks for Accessibility trust and fails with a user-actionable error message when permissions are missing
- the backend now also captures frontmost app/window/role metadata and rejects obviously non-text-focused controls before paste
- role validation is now bundle-aware: generic apps stay strict, while known messenger/browser bundles can accept broader roles like `AXWebArea`
- the tray layer now exposes a non-transcribing inspection action so active-target diagnostics can reuse the same output-target abstraction without entering the recording flow
- Telegram Desktop and WhatsApp Desktop now also have app profiles with composer-specific focus hints so validation failures and inspection output are more actionable than generic role errors

## Planned platform backends

### macOS

- Accessibility permission required
- Focus detection and paste/insertion via Accessibility APIs
- Good first target for active-input support

### Windows

- UI Automation / Win32 active window and focused control lookup
- Clipboard-first fallback when direct insertion is not reliable

### Linux

- Separate backend strategy for X11 and Wayland
- Clipboard-first fallback likely needed for some environments

## Expected future split

When this project is mature enough to move into a separate repository, the intended boundary is:

- keep `gigaam` as the model library dependency
- move `apps/gigaam-capture` into its own repository root
- publish a dedicated app package and desktop build pipeline

## Near-term roadmap

1. Add settings dialog for hotkey, model, output mode, and history path.
2. Move transcription work off the UI thread.
3. Add waveform and recording timer feedback.
4. Add active-text-field automation backend for macOS.
5. Add packaging for macOS app bundle, Windows executable, and Linux desktop bundle.

## Roadmap document

The living roadmap is maintained here:

- [`docs/roadmap.md`](./roadmap.md)

## Implemented since scaffold

- Transcription now runs off the UI thread through a Qt worker thread.
- Global hotkey events are marshalled into the Qt event loop via a signal.
- A settings dialog exists for hotkey, model, recording duration, sample rate, channels, and output mode.
- The tray menu can inspect the current output target context without starting transcription.
