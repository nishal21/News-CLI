"""Multi-provider text-to-speech for World News CLI.

Catalog from official docs: worldnews.voice_catalog
Default free: Edge TTS. Also Fish Audio (s2.1-pro-free), Gemini TTS/Live,
OpenAI Realtime, ElevenLabs Live, Deepgram Speak WS, Cartesia Live,
Groq Orpheus, gTTS.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path
from typing import Callable

from worldnews.voice_catalog import (
    CARTESIA_LIVE_MODELS,
    ELEVEN_LIVE_MODELS,
    FISH_MODELS,
    GEMINI_LIVE_MODELS,
    GEMINI_TTS_MODELS,
    OPENAI_LIVE_MODELS,
    VOICE_PROVIDERS,
    normalize_voice_id,
    voice_paste_placeholder,
)

# Live ↔ batch share the same vendor API key
_KEY_GROUPS = (
    ("gemini", "gemini-live"),
    ("openai", "openai-live"),
    ("elevenlabs", "elevenlabs-live"),
    ("deepgram", "deepgram-live"),
    ("cartesia", "cartesia-live"),
)
_SHARED_AI_KEYS = {
    "gemini": "gemini",
    "gemini-live": "gemini",
    "groq": "groq",
    "openai": "openai",
    "openai-live": "openai",
}

_ENV_API_KEYS = {
    "fish": ("FISH_API_KEY", "FISH_AUDIO_API_KEY"),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "gemini-live": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "openai-live": ("OPENAI_API_KEY",),
    "elevenlabs": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
    "elevenlabs-live": ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY"),
    "deepgram": ("DEEPGRAM_API_KEY",),
    "deepgram-live": ("DEEPGRAM_API_KEY",),
    "cartesia": ("CARTESIA_API_KEY",),
    "cartesia-live": ("CARTESIA_API_KEY",),
}

_WAV_PROVIDERS = frozenset(
    {
        "gemini",
        "gemini-live",
        "groq",
        "openai-live",
        "cartesia-live",
        "deepgram-live",
    }
)


class VoiceConfig:
    def __init__(self):
        from worldnews.paths import resolve_config_file

        self.path = str(resolve_config_file("voice.json", ".news-cli-voice.json"))
        self.config = self._load()

    def _default(self):
        providers = {}
        for pk, pv in VOICE_PROVIDERS.items():
            entry = {"api_key": "", "voice": pv["default_voice"]}
            if pv.get("default_model"):
                entry["model"] = pv["default_model"]
            providers[pk] = entry
        return {
            "provider": "edge",
            "rate": "+20%",
            "openai_model": "gpt-4o-mini-tts",
            "auto_speak_summary": False,
            "providers": providers,
        }

    def _load(self):
        default = self._default()
        saved = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    saved = json.load(f)
            except Exception:
                pass
        for k, v in default.items():
            if k not in saved:
                saved[k] = v
        if "providers" not in saved:
            saved["providers"] = default["providers"]
        else:
            for pk, pv in default["providers"].items():
                if pk not in saved["providers"]:
                    saved["providers"][pk] = pv
                else:
                    for field, fval in pv.items():
                        saved["providers"][pk].setdefault(field, fval)
        return saved

    def save(self):
        from pathlib import Path

        from worldnews.paths import migrate_to_modern, write_json

        self.path = str(
            migrate_to_modern(Path(self.path), "voice.json", private=True)
        )
        write_json(self.path, self.config, private=True)

    def get_provider(self):
        return self.config.get("provider", "edge")

    def get_voice(self, provider=None):
        p = provider or self.get_provider()
        return self.config["providers"].get(p, {}).get(
            "voice", VOICE_PROVIDERS.get(p, {}).get("default_voice", "")
        )

    def get_model(self, provider=None):
        p = provider or self.get_provider()
        return self.config["providers"].get(p, {}).get(
            "model",
            VOICE_PROVIDERS.get(p, {}).get(
                "default_model", self.config.get("openai_model", "")
            ),
        )

    def set_model(self, model: str, provider=None):
        p = provider or self.get_provider()
        if p in VOICE_PROVIDERS:
            self.config["providers"][p]["model"] = model
            if p == "openai":
                self.config["openai_model"] = model
            self.save()

    def get_api_key(self, provider=None):
        p = provider or self.get_provider()
        key = (self.config["providers"].get(p, {}).get("api_key") or "").strip()
        if key:
            return key
        for group in _KEY_GROUPS:
            if p in group:
                for alt in group:
                    k = (
                        self.config["providers"].get(alt, {}).get("api_key") or ""
                    ).strip()
                    if k:
                        return k
                break
        # Reuse keys already saved in AI settings when present
        ai_prov = _SHARED_AI_KEYS.get(p)
        if ai_prov:
            try:
                from worldnews.ai import ai as _ai

                k = (_ai.get_api_key(ai_prov) or "").strip()
                if k:
                    return k
            except Exception:
                pass
        for env_name in _ENV_API_KEYS.get(p, ()):
            k = (os.environ.get(env_name) or "").strip()
            if k:
                return k
        return ""

    def set_provider(self, provider, voice=None):
        if provider in VOICE_PROVIDERS:
            self.config["provider"] = provider
            if voice:
                self.config["providers"][provider]["voice"] = voice
            self.save()

    def set_voice(self, voice, provider=None):
        p = provider or self.get_provider()
        if p in VOICE_PROVIDERS:
            self.config["providers"][p]["voice"] = voice
            self.save()

    def set_api_key(self, provider, key):
        if provider not in VOICE_PROVIDERS:
            return
        cleaned = (key or "").strip()
        self.config["providers"][provider]["api_key"] = cleaned
        # Share batch ↔ live keys for the same vendor
        if cleaned:
            for group in _KEY_GROUPS:
                if provider in group:
                    for alt in group:
                        self.config["providers"][alt]["api_key"] = cleaned
                    break
        self.save()

    def set_rate(self, rate: str):
        self.config["rate"] = rate
        self.save()

    def get_rate(self):
        return self.config.get("rate", "+0%")

    def get_status(self):
        p = self.get_provider()
        info = VOICE_PROVIDERS.get(p, {})
        voice = self.get_voice()
        label = info.get("voice_labels", {}).get(voice, voice)
        model = self.get_model(p)
        extra = f" · {model}" if model and info.get("models") else ""
        if info.get("requires_key") and not self.get_api_key(p):
            return f"{info.get('name', p)} — API key not set ({info.get('setup_url', '')})"
        return f"{info.get('name', p)} · voice {label}{extra} · rate {self.get_rate()}"


voice_cfg = VoiceConfig()


def _rate_to_fish_speed(rate: str) -> float:
    """Map Edge-style rate (+20%) to Fish prosody speed (0.5–2.0)."""
    raw = (rate or "+0%").strip()
    m = re.match(r"([+-]?\d+)\s*%?", raw)
    if not m:
        return 1.0
    return max(0.5, min(2.0, 1.0 + int(m.group(1)) / 100.0))


def _write_wav_pcm16(path: Path, pcm: bytes, sample_rate: int = 24000) -> None:
    """Write little-endian 16-bit mono PCM as WAV."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


