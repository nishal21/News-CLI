"""Voice / TTS setup modal."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from worldnews.tts import (
    VOICE_PROVIDERS,
    normalize_voice_id,
    voice_cfg,
    voice_paste_placeholder,
)


class VoiceSetupScreen(ModalScreen[dict | None]):
    """Configure TTS provider, voice, rate, and API keys."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    RATES = ["-25%", "-10%", "+0%", "+10%", "+25%", "+50%"]

    def __init__(self) -> None:
        super().__init__()
        self._pending_provider = voice_cfg.get_provider()
        self._pending_voice = voice_cfg.get_voice()
        self._pending_rate = voice_cfg.get_rate()
        self._pending_model = voice_cfg.get_model(self._pending_provider)
        self._voice_id_map: dict[str, str] = {}
        self._voice_model_id_map: dict[str, str] = {}
        self._saved = False

    def compose(self) -> ComposeResult:
        with Vertical(id="voice-setup-box"):
            yield Label("Voice / TTS setup", classes="modal-title")
            yield Static(self._status(), id="voice-setup-status")
            with VerticalScroll(id="voice-setup-scroll"):
                yield Label("1. Provider  (Edge free · Fish / Gemini with key)")
                yield OptionList(*self._provider_options(), id="voice-prov-list")
                yield Label("2. Model")
                yield OptionList(*self._model_options(), id="voice-model-list")
                yield Label("3. Voice  (pick list or paste id/URL from site)")
                yield OptionList(*self._voice_options(), id="voice-list")
                yield Static(self._paste_hint(), id="voice-paste-hint")
                yield Input(
                    placeholder=voice_paste_placeholder(self._pending_provider),
                    id="voice-id-input",
                    value=self._paste_field_value(),
                )
                with Horizontal(classes="settings-row"):
                    yield Button("Use pasted ID", id="voice-btn-use-id")
                yield Label("4. Speed")
                yield OptionList(
                    *[
                        Option(
                            f"{'›' if r == self._pending_rate else ' '} {r}",
                            id=f"rate-{i}",
                        )
                        for i, r in enumerate(self.RATES)
                    ],
                    id="voice-rate-list",
                )
                yield Label("5. API key (Fish / Gemini / ElevenLabs / …)")
                yield Static(self._key_hint(), id="voice-key-hint")
                yield Input(
                    placeholder="paste API key…",
                    password=True,
                    id="voice-key-input",
                    value=voice_cfg.get_api_key(self._pending_provider) or "",
                )
            with Horizontal(id="voice-setup-footer"):
                yield Button("Save key", id="voice-btn-save")
                yield Button("Clear key", id="voice-btn-clear")
                yield Button("Apply", variant="primary", id="voice-btn-apply")
                yield Button("Test", id="voice-btn-test")
                yield Button("Close", id="voice-btn-close")

    def _paste_hint(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        url = info.get("setup_url", "")
        return (
            f"Custom voice for [b]{info.get('name', self._pending_provider)}[/] — "
            f"paste id or library URL, then Use pasted ID\n{url}"
        )

    def _paste_field_value(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        voices = info.get("voices", [])
        v = self._pending_voice or ""
        if v and v not in voices:
            return v
        return ""

    def _status(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        labels = info.get("voice_labels", {})
        vlabel = labels.get(self._pending_voice, self._pending_voice)
        model = self._pending_model or ""
        return (
            f"Active: {voice_cfg.get_status()}\n"
            f"Editing: [b]{info.get('name', self._pending_provider)}[/] · "
            f"{vlabel} · {model} · rate {self._pending_rate}"
        )

    def _key_hint(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        if not info.get("requires_key"):
            return f"{info.get('name', '')} — no API key · {info.get('setup_cmd', '')}"
        has = bool(voice_cfg.get_api_key(self._pending_provider))
        return (
            f"{'Key saved ✓' if has else '⚠ Key required'} · {info.get('setup_cmd', '')}\n"
            f"{info.get('setup_url', '')}"
        )

    def _provider_options(self) -> list[Option]:
        opts = []
        for pk, pv in VOICE_PROVIDERS.items():
            free = "free" if pv.get("free") else "paid"
            key_ok = (
                "key·ok"
                if (voice_cfg.get_api_key(pk) or not pv.get("requires_key"))
                else "needs·key"
            )
            live = " live" if pv.get("live") else ""
            mark = "›" if pk == self._pending_provider else " "
            opts.append(
                Option(
                    f"{mark} {pv['name']}  [{free}{live}] [{key_ok}]",
                    id=f"vp-{pk}",
                )
            )
        return opts

    def _model_options(self) -> list[Option]:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        models = info.get("models", [])
        labels = info.get("model_labels", {})
        self._voice_model_id_map = {}
        opts = []
        for i, m in enumerate(models):
            oid = f"vm-{i}"
            self._voice_model_id_map[oid] = m
            mark = "›" if m == self._pending_model else " "
            opts.append(Option(f"{mark} {labels.get(m, m)}", id=oid))
        if not opts:
            opts.append(Option("(n/a for this provider)", id="vm-none", disabled=True))
        return opts

    def _voice_options(self) -> list[Option]:
        info = VOICE_PROVIDERS.get(self._pending_provider, {})
        voices = list(info.get("voices", []))
        labels = dict(info.get("voice_labels", {}))
        self._voice_id_map = {}
        opts = []
        if self._pending_voice and self._pending_voice not in voices:
            self._voice_id_map["vv-custom"] = self._pending_voice
            opts.append(Option(f"› Custom · {self._pending_voice}", id="vv-custom"))
        for i, v in enumerate(voices):
            oid = f"vv-{i}"
            self._voice_id_map[oid] = v
            label = labels.get(v, v)
            mark = "›" if v == self._pending_voice else " "
            opts.append(Option(f"{mark} {label}", id=oid))
        if not opts:
            opts.append(Option("(no voices)", id="vv-none", disabled=True))
        return opts

    def _apply_pasted_voice(self) -> bool:
        try:
            raw = self.query_one("#voice-id-input", Input).value
        except Exception:
            return False
        vid = normalize_voice_id(raw, self._pending_provider)
        if not vid:
            return False
        self._pending_voice = vid
        return True

    def _refresh(self) -> None:
        try:
            pl = self.query_one("#voice-prov-list", OptionList)
            pl.clear_options()
            pl.add_options(self._provider_options())
            try:
                ml = self.query_one("#voice-model-list", OptionList)
                ml.clear_options()
                ml.add_options(self._model_options())
            except Exception:
                pass
            vl = self.query_one("#voice-list", OptionList)
            vl.clear_options()
            vl.add_options(self._voice_options())
            rl = self.query_one("#voice-rate-list", OptionList)
            rl.clear_options()
            rl.add_options(
                [
                    Option(
                        f"{'›' if r == self._pending_rate else ' '} {r}",
                        id=f"rate-{i}",
                    )
                    for i, r in enumerate(self.RATES)
                ]
            )
            self.query_one("#voice-key-hint", Static).update(self._key_hint())
            self.query_one("#voice-paste-hint", Static).update(self._paste_hint())
            paste = self.query_one("#voice-id-input", Input)
            paste.placeholder = voice_paste_placeholder(self._pending_provider)
            paste.value = self._paste_field_value()
            self.query_one("#voice-key-input", Input).value = (
                voice_cfg.get_api_key(self._pending_provider) or ""
            )
            self.query_one("#voice-setup-status", Static).update(self._status())
        except Exception:
            pass

    def _pick_provider(self, pk: str) -> None:
        if pk not in VOICE_PROVIDERS:
            return
        self._pending_provider = pk
        self._pending_voice = (
            voice_cfg.config.get("providers", {}).get(pk, {}).get("voice")
            or VOICE_PROVIDERS[pk]["default_voice"]
        )
        self._pending_model = (
            voice_cfg.config.get("providers", {}).get(pk, {}).get("model")
            or VOICE_PROVIDERS[pk].get("default_model", "")
        )
        self._refresh()

    @on(OptionList.OptionSelected, "#voice-prov-list")
    def on_prov(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self._pick_provider(str(event.option_id).removeprefix("vp-"))

    @on(OptionList.OptionHighlighted, "#voice-prov-list")
    def on_prov_hi(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id:
            self._pick_provider(str(event.option_id).removeprefix("vp-"))

    @on(OptionList.OptionSelected, "#voice-model-list")
    def on_vmodel(self, event: OptionList.OptionSelected) -> None:
        mid = self._voice_model_id_map.get(str(event.option_id or ""))
        if mid:
            self._pending_model = mid
            self._refresh()

    @on(OptionList.OptionSelected, "#voice-list")
    def on_voice(self, event: OptionList.OptionSelected) -> None:
        vid = self._voice_id_map.get(str(event.option_id or ""))
        if vid:
            self._pending_voice = vid
            self._refresh()

    @on(OptionList.OptionSelected, "#voice-rate-list")
    def on_rate(self, event: OptionList.OptionSelected) -> None:
        oid = str(event.option_id or "")
        if oid.startswith("rate-"):
            try:
                idx = int(oid.removeprefix("rate-"))
                self._pending_rate = self.RATES[idx]
                self._refresh()
            except (ValueError, IndexError):
                pass

    @on(Input.Submitted, "#voice-id-input")
    def on_voice_id_submit(self, _event: Input.Submitted) -> None:
        if self._apply_pasted_voice():
            self._refresh()
            try:
                self.app.notify(
                    f"Custom voice → {self._pending_voice}",
                    severity="information",
                )
            except Exception:
                pass

    @on(Button.Pressed)
    def on_btn(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "voice-btn-close":
            self.dismiss({"saved": self._saved} if self._saved else None)
        elif bid == "voice-btn-use-id":
            if self._apply_pasted_voice():
                self._refresh()
                try:
                    self.app.notify(
                        f"Custom voice → {self._pending_voice}",
                        severity="information",
                    )
                except Exception:
                    pass
            else:
                try:
                    self.app.notify(
                        "Paste a voice id or library URL first",
                        severity="warning",
                    )
                except Exception:
                    pass
        elif bid == "voice-btn-save":
            key = self.query_one("#voice-key-input", Input).value.strip()
            voice_cfg.set_api_key(self._pending_provider, key)
            self._saved = True
            self._refresh()
            try:
                self.app.notify("Voice API key saved", severity="information")
            except Exception:
                pass
        elif bid == "voice-btn-clear":
            voice_cfg.set_api_key(self._pending_provider, "")
            self.query_one("#voice-key-input", Input).value = ""
            self._saved = True
            self._refresh()
        elif bid == "voice-btn-apply":
            self._apply_pasted_voice()
            key = self.query_one("#voice-key-input", Input).value.strip()
            if key:
                voice_cfg.set_api_key(self._pending_provider, key)
            info = VOICE_PROVIDERS.get(self._pending_provider, {})
            if info.get("requires_key") and not voice_cfg.get_api_key(
                self._pending_provider
            ):
                try:
                    self.app.notify(
                        "Paste an API key and press Save key first",
                        severity="warning",
                    )
                except Exception:
                    pass
                return
            voice_cfg.set_provider(self._pending_provider, self._pending_voice)
            if self._pending_model:
                voice_cfg.set_model(self._pending_model, self._pending_provider)
            voice_cfg.set_rate(self._pending_rate)
            self._saved = True
            self._refresh()
            try:
                self.app.notify(
                    f"Voice → {self._pending_provider} / {self._pending_voice}",
                    severity="information",
                )
            except Exception:
                pass
            self.dismiss(
                {
                    "saved": True,
                    "provider": self._pending_provider,
                    "voice": self._pending_voice,
                    "model": self._pending_model,
                }
            )
        elif bid == "voice-btn-test":
            self._apply_pasted_voice()
            voice_cfg.set_provider(self._pending_provider, self._pending_voice)
            if self._pending_model:
                voice_cfg.set_model(self._pending_model, self._pending_provider)
            voice_cfg.set_rate(self._pending_rate)
            key = self.query_one("#voice-key-input", Input).value.strip()
            if key:
                voice_cfg.set_api_key(self._pending_provider, key)
            self._saved = True
            try:
                self.app.action_speak_test()
            except Exception:
                try:
                    self.app.notify("Open Speak (t) after Apply", severity="information")
                except Exception:
                    pass
