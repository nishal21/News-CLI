"""Voice provider catalog — models & voices from official docs.

Sources:
- Fish Audio: https://docs.fish.audio/ (s2.1-pro-free / s2.1-pro / s2-pro / s1)
- Gemini TTS/Live: https://ai.google.dev/gemini-api/docs/speech-generation
- OpenAI TTS: https://developers.openai.com/api/docs/guides/text-to-speech
- ElevenLabs: https://elevenlabs.io/docs/overview/models
- Deepgram Aura-2: https://developers.deepgram.com/docs/tts-models
- Groq Orpheus: https://console.groq.com/docs/text-to-speech
- Cartesia Sonic: https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
- OpenAI Realtime: https://developers.openai.com/api/docs/guides/realtime-websocket
- ElevenLabs Live WS: https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts
- Edge TTS: edge-tts list_voices() (en-* neural)
"""

from __future__ import annotations

import re

GEMINI_VOICE_LABELS = {
    "Zephyr": "Bright",
    "Puck": "Upbeat",
    "Charon": "Informative",
    "Kore": "Firm",
    "Fenrir": "Excitable",
    "Leda": "Youthful",
    "Orus": "Firm",
    "Aoede": "Breezy",
    "Callirrhoe": "Easy-going",
    "Autonoe": "Bright",
    "Enceladus": "Breathy",
    "Iapetus": "Clear",
    "Umbriel": "Easy-going",
    "Algieba": "Smooth",
    "Despina": "Smooth",
    "Erinome": "Clear",
    "Algenib": "Gravelly",
    "Rasalgethi": "Informative",
    "Laomedeia": "Upbeat",
    "Achernar": "Soft",
    "Alnilam": "Firm",
    "Schedar": "Even",
    "Gacrux": "Mature",
    "Pulcherrima": "Forward",
    "Achird": "Friendly",
    "Zubenelgenubi": "Casual",
    "Vindemiatrix": "Gentle",
    "Sadachbia": "Lively",
    "Sadaltager": "Knowledgeable",
    "Sulafat": "Warm"
}
GEMINI_VOICES = list(GEMINI_VOICE_LABELS.keys())

GEMINI_TTS_MODELS = [
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
    "gemini-2.5-pro-preview-tts",
]

GEMINI_LIVE_MODELS = [
    "gemini-3.1-flash-live-preview",
    "gemini-2.5-flash-preview-native-audio-dialog",
    "gemini-2.5-flash-live-preview",
]

OPENAI_LIVE_MODELS = [
    "gpt-realtime-2.1",
    "gpt-realtime",
    "gpt-realtime-2",
    "gpt-4o-realtime-preview",
]
OPENAI_LIVE_VOICES = [
    "marin", "cedar",  # recommended
    "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse",
]

ELEVEN_LIVE_MODELS = [
    "eleven_flash_v2_5",  # best realtime latency (~75ms)
    "eleven_flash_v2",
    "eleven_multilingual_v2",
    "eleven_turbo_v2_5",
]

CARTESIA_LIVE_MODELS = [
    "sonic-3.5",
    "sonic-latest",
    "sonic-3",
]

# News / broadcast-friendly Edge voices listed first (same full set below)
EDGE_NEWS_VOICES = [
    "en-US-JennyNeural",  # classic news-reader feel
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-GB-SoniaNeural",
    "en-GB-RyanNeural",
    "en-US-ChristopherNeural",
    "en-US-EricNeural",
    "en-IN-NeerjaExpressiveNeural",
]

