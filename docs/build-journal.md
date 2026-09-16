# GigaAM Capture Build Journal

## Scope

This document captures the working dialog and key decisions starting from the beginning of the standalone app project design.

## Dialogue Log

### Step 1. Choosing the implementation path

**User**

Agreed to proceed with the second option: first define the architecture of the future desktop app instead of immediately coding the whole product.

**Assistant**

Recommended not starting with a large windowed desktop application.
Suggested a focused MVP in the form of a menu bar / tray-style desktop app with:

- a global hotkey to start recording
- a second press to stop recording
- short-form transcription through GigaAM
- local history saved to a folder

Also proposed Python + PySide6 as the base stack, with a service split for:

- app shell
- global hotkeys
- microphone recording
- transcription
- history storage
- settings

Planned first output mode: clipboard.
Planned future output mode: insertion into the currently active text input in other applications.

### Step 2. Refining the product direction

**User**

Confirmed the direction and added requirements:

- everything should be оформлено as a separate project
- the structure should support future scaling to Windows and Linux/Ubuntu
- the app should be shaped so it can later live as a fork / separate repository if possible
- future functionality should include activation from dialog windows / input fields of other apps such as Telegram and WhatsApp

**Assistant**

Interpreted this as a requirement for:

- a standalone app project next to the `gigaam` library, not mixed into the library package itself
- a layered architecture with clean boundaries between UI, platform automation, and core services
- a future accessibility / active-input automation subsystem for messenger integrations

### Step 3. Baseline checks before scaffolding

**Assistant actions**

Checked:

- repository root and current git remote
- dirty working tree state
- top-level repository contents
- `.gitignore`
- availability of existing app folders or special project areas

**Outcome**

Confirmed:

- the repository already had local modifications from installation and test fixes
- no existing standalone desktop app project structure was present
- it was safe to create a separate project inside the repository without mixing it into the core package

### Step 4. Creating the standalone project scaffold

**Assistant**

Created a new project at:

- `apps/gigaam-capture`

Initial project goals:

- standalone desktop application scaffold
- cross-platform foundation for macOS, Windows, and Linux
- tray-style shell
- global hotkey capture flow
- local history persisted as files and JSONL
- future active-text-field insertion support

**Files created**

- `apps/gigaam-capture/pyproject.toml`
- `apps/gigaam-capture/README.md`
- `apps/gigaam-capture/src/gigaam_capture/__init__.py`
- `apps/gigaam-capture/src/gigaam_capture/__main__.py`
- `apps/gigaam-capture/src/gigaam_capture/config.py`
- `apps/gigaam-capture/src/gigaam_capture/models.py`
- `apps/gigaam-capture/src/gigaam_capture/history.py`
- `apps/gigaam-capture/src/gigaam_capture/output_targets.py`
- `apps/gigaam-capture/src/gigaam_capture/services/__init__.py`
- `apps/gigaam-capture/src/gigaam_capture/services/hotkeys.py`
- `apps/gigaam-capture/src/gigaam_capture/services/recording.py`
- `apps/gigaam-capture/src/gigaam_capture/services/transcription.py`
- `apps/gigaam-capture/src/gigaam_capture/platform/__init__.py`
- `apps/gigaam-capture/src/gigaam_capture/platform/automation.py`
- `apps/gigaam-capture/src/gigaam_capture/ui/__init__.py`
- `apps/gigaam-capture/src/gigaam_capture/ui/tray.py`
- `apps/gigaam-capture/tests/test_config.py`
- `apps/gigaam-capture/tests/test_history.py`

### Step 5. Architecture decisions encoded in code

**Assistant**

Separated the app into layers:

- configuration and paths
- data models
- history persistence
- recording service
- transcription service
- hotkey service
- output target abstraction
- platform automation planning
- tray UI shell

**Important product choices at this stage**

- `clipboard` is the first delivery mode because it is the safest and most portable MVP
- `active-text-field` is intentionally modeled as a future target instead of being hardcoded into the first release
- platform-specific automation is kept isolated so messenger integrations can later be implemented without rewriting the core app

### Step 6. Cross-platform planning

**Assistant**

Added explicit planning for:

