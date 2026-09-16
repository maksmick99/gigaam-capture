# GigaAM Capture

Standalone desktop app for short-form speech transcription with GigaAM.

## Goals

- Cross-platform foundation for macOS, Windows, and Linux
- Global hotkey driven recording flow
- Local history persisted as files and JSONL
- Target-app automation for messengers and other text inputs

## Current scope

- Tray-style desktop application shell
- Global hotkey service with platform-aware defaults and validation
- Short audio recording to WAV with a real duration and an automatic stop at
  the configured limit
- GigaAM transcription on a background thread
- History storage in a user data directory (JSONL + `.txt` per transcript)
- Clipboard output target
- `active-text-field` output target with focus validation, app profiles, and a
  configurable clipboard fallback
- Settings dialog for hotkey, model, duration, sample rate, channels, output
  mode, and fallback behavior
- Rotating log file plus an `inspect` diagnostics command

## Platform support for `active-text-field`

| Platform | Backend | Notes |
| --- | --- | --- |
| macOS | Accessibility APIs + synthetic `Cmd+V` | Needs Accessibility permission |
| Windows | UI Automation focus inspection + Win32 `Ctrl+V` | Falls back to a window-class allowlist when UI Automation is unavailable |
| Linux | Not implemented | Use clipboard mode |

The available targets are reported at runtime (`python -m gigaam_capture.inspect`),
and a target that is not supported on the current platform is replaced by
clipboard delivery at startup instead of crashing the app.

## Install

`gigaam` is not published to PyPI in a current form, so install the base library
from its source repository first, then install this app into the same
environment. The GigaAM revision is pinned to commit
`7447938d791c4f3e643386ee22c33777004293a5` so a fresh environment always builds
the same code rather than following `main`.

```bash
# 1) Install the GigaAM library (from its own checkout)
git clone https://github.com/salute-developers/GigaAM.git
cd GigaAM
git checkout 7447938d791c4f3e643386ee22c33777004293a5
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[torch]"   # or add extra: [longform], [train]

# 2) Install this app into the same virtual environment
cd <path-to-this-repo>
python -m pip install -e ".[dev]"

# 3) Platform extras (optional but recommended)
python -m pip install -e ".[windows]"   # UI Automation introspection on Windows
python -m pip install -e ".[macos]"     # pyobjc frameworks on macOS
```

Alternatively, the ASR runtime can be installed directly from the pinned
revision through the `asr` extra (requires `git` on `PATH`):

```bash
python -m pip install -e ".[asr]"
```

Install `ffmpeg` and make sure it is on `PATH`, then grant microphone (and, for
`active-text-field`, accessibility/automation) permissions when your OS asks.

## Run

```bash
gigaam-capture            # or: python -m gigaam_capture
```

Default hotkeys:

- macOS: `<cmd>+<shift>+r`
- Windows/Linux: `<ctrl>+<alt>+r` (avoids the system `Win+R` shortcut)

Press the hotkey to start recording and press it again to stop and transcribe.
Recording also stops automatically at the configured maximum duration.

## Diagnostics

```bash
python -m gigaam_capture.inspect          # capabilities + current active target
python -m gigaam_capture.inspect --json   # machine-readable report
```

Logs are written to `<user data dir>/logs/app.log` (rotating, 1 MB x 3). The
tray menu also offers `Inspect active target`, which reports the same target
description without starting recording or transcription.

## Development

```bash
python -m pytest -q          # tests (src layout is wired through pytest's pythonpath)
python -m ruff check src tests
```

The regular suite stays fast and needs neither the model nor OS permissions. A
real-runtime smoke test (load `v3_e2e_rnnt`, transcribe a short WAV) is tagged
with the `model` marker and only runs when explicitly requested, after the
`asr` extra has been installed:

```bash
python -m pytest -m model -q tests/test_model_smoke.py
```

## Output modes

### Clipboard (default)

The transcript is copied to the system clipboard. This mode has no permission
requirements and works on every platform.

### Active text field

The transcript is pasted into the currently focused text input:

1. the focused control is validated against platform heuristics and known
   application profiles (Telegram Desktop, WhatsApp Desktop, browsers, and
   similar chat clients)
2. the transcript is placed into the clipboard
3. a synthetic paste shortcut is sent and the previous clipboard content is restored

If validation or paste fails, `fallback_to_clipboard` (enabled by default)
copies the transcript to the clipboard and shows a warning instead of leaving
the app stuck.

Focus problems are reported with actionable text, and a focused control that
clearly is not a text input is rejected instead of pasting blindly.

## Roadmap

The living roadmap is maintained in [`docs/roadmap.md`](docs/roadmap.md), with
architecture notes in [`docs/architecture.md`](docs/architecture.md) and a
decision log in [`docs/build-journal.md`](docs/build-journal.md).

## Platform notes

Permissions, focus behavior, and per-application caveats are documented in
[`docs/platform-notes.md`](docs/platform-notes.md).