EDGE_EN_VOICES = [
    *EDGE_NEWS_VOICES,
    "en-AU-NatashaNeural",
    "en-AU-WilliamMultilingualNeural",
    "en-CA-ClaraNeural",
    "en-CA-LiamNeural",
    "en-GB-LibbyNeural",
    "en-GB-MaisieNeural",
    "en-GB-ThomasNeural",
    "en-HK-SamNeural",
    "en-HK-YanNeural",
    "en-IE-ConnorNeural",
    "en-IE-EmilyNeural",
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "en-KE-AsiliaNeural",
    "en-KE-ChilembaNeural",
    "en-NG-AbeoNeural",
    "en-NG-EzinneNeural",
    "en-NZ-MitchellNeural",
    "en-NZ-MollyNeural",
    "en-PH-JamesNeural",
    "en-PH-RosaNeural",
    "en-SG-LunaNeural",
    "en-SG-WayneNeural",
    "en-TZ-ElimuNeural",
    "en-TZ-ImaniNeural",
    "en-US-AnaNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-AndrewNeural",
    "en-US-AvaMultilingualNeural",
    "en-US-AvaNeural",
    "en-US-BrianMultilingualNeural",
    "en-US-BrianNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-EmmaNeural",
    "en-US-MichelleNeural",
    "en-US-RogerNeural",
    "en-US-SteffanNeural",
    "en-ZA-LeahNeural",
    "en-ZA-LukeNeural",
]
# De-dupe while preserving order (news picks appear once at top)
_seen_edge: set[str] = set()
EDGE_EN_VOICES = [
    v for v in EDGE_EN_VOICES if not (v in _seen_edge or _seen_edge.add(v))
]
EDGE_VOICE_LABELS = {
    "en-US-JennyNeural": "Jenny — news reader (US)",
    "en-US-GuyNeural": "Guy — broadcast (US)",
    "en-US-AriaNeural": "Aria — clear news (US)",
    "en-GB-SoniaNeural": "Sonia — BBC-style (UK)",
    "en-GB-RyanNeural": "Ryan — news (UK)",
    "en-US-ChristopherNeural": "Christopher — authoritative",
    "en-US-EricNeural": "Eric — news desk",
    "en-IN-NeerjaExpressiveNeural": "Neerja — expressive (IN)",
    "en-US-AvaNeural": "Ava — warm default",
}

# Fish Audio — https://docs.fish.audio/ + public Voice Library (fish.audio/m/<id>)
FISH_MODELS = [
    "s2.1-pro-free",  # same quality as s2.1-pro · $0 fair-use (recommended)
    "s2.1-pro",  # production SLA
    "s2-pro",  # previous S2 · [bracket] expression
    "s1",  # (parenthesis) emotions
    "speech-1.6",
    "speech-1.5",
]
FISH_MODEL_LABELS = {
    "s2.1-pro-free": "S2.1-Pro Free — best free expressive (fair use)",
    "s2.1-pro": "S2.1-Pro — production",
    "s2-pro": "S2-Pro — [emotion] brackets",
    "s1": "S1 — (emotion) tags",
    "speech-1.6": "Speech 1.6 (legacy)",
    "speech-1.5": "Speech 1.5 (legacy)",
}
# Curated news + expressive library voices (id from fish.audio/m/<id>/)
FISH_VOICES = {
    "default": "Default Fish voice (no clone)",
    "a0cd220b3c834df8b97a865bacb79c79": "Reporter-NBC — news desk",
    "8e929bd1003d44d3b84872d6ed45a3ec": "News Reporter — authoritative",
    "bb7cdc74cdbe4ec081e52c15f7d7860a": "Charlie Van Dyke — news open",
    "72d1c68538f544feb6eeb49414c8b44e": "Chris Corley — news open",
    "e649dfa32586489cab1ccea881b4ba10": "Professional News Anchor",
    "f5b3364daab74d1c8b691cb6616969ec": "Lani York — newscaster",
    "4147e943b07a46bcaf3a5b565a590ec9": "Jon — documentary narrator",
    "44a39f07084d4c108d4f1f44e831fd86": "Antony — storyteller",
    "584afa907518428fac9b04c92ec8a563": "Jessica — storyteller",
    "ff8eddb72a7d4484b26fba4d635034d9": "Dynamic Female Narrator",
    "66826c75508a44b79334d7ee1caa8d21": "Lily — expressive narrator",
    "802e3bc2b27e49c2995d23ef70e6ac89": "Docs sample voice",
    "9a9cf47702da476aa4629e2506d4a857": "Docs sample voice 2",
}