- macOS accessibility-based input automation
- Windows UI Automation / Win32 active control targeting
- Linux split handling for X11 and Wayland

Also documented that this project is intentionally structured so it can later be moved out of the monorepo-like repository layout into its own repository while keeping `gigaam` as a dependency.

### Step 7. Validation of the new app scaffold

**Assistant actions**

Installed the new project into the existing virtual environment:

```bash
python -m pip install -e "apps/gigaam-capture[dev]"
```

Ran focused tests:

```bash
python -m pytest apps/gigaam-capture/tests -q
```

Ran an import smoke check for the layered modules.

**Outcome**

- the standalone project installed successfully
- the focused tests passed
- imports for the app modules passed

### Step 8. Documentation and cleanup

**Assistant**

Added architecture notes to:

- `apps/gigaam-capture/docs/architecture.md`

Updated repository ignore rules to avoid carrying app-local build/test artifacts and removed a transient pytest log file from the repository root.

### Step 9. Current state before further implementation

At this point the project contains:

- a dedicated standalone app package
- a first MVP skeleton for tray capture flow
- storage for transcript history
- a future-ready abstraction for injecting text into active application inputs
- a cross-platform architecture plan
- validation that the project installs and basic tests pass

## Current functional status

Implemented in scaffold form:

- tray application shell
- global hotkey service abstraction
- recording service abstraction
- GigaAM transcription service integration
- history persistence to `.jsonl` and `.txt`
- clipboard output target
- non-blocking transcription through a Qt worker thread
- signal-based hotkey handoff into the Qt event loop
- settings dialog with persisted live updates for hotkey, model, duration, sample rate, channels, and output mode
- first macOS `active-text-field` backend using clipboard plus synthetic `Cmd+V`

Planned but not yet implemented:

- non-blocking background transcription worker
- settings dialog
- active input insertion for Telegram / WhatsApp / other chat apps
- platform-specific automation backends
- Windows and Linux packaging/runtime validation

## Notes for the next phase

The next planned engineering steps were:

1. move transcription off the UI thread
2. add a settings dialog
3. implement a first macOS backend for active text-field insertion
4. later port the same output-target abstraction to Windows and Linux

## Dialogue Log Continuation

### Step 10. Moving transcription off the UI thread

**User**

Asked to continue implementation.

**Assistant**

Identified the first concrete engineering risk in the new app skeleton: the tray controller still called `model.transcribe(...)` synchronously from the main UI path.

Implemented:

- `TranscriptionWorker` based on `QThread`
- controller state guard for `transcribing`
- async completion and error callbacks
- cleanup for worker and thread lifecycle

Also changed global hotkey dispatch so the `pynput` callback does not directly manipulate Qt state. Instead, it now emits a Qt signal that is handled on the application side.

**Validation**

- standalone app tests passed
- focused unit test confirmed the controller enters `transcribing` and launches background work without blocking the UI path

### Step 11. Adding runtime settings

**Assistant**

Added a first settings dialog and live settings application.

Implemented:

- `SettingsDialog` for hotkey, model, max duration, sample rate, channels, and output mode
- controller-level `update_settings(...)`
- recording/transcription service update hooks
- hotkey restart after settings change
- persistence through `SettingsStore`

The settings flow is intentionally still conservative:

- settings can only be changed while the app is idle
- output mode already exposes `active-text-field` as a future target, but clipboard remains the only implemented delivery backend

**Validation**

- app tests passed after the change
- updated UI modules imported successfully

### Step 12. First macOS active-input backend

**User**

Requested to continue with the first priority item: active text-field integration.

**Assistant**

Chose the narrowest useful macOS implementation instead of starting with deep Accessibility tree inspection.

Implemented:

- output-target factory selection based on `target_mode`
- `MacOSPasteAutomation` backend
- `ActiveTextFieldTarget` backed by platform automation instead of a placeholder exception
- tray/controller wiring so output mode actually changes runtime delivery behavior

The first backend works by:

1. placing the transcript into the system clipboard
2. sending a synthetic `Cmd+V`
3. restoring the previous clipboard text shortly after paste

This is intentionally generic so it can work with many already-focused chat inputs such as Telegram Desktop, WhatsApp Desktop, and browser-based messengers without app-specific integration.