def _pad_wav_lead_silence(path: Path, ms: int = 220) -> Path:
    """Prepend silence so DAC open latency doesn't clip the first words."""
    try:
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            width = wf.getsampwidth()
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        n = max(1, int(rate * (ms / 1000.0)))
        silence = b"\x00" * (n * channels * width)
        out = path.with_name(path.stem + f"-pad{ms}" + path.suffix)
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(width)
            wf.setframerate(rate)
            wf.writeframes(silence + frames)
        return out
    except Exception:
        return path


def _silent_wav(path: Path, ms: int = 180, sample_rate: int = 24000) -> Path:
    """Write a short silent WAV used to warm up the audio device."""
    n = max(1, int(sample_rate * (ms / 1000.0)))
    _write_wav_pcm16(path, b"\x00\x00" * n, sample_rate)
    return path


def _run_async(coro):
    """Run async coroutine from sync Speak thread (handles nested loops)."""
    import asyncio

    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        if "asyncio.run()" in str(e) or "event loop" in str(e).lower():
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        raise


def _ws_connect(uri: str, **kwargs):
    """Return websockets.connect(...) CM; supports both header kwarg names."""
    import inspect

    import websockets

    headers = kwargs.pop("headers", None) or {}
    sig = inspect.signature(websockets.connect)
    if "additional_headers" in sig.parameters:
        return websockets.connect(uri, additional_headers=headers, **kwargs)
    if "extra_headers" in sig.parameters:
        return websockets.connect(uri, extra_headers=headers, **kwargs)
    return websockets.connect(uri, **kwargs)


# Edge neural voices for languages that break in the TUI (auto-picked on Speak).
_EDGE_LANG_VOICES = {
    "ML": "ml-IN-SobhanaNeural",
    "HI": "hi-IN-SwaraNeural",
    "TA": "ta-IN-PallaviNeural",
    "TE": "te-IN-ShrutiNeural",
    "KN": "kn-IN-SapnaNeural",
    "BN": "bn-IN-TanishaaNeural",
    "GU": "gu-IN-DhwaniNeural",
    "MR": "mr-IN-AarohiNeural",
    "PA": "pa-IN-VaaniNeural",
    "OR": "or-IN-SubhasiniNeural",  # may 404 → fallback handled by synth
    "SI": "si-LK-ThiliniNeural",
    "AR": "ar-SA-ZariyahNeural",
    "UR": "ur-PK-UzmaNeural",
    "FA": "fa-IR-DilaraNeural",
    "HE": "he-IL-HilaNeural",
    "TH": "th-TH-PremwadeeNeural",
    "MY": "my-MM-NilarNeural",
    "KM": "km-KH-SreymomNeural",
    "AM": "am-ET-MekdesNeural",
    "JA": "ja-JP-NanamiNeural",
    "KO": "ko-KR-SunHiNeural",
    "ZH": "zh-CN-XiaoxiaoNeural",
    "NE": "ne-NP-HemkalaNeural",
}


def edge_voice_for_lang(lang: str) -> str | None:
    code = (lang or "").strip().upper()
    if not code:
        return None
    code = code.split("-")[0][:2] if len(code) > 3 else code[:2]
    return _EDGE_LANG_VOICES.get(code)


def gtts_lang_for_code(lang: str) -> str | None:
    """Map article lang tag → gTTS lang code."""
    code = (lang or "").strip().lower().replace("_", "-")
    if not code:
        return None
    base = code.split("-")[0][:2]
    # gTTS uses ISO 639-1; a few need special forms
    special = {"zh": "zh-CN", "iw": "iw", "he": "iw", "jv": "jw"}
    return special.get(base, base)