DEEPGRAM_VOICES = {
    "aura-2-agathe-fr": "Agathe",
    "aura-2-agustina-es": "Agustina",
    "aura-2-alvaro-es": "Alvaro",
    "aura-2-ama-ja": "Ama",
    "aura-2-amalthea-en": "Amalthea",
    "aura-2-andromeda-en": "Andromeda",
    "aura-2-antonia-es": "Antonia",
    "aura-2-apollo-en": "Apollo",
    "aura-2-aquila-es": "Aquila",
    "aura-2-arcas-en": "Arcas",
    "aura-2-aries-en": "Aries",
    "aura-2-asteria-en": "Asteria",
    "aura-2-athena-en": "Athena",
    "aura-2-atlas-en": "Atlas",
    "aura-2-aurelia-de": "Aurelia",
    "aura-2-aurora-en": "Aurora",
    "aura-2-beatrix-nl": "Beatrix",
    "aura-2-callista-en": "Callista",
    "aura-2-carina-es": "Carina",
    "aura-2-celeste-es": "Celeste",
    "aura-2-cesare-it": "Cesare",
    "aura-2-cinzia-it": "Cinzia",
    "aura-2-cora-en": "Cora",
    "aura-2-cordelia-en": "Cordelia",
    "aura-2-cornelia-nl": "Cornelia",
    "aura-2-daphne-nl": "Daphne",
    "aura-2-delia-en": "Delia",
    "aura-2-demetra-it": "Demetra",
    "aura-2-diana-es": "Diana",
    "aura-2-dionisio-it": "Dionisio",
    "aura-2-draco-en": "Draco",
    "aura-2-ebisu-ja": "Ebisu",
    "aura-2-elara-de": "Elara",
    "aura-2-electra-en": "Electra",
    "aura-2-elio-it": "Elio",
    "aura-2-estrella-es": "Estrella",
    "aura-2-fabian-de": "Fabian",
    "aura-2-flavio-it": "Flavio",
    "aura-2-fujin-ja": "Fujin",
    "aura-2-gloria-es": "Gloria",
    "aura-2-harmonia-en": "Harmonia",
    "aura-2-hector-fr": "Hector",
    "aura-2-helena-en": "Helena",
    "aura-2-hera-en": "Hera",
    "aura-2-hermes-en": "Hermes",
    "aura-2-hestia-nl": "Hestia",
    "aura-2-hyperion-en": "Hyperion",
    "aura-2-iris-en": "Iris",
    "aura-2-izanami-ja": "Izanami",
    "aura-2-janus-en": "Janus",
    "aura-2-javier-es": "Javier",
    "aura-2-julius-de": "Julius",
    "aura-2-juno-en": "Juno",
    "aura-2-jupiter-en": "Jupiter",
    "aura-2-kara-de": "Kara",
    "aura-2-lara-de": "Lara",
    "aura-2-lars-nl": "Lars",
    "aura-2-leda-nl": "Leda",
    "aura-2-livia-it": "Livia",
    "aura-2-luciano-es": "Luciano",
    "aura-2-luna-en": "Luna",
    "aura-2-maia-it": "Maia",
    "aura-2-mars-en": "Mars",
    "aura-2-melia-it": "Melia",
    "aura-2-minerva-en": "Minerva",
    "aura-2-neptune-en": "Neptune",
    "aura-2-nestor-es": "Nestor",
    "aura-2-odysseus-en": "Odysseus",
    "aura-2-olivia-es": "Olivia",
    "aura-2-ophelia-en": "Ophelia",
    "aura-2-orion-en": "Orion",
    "aura-2-orpheus-en": "Orpheus",
    "aura-2-pandora-en": "Pandora",
    "aura-2-perseo-it": "Perseo",
    "aura-2-phoebe-en": "Phoebe",
    "aura-2-pluto-en": "Pluto",
    "aura-2-rhea-nl": "Rhea",
    "aura-2-roman-nl": "Roman",
    "aura-2-sander-nl": "Sander",
    "aura-2-saturn-en": "Saturn",
    "aura-2-selena-es": "Selena",
    "aura-2-selene-en": "Selene",
    "aura-2-silvia-es": "Silvia",
    "aura-2-sirio-es": "Sirio",
    "aura-2-thalia-en": "Thalia",
    "aura-2-theia-en": "Theia",
    "aura-2-uzume-ja": "Uzume",
    "aura-2-valerio-es": "Valerio",
    "aura-2-vesta-en": "Vesta",
    "aura-2-viktoria-de": "Viktoria",
    "aura-2-zeus-en": "Zeus"
}