**Validation**

- standalone tests passed after the backend was added
- import smoke checks for output-target and automation layers passed

### Step 13. macOS permission diagnostics and tray status feedback

**User**

Asked to continue following the implementation plan.

**Assistant**

Focused first on the weak point of the new macOS backend: missing Accessibility permissions would previously fail too opaquely.

Implemented:

- `AutomationPermissionError`
- explicit macOS Accessibility trust check before active-field paste
- clearer user-actionable error text pointing to System Settings -> Privacy & Security -> Accessibility

After that, added a small tray UX improvement:

- dedicated disabled status line in the tray menu
- status now shows current hotkey and current target mode
- delivery completion emits a target-aware notification message

**Validation**

- standalone app tests passed after the permission diagnostics work
- a tray status test was adjusted to avoid constructing a real `QSystemTrayIcon` in headless pytest on macOS
- final standalone test suite status: passing

### Step 14. First app-aware macOS target introspection

**User**

Asked to continue with the app-aware macOS automation direction.

**Assistant**

Avoided jumping straight to messenger-specific selectors. Instead, implemented a generic but app-aware layer on top of the existing paste backend.

Implemented:

- frontmost application metadata lookup for macOS
- focused UI role inspection via Accessibility APIs
- validation that rejects obviously non-text-focused controls before paste
- history target metadata propagation so saved transcript records can capture where delivery was aimed

This means the backend is now smarter than simple blind paste:

- it still works generically with Telegram / WhatsApp / browser chat inputs
- it can now fail early when the focused control clearly is not an editable target
- it records a human-readable target hint such as app / window / role context

**Validation**

- standalone tests passed after the app-aware metadata layer was added
- focused tests cover acceptance of text-like roles, rejection of non-text roles, and persistence of target metadata into saved history records

### Step 15. Bundle-aware heuristics for messenger and browser apps

**User**

Asked to continue.

**Assistant**

Refined the macOS app-aware validation logic so it would not be too permissive for arbitrary apps and not too strict for real messenger/browser chat surfaces.

Implemented:

- strict generic role acceptance for normal applications
- bundle-specific role overrides for known apps such as Telegram Desktop, WhatsApp Desktop, Safari, Chrome, Edge, Brave, Chromium, Firefox, and Opera
- guidance in error messages when a broad role like `AXWebArea` appears outside a recognized messenger/browser bundle

This made the automation policy more realistic:

- generic apps still need obviously text-like focused roles
- known browser or Electron-style chat clients can use broader focused roles when they are expected in real chat surfaces

**Validation**

- standalone app tests passed after bundle-aware heuristics were added
- focused tests now cover acceptance and rejection paths for `AXWebArea` depending on bundle identity

### Step 16. Tray debug action for active target inspection

**User**

Asked to continue with the first next step: add a debug action that shows the current frontmost target context without launching transcription.

**Assistant**

Added a tray-level diagnostic path that reuses the existing output-target abstraction instead of introducing a separate macOS-only UI code path.

Implemented:

- a public controller method for inspecting the current target context
- clipboard-mode fallback text that avoids unnecessary automation probing
- a new tray menu action `Inspect active target`
- success and failure tray notifications for active-target diagnostics without starting recording or model inference

This keeps the diagnostic behavior aligned with the actual delivery path:

- clipboard mode reports that no active-app inspection is needed
- active-text-field mode surfaces the same target description used for history metadata
- automation failures such as missing Accessibility permissions are shown directly instead of being silently collapsed to a generic target name

**Validation**

- focused standalone tests passed after the tray inspection action was added
- headless-safe tests now cover controller inspection, successful tray inspection, and failure reporting

### Step 17. App-specific Telegram and WhatsApp focus heuristics

**User**

Asked to proceed with the second next step: go deeper on app-specific heuristics for Telegram and WhatsApp using the new inspection path.

**Assistant**

Refined the macOS automation layer from bundle-aware role checks into small app profiles for known messenger targets.

Implemented:

- app profiles for Telegram Desktop and WhatsApp Desktop
- app-specific focus hints that explicitly point the user to the message composer
- enriched target summaries that expose the recognized profile in inspection output
- validation errors that now combine frontmost target metadata with app-aware guidance

