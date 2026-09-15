# Platform notes

This document collects what has to be true for `active-text-field` delivery to
work on each platform, plus the manual checks that must be run before a release.

## Diagnostics first

```bash
python -m gigaam_capture.inspect           # capabilities + current target
python -m gigaam_capture.inspect --json    # machine-readable
python -m gigaam_capture.inspect --no-active-target
```

The same information is available from the tray menu (`Inspect active target`).
Inspection never starts recording or transcription. Results are appended to
`<user data dir>/logs/app.log`.

## macOS

For `active-text-field` output mode:

- place the cursor in the target app input field first
- grant Accessibility permissions to the app / Python runtime if prompted
- the implementation pastes by copying the transcript to the system clipboard
  and sending a synthetic `Cmd+V`, then restoring the previous clipboard text

If paste fails immediately, check:

- System Settings -> Privacy & Security -> Accessibility
- your terminal, Python runtime, or packaged app is allowed there

The backend inspects the frontmost application and the focused UI role before
pasting. A focused control that clearly is not a text input is rejected with a
descriptive error instead of pasting blindly.

Broader roles such as `AXWebArea` are accepted only for recognized app bundles
(Telegram Desktop, WhatsApp Desktop, Safari, Chrome, Edge, Brave, Chromium,
Firefox, Opera). Telegram Desktop and WhatsApp Desktop additionally expose
composer-specific focus hints in validation errors and inspection output.

## Windows

Focus validation prefers UI Automation: the focused element's control type is
read through COM (`comtypes`) and must be `Edit`, `Document`, or `ComboBox`.
When UI Automation is unavailable, the backend falls back to a Win32 window
class allowlist (for example `Edit`, `RichEdit50W`, `Scintilla`) combined with
application profiles for chat clients (`telegram.exe`, `whatsapp.exe`,
`discord.exe`, `slack.exe`) and browsers (`chrome.exe`, `msedge.exe`,
`firefox.exe`, `brave.exe`, `opera.exe`, `chromium.exe`).

Known limitations:

- Windows blocks synthetic input from a non-elevated process into an elevated
  target window (UIPI). Paste then fails with an explicit elevation hint.
- Chat clients built on Electron or Qt expose shell window classes; validation
  therefore relies on UI Automation control types for these targets whenever it
  is available.

Manual matrix (Windows):

| Target | Mode | Expected |
| --- | --- | --- |
| Notepad | `active-text-field` | Pastes into the editor when the caret is in the text area |
| Chrome/Edge (web chat) | `active-text-field` | Pastes into the focused input; rejects page background |
| Telegram Desktop | `active-text-field` | Pastes into the message composer; rejects other controls with a composer hint |
| WhatsApp Desktop | `active-text-field` | Same as Telegram |
| Elevated target (for example an admin terminal) | `active-text-field` | Fails with an elevation hint and falls back to the clipboard |
| Any app, no focus | `clipboard` | Always copies the transcript |

## Linux

`active-text-field` is not implemented: the app reports it as unavailable,
settings only offer supported targets, and a previously saved unsupported mode
is replaced by clipboard delivery at startup.

## Permissions summary

| Platform | Recording | `active-text-field` |
| --- | --- | --- |
| macOS | Microphone prompt | Accessibility permission |
| Windows | Microphone privacy setting | None (UI Automation is read-only for the user) |
| Linux | Microphone via PipeWire/PulseAudio | Not implemented |