OPENAI_VOICES = [
    "marin", "cedar",  # recommended best quality
    "alloy", "ash", "ballad", "coral", "echo", "fable",
    "nova", "onyx", "sage", "shimmer", "verse",
]
OPENAI_MODELS = [
    "gpt-4o-mini-tts",
    "gpt-4o-mini-tts-2025-12-15",
    "tts-1-hd",
    "tts-1",
]

ELEVEN_MODELS = [
    "eleven_v3",
    "eleven_multilingual_v2",
    "eleven_flash_v2_5",
    "eleven_flash_v2",
    "eleven_turbo_v2_5",  # deprecated but listed in docs
    "eleven_turbo_v2",
]
ELEVEN_VOICES = {
    "21m00Tcm4TlvDq8ikWAM": "Rachel",
    "AZnzlk1XvdvUeBnXmlld": "Domi",
    "EXAVITQu4vr4xnSDxMaL": "Bella",
    "ErXwobaYiN019PkySvjV": "Antoni",
    "MF3mGyEYCl7XYWbV9V6O": "Elli",
    "TxGEqnHWrfWFTfGW9XjX": "Josh",
    "VR6AewLTigWG4xSOukaG": "Arnold",
    "pNInz6obpgDQGcFmaJgB": "Adam",
    "yoZ06aMxZJJ28mfd3POQ": "Sam",
    "XB0fDUnXU5powFXDhCwa": "Charlotte",
    "iP95p4xoKVk53GoZ742B": "Chris",
    "onwK4e9ZLuTAKqWW03F9": "Daniel",
    "cjVigY5qzO86Huf0OWal": "Eric",
    "JBFqnCBsd6RMkjVDRZzb": "George",
    "N2lVS1w4EtoT3dr4eOWO": "Callum",
    "SAz9YHcvj6GT2YYXdXww": "River",
    "TX3LPaxmHKxFdv7VOQHJ": "Liam",
    "Xb7hH8MSUJpSbSDYk0k2": "Alice",
    "XrExE9yKIg1WjnnlVkGX": "Matilda",
    "bIHbv24MWmeRgasZH58o": "Will",
    "cgSgspJ2msmNjvvpLSC2": "Jessica",
    "nPczCjzI2devNBz1zQrb": "Brian",
    "pqHfZKP75CvOlQylNhV4": "Bill",
}

GROQ_EN_VOICES = ["autumn", "diana", "hannah", "austin", "daniel", "troy"]
GROQ_AR_VOICES = ["fahad", "sultan", "noura", "lulwa", "aisha"]
GROQ_MODELS = [
    "canopylabs/orpheus-v1-english",
    "canopylabs/orpheus-arabic-saudi",
]

