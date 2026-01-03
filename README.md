<div align="center">
    <img src="resources/icons/typr.svg" alt="Typr Logo" width="64"/>
</div>

<h1 align="center">Typr</h1>
<p align="center">Push-to-talk speech-to-text for Linux desktop</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10+-blue.svg"></a>
  <a href="https://github.com/murtaza-nasir/typr/releases/latest"><img alt="Latest Version" src="https://img.shields.io/badge/version-0.1.0-brightgreen.svg"></a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

## Overview

Typr is a lightweight speech-to-text application that lives in your system tray. Hold a hotkey to record your voice, release to transcribe, and the text is automatically typed into any focused input field. Works with OpenAI's Whisper API or any compatible local endpoint.

**Key highlights:**
- 🎤 **Push-to-talk** - Natural voice input workflow
- ⌨️ **Types anywhere** - Works in any application, any input field
- 🐧 **Linux native** - Built for Wayland and X11 using evdev
- 🏠 **Self-hosted friendly** - Use local Whisper servers or OpenAI API

## Features

### Core Functionality
- **Push-to-Talk Recording** - Hold hotkey to record, release to transcribe and type
- **Universal Text Input** - Types directly into any focused field using kernel-level input
- **System Tray Integration** - Runs quietly with visual status indicators
- **Click-to-Record** - Alternative mouse-based recording via tray icon

### Flexibility
- **Custom API Endpoints** - Use OpenAI, local Whisper servers, or any compatible API
- **Dynamic Model Discovery** - Fetch available models from your endpoint
- **Configurable Hotkeys** - Set any key combination for push-to-talk
- **Multiple Whisper Models** - Support for whisper-1, gpt-4o-transcribe, and custom models

### Technical
- **Wayland & X11 Support** - Uses evdev for compositor-independent operation
- **No Root Required** - Works with standard `input` group membership
- **Lightweight** - Minimal resource usage, Python/PyQt6 based
- **Auto-start** - Optional launch on login

## Installation

### Quick Install (Arch/CachyOS)

```bash
# Clone the repository
git clone https://github.com/murtaza-nasir/typr.git
cd typr

# Run installer
./install.sh
```

### Manual Installation

```bash
# Install system dependencies
sudo pacman -S python-pyqt6 python-pyaudio portaudio

# Install Python package
pip install --user -e .

# Add yourself to the input group (required for hotkeys and typing)
sudo usermod -aG input $USER

# Log out and back in for group membership to take effect
```

### Verify Setup

```bash
# Check you're in the input group
groups | grep input

# Run Typr
typr
```

## Usage

1. **Launch** - Run `typr` or find it in your application menu
2. **Configure** - Right-click tray icon → **Settings**
   - Go to **API** tab → Enter your API key and endpoint
   - Go to **General** tab → Click **Fetch** to load available models
3. **Record** - **Hold** `Meta+Shift+Space` to record
4. **Transcribe** - **Release** the hotkey to transcribe and type

The transcribed text will be typed into whatever input field is currently focused.

### Alternative: Click to Record

You can also **left-click** the tray icon to start recording, and click again to stop.

## Configuration

Settings are stored in `~/.config/typr/config.json`

### Hotkeys

Configure via Settings → Hotkeys tab, or edit the config file:

```json
{
  "hotkeys": {
    "push_to_talk": "Meta+Shift+Space"
  }
}
```

**Supported format:** `Modifier+Modifier+Key`

| Modifiers | Keys |
|-----------|------|
| `Meta` (Super/Win) | `Space`, `Enter`, `Tab` |
| `Shift` | `F1` - `F12` |
| `Ctrl` | `A` - `Z` |
| `Alt` | `0` - `9` |

### API Endpoints

Works with any OpenAI-compatible transcription API:

| Provider | Base URL |
|----------|----------|
| OpenAI | `https://api.openai.com/v1` |
| Local Whisper | `http://localhost:8080/v1` |
| Custom | Any OpenAI-compatible endpoint |

### Models

**OpenAI models:**
- `whisper-1` - Standard Whisper model
- `gpt-4o-transcribe` - Higher accuracy
- `gpt-4o-mini-transcribe` - Faster processing

**Local endpoints:** Click **Fetch** in Settings to discover available models.

## Troubleshooting

### "No keyboard devices found"

You need to be in the `input` group:

```bash
sudo usermod -aG input $USER
# Log out and back in
```

### Text not being typed

Same fix - the `input` group is required for UInput (virtual keyboard):

```bash
groups | grep input  # Should show 'input'
```

### ALSA/JACK warnings on startup

These are harmless - PyAudio probes various audio backends during initialization. The warnings don't affect functionality.

### Hotkey not working

1. Verify the hotkey format in Settings → Hotkeys
2. Check that no other application is using the same hotkey
3. Try a different key combination

### API errors

1. Verify your API key is correct
2. Check the base URL matches your provider
3. Click **Test Connection** in Settings → API tab
4. For local endpoints, ensure the server is running

## Tech Stack

- **Language**: Python 3.10+
- **UI Framework**: PyQt6
- **Audio**: PyAudio with PipeWire/PulseAudio
- **Input/Output**: evdev (kernel-level keyboard access)
- **API Client**: httpx

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

- [Report bugs](https://github.com/murtaza-nasir/typr/issues)
- [Request features](https://github.com/murtaza-nasir/typr/issues)

## Acknowledgments

- [OpenAI Whisper](https://openai.com/research/whisper) for the transcription API
- [evdev](https://python-evdev.readthedocs.io/) for Linux input device access
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the UI framework
