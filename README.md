# Typr

Speech-to-text for Linux using OpenAI-compatible Whisper API.

## Features

- **Push-to-talk** - Hold hotkey to record, release to transcribe
- **System tray** - Runs quietly with status indicators
- **Works everywhere** - Uses evdev for input/output (Wayland, X11, any compositor)
- **Custom endpoints** - Supports local Whisper servers or any OpenAI-compatible API
- **Auto-start** - Launches on login

## Requirements

- Linux (tested on CachyOS/Arch with KDE Plasma)
- User must be in the `input` group (for keyboard access)
- OpenAI API key or local Whisper endpoint

## Installation

```bash
./install.sh
```

Or manually:

```bash
# Install dependencies
sudo pacman -S python-pyqt6 python-pyaudio portaudio

# Install package
pip install --user -e .

# Ensure you're in the input group
sudo usermod -aG input $USER
# Log out and back in for group change to take effect
```

## Usage

1. Run `typr` or find it in your application menu
2. Right-click tray icon → **Settings**
3. Go to **API** tab → enter your API key and endpoint
4. Go to **General** tab → click **Fetch** to load available models
5. **Hold** `Meta+Shift+Space` to record, **release** to transcribe
6. Text appears in the focused input field

You can also left-click the tray icon to start/stop recording.

## Configuration

Settings are stored in `~/.config/typr/config.json`

### Hotkeys

Configure in Settings → Hotkeys tab, or edit config directly:

- **Push-to-Talk**: `Meta+Shift+Space` (default)

Supported format: `Modifier+Modifier+Key`
- Modifiers: `Meta`, `Shift`, `Ctrl`, `Alt`
- Keys: `Space`, `Enter`, `F1`-`F12`, or any letter

### API Endpoints

Works with:
- **OpenAI API**: `https://api.openai.com/v1`
- **Local Whisper**: Any OpenAI-compatible endpoint (e.g., `http://localhost:8080/v1`)

### Models

For OpenAI:
- `whisper-1` - Standard Whisper model
- `gpt-4o-transcribe` - Better accuracy
- `gpt-4o-mini-transcribe` - Faster

For local endpoints, click **Fetch** in Settings to discover available models.

## Troubleshooting

### "No keyboard devices found"
Ensure you're in the `input` group:
```bash
sudo usermod -aG input $USER
# Log out and back in
```

### ALSA/JACK warnings
These are harmless - PyAudio probes various audio backends on startup.

### Text not typing
Make sure you're in the `input` group for UInput access.

## License

MIT