CARTESIA_VOICES = {
    "f786b574-daa5-4673-aa0c-cbe3e8534c02": "Katie (en-US Female)",
    "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4": "Skylar (en-US Female)",
    "a5136bf9-224c-4d76-b823-52bd5efcffcc": "Jameson (en-US Male)",
    "62ae83ad-4f6a-430b-af41-a9bede9286ca": "Gemma (en-GB Female)",
    "ef191366-f52f-447a-a398-ed8c0f2943a1": "Archie (en-GB Male)",
}
CARTESIA_MODELS = [
    "sonic-3.5",
    "sonic-3.5-2026-05-04",
    "sonic-3",
    "sonic-latest",
]

GTTS_LANGS = [
    "en", "en-uk", "en-au", "en-in", "en-us",
    "hi", "es", "es-es", "es-us", "fr", "de", "it", "pt", "pt-br",
    "ja", "ko", "zh-CN", "zh-TW", "ar", "ru", "tr", "pl", "nl",
    "sv", "da", "fi", "no", "cs", "el", "he", "id", "th", "vi",
    "uk", "ro", "hu", "bn", "ta", "te", "mr", "gu", "kn", "ml",
]


def build_providers() -> dict:
    gemini_labels = {k: f"{k} — {v}" for k, v in GEMINI_VOICE_LABELS.items()}
    # Highlight news-friendly Gemini voices in labels
    for news_name in ("Charon", "Rasalgethi", "Sadaltager", "Kore", "Orus", "Alnilam"):
        if news_name in gemini_labels:
            gemini_labels[news_name] = f"{gemini_labels[news_name]} · news"
    dg_labels = {mid: f"{name} ({mid})" for mid, name in DEEPGRAM_VOICES.items()}
    # Prefer English news-ish Deepgram voices at top of list
    dg_news_first = [
        "aura-2-thalia-en",
        "aura-2-athena-en",
        "aura-2-orion-en",
        "aura-2-zeus-en",
        "aura-2-arcas-en",
        "aura-2-apollo-en",
        "aura-2-andromeda-en",
        "aura-2-helena-en",
    ]
    dg_voices_ordered = dg_news_first + [
        m for m in DEEPGRAM_VOICES if m not in dg_news_first
    ]
    for mid in dg_news_first:
        if mid in dg_labels:
            dg_labels[mid] = f"{DEEPGRAM_VOICES[mid]} — news/broadcast ({mid})"

    return {
        "edge": {
            "name": "Edge TTS (Free · best no-key default)",
            "free": True,
            "requires_key": False,
            "setup_url": "https://github.com/rany2/edge-tts",
            "setup_cmd": "No API key — Microsoft Edge neural voices (news picks first)",
            "default_voice": "en-US-JennyNeural",
            "voices": EDGE_EN_VOICES,
            "voice_labels": EDGE_VOICE_LABELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Edge voice name e.g. en-US-AvaNeural…",
        },
        "fish": {
            "name": "Fish Audio (Free tier · expressive)",
            "free": True,
            "requires_key": True,
            "setup_url": "https://fish.audio/app/api-keys",
            "setup_cmd": (
                "fish.audio key — use s2.1-pro-free + news/narrator library voices"
            ),
            "default_voice": "a0cd220b3c834df8b97a865bacb79c79",
            "default_model": "s2.1-pro-free",
            "voices": list(FISH_VOICES.keys()),
            "voice_labels": FISH_VOICES,
            "models": FISH_MODELS,
            "model_labels": FISH_MODEL_LABELS,
            "custom_voice": True,
            "voice_paste_hint": "paste fish.audio/m/<id> URL or reference_id…",
        },
        "gemini": {
            "name": "Gemini TTS (Google · free tier)",
            "free": True,
            "requires_key": True,
            "setup_url": "https://aistudio.google.com/apikey",
            "setup_cmd": "AI Studio key — generateContent AUDIO (all TTS models + 30 voices)",
            "default_voice": "Charon",
            "default_model": GEMINI_TTS_MODELS[0],
            "voices": GEMINI_VOICES,
            "voice_labels": gemini_labels,
            "models": GEMINI_TTS_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Gemini voice name e.g. Kore / Charon…",
        },
        "gemini-live": {
            "name": "Gemini Live (Google · realtime)",
            "free": True,
            "requires_key": True,
            "live": True,
            "setup_url": "https://aistudio.google.com/apikey",
            "setup_cmd": "Same Gemini key — Live API WebSocket",
            "default_voice": "Charon",
            "default_model": GEMINI_LIVE_MODELS[0],
            "voices": GEMINI_VOICES,
            "voice_labels": gemini_labels,
            "models": GEMINI_LIVE_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Gemini voice name e.g. Kore / Charon…",
        },
        "groq": {
            "name": "Groq Orpheus TTS (Free tier · expressive)",
            "free": True,
            "requires_key": True,
            "setup_url": "https://console.groq.com/keys",
            "setup_cmd": "Orpheus English + Arabic — [emotion] tags; accept model terms",
            "default_voice": "troy",
            "default_model": "canopylabs/orpheus-v1-english",
            "voices": GROQ_EN_VOICES + GROQ_AR_VOICES,
            "voice_labels": {
                **{v: f"{v} (English · expressive)" for v in GROQ_EN_VOICES},
                **{v: f"{v} (Arabic Saudi)" for v in GROQ_AR_VOICES},
            },
            "models": GROQ_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Groq Orpheus voice name e.g. autumn…",
        },
        "gtts": {
            "name": "Google Translate TTS (Free)",
            "free": True,
            "requires_key": False,
            "setup_url": "https://pypi.org/project/gTTS/",
            "setup_cmd": "No key — gTTS languages from package",
            "default_voice": "en",
            "voices": GTTS_LANGS,
            "custom_voice": True,
            "voice_paste_hint": "paste language code e.g. en / hi / ja…",
        },
        "openai": {
            "name": "OpenAI TTS",
            "free": False,
            "requires_key": True,
            "setup_url": "https://platform.openai.com/api-keys",
            "setup_cmd": "All docs voices (marin/cedar best) + gpt-4o-mini-tts / tts-1-hd",
            "default_voice": "marin",
            "default_model": "gpt-4o-mini-tts",
            "voices": OPENAI_VOICES,
            "models": OPENAI_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste OpenAI voice name e.g. marin / cedar…",
        },
        "openai-live": {
            "name": "OpenAI Realtime (Live)",
            "free": False,
            "requires_key": True,
            "live": True,
            "setup_url": "https://platform.openai.com/api-keys",
            "setup_cmd": "Same OpenAI key — Realtime WebSocket speech (gpt-realtime)",
            "default_voice": "marin",
            "default_model": OPENAI_LIVE_MODELS[0],
            "voices": OPENAI_LIVE_VOICES,
            "models": OPENAI_LIVE_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste OpenAI Realtime voice e.g. marin…",
        },
        "elevenlabs": {
            "name": "ElevenLabs",
            "free": False,
            "requires_key": True,
            "setup_url": "https://elevenlabs.io/app/settings/api-keys",
            "setup_cmd": "All TTS models from docs (v3, multilingual v2, flash, turbo)",
            "default_voice": "21m00Tcm4TlvDq8ikWAM",
            "default_model": "eleven_multilingual_v2",
            "voices": list(ELEVEN_VOICES.keys()),
            "voice_labels": ELEVEN_VOICES,
            "models": ELEVEN_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste ElevenLabs voice id from voice library…",
        },
        "elevenlabs-live": {
            "name": "ElevenLabs Live (WebSocket)",
            "free": False,
            "requires_key": True,
            "live": True,
            "setup_url": "https://elevenlabs.io/app/settings/api-keys",
            "setup_cmd": "Same ElevenLabs key — stream-input WS (flash_v2_5 best)",
            "default_voice": "21m00Tcm4TlvDq8ikWAM",
            "default_model": ELEVEN_LIVE_MODELS[0],
            "voices": list(ELEVEN_VOICES.keys()),
            "voice_labels": ELEVEN_VOICES,
            "models": ELEVEN_LIVE_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste ElevenLabs voice id from voice library…",
        },
        "deepgram": {
            "name": "Deepgram Aura-2 ($200 free credit)",
            "free": True,
            "requires_key": True,
            "setup_url": "https://console.deepgram.com/",
            "setup_cmd": "Aura-2 voices — news picks first · free credit for new accounts",
            "default_voice": "aura-2-thalia-en",
            "voices": dg_voices_ordered,
            "voice_labels": dg_labels,
            "custom_voice": True,
            "voice_paste_hint": "paste Aura model e.g. aura-2-orion-en…",
        },
        "deepgram-live": {
            "name": "Deepgram Live (Speak WS)",
            "free": True,
            "requires_key": True,
            "live": True,
            "setup_url": "https://console.deepgram.com/",
            "setup_cmd": "Same Deepgram key — Speak WebSocket streaming",
            "default_voice": "aura-2-thalia-en",
            "voices": dg_voices_ordered,
            "voice_labels": dg_labels,
            "custom_voice": True,
            "voice_paste_hint": "paste Aura model e.g. aura-2-orion-en…",
        },
        "cartesia": {
            "name": "Cartesia Sonic",
            "free": False,
            "requires_key": True,
            "setup_url": "https://play.cartesia.ai/",
            "setup_cmd": "Sonic 3.5 / 3 / latest — featured agent voices from docs",
            "default_voice": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
            "default_model": "sonic-3.5",
            "voices": list(CARTESIA_VOICES.keys()),
            "voice_labels": CARTESIA_VOICES,
            "models": CARTESIA_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Cartesia voice UUID from play.cartesia.ai…",
        },
        "cartesia-live": {
            "name": "Cartesia Live (WebSocket)",
            "free": False,
            "requires_key": True,
            "live": True,
            "setup_url": "https://play.cartesia.ai/",
            "setup_cmd": "Same Cartesia key — realtime WS TTS (sonic-3.5)",
            "default_voice": "f786b574-daa5-4673-aa0c-cbe3e8534c02",
            "default_model": CARTESIA_LIVE_MODELS[0],
            "voices": list(CARTESIA_VOICES.keys()),
            "voice_labels": CARTESIA_VOICES,
            "models": CARTESIA_LIVE_MODELS,
            "custom_voice": True,
            "voice_paste_hint": "paste Cartesia voice UUID from play.cartesia.ai…",
        },
    }


