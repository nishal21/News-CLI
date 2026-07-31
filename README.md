# World News CLI

[![PyPI](https://img.shields.io/pypi/v/worldnews-cli.svg)](https://pypi.org/project/worldnews-cli/0.4.2/)
[![Python](https://img.shields.io/pypi/pyversions/worldnews-cli.svg)](https://pypi.org/project/worldnews-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Full-screen terminal news reader built with [Textual](https://textual.textualize.io/). Sidebar, headlines, article pane, themes, AI summarize/explain, and text-to-speech that can highlight the sentence being read.

**Live on PyPI:** [worldnews-cli 0.4.2](https://pypi.org/project/worldnews-cli/0.4.2/)

Requires Python 3.9+.

## Install

Fastest path for most people:

```bash
pip install worldnews-cli
```

Isolated tool install (recommended on shared machines):

```bash
pipx install worldnews-cli
# or
uv tool install worldnews-cli
```

Optional extras for offline/gTTS playback helpers:

```bash
pip install "worldnews-cli[voice]"
```

From a local clone (developers):

```bash
pip install -e .
# or
pip install -r requirements.txt
```



## Run

```bash
worldnews
# short alias:
news
```

If the console script is not on your PATH:

```bash
python -m worldnews
# Windows launcher often works as:
py -m worldnews
```

Useful flags:

```bash
worldnews --category tech
worldnews --chat
worldnews --summary
worldnews --offline
worldnews --add-feed "My Blog" "https://example.com/feed.xml"
worldnews --version
```



## Keys


| Key                 | Action                                                       |
| ------------------- | ------------------------------------------------------------ |
| `j` / `k` or arrows | Move in the list                                             |
| `Enter`             | Open article (on a phone-width terminal: full-screen reader) |
| `Esc` / `q`         | Back to list, or quit                                        |
| `a` / `e`           | AI summarize / explain                                       |
| `t`                 | Speak article (press again to stop)                          |
| `/`                 | Filter headlines                                             |
| `Ctrl+P`            | Command palette                                              |
| `s`                 | Settings (App, AI, Voice)                                    |
| `[` / `]`           | Previous / next feed                                         |
| `1`–`9`             | Jump to a numbered category                                  |
| `b`                 | Bookmark                                                     |
| `o`                 | Open in browser                                              |
| `?`                 | Help                                                         |


On narrow terminals (about under 84 columns), the app switches to a phone layout: Enter opens the reader full width, Esc/Back returns to the list, and a Back button appears in the action row.

## What you get

- Categories such as General, Tech, AI, Sports, Anime, plus All, Bookmarks, Offline, and My Feeds
- Custom sites via palette `add-feed` (website or RSS; feed discovery when possible)
- Infinite scroll on headline lists (50 at a time)
- Animated ASCII boot / fetch splash (WORLD NEWS figlet + gradient)
- Themes: Newsroom (default), Phosphor, Broadsheet, Nord, GitHub Dark, High Contrast
- AI summarize / explain / chat (default free provider needs no key; many others supported)
- Speak (`t`) with free Edge TTS by default; optional Fish Audio, Gemini, Groq, and paid live providers
- Paste a voice id or library URL in Settings → Voice when you use a provider API key

Config lives under `~/.config/worldnews/` (older `~/.news-cli-*.json` files are still read).

## AI

Default free path: [OpenCode Zen](https://opencode.ai) (`big-pickle`), no API key.

Also wired: Hack Club AI, Ollama, LM Studio, Groq, Gemini, OpenRouter, and others.

In the app: `s` → AI tab (or palette → `ai-provider`). Pick a provider/model, paste a key if required, Save key, Apply AI.

Hack Club keys: [ai.hackclub.com](https://ai.hackclub.com/)

## Voice / TTS


| Provider               | Cost        | Key                                                                                   |
| ---------------------- | ----------- | ------------------------------------------------------------------------------------- |
| Edge TTS               | Free        | None (default)                                                                        |
| Fish Audio             | Free tier   | [fish.audio](https://fish.audio/app/api-keys) (`s2.1-pro-free`, news/narrator voices) |
| Gemini TTS / Live      | Free tier   | Google AI Studio                                                                      |
| Groq Orpheus           | Free tier   | Groq                                                                                  |
| Deepgram Aura-2 / Live | Free credit | Deepgram                                                                              |
| OpenAI / Realtime      | Paid        | OpenAI                                                                                |
| ElevenLabs / Live      | Free/paid   | ElevenLabs                                                                            |
| Cartesia / Live        | Paid        | Cartesia                                                                              |
| gTTS                   | Free        | None                                                                                  |


Flow: `s` → Voice → provider → model → voice (or paste id/URL) → API key if needed → Apply voice → `t`.

You can also set `FISH_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, and similar env vars.

Provider docs: [Fish](https://docs.fish.audio/) · [Gemini speech](https://ai.google.dev/gemini-api/docs/speech-generation) · [Groq TTS](https://console.groq.com/docs/text-to-speech)

## Complex scripts (Malayalam, Hindi, Arabic, …)

Cell-grid terminals (including Windows Terminal) often **cannot shape** Indic scripts the way a browser does. World News keeps the TUI usable with a safe default:

| Mode | How to enable | Behavior |
| ---- | ------------- | -------- |
| **safe** (default) | Settings → App → Scripts, or no flag | No Indic/Arabic glyphs in the TUI (list + reader); press **o** for browser |
| **plain** | `--plain` / `--ascii` | Same as safe for hostile scripts |
| **native** | `--native-titles` | Show native script in list/reader (may still overlap on Windows Terminal) |

**Fonts / hosts**

- **Windows:** use [Windows Terminal](https://aka.ms/terminal), not legacy `cmd.exe`. Set the profile font to **Nirmala UI** or **Noto Sans Malayalam**.
- **Termux:** install a Malayalam-capable font (e.g. Noto) via your font packages.
- **Linux / macOS:** UTF-8 locale (`LANG=*.UTF-8`) + Noto / Meera / Rachana.

Startup forces UTF-8 I/O and enables Windows virtual terminal processing when possible. Full OpenType shaping still requires a capable terminal + font — for clearest reading press **o** (open in browser).

## Phone and small terminals

This is a terminal UI. On Android, Termux is the usual host:

```bash
pkg update && pkg install python libxml2 libxslt libjpeg-turbo
pip install worldnews-cli
# optional
pip install "worldnews-cli[voice]"
pkg install termux-api ffmpeg
python -m worldnews
```

Other options: JuiceSSH/ConnectBot into a machine that already has `worldnews`, or a-Shell/iSH on iOS with Python + pip.

Width behavior (approximate):


| Columns  | Layout                                    |
| -------- | ----------------------------------------- |
| 100+     | Sidebar + list + reader                   |
| 84–99    | List first; Enter opens reader            |
| under 84 | Single column; Enter = reader, Esc = list |
| under 56 | Compact rows and short keyhints           |


Links open with `termux-open-url` when Termux API is installed.

## Development

```bash
git clone <your-repo-url>
cd news-cli
pip install -e ".[dev,voice]"
python -m worldnews
```



## License

MIT