This improves the real debugging loop for messenger integrations:

- inspection output now shows when the current frontmost target matches a known Telegram or WhatsApp profile
- invalid focus states no longer fail with only a generic role mismatch
- the same automation slice remains reusable for future messenger-specific expansion instead of branching into separate UI code paths

**Validation**

- focused automation tests passed after app-profile heuristics were added
- tests now cover Telegram profile summaries and WhatsApp-specific focus guidance

## Summary

The new project started as a consciously separate, scalable desktop app scaffold rather than an extension of the core `gigaam` package. The main product constraint already captured in the architecture is that future integrations with messenger apps should work through a dedicated active-input automation layer, not through ad hoc application-specific logic spread across the codebase.

## Dialogue Log Continuation: hardening, Windows parity, and reproducibility

> Note: the app now lives at the repository root (`src/gigaam_capture`), while
> the earlier entries in this journal still describe the original
> `apps/gigaam-capture` layout inside the GigaAM repository.

### Step 18. Reproducible environment and quality gates

**Assistant**

Closed the gap between "tests pass on the author's machine" and "tests pass from
a clean clone":

- `pyproject.toml`: added `pythonpath = ["src"]` so pytest works without an
  editable install, declared extras `asr` (git dependency on GigaAM, because
  PyPI only hosts a stale `gigaam` 0.1.0), `macos` (pyobjc frameworks),
  `windows` (comtypes), and extended `dev` with `pytest-cov`, `black`, `isort`,
  and `ruff` plus a ruff lint configuration.
- `services/transcription.py`: the `gigaam` import became lazy with a
  user-actionable error, so the app and the test suite run without the ASR
  runtime.
- Added `.github/workflows/ci.yml`: matrix `ubuntu`/`macos`/`windows` x Python
  3.10/3.12, offscreen Qt, ruff, pytest with coverage, and a capability report
  through the new diagnostics command.

**Validation**

- `python -m pytest -q` ran green on Windows from a clean checkout without an
  editable install.
- `python -m pip install -e ".[dev]"` produced the console script and a working
  `python -m gigaam_capture.inspect`.

### Step 19. Fixing the P0 defects in the capture flow

**Assistant**

Worked through the failure modes found during the audit:

- **Delivery could permanently freeze the app.** `AppController` called
  `deliver()` inside a Qt slot without error handling, so a failing
  `active-text-field` paste skipped the `idle` transition and left the app in
  `transcribing` until restart. Delivery now returns a `DeliveryOutcome`,
  records a `delivery_status` in history, emits `delivery_failed`, moves to
  `error`, and can fall back to the clipboard (`fallback_to_clipboard`).
- **An unsupported target crashed the next start.** `create_output_target` now
  raises a domain `UnsupportedTargetError`, `platform` reports capabilities, the
  settings dialog offers only supported targets, settings are applied before
  being persisted, and startup replaces an unsupported saved mode with clipboard
  delivery plus a warning.
- **Recording duration was wrong.** The service allocated a fixed-size buffer and
  reported `len(buffer) / sample_rate`, i.e. always the configured maximum. It
  now collects chunks through an injectable recorder, reports the real frame
  count, truncates at the limit, exposes `elapsed_seconds`/`remaining_seconds`,
  and finishes automatically through `poll()` called by a controller `QTimer`.
- **Shutdown leaked the capture stream.** `AppController.shutdown()` stops an
  active recording and logs the discarded audio path.
- **Settings could crash startup.** `settings_from_payload` ignores unknown keys
  and replaces invalid values with defaults; hotkeys are validated through
  `pynput` parsing with a friendly message, and the default hotkey is now
  platform-aware (`<cmd>+<shift>+r` on macOS, `<ctrl>+<alt>+r` elsewhere).
- Removed dead code (`AccessibilityAutomationPlan`, `PLANNED_AUTOMATION`,
  `QDesktopServicesShim`) and replaced the fragile `.wav` → `.txt` string
  substitution with `Path.with_suffix`.

**Validation**