VOICE_PROVIDERS = build_providers()


def normalize_voice_id(raw: str, provider: str = "") -> str:
    """Turn a pasted library URL or raw id into the provider voice id.

    Accepts fish.audio/m/<id>, ElevenLabs/Cartesia URLs, UUIDs, or plain ids.
    """
    text = (raw or "").strip().strip("\"'")
    if not text:
        return ""
    # Fish Audio library page
    m = re.search(r"fish\.audio/m/([a-f0-9]+)", text, re.I)
    if m:
        return m.group(1)
    # Explicit query params
    m = re.search(
        r"(?:voice[_-]?id|reference[_-]?id|model[_-]?id)=([A-Za-z0-9_-]+)",
        text,
        re.I,
    )
    if m:
        return m.group(1)
    # Cartesia-style UUID anywhere in the paste
    m = re.search(
        r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
        text,
        re.I,
    )
    if m and (not provider or provider.startswith("cartesia") or "cartesia" in text.lower()):
        return m.group(1)
    # Generic URL → last path segment
    if "://" in text or text.startswith("www."):
        path = text.split("?", 1)[0].rstrip("/")
        seg = path.rsplit("/", 1)[-1]
        if seg and seg not in {"m", "voice", "voices", "app", "models"}:
            return seg
    return text


def voice_paste_placeholder(provider: str) -> str:
    info = VOICE_PROVIDERS.get(provider, {})
    return info.get(
        "voice_paste_hint",
        "paste voice id or library URL from the provider site…",
    )