class TTSEngine:
    """Synthesize + play article audio; stoppable."""

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._speak_lang: str | None = None
        self._playing = False
        from worldnews.paths import cache_dir

        self.cache_dir = cache_dir() / "tts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.last_play_error: str | None = None

    @property
    def is_playing(self) -> bool:
        return self._playing

    def stop(self):
        with self._lock:
            self._playing = False
            self._cleanup_proc()

    def _cleanup_proc(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def speak(
        self,
        text: str,
        on_sentence: Callable[[int, str, list[str]], None] | None = None,
        sentences: list[str] | None = None,
        lang: str | None = None,
    ) -> str:
        """Synthesize + play. Prefers sentence-by-sentence for fast start & sync.

        ``lang`` (article language tag, e.g. ML/HI/AR) picks a matching Edge/gTTS
        voice when the user is on those providers so non-English stories are audible.
        """
        text = (text or "").strip()
        if not text:
            return "Nothing to speak"
        if len(text) > 3500:
            text = text[:3497] + "…"
        self.stop()
        provider = voice_cfg.get_provider()
        self._speak_lang = (lang or "").strip().upper()[:8] or None
        sents = sentences or split_speech_sentences(text)
        if not sents:
            sents = [text]

        # Sentence pipeline: first audio ASAP + highlight locked to each clip
        if on_sentence and len(sents) >= 1:
            try:
                return self._speak_sentences(sents, provider, on_sentence)
            except Exception:
                pass  # fall through to one-shot batch

        try:
            path = self._synthesize_with_fallback(provider, text)
        except Exception as exc:
            try:
                return self._pyttsx3_speak(text)
            except Exception as e3:
                return f"TTS failed: {exc} | fallback: {e3}"
        self._playing = True
        try:
            # Warm device + pad WAV so first words aren't clipped
            self._prime_playback()
            path = self._prepare_play_path(path, first=True)
            self._play_file_blocking(path)
        finally:
            self._playing = False
            self._cleanup_proc()
            self._speak_lang = None
        name = VOICE_PROVIDERS.get(provider, {}).get("name", provider)
        return f"Speaking via {name}"

    def _speak_sentences(
        self,
        sentences: list[str],
        provider: str,
        on_sentence: Callable[[int, str, list[str]], None],
    ) -> str:
        """Play one sentence at a time; prefetch the next while current plays."""
        self._playing = True
        name = VOICE_PROVIDERS.get(provider, {}).get("name", provider)
        next_path: Path | None = None
        next_err: Exception | None = None

        def synth(s: str) -> Path:
            return self._synthesize_with_fallback(provider, s)

        # First sentence — this is the click→audio latency path (keep short)
        try:
            path = synth(sentences[0])
        except Exception as exc:
            self._playing = False
            raise exc

        # Open DAC on silence first — otherwise sentence 1 loses its opening words
        self._prime_playback()

        for i, sentence in enumerate(sentences):
            if not self._playing:
                break
            try:
                on_sentence(i, sentence, sentences)
            except Exception:
                pass

            # Prefetch next clip while we play this one
            pref_thread = None
            if i + 1 < len(sentences):

                def _prefetch(idx: int = i + 1) -> None:
                    nonlocal next_path, next_err
                    try:
                        next_path = synth(sentences[idx])
                        next_err = None
                    except Exception as e:
                        next_path = None
                        next_err = e

                next_path = None
                next_err = None
                pref_thread = threading.Thread(target=_prefetch, daemon=True)
                pref_thread.start()

            play_path = self._prepare_play_path(path, first=(i == 0))
            # Brief settle so highlight/UI work doesn't race device start
            if i == 0:
                time.sleep(0.05)
            self._play_file_blocking(play_path)
            if not self._playing:
                break

            if pref_thread is not None:
                pref_thread.join(timeout=180)
                if next_path is not None:
                    path = next_path
                elif next_err is not None and i + 1 < len(sentences):
                    # Try once more inline
                    try:
                        path = synth(sentences[i + 1])
                    except Exception:
                        break
                else:
                    break

        self._playing = False
        self._cleanup_proc()
        self._speak_lang = None
        return f"Speaking via {name}"

    def _lead_in_path(self) -> Path:
        path = self.cache_dir / "_lead_in_silence.wav"
        if not path.exists() or path.stat().st_size < 100:
            _silent_wav(path, ms=200, sample_rate=24000)
        return path

    def _prime_playback(self) -> None:
        """Play a short silent clip so the first real words aren't clipped."""
        if not self._playing:
            return
        try:
            self._play_file_blocking(self._lead_in_path())
        except Exception:
            pass

    def _prepare_play_path(self, path: Path, *, first: bool) -> Path:
        """Pad first WAV clips with lead silence (MP3 relies on _prime_playback)."""
        if first and path.suffix.lower() == ".wav":
            return _pad_wav_lead_silence(path, ms=220)
        return path
    def _synthesize_with_fallback(self, provider: str, text: str) -> Path:
        text = (text or "").strip()
        if not text:
            raise ValueError("empty text")
        try:
            return self._synthesize(provider, text)
        except Exception as exc:
            last = exc
            for fb in ("edge", "gtts"):
                if fb == provider:
                    continue
                try:
                    return self._synthesize(fb, text)
                except Exception as e2:
                    last = e2
            raise last

    def _synthesize(self, provider: str, text: str) -> Path:
        voice = voice_cfg.get_voice(provider)
        # Match article language when speaking hidden complex-script stories
        lang = getattr(self, "_speak_lang", None) or ""
        if lang:
            if provider == "edge":
                mapped = edge_voice_for_lang(lang)
                if mapped:
                    voice = mapped
            elif provider == "gtts":
                voice = gtts_lang_for_code(lang) or voice or "en"
        stamp = int(time.time() * 1000)
        if provider in _WAV_PROVIDERS:
            out = self.cache_dir / f"speak-{stamp}.wav"
        elif provider in ("elevenlabs-live",):
            # ElevenLabs stream-input defaults to mp3 chunks
            out = self.cache_dir / f"speak-{stamp}.mp3"
        else:
            out = self.cache_dir / f"speak-{stamp}.mp3"
        if provider == "edge":
            self._edge(text, voice, out)
        elif provider == "gemini":
            self._gemini_tts(text, voice, out)
        elif provider == "gemini-live":
            self._gemini_live(text, voice, out)
        elif provider == "elevenlabs":
            self._elevenlabs(text, voice, out)
        elif provider == "elevenlabs-live":
            self._elevenlabs_live(text, voice, out)
        elif provider == "openai":
            self._openai(text, voice, out)
        elif provider == "openai-live":
            self._openai_live(text, voice, out)
        elif provider == "deepgram":
            self._deepgram(text, voice, out)
        elif provider == "deepgram-live":
            self._deepgram_live(text, voice, out)
        elif provider == "groq":
            self._groq(text, voice, out)
        elif provider == "cartesia":
            self._cartesia(text, voice, out)
        elif provider == "cartesia-live":
            self._cartesia_live(text, voice, out)
        elif provider == "fish":
            self._fish(text, voice, out)
        elif provider == "gtts":
            self._gtts(text, voice, out)
        else:
            raise ValueError(f"Unknown voice provider: {provider}")
        return out

    def _edge(self, text: str, voice: str, out: Path):
        try:
            import edge_tts
        except ImportError as e:
            raise ImportError("Install edge-tts: pip install edge-tts") from e
        rate = voice_cfg.get_rate()
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)

        async def _run():
            await communicate.save(str(out))

        import asyncio

        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()

    def _gemini_tts(self, text: str, voice: str, out: Path):
        """Gemini TTS via generateContent — speech-generation docs."""
        key = voice_cfg.get_api_key("gemini")
        if not key:
            raise ValueError(
                "Gemini API key not set (Settings → Voice → Gemini TTS). "
                "Get one at https://aistudio.google.com/apikey"
            )
        model = voice_cfg.get_model("gemini") or GEMINI_TTS_MODELS[0]
        # Steerable style prompt for news narration (TTS models accept style in text)
        prompt = (
            "Read the following news story aloud clearly and naturally, "
            "like a professional news anchor:\n\n"
            f"{text}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice or "Kore"}
                    }
                },
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            raise RuntimeError(f"Gemini TTS HTTP {e.code}: {body}") from e

        pcm = self._extract_gemini_audio_b64(data)
        if not pcm:
            raise RuntimeError("Gemini TTS returned no audio data")
        _write_wav_pcm16(out, pcm, sample_rate=24000)

    def _extract_gemini_audio_b64(self, data: dict) -> bytes:
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return b""
        chunks = []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            b64 = inline.get("data")
            if b64:
                chunks.append(base64.b64decode(b64))
        return b"".join(chunks)

    def _gemini_live(self, text: str, voice: str, out: Path):
        """Gemini Live API (WebSocket) — narrate article with native audio."""
        key = voice_cfg.get_api_key("gemini-live")
        if not key:
            raise ValueError(
                "Gemini API key not set (Settings → Voice → Gemini Live). "
                "https://aistudio.google.com/apikey"
            )
        model = voice_cfg.get_model("gemini-live") or GEMINI_LIVE_MODELS[0]
        try:
            import websockets
        except ImportError as e:
            raise ImportError(
                "Install websockets for Gemini Live: pip install websockets"
            ) from e

        prompt = (
            "You are a professional news narrator. Read the following article "
            "aloud clearly and faithfully. Do not add commentary or greetings — "
            "only speak the article content.\n\n"
            f"{text}"
        )

        async def _run() -> bytes:
            import asyncio

            ws_url = (
                "wss://generativelanguage.googleapis.com/ws/"
                "google.ai.generativelanguage.v1beta.GenerativeService"
                f".BidiGenerateContent?key={key}"
            )
            audio_chunks: list[bytes] = []
            async with websockets.connect(
                ws_url, max_size=16 * 1024 * 1024, open_timeout=30
            ) as ws:
                setup = {
                    "setup": {
                        "model": f"models/{model}",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {
                                        "voiceName": voice or "Kore"
                                    }
                                }
                            },
                        },
                        "systemInstruction": {
                            "parts": [
                                {
                                    "text": (
                                        "You are a news reader. Speak clearly. "
                                        "Do not invent facts."
                                    )
                                }
                            ]
                        },
                    }
                }
                await ws.send(json.dumps(setup))

                # Wait for setupComplete (with timeout)
                setup_ok = False
                deadline = time.time() + 30
                while time.time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg = json.loads(raw)
                    if "setupComplete" in msg or "setup_complete" in msg:
                        setup_ok = True
                        break
                    # Some servers may send error
                    if "error" in msg:
                        raise RuntimeError(f"Gemini Live setup error: {msg['error']}")
                if not setup_ok:
                    raise RuntimeError("Gemini Live: no setupComplete received")

                # 3.1 Live prefers realtimeInput for text; 2.5 uses clientContent
                if "3.1" in model:
                    await ws.send(json.dumps({"realtimeInput": {"text": prompt}}))
                else:
                    await ws.send(
                        json.dumps(
                            {
                                "clientContent": {
                                    "turns": [
                                        {
                                            "role": "user",
                                            "parts": [{"text": prompt}],
                                        }
                                    ],
                                    "turnComplete": True,
                                }
                            }
                        )
                    )

                turn_done = False
                recv_deadline = time.time() + 180
                while time.time() < recv_deadline and not turn_done:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except Exception:
                        break
                    msg = json.loads(raw)
                    if "error" in msg:
                        raise RuntimeError(f"Gemini Live error: {msg['error']}")
                    sc = msg.get("serverContent") or msg.get("server_content") or {}
                    mt = sc.get("modelTurn") or sc.get("model_turn") or {}
                    for part in mt.get("parts") or []:
                        inline = part.get("inlineData") or part.get("inline_data") or {}
                        b64 = inline.get("data")
                        if b64:
                            audio_chunks.append(base64.b64decode(b64))
                    if sc.get("turnComplete") or sc.get("turn_complete"):
                        turn_done = True
                    if sc.get("generationComplete") or sc.get("generation_complete"):
                        turn_done = True

            return b"".join(audio_chunks)

        pcm = _run_async(_run())
        if not pcm:
            raise RuntimeError("Gemini Live returned no audio")
        _write_wav_pcm16(out, pcm, sample_rate=24000)

    def _openai_live(self, text: str, voice: str, out: Path):
        """OpenAI Realtime WebSocket — narrate article as audio."""
        key = voice_cfg.get_api_key("openai-live")
        if not key:
            raise ValueError(
                "OpenAI API key not set (Settings → Voice → OpenAI Realtime). "
                "https://platform.openai.com/api-keys"
            )
        model = voice_cfg.get_model("openai-live") or OPENAI_LIVE_MODELS[0]
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Install websockets for live voice: pip install websockets"
            ) from e

        prompt = (
            "You are a professional news narrator. Read the following article "
            "aloud clearly and faithfully. Do not add commentary — only speak "
            "the article content.\n\n"
            f"{text}"
        )

        async def _run() -> bytes:
            import asyncio

            uri = f"wss://api.openai.com/v1/realtime?model={model}"
            audio_chunks: list[bytes] = []
            async with _ws_connect(
                uri,
                headers={
                    "Authorization": f"Bearer {key}",
                    "OpenAI-Beta": "realtime=v1",
                },
                max_size=16 * 1024 * 1024,
                open_timeout=30,
            ) as ws:
                # Wait for session.created
                deadline = time.time() + 30
                while time.time() < deadline:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    msg = json.loads(raw)
                    if msg.get("type") == "session.created":
                        break
                    if msg.get("type") == "error":
                        raise RuntimeError(f"OpenAI Realtime: {msg}")

                await ws.send(
                    json.dumps(
                        {
                            "type": "session.update",
                            "session": {
                                "type": "realtime",
                                "model": model,
                                "output_modalities": ["audio"],
                                "instructions": (
                                    "You are a news reader. Speak clearly. "
                                    "Do not invent facts."
                                ),
                                "audio": {
                                    "output": {
                                        "format": {
                                            "type": "audio/pcm",
                                            "rate": 24000,
                                        },
                                        "voice": voice or "marin",
                                    },
                                },
                            },
                        }
                    )
                )

                await ws.send(
                    json.dumps(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "user",
                                "content": [
                                    {"type": "input_text", "text": prompt}
                                ],
                            },
                        }
                    )
                )
                await ws.send(
                    json.dumps(
                        {
                            "type": "response.create",
                            "response": {
                                "output_modalities": ["audio"],
                            },
                        }
                    )
                )

                recv_deadline = time.time() + 180
                while time.time() < recv_deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except Exception:
                        break
                    msg = json.loads(raw)
                    mtype = msg.get("type") or ""
                    if mtype == "error":
                        raise RuntimeError(f"OpenAI Realtime error: {msg}")
                    # New + legacy audio delta event names
                    if mtype in (
                        "response.output_audio.delta",
                        "response.audio.delta",
                    ):
                        b64 = msg.get("delta") or ""
                        if b64:
                            audio_chunks.append(base64.b64decode(b64))
                    if mtype in (
                        "response.done",
                        "response.output_audio.done",
                        "response.audio.done",
                    ):
                        if mtype == "response.done" or audio_chunks:
                            # Keep collecting until response.done for full audio
                            if mtype == "response.done":
                                break
            return b"".join(audio_chunks)

        pcm = _run_async(_run())
        if not pcm:
            raise RuntimeError("OpenAI Realtime returned no audio")
        _write_wav_pcm16(out, pcm, sample_rate=24000)

    def _elevenlabs_live(self, text: str, voice_id: str, out: Path):
        """ElevenLabs stream-input WebSocket TTS."""
        key = voice_cfg.get_api_key("elevenlabs-live")
        if not key:
            raise ValueError(
                "ElevenLabs API key not set (Settings → Voice → ElevenLabs Live)"
            )
        model = voice_cfg.get_model("elevenlabs-live") or ELEVEN_LIVE_MODELS[0]
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Install websockets for live voice: pip install websockets"
            ) from e

        async def _run() -> bytes:
            import asyncio

            uri = (
                f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                f"/stream-input?model_id={model}&output_format=mp3_44100_128"
            )
            chunks: list[bytes] = []
            async with _ws_connect(
                uri,
                headers={"xi-api-key": key},
                max_size=16 * 1024 * 1024,
                open_timeout=30,
            ) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "text": " ",
                            "voice_settings": {
                                "stability": 0.4,
                                "similarity_boost": 0.8,
                            },
                            "xi_api_key": key,
                        }
                    )
                )
                # Send article in chunks ending with space (docs); flush last
                piece = text.strip() + " "
                await ws.send(
                    json.dumps({"text": piece, "try_trigger_generation": True})
                )
                await ws.send(json.dumps({"text": "", "flush": True}))
                await ws.send(json.dumps({"text": ""}))

                recv_deadline = time.time() + 180
                while time.time() < recv_deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except Exception:
                        break
                    if isinstance(raw, bytes):
                        chunks.append(raw)
                        continue
                    msg = json.loads(raw)
                    if msg.get("error") or msg.get("message") == "error":
                        raise RuntimeError(f"ElevenLabs Live: {msg}")
                    b64 = msg.get("audio")
                    if b64:
                        chunks.append(base64.b64decode(b64))
                    if msg.get("isFinal") or msg.get("is_final"):
                        break
            return b"".join(chunks)

        data = _run_async(_run())
        if not data:
            raise RuntimeError("ElevenLabs Live returned no audio")
        out.write_bytes(data)

    def _deepgram_live(self, text: str, model_voice: str, out: Path):
        """Deepgram Speak WebSocket — linear16 PCM stream."""
        key = voice_cfg.get_api_key("deepgram-live")
        if not key:
            raise ValueError(
                "Deepgram API key not set (Settings → Voice → Deepgram Live). "
                "https://console.deepgram.com/"
            )
        model = model_voice or "aura-2-thalia-en"
        sample_rate = 24000
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Install websockets for live voice: pip install websockets"
            ) from e

        async def _run() -> bytes:
            import asyncio

            uri = (
                f"wss://api.deepgram.com/v1/speak"
                f"?model={model}&encoding=linear16&sample_rate={sample_rate}"
            )
            chunks: list[bytes] = []
            async with _ws_connect(
                uri,
                headers={"Authorization": f"Token {key}"},
                max_size=16 * 1024 * 1024,
                open_timeout=30,
            ) as ws:
                # Docs/SDKs use Speak or Text; try Speak then Flush/Close
                await ws.send(json.dumps({"type": "Speak", "text": text}))
                await ws.send(json.dumps({"type": "Flush"}))

                recv_deadline = time.time() + 180
                while time.time() < recv_deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except Exception:
                        break
                    if isinstance(raw, (bytes, bytearray)):
                        chunks.append(bytes(raw))
                        continue
                    msg = json.loads(raw)
                    mtype = (msg.get("type") or "").lower()
                    if mtype in ("error",):
                        raise RuntimeError(f"Deepgram Live: {msg}")
                    if mtype in ("flushed", "metadata", "close", "closed"):
                        # Flushed means audio for this request is done
                        if mtype in ("flushed", "close", "closed"):
                            break
                try:
                    await ws.send(json.dumps({"type": "Close"}))
                except Exception:
                    pass
            return b"".join(chunks)

        pcm = _run_async(_run())
        if not pcm:
            raise RuntimeError("Deepgram Live returned no audio")
        _write_wav_pcm16(out, pcm, sample_rate=sample_rate)

    def _cartesia_live(self, text: str, voice_id: str, out: Path):
        """Cartesia Sonic WebSocket TTS (pcm_s16le)."""
        key = voice_cfg.get_api_key("cartesia-live")
        if not key:
            raise ValueError(
                "Cartesia API key not set (Settings → Voice → Cartesia Live). "
                "https://play.cartesia.ai/"
            )
        model = voice_cfg.get_model("cartesia-live") or CARTESIA_LIVE_MODELS[0]
        sample_rate = 24000
        try:
            import websockets  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Install websockets for live voice: pip install websockets"
            ) from e

        async def _run() -> bytes:
            import asyncio

            uri = "wss://api.cartesia.ai/tts/websocket"
            ctx = str(uuid.uuid4())
            chunks: list[bytes] = []
            async with _ws_connect(
                uri,
                headers={
                    "X-API-Key": key,
                    "Cartesia-Version": "2025-04-16",
                },
                max_size=16 * 1024 * 1024,
                open_timeout=30,
            ) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "model_id": model,
                            "transcript": text,
                            "voice": {"mode": "id", "id": voice_id},
                            "language": "en",
                            "context_id": ctx,
                            "continue": False,
                            "output_format": {
                                "container": "raw",
                                "encoding": "pcm_s16le",
                                "sample_rate": sample_rate,
                            },
                        }
                    )
                )
                recv_deadline = time.time() + 180
                while time.time() < recv_deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except Exception:
                        break
                    if isinstance(raw, (bytes, bytearray)):
                        chunks.append(bytes(raw))
                        continue
                    msg = json.loads(raw)
                    if msg.get("error") or msg.get("type") == "error":
                        raise RuntimeError(f"Cartesia Live: {msg}")
                    # chunk messages carry base64 audio
                    b64 = msg.get("data") or msg.get("audio")
                    if b64 and isinstance(b64, str):
                        chunks.append(base64.b64decode(b64))
                    if msg.get("done") or msg.get("type") == "done":
                        break
            return b"".join(chunks)

        pcm = _run_async(_run())
        if not pcm:
            raise RuntimeError("Cartesia Live returned no audio")
        _write_wav_pcm16(out, pcm, sample_rate=sample_rate)

    def _elevenlabs(self, text: str, voice_id: str, out: Path):
        key = voice_cfg.get_api_key("elevenlabs")
        if not key:
            raise ValueError("ElevenLabs API key not set (Settings → Voice)")
        model = voice_cfg.get_model("elevenlabs") or "eleven_multilingual_v2"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.write_bytes(r.read())

    def _openai(self, text: str, voice: str, out: Path):
        key = voice_cfg.get_api_key("openai")
        if not key:
            raise ValueError("OpenAI API key not set (Settings → Voice)")
        model = voice_cfg.get_model("openai") or voice_cfg.config.get(
            "openai_model", "gpt-4o-mini-tts"
        )
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        # Steerable instructions supported on gpt-4o-mini-tts (not tts-1 / tts-1-hd)
        if "gpt-4o-mini-tts" in model:
            payload["instructions"] = (
                "Speak clearly like a professional news anchor."
            )
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.write_bytes(r.read())

    def _deepgram(self, text: str, model_voice: str, out: Path):
        """Deepgram Aura-2 — POST /v1/speak?model=aura-2-*"""
        key = voice_cfg.get_api_key("deepgram")
        if not key:
            raise ValueError(
                "Deepgram API key not set (Settings → Voice). "
                "https://console.deepgram.com/"
            )
        model = model_voice or "aura-2-thalia-en"
        url = f"https://api.deepgram.com/v1/speak?model={model}&encoding=mp3"
        req = urllib.request.Request(
            url,
            data=json.dumps({"text": text}).encode(),
            headers={
                "Authorization": f"Token {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.write_bytes(r.read())

    def _groq(self, text: str, voice: str, out: Path):
        """Groq Orpheus TTS — OpenAI-compatible /openai/v1/audio/speech."""
        key = voice_cfg.get_api_key("groq")
        if not key:
            # Reuse AI Groq key if present
            try:
                from worldnews.ai import ai as _ai

                key = _ai.get_api_key("groq") or ""
            except Exception:
                key = ""
        if not key:
            raise ValueError(
                "Groq API key not set (Settings → Voice). "
                "https://console.groq.com/keys"
            )
        model = voice_cfg.get_model("groq") or "canopylabs/orpheus-v1-english"
        # Auto-pick Arabic model if Arabic voice selected
        ar = {"fahad", "sultan", "noura", "lulwa", "aisha"}
        if voice in ar and "arabic" not in model:
            model = "canopylabs/orpheus-arabic-saudi"
        # Orpheus English supports vocal directions in brackets
        if "english" in model and "[" not in text:
            text = f"[clear] {text}"
        payload = {
            "model": model,
            "input": text[:5000],
            "voice": voice or "troy",
            "response_format": "wav",
        }
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/speech",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.write_bytes(r.read())

    def _cartesia(self, text: str, voice_id: str, out: Path):
        """Cartesia Sonic REST bytes endpoint."""
        key = voice_cfg.get_api_key("cartesia")
        if not key:
            raise ValueError(
                "Cartesia API key not set (Settings → Voice). "
                "https://play.cartesia.ai/"
            )
        model = voice_cfg.get_model("cartesia") or "sonic-3.5"
        payload = {
            "model_id": model,
            "transcript": text,
            "voice": {"mode": "id", "id": voice_id},
            "output_format": {
                "container": "mp3",
                "bit_rate": 128000,
                "sample_rate": 44100,
            },
            "language": "en",
        }
        req = urllib.request.Request(
            "https://api.cartesia.ai/tts/bytes",
            data=json.dumps(payload).encode(),
            headers={
                "X-API-Key": key,
                "Cartesia-Version": "2025-04-16",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.write_bytes(r.read())

    def _fish(self, text: str, voice_id: str, out: Path):
        """Fish Audio TTS — https://docs.fish.audio/ POST /v1/tts (JSON).

        Models via `model` header: s2.1-pro-free (default), s2.1-pro, s2-pro, s1, …
        Voice via body `reference_id` (library id from fish.audio/m/<id>).
        """
        key = voice_cfg.get_api_key("fish")
        if not key:
            raise ValueError(
                "Fish Audio API key not set (Settings → Voice → Fish Audio). "
                "Get one free at https://fish.audio/app/api-keys"
            )
        model = voice_cfg.get_model("fish") or FISH_MODELS[0]
        # News-reader style cues (S2 = [brackets], S1 = (parens))
        stripped = (text or "").lstrip()
        if model.startswith("s2") and not stripped.startswith("["):
            text = f"[clear professional news anchor] {text}"
        elif model == "s1" and not stripped.startswith("("):
            text = f"(serious)(confident) {text}"

        speed = _rate_to_fish_speed(voice_cfg.get_rate())
        payload: dict = {
            "text": text,
            "format": "mp3",
            "mp3_bitrate": 128,
            "normalize": True,
            "latency": "normal",
        }
        rid = (voice_id or "").strip()
        if rid and rid.lower() not in ("default", "none", "-"):
            payload["reference_id"] = rid
        if abs(speed - 1.0) > 0.01:
            payload["prosody"] = {"speed": speed}

        req = urllib.request.Request(
            "https://api.fish.audio/v1/tts",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "model": model,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out.write_bytes(r.read())
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            raise RuntimeError(
                f"Fish Audio HTTP {e.code}: {body or e.reason}"
            ) from e

    def _gtts(self, text: str, lang: str, out: Path):
        try:
            from gtts import gTTS
        except ImportError as e:
            raise ImportError("Install gTTS: pip install gTTS") from e
        # gTTS accepts locale tags; normalize e.g. en-uk → en, zh-CN stays
        code = (lang or "en").replace("_", "-")
        if code.lower().startswith("zh"):
            tld = "com"
            lang_code = "zh-CN" if "TW" not in code.upper() else "zh-TW"
        else:
            lang_code = code.split("-")[0]
            tld = "co.uk" if "uk" in code.lower() else "com"
        tts = gTTS(text=text, lang=lang_code, tld=tld)
        tts.save(str(out))

    def _pyttsx3_speak(self, text: str) -> str:
        try:
            import pyttsx3
        except ImportError as e:
            raise ImportError("Install pyttsx3: pip install pyttsx3") from e
        engine = pyttsx3.init()
        self._playing = True
        engine.say(text)
        engine.runAndWait()
        self._playing = False
        return "Spoke via offline pyttsx3"

    def _play_with_miniaudio(self, path: Path) -> bool:
        """Fast in-process mp3/wav playback. Returns False if unavailable."""
        try:
            import miniaudio
        except ImportError:
            return False
        try:
            info = miniaudio.get_file_info(str(path))
            duration = float(getattr(info, "duration", 0) or 0)
            if duration <= 0:
                duration = max(0.5, path.stat().st_size / 4000.0)
            stream = miniaudio.stream_file(str(path))
            with miniaudio.PlaybackDevice() as device:
                device.start(stream)
                # Let the device actually start outputting before we trust timing
                time.sleep(0.04)
                end = time.time() + duration + 0.15
                while time.time() < end and self._playing:
                    time.sleep(0.03)
            return True
        except Exception:
            return False

    def _play_with_pygame(self, path: Path) -> bool:
        """Optional pygame playback. Returns False if unavailable."""
        try:
            import pygame
        except ImportError:
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.play()
            # Mixer often drops the first ~50–100ms on cold start
            time.sleep(0.02)
            while pygame.mixer.music.get_busy() and self._playing:
                time.sleep(0.03)
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _play_file_blocking(self, path: Path) -> None:
        """Play one audio file and wait until it finishes (or stop())."""
        if not self._playing:
            return
        path = path.resolve()
        self._cleanup_proc()
        self.last_play_error = None

        # In-process players start much faster than PowerShell MediaPlayer
        if self._play_with_miniaudio(path):
            return
        if self._play_with_pygame(path):
            return

        cmds: list[list[str]] = []
        if sys.platform == "darwin":
            cmds.append(["afplay", str(path)])
        cmds.extend(
            [
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)],
                ["mpv", "--no-video", "--really-quiet", str(path)],
                ["mpg123", "-q", str(path)],
                # Termux / Linux fallbacks
                ["termux-media-player", "play", str(path)],
                ["aplay", str(path)],
                ["play", "-q", str(path)],
            ]
        )

        proc = None
        for cmd in cmds:
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                break
            except FileNotFoundError:
                continue

        if proc is None and sys.platform == "win32":
            if path.suffix.lower() == ".wav":
                ps = (
                    f"$p = New-Object System.Media.SoundPlayer '{path}'; "
                    "$p.PlaySync();"
                )
            else:
                # Wait until media is loaded BEFORE Play — otherwise first words clip
                ps = (
                    "Add-Type -AssemblyName presentationCore; "
                    "$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open([Uri]'{path.as_uri()}'); "
                    "$deadline = (Get-Date).AddSeconds(8); "
                    "while (-not $p.NaturalDuration.HasTimeSpan) { "
                    "  if ((Get-Date) -gt $deadline) { break }; "
                    "  Start-Sleep -Milliseconds 40 "
                    "}; "
                    "Start-Sleep -Milliseconds 80; "
                    "$p.Position = [TimeSpan]::Zero; "
                    "$p.Play(); "
                    "if ($p.NaturalDuration.HasTimeSpan) { "
                    "  $ms = [int](($p.NaturalDuration.TimeSpan.TotalSeconds + 0.25) * 1000); "
                    "  Start-Sleep -Milliseconds $ms "
                    "} else { "
                    "  Start-Sleep -Seconds 8 "
                    "}; "
                    "$p.Stop(); $p.Close()"
                )
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        if proc is None:
            from worldnews.platform import which_player_hint

            self.last_play_error = which_player_hint()
            self._playing = False
            return

        self._proc = proc
        while self._playing and proc.poll() is None:
            time.sleep(0.03)
        if not self._playing and proc.poll() is None:
            self._cleanup_proc()
        else:
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None


tts_engine = TTSEngine()


# Common title/corp abbrevs that end with "." but do not end a sentence
_SPEECH_ABBREVS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "ave",
        "blvd",
        "rd",
        "vs",
        "etc",
        "approx",
        "dept",
        "univ",
        "assn",
        "bros",
        "inc",
        "ltd",
        "corp",
        "co",
        "no",
        "vol",
        "fig",
        "eq",
        "gen",
        "gov",
        "sen",
        "rep",
        "rev",
        "hon",
        "pres",
        "ft",
        "mt",
        "al",  # et al.
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
        "mon",
        "tue",
        "tues",
        "wed",
        "thu",
        "thur",
        "thurs",
        "fri",
        "sat",
        "sun",
    }
)

# Dotted forms: U.S. / e.g. / Ph.D. (compare without dots, lowercased)
_SPEECH_DOTTED = frozenset(
    {
        "us",
        "uk",
        "eu",
        "un",
        "usa",
        "eg",
        "ie",
        "am",
        "pm",
        "phd",
        "md",
        "ba",
        "ma",
        "bsc",
        "msc",
        "llb",
        "jd",
        "tv",
        "dc",
        "nyc",
    }
)


def _token_before_sentence_punct(segment: str) -> str:
    """Word immediately before trailing .!? (and optional closing quotes)."""
    s = re.sub(r'[.!?]["\'”’)\]\}]*\s*$', "", (segment or "").rstrip())
    m = re.search(r"([A-Za-z0-9][A-Za-z0-9.'’_-]*)$", s)
    return m.group(1) if m else ""


def _is_speech_sentence_boundary(
    segment: str, punct: str, next_ch: str, *, at_end: bool
) -> bool:
    """True when ``punct`` at end of ``segment`` should start a new spoken sentence."""
    if punct in "!?":
        return True
    if at_end:
        return True

    stripped = segment.rstrip()
    # Mid-ellipsis: only break if a new sentence clearly starts
    if stripped.endswith("..."):
        return bool(next_ch and (next_ch.isupper() or next_ch in "\"'“‘"))

    token = _token_before_sentence_punct(segment)
    if not token:
        return bool(next_ch and next_ch.isupper())

    core = token.rstrip(".")
    low = core.lower()

    # Single-letter initials: "J." / "R." in J.R.R. Tolkien
    if len(core) == 1 and core.isalpha():
        return False

    # Run of initials at the end: J.R.R. / J. R. R.
    if re.search(r"(?:\b[A-Za-z]\.\s*){2,}$", stripped):
        return False

    if low in _SPEECH_ABBREVS:
        return False

    # U.S. / e.g. / Ph.D.
    dotted_key = low.replace(".", "")
    if "." in token and dotted_key in _SPEECH_DOTTED:
        return False

    # Decimals / versions: 3.14 or v2.0
    if core[-1:].isdigit() and next_ch.isdigit():
        return False

    # Continuation in same sentence (lowercase or comma-ish flow)
    if next_ch.islower():
        return False

    return True


def split_speech_sentences(text: str) -> list[str]:
    """Split narration into sentence-sized chunks for highlight sync.

    Avoids false breaks on initials (J.R.R.), titles (Mr./Dr.), dotted
    abbrevs (U.S./e.g.), and decimals. Also breaks on Indic danda and
    CJK / Arabic sentence punctuation so Malayalam/Hindi/Arabic chunk cleanly.
    """
    raw = " ".join((text or "").split())
    if not raw:
        return []

    # Normalize common non-Latin terminators to '.' for the Latin splitter path
    for mark in ("।", "॥", "。", "！", "？", "؟", "﹒"):
        raw = raw.replace(mark, ". ")

    sentences: list[str] = []
    start = 0
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch in ".!?":
            j = i
            # Allow !!! / ??? / …-ish runs of ?!
            while j < n and raw[j] in ".!?":
                j += 1
            while j < n and raw[j] in "\"'”’)":
                j += 1

            at_end = j >= n
            if not at_end and not raw[j].isspace():
                # e.g. example.com or 3.14 — not a spoken break
                i += 1
                continue

            k = j
            while k < n and raw[k].isspace():
                k += 1
            next_ch = raw[k] if k < n else ""
            segment = raw[start:j]

            if not _is_speech_sentence_boundary(
                segment, ch, next_ch, at_end=at_end
            ):
                i = max(j, i + 1)
                continue

            piece = segment.strip()
            if piece:
                sentences.append(piece)
            start = k
            i = k
            continue
        i += 1

    tail = raw[start:].strip()
    if tail:
        sentences.append(tail)

    # Only merge true leftovers (lone initials), not short real sentences
    merged: list[str] = []
    for p in sentences:
        if merged and re.fullmatch(r"(?:[A-Za-z]\.\s*)+", p):
            merged[-1] = f"{merged[-1]} {p}"
        else:
            merged.append(p)
    # Cap very long runs (no punctuation) into ~280 char chunks for TTS APIs
    capped: list[str] = []
    for p in merged:
        if len(p) <= 280:
            capped.append(p)
            continue
        buf = p
        while len(buf) > 280:
            cut = buf.rfind(" ", 0, 280)
            if cut < 80:
                cut = 280
            capped.append(buf[:cut].strip())
            buf = buf[cut:].strip()
        if buf:
            capped.append(buf)
    return capped or [raw]


def split_body_sentences(plain: str, max_chars: int = 2800) -> list[str]:
    """Sentence-split on-screen body so each chunk still exists in the body.

    Splits per paragraph (keeps ``\\n\\n`` boundaries) so highlight ``find()``
    cannot fail after whitespace collapse.
    """
    text = (plain or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paras:
        paras = [text]
    out: list[str] = []
    total = 0
    for para in paras:
        for s in split_speech_sentences(para):
            if total + len(s) + 1 > max_chars:
                return out or [s[:max_chars]]
            out.append(s)
            total += len(s) + 1
    return out


def locate_sentence_in_body(plain: str, sentence: str) -> tuple[int, str]:
    """Return (start, matched_span) in ``plain`` for a spoken sentence."""
    plain = plain or ""
    current = (sentence or "").strip()
    if not plain or not current:
        return -1, current

    pos = plain.find(current)
    if pos >= 0:
        return pos, current

    alt = current.rstrip(".!?…").strip()
    if alt and alt != current:
        pos = plain.find(alt)
        if pos >= 0:
            return pos, alt

    needle = current[:40].strip()
    if len(needle) >= 12:
        pos = plain.find(needle)
        if pos >= 0:
            end = pos + len(needle)
            for sep in (". ", "! ", "? ", ".\n", "!\n", "?\n", "\n\n"):
                j = plain.find(sep, end)
                if j != -1 and j - pos < 400:
                    end = j + 1
                    break
            return pos, plain[pos:end]

    # Whitespace-flexible: spoken text collapsed spaces; body may have \\n\\n
    parts = [p for p in re.split(r"\s+", current) if p]
    if len(parts) >= 2:
        pat = r"\s+".join(re.escape(p) for p in parts)
        m = re.search(pat, plain)
        if m:
            return m.start(), plain[m.start() : m.end()]

    return -1, current


def article_speech_sentences(article: dict, max_chars: int = 2800) -> list[str]:
    """Sentences spoken aloud — same content the reader highlights."""
    title = (article.get("title") or "").strip()
    source = (article.get("source") or "").strip()
    desc = (article.get("description") or "").strip()
    chunks: list[str] = []
    if title:
        chunks.append(title if title.endswith((".", "!", "?")) else title + ".")
    if source:
        chunks.append(f"From {source}.")
    if desc:
        # Prefer paragraph breaks from scraped body, then sentence-split
        paras = [p.strip() for p in desc.split("\n\n") if p.strip()]
        if not paras:
            paras = [desc]
        for para in paras:
            chunks.extend(split_speech_sentences(para))
    # Enforce TTS length budget
    out: list[str] = []
    total = 0
    for s in chunks:
        if total + len(s) + 1 > max_chars:
            break
        out.append(s)
        total += len(s) + 1
    return out or ([title, desc] if desc else [title or "No content."])


def article_speech_text(article: dict, max_chars: int = 2800) -> str:
    sents = article_speech_sentences(article, max_chars=max_chars)
    text = " ".join(s for s in sents if s)
    if len(text) > max_chars:
        text = text[: max_chars - 1].rsplit(" ", 1)[0] + "."
    return text