- New test modules cover delivery fallback, failed delivery without fallback,
  clipboard fallback failure, recovery after failure, recording duration and
  auto-stop, settings robustness, hotkey validation, and platform gating.
- The suite grew from 22 to 86 passing tests; ruff is clean.

### Step 20. Windows active-text-field parity

**User**

Chose to implement Windows parity first so the app can be developed and verified
on the primary machine.

**Assistant**

Split the platform layer and implemented the Windows backend:

- extracted shared types into `platform/targets.py` (`ActiveAppAutomation`,
  `ActiveTargetInfo`, `AppProfile`, `AutomationPermissionError`) and moved the
  macOS backend into `platform/macos.py`;
- added `platform/windows.py` with a `ctypes` Win32 adapter (foreground window,
  window text, class name, focused window through `GetGUIThreadInfo`, process
  image name through `QueryFullProcessImageNameW`) — no pywin32 dependency;
- added `platform/windows_uia.py`, which reads the focused UI Automation element
  through COM (`comtypes`) and maps control type ids to readable names;
- focus validation prefers UI Automation control types (`Edit`, `Document`,
  `ComboBox`) and falls back to a window-class allowlist with per-process
  profiles for chat clients and browsers;
- paste uses `Ctrl+V` through `pynput`, with an explicit UIPI/elevation hint when
  synthesised input is blocked;
- `platform/automation.py` became a facade with platform dispatch, keeping the
  historical import path working.

**Validation**

- Windows backend tests cover profile resolution, UI Automation acceptance and
  rejection, the Win32 fallback (including Qt shells only for Qt-aware profiles),
  validation before clipboard access, and the platform factory.
- Live verification on Windows: the Win32 adapter read the foreground window,
  class and process; UI Automation reported the focused control as `Edit`; the
  diagnostics command reported
  `active-text-field: available (Windows UI Automation + Win32 paste)`.

### Step 21. Diagnostics, logging, and documentation

**Assistant**

Made the capture flow observable and the documentation truthful:

- added `gigaam_capture/log.py` with a rotating file handler
  (`<user data dir>/logs/app.log`, 1 MB x 3) and a stream handler limited to
  warnings so CLI output stays clean;
- added `python -m gigaam_capture.inspect` (`--json`, `--no-active-target`) that
  reports capabilities, the chosen inspector, the active target, and exits
  non-zero when inspection fails;
- rewrote `docs/architecture.md` around the platform layer, delivery behavior,
  recording behavior, and observability; added `docs/platform-notes.md` with
  permission requirements and a manual Windows test matrix;
- fixed `docs/roadmap.md` (escaped Markdown that never rendered) and added a
  status section listing what shipped and what remains;
- updated `README.md` for the current install/run flow, the platform support
  table, diagnostics, and output modes.

**Validation**

### Step 22. Pinned GigaAM revision and real-model smoke test

**Assistant**

Closed the two remaining reproducibility gaps from the M4 plan (``Шаг 1`` and
``Шаг 5``):

- Pinned the ASR runtime to commit `7447938d791c4f3e643386ee22c33777004293a5`
  of `salute-developers/GigaAM` (the `main` head at the time of pinning) in the
  `asr` extra of `pyproject.toml`, so a fresh environment no longer follows a
  floating `main`. The README now documents both the explicit `git checkout`
  path and the `.[asr]` install path. The recommended `third_party/gigaam`
  submodule from the plan remains a follow-up; the pinned-SHA git install
  satisfies the milestone's reproducibility acceptance without adding submodule
  plumbing to the source tree.
- Added `tests/test_model_smoke.py`, tagged `@pytest.mark.model`, which loads
  the default `v3_e2e_rnnt` model and transcribes a short generated WAV. The
  test is excluded from the fast suite by the `model` marker (and skips via
  `importorskip` when the ASR runtime is absent), so `pytest` stays model-free
  and requires no OS permissions by default.

**Remaining for M4 (requires a clean Windows 10/11 x64 host)**

- Run the real-model smoke against `v3_e2e_rnnt` on Windows (``Шаг 7``) and
  record the results in `docs/platform-notes.md`.
- Final manual capture matrix (hotkey → recording → transcription → clipboard →
  active-field paste → fallback → shutdown) on Windows.

