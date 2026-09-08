# GigaAM Capture

Standalone desktop app scaffold for short-form speech transcription with GigaAM.

## Goals

- Cross-platform foundation for macOS, Windows, and Linux
- Global hotkey driven recording flow
- Local history persisted as files and JSONL
- Future target-app automation for messengers and other text inputs

## Current MVP scope

- Tray-style desktop application shell
- Global hotkey service abstraction
- Short audio recording to WAV
- GigaAM transcription service integration
- History storage in a user data directory
- Clipboard output target
- Settings dialog for hotkey, model, duration, and output mode
- macOS active text-field paste mode via clipboard plus synthetic `Cmd+V`

## Install

`gigaam` is not published to PyPI yet, so install the base library from its source repository first, then install this app into the same environment.

```bash
# 1) Install the GigaAM library (from its own checkout)
git clone https://github.com/salute-developers/GigaAM.git
cd GigaAM
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[torch]"     # or add extra: [longform], [train]

# 2) Install this app into the same virtual environment
cd <path-to-this-repo>
python -m pip install -e ".[dev]"
```

Install `ffmpeg` and grant microphone / accessibility permissions when prompted by your OS.

## Run

From the app virtual environment:

```bash
gigaam-capture
```

## Development

From the app repository root:

```bash
python -m pytest -v tests/
```

## macOS active text-field mode

For `active-text-field` output mode on macOS:

- place the cursor in the target app input field first
- grant Accessibility permissions to the app / Python runtime if prompted
- the current implementation pastes by copying the transcript to the system clipboard and sending `Cmd+V`

If paste mode fails immediately, first check:

- System Settings -> Privacy & Security -> Accessibility
- your terminal, Python runtime, or packaged app is allowed there

This is the first compatibility path for apps such as Telegram Desktop, WhatsApp Desktop, and browser chat inputs.

The macOS backend now also inspects the frontmost application and focused UI role before paste. If the focused control clearly does not look like a text input, delivery is aborted with a descriptive error instead of pasting blindly.

Known messenger/browser heuristics now allow broader focused roles such as `AXWebArea` only for recognized app bundles like Telegram Desktop, WhatsApp Desktop, Safari, Chrome, Edge, Brave, Chromium, and Firefox.

Telegram Desktop and WhatsApp Desktop now also use app-specific focus hints during validation. If the focused control is wrong, the error and tray inspection output point you to the message composer instead of showing only a generic text-input failure.

For diagnostics, the tray menu now includes `Inspect active target`, which reports the current output context without starting recording or transcription. In `active-text-field` mode this helps verify the frontmost app, window, focused role, or a missing Accessibility permission before a real paste attempt.

## Roadmap

- Settings dialog
- Active text-field insertion for Telegram, WhatsApp, and similar apps
- Long-form mode with segmentation
- Rich history viewer
- Packaged desktop distributions for macOS, Windows, and Linux
