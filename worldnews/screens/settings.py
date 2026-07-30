"""Tabbed settings: App · AI · Voice."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from worldnews.ai import PROVIDERS, ai
from worldnews.screens.feeds import ManageFeedsScreen
from worldnews.themes import THEMES
from worldnews.tts import (
    VOICE_PROVIDERS,
    normalize_voice_id,
    voice_cfg,
    voice_paste_placeholder,
)


class SettingsScreen(ModalScreen[dict | None]):
    """Tabbed settings: App · AI · Voice — pickers that actually work."""

    BINDINGS = [
        ("escape", "dismiss_settings", "Close"),
        ("q", "dismiss_settings", "Close"),
    ]

    VOICE_RATES = ["-25%", "-10%", "+0%", "+10%", "+25%", "+50%"]

    def __init__(self, settings) -> None:
        super().__init__()
        self.settings = settings
        self._pending_provider = ai.get_provider()
        self._pending_model = ai.get_model()
        self._pending_voice_provider = voice_cfg.get_provider()
        self._pending_voice = voice_cfg.get_voice()
        self._pending_rate = voice_cfg.get_rate()
        self._pending_voice_model = voice_cfg.get_model(
            self._pending_voice_provider
        )
        self._changed: dict = {}
        self._model_id_map: dict[str, str] = {}
        self._voice_id_map: dict[str, str] = {}
        self._voice_model_id_map: dict[str, str] = {}
        self._updating = False
        self._preview_provider: str | None = None
        self._preview_voice_provider: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Label("Settings", classes="modal-title")
            yield Static(self._status_text(), id="settings-status")
            with TabbedContent(id="settings-tabs"):
                with TabPane("App", id="tab-app"):
                    with VerticalScroll(classes="tab-scroll"):
                        yield Label("Theme  · Enter or click to save")
                        yield OptionList(*self._theme_options(), id="theme-list")
                        with Horizontal(classes="settings-row"):
                            yield Button(
                                f"Density: {self.settings.density}",
                                id="btn-density",
                            )
                            yield Button(
                                f"Images: {'on' if self.settings.auto_images else 'off'}",
                                id="btn-images",
                            )
                            yield Button("My websites", id="btn-feeds")
                        yield Static(
                            "Themes preview as you move · Enter saves.\n"
                            "My websites = add any news site (any language).",
                            classes="settings-hint",
                        )

                with TabPane("AI", id="tab-ai"):
                    with VerticalScroll(classes="tab-scroll"):
                        yield Static(self._ai_status(), id="ai-active")
                        yield Label("1. Provider  · click / Enter to select")
                        yield OptionList(
                            *self._provider_options(), id="provider-list"
                        )
                        yield Label("2. Model")
                        yield OptionList(
                            *self._model_options(self._pending_provider),
                            id="model-list",
                        )
                        yield Label("3. API key")
                        yield Static(
                            self._key_hint(self._pending_provider), id="key-hint"
                        )
                        yield Input(
                            placeholder="paste API key…",
                            password=True,
                            id="api-key-input",
                            value=ai.get_api_key(self._pending_provider) or "",
                        )
                        with Horizontal(classes="settings-row"):
                            yield Button("Save key", id="btn-save-key")
                            yield Button("Clear key", id="btn-clear-key")
                            yield Button(
                                "Apply AI", variant="primary", id="btn-apply-ai"
                            )

                with TabPane("Voice", id="tab-voice"):
                    with VerticalScroll(classes="tab-scroll"):
                        yield Static(self._voice_status(), id="voice-active")
                        yield Label("1. Provider  · Edge free · Gemini TTS/Live best")
                        yield OptionList(
                            *self._voice_provider_options(), id="voice-prov-list"
                        )
                        yield Label("2. Model  (Gemini / OpenAI)")
                        yield OptionList(
                            *self._voice_model_options(), id="voice-model-list"
                        )
                        yield Label("3. Voice  (pick list or paste id/URL from site)")
                        yield OptionList(*self._voice_options(), id="voice-list")
                        yield Static(
                            self._voice_paste_hint(), id="voice-paste-hint"
                        )
                        yield Input(
                            placeholder=voice_paste_placeholder(
                                self._pending_voice_provider
                            ),
                            id="voice-id-input",
                            value=self._voice_paste_field_value(),
                        )
                        with Horizontal(classes="settings-row"):
                            yield Button(
                                "Use pasted ID", id="btn-voice-use-id"
                            )
                        yield Label("4. Speed")
                        yield OptionList(
                            *self._rate_options(), id="voice-rate-list"
                        )
                        yield Label(
                            "5. API key (Fish / Gemini / ElevenLabs / …)"
                        )
                        yield Static(
                            self._voice_key_hint(), id="voice-key-hint"
                        )
                        yield Input(
                            placeholder="paste voice API key…",
                            password=True,
                            id="voice-key-input",
                            value=voice_cfg.get_api_key(
                                self._pending_voice_provider
                            )
                            or "",
                        )
                        with Horizontal(classes="settings-row"):
                            yield Button("Save key", id="btn-voice-save")
                            yield Button(
                                "Apply voice",
                                variant="primary",
                                id="btn-apply-voice",
                            )
                            yield Button("Test", id="btn-voice-test")

            with Horizontal(id="settings-footer"):
                yield Button("Done", variant="success", id="btn-done")

    def on_mount(self) -> None:
        try:
            self.query_one("#settings-tabs", TabbedContent).active = "tab-ai"
        except Exception:
            pass

    def action_dismiss_settings(self) -> None:
        self.dismiss(self._changed or None)

    def _on_manage_from_settings(self, result: dict | None) -> None:
        self._changed["feeds"] = True
        try:
            sidebar = self.app.query_one("#sidebar")
            if hasattr(sidebar, "refresh_custom_label"):
                sidebar.refresh_custom_label()
        except Exception:
            pass
        if result and result.get("open"):
            self.dismiss({"feeds": True, "open_custom": True})

    def _status_text(self) -> str:
        return (
            f"Theme [b]{self.settings.theme}[/] · "
            f"Density [b]{self.settings.density}[/] · "
            f"Images [b]{'on' if self.settings.auto_images else 'off'}[/]\n"
            f"AI [b]{ai.get_provider()}[/] / {ai.get_model()} · "
            f"Voice [b]{voice_cfg.get_provider()}[/]"
        )

    def _ai_status(self) -> str:
        info = ai.get_provider_info()
        pend = PROVIDERS.get(self._pending_provider, {})
        return (
            f"Active: [b]{info['name']}[/] · {info['model']}\n"
            f"Selected: [b]{pend.get('name', self._pending_provider)}[/] · "
            f"{self._pending_model}"
        )

    def _voice_status(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        labels = info.get("voice_labels", {})
        v = labels.get(self._pending_voice, self._pending_voice)
        model = self._pending_voice_model or ""
        model_bit = f" · {model}" if model else ""
        return (
            f"Active: {voice_cfg.get_status()}\n"
            f"Selected: [b]{info.get('name', self._pending_voice_provider)}[/] · "
            f"{v}{model_bit} · {self._pending_rate}"
        )

    def _theme_options(self) -> list[Option]:
        current = self.settings.theme
        return [
            Option(
                f"{'› ' if name == current else '  '}{name}",
                id=f"theme-{name}",
            )
            for name in THEMES
        ]

    def _provider_options(self) -> list[Option]:
        opts = []
        for pk, pv in PROVIDERS.items():
            free = "free" if pv.get("free") else "paid"
            key_ok = (
                "ok"
                if (ai.get_api_key(pk) or not pv.get("requires_key"))
                else "needs·key"
            )
            mark = "›" if pk == self._pending_provider else " "
            opts.append(
                Option(
                    f"{mark} {pv['name']}  [{free}] [{key_ok}]",
                    id=f"prov-{pk}",
                )
            )
        return opts

    def _model_options(self, provider: str) -> list[Option]:
        models = PROVIDERS.get(provider, {}).get("models", [])
        current = self._pending_model
        opts = []
        self._model_id_map = {}
        for i, m in enumerate(models):
            oid = f"mdl-{i}"
            self._model_id_map[oid] = m
            mark = "›" if m == current else " "
            opts.append(Option(f"{mark} {m}", id=oid))
        if not opts:
            opts.append(Option("(no models listed)", id="mdl-none", disabled=True))
        return opts

    def _key_hint(self, provider: str) -> str:
        info = PROVIDERS.get(provider, {})
        if not info.get("requires_key"):
            return f"{info.get('name', provider)} — no API key required"
        has = bool(ai.get_api_key(provider))
        return (
            f"{'Key saved ✓' if has else '⚠ Key needed'} · "
            f"{info.get('setup_cmd', '')}\n{info.get('setup_url', '')}"
        )

    def _voice_provider_options(self) -> list[Option]:
        opts = []
        for pk, pv in VOICE_PROVIDERS.items():
            free = "free" if pv.get("free") else "paid"
            key_ok = (
                "ok"
                if (voice_cfg.get_api_key(pk) or not pv.get("requires_key"))
                else "needs·key"
            )
            live = " live" if pv.get("live") else ""
            mark = "›" if pk == self._pending_voice_provider else " "
            opts.append(
                Option(
                    f"{mark} {pv['name']}  [{free}{live}] [{key_ok}]",
                    id=f"vp-{pk}",
                )
            )
        return opts

    def _voice_options(self) -> list[Option]:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        voices = list(info.get("voices", []))
        labels = dict(info.get("voice_labels", {}))
        self._voice_id_map = {}
        opts = []
        if self._pending_voice and self._pending_voice not in voices:
            self._voice_id_map["vv-custom"] = self._pending_voice
            opts.append(
                Option(f"› Custom · {self._pending_voice}", id="vv-custom")
            )
        for i, v in enumerate(voices):
            oid = f"vv-{i}"
            self._voice_id_map[oid] = v
            mark = "›" if v == self._pending_voice else " "
            opts.append(Option(f"{mark} {labels.get(v, v)}", id=oid))
        if not opts:
            opts.append(Option("(no voices)", id="vv-none", disabled=True))
        return opts

    def _voice_paste_hint(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        return (
            f"Custom voice — paste id or library URL for "
            f"[b]{info.get('name', self._pending_voice_provider)}[/]\n"
            f"{info.get('setup_url', '')}"
        )

    def _voice_paste_field_value(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        voices = info.get("voices", [])
        v = self._pending_voice or ""
        if v and v not in voices:
            return v
        return ""

    def _apply_pasted_voice(self) -> bool:
        try:
            raw = self.query_one("#voice-id-input", Input).value
        except Exception:
            return False
        vid = normalize_voice_id(raw, self._pending_voice_provider)
        if not vid:
            return False
        self._pending_voice = vid
        return True

    def _voice_model_options(self) -> list[Option]:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        models = info.get("models", [])
        labels = info.get("model_labels", {})
        self._voice_model_id_map = {}
        opts = []
        for i, m in enumerate(models):
            oid = f"vm-{i}"
            self._voice_model_id_map[oid] = m
            mark = "›" if m == self._pending_voice_model else " "
            opts.append(Option(f"{mark} {labels.get(m, m)}", id=oid))
        if not opts:
            opts.append(
                Option("(no model picker for this provider)", id="vm-none", disabled=True)
            )
        return opts

    def _rate_options(self) -> list[Option]:
        return [
            Option(
                f"{'›' if r == self._pending_rate else ' '} {r}",
                id=f"rate-{i}",
            )
            for i, r in enumerate(self.VOICE_RATES)
        ]

    def _voice_key_hint(self) -> str:
        info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
        if not info.get("requires_key"):
            return f"{info.get('name', '')} — no API key · {info.get('setup_cmd', '')}"
        has = bool(voice_cfg.get_api_key(self._pending_voice_provider))
        return (
            f"{'Key saved ✓' if has else '⚠ Key required'} · "
            f"{info.get('setup_cmd', '')}\n{info.get('setup_url', '')}"
        )

    def _apply_theme(self, name: str, *, persist: bool = True) -> None:
        if name not in THEMES:
            return
        if persist:
            self.settings.set_theme(name)
            self._changed["theme"] = name
        try:
            from worldnews.themes import register_themes

            register_themes(self.app)
            self.app.theme = name
            self.app.refresh_css(animate=False)
        except Exception:
            pass
        try:
            live = name if not persist else self.settings.theme
            self.query_one("#settings-status", Static).update(
                f"Theme [b]{live}[/] · "
                f"Density [b]{self.settings.density}[/] · "
                f"Images [b]{'on' if self.settings.auto_images else 'off'}[/]\n"
                f"AI [b]{ai.get_provider()}[/] / {ai.get_model()} · "
                f"Voice [b]{voice_cfg.get_provider()}[/]"
                + ("" if persist else "  [dim](preview — Enter to save)[/]")
            )
        except Exception:
            pass
        if persist:
            try:
                self._updating = True
                tl = self.query_one("#theme-list", OptionList)
                tl.clear_options()
                tl.add_options(self._theme_options())
                self.app.notify(f"Theme saved: {name}", severity="information")
            except Exception:
                pass
            finally:
                self._updating = False

    def _refresh_ai_panel(self, *, rebuild_providers: bool = False) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            if rebuild_providers:
                pl = self.query_one("#provider-list", OptionList)
                pl.clear_options()
                pl.add_options(self._provider_options())
            ml = self.query_one("#model-list", OptionList)
            ml.clear_options()
            ml.add_options(self._model_options(self._pending_provider))
            self.query_one("#key-hint", Static).update(
                self._key_hint(self._pending_provider)
            )
            self.query_one("#api-key-input", Input).value = (
                ai.get_api_key(self._pending_provider) or ""
            )
            self.query_one("#ai-active", Static).update(self._ai_status())
            self.query_one("#settings-status", Static).update(self._status_text())
        except Exception:
            pass
        finally:
            self._updating = False

    def _select_provider(self, pk: str) -> None:
        if pk not in PROVIDERS:
            return
        self._pending_provider = pk
        self._pending_model = (
            ai.config.get("providers", {}).get(pk, {}).get("model")
            or PROVIDERS[pk]["default_model"]
        )
        self._refresh_ai_panel(rebuild_providers=False)

    def _pick_voice_provider(self, pk: str) -> None:
        if pk not in VOICE_PROVIDERS:
            return
        self._pending_voice_provider = pk
        self._pending_voice = (
            voice_cfg.config.get("providers", {}).get(pk, {}).get("voice")
            or VOICE_PROVIDERS[pk]["default_voice"]
        )
        self._pending_voice_model = (
            voice_cfg.config.get("providers", {}).get(pk, {}).get("model")
            or VOICE_PROVIDERS[pk].get("default_model", "")
        )
        self._refresh_voice_panel(rebuild_providers=False)

    def _refresh_voice_panel(self, *, rebuild_providers: bool = False) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            if rebuild_providers:
                pl = self.query_one("#voice-prov-list", OptionList)
                pl.clear_options()
                pl.add_options(self._voice_provider_options())
            try:
                ml = self.query_one("#voice-model-list", OptionList)
                ml.clear_options()
                ml.add_options(self._voice_model_options())
            except Exception:
                pass
            vl = self.query_one("#voice-list", OptionList)
            vl.clear_options()
            vl.add_options(self._voice_options())
            rl = self.query_one("#voice-rate-list", OptionList)
            rl.clear_options()
            rl.add_options(self._rate_options())
            self.query_one("#voice-key-hint", Static).update(self._voice_key_hint())
            self.query_one("#voice-key-input", Input).value = (
                voice_cfg.get_api_key(self._pending_voice_provider) or ""
            )
            try:
                self.query_one("#voice-paste-hint", Static).update(
                    self._voice_paste_hint()
                )
                paste = self.query_one("#voice-id-input", Input)
                paste.placeholder = voice_paste_placeholder(
                    self._pending_voice_provider
                )
                paste.value = self._voice_paste_field_value()
            except Exception:
                pass
            self.query_one("#voice-active", Static).update(self._voice_status())
            self.query_one("#settings-status", Static).update(self._status_text())
        except Exception:
            pass
        finally:
            self._updating = False

    # ── Theme ─────────────────────────────────────────────────────

    @on(OptionList.OptionHighlighted, "#theme-list")
    def theme_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._updating or not event.option_id:
            return
        self._apply_theme(str(event.option_id).removeprefix("theme-"), persist=False)

    @on(OptionList.OptionSelected, "#theme-list")
    def theme_picked(self, event: OptionList.OptionSelected) -> None:
        if not event.option_id:
            return
        self._apply_theme(str(event.option_id).removeprefix("theme-"), persist=True)

    # ── AI pickers ────────────────────────────────────────────────

    @on(OptionList.OptionHighlighted, "#provider-list")
    def provider_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Preview models while browsing — Enter commits."""
        if self._updating or not event.option_id:
            return
        pk = str(event.option_id).removeprefix("prov-")
        if pk not in PROVIDERS:
            return
        self._preview_provider = pk
        preview = (
            ai.config.get("providers", {}).get(pk, {}).get("model")
            or PROVIDERS[pk]["default_model"]
        )
        self._updating = True
        try:
            ml = self.query_one("#model-list", OptionList)
            # Build options for highlighted provider without committing pending
            old_p, old_m = self._pending_provider, self._pending_model
            self._pending_provider, self._pending_model = pk, preview
            ml.clear_options()
            ml.add_options(self._model_options(pk))
            self.query_one("#key-hint", Static).update(self._key_hint(pk))
            self.query_one("#api-key-input", Input).value = ai.get_api_key(pk) or ""
            info = ai.get_provider_info()
            self.query_one("#ai-active", Static).update(
                f"Active: [b]{info['name']}[/] · {info['model']}\n"
                f"Highlight: [b]{PROVIDERS[pk]['name']}[/] · {preview}  "
                f"[dim](Enter to select · then Apply AI)[/]"
            )
            self._pending_provider, self._pending_model = old_p, old_m
        except Exception:
            pass
        finally:
            self._updating = False

    @on(OptionList.OptionSelected, "#provider-list")
    def provider_picked(self, event: OptionList.OptionSelected) -> None:
        if self._updating or not event.option_id:
            return
        pk = str(event.option_id).removeprefix("prov-")
        self._select_provider(pk)
        self._preview_provider = None
        self._refresh_ai_panel(rebuild_providers=True)
        try:
            self.app.notify(
                f"Provider selected: {PROVIDERS.get(pk, {}).get('name', pk)}",
                severity="information",
            )
        except Exception:
            pass

    @on(OptionList.OptionSelected, "#model-list")
    def model_picked(self, event: OptionList.OptionSelected) -> None:
        if self._updating or not event.option_id:
            return
        mid = self._model_id_map.get(str(event.option_id))
        if mid:
            if self._preview_provider and self._preview_provider in PROVIDERS:
                self._pending_provider = self._preview_provider
                self._preview_provider = None
            self._pending_model = mid
            self._refresh_ai_panel(rebuild_providers=True)
            try:
                self.app.notify(
                    f"Selected: {self._pending_provider} / {mid}",
                    severity="information",
                )
            except Exception:
                pass

    # ── Voice pickers ─────────────────────────────────────────────

    @on(OptionList.OptionHighlighted, "#voice-prov-list")
    def voice_prov_hi(self, event: OptionList.OptionHighlighted) -> None:
        if self._updating or not event.option_id:
            return
        pk = str(event.option_id).removeprefix("vp-")
        if pk not in VOICE_PROVIDERS:
            return
        preview = (
            voice_cfg.config.get("providers", {}).get(pk, {}).get("voice")
            or VOICE_PROVIDERS[pk]["default_voice"]
        )
        self._updating = True
        try:
            old_p, old_v = self._pending_voice_provider, self._pending_voice
            self._pending_voice_provider, self._pending_voice = pk, preview
            vl = self.query_one("#voice-list", OptionList)
            vl.clear_options()
            vl.add_options(self._voice_options())
            self.query_one("#voice-key-hint", Static).update(self._voice_key_hint())
            self.query_one("#voice-key-input", Input).value = (
                voice_cfg.get_api_key(pk) or ""
            )
            labels = VOICE_PROVIDERS[pk].get("voice_labels", {})
            self.query_one("#voice-active", Static).update(
                f"Active: {voice_cfg.get_status()}\n"
                f"Highlight: [b]{VOICE_PROVIDERS[pk]['name']}[/] · "
                f"{labels.get(preview, preview)}  [dim](Enter to select)[/]"
            )
            self._pending_voice_provider, self._pending_voice = old_p, old_v
        except Exception:
            pass
        finally:
            self._updating = False

    @on(OptionList.OptionSelected, "#voice-prov-list")
    def voice_prov_sel(self, event: OptionList.OptionSelected) -> None:
        if self._updating or not event.option_id:
            return
        self._pick_voice_provider(str(event.option_id).removeprefix("vp-"))
        self._refresh_voice_panel(rebuild_providers=True)

    @on(OptionList.OptionSelected, "#voice-model-list")
    def voice_model_sel(self, event: OptionList.OptionSelected) -> None:
        if self._updating or not event.option_id:
            return
        mid = self._voice_model_id_map.get(str(event.option_id))
        if mid:
            self._pending_voice_model = mid
            self._refresh_voice_panel(rebuild_providers=False)
            try:
                self.app.notify(f"Voice model: {mid}", severity="information")
            except Exception:
                pass

    @on(OptionList.OptionSelected, "#voice-list")
    def voice_sel(self, event: OptionList.OptionSelected) -> None:
        if self._updating or not event.option_id:
            return
        vid = self._voice_id_map.get(str(event.option_id))
        if vid:
            self._pending_voice = vid
            self._refresh_voice_panel(rebuild_providers=False)

    @on(OptionList.OptionSelected, "#voice-rate-list")
    def rate_sel(self, event: OptionList.OptionSelected) -> None:
        oid = str(event.option_id or "")
        if oid.startswith("rate-"):
            try:
                self._pending_rate = self.VOICE_RATES[int(oid.removeprefix("rate-"))]
                self._refresh_voice_panel(rebuild_providers=False)
            except (ValueError, IndexError):
                pass

    @on(Input.Submitted, "#voice-id-input")
    def voice_id_submit(self, _event: Input.Submitted) -> None:
        if self._apply_pasted_voice():
            self._refresh_voice_panel(rebuild_providers=False)
            try:
                self.app.notify(
                    f"Custom voice → {self._pending_voice}",
                    severity="information",
                )
            except Exception:
                pass

    # ── Buttons ───────────────────────────────────────────────────

    @on(Button.Pressed)
    def buttons(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn-done":
            self.dismiss(self._changed or None)
        elif bid == "btn-density":
            new = "compact" if self.settings.density == "normal" else "normal"
            self.settings.set_density(new)
            self._changed["density"] = new
            event.button.label = f"Density: {new}"
            self.query_one("#settings-status", Static).update(self._status_text())
        elif bid == "btn-images":
            self.settings.toggle_auto_images()
            self._changed["images"] = self.settings.auto_images
            event.button.label = (
                f"Images: {'on' if self.settings.auto_images else 'off'}"
            )
            self.query_one("#settings-status", Static).update(self._status_text())
        elif bid == "btn-feeds":
            feeds = getattr(self.app, "custom_feeds", None)
            if feeds is not None:
                self.app.push_screen(
                    ManageFeedsScreen(feeds), self._on_manage_from_settings
                )
        elif bid == "btn-save-key":
            key = self.query_one("#api-key-input", Input).value.strip()
            ai.set_api_key(self._pending_provider, key)
            self._changed["ai"] = True
            self._refresh_ai_panel(rebuild_providers=True)
            self.app.notify("AI API key saved", severity="information")
        elif bid == "btn-clear-key":
            ai.set_api_key(self._pending_provider, "")
            self.query_one("#api-key-input", Input).value = ""
            self._changed["ai"] = True
            self._refresh_ai_panel(rebuild_providers=True)
        elif bid == "btn-apply-ai":
            key = self.query_one("#api-key-input", Input).value.strip()
            if key:
                ai.set_api_key(self._pending_provider, key)
            info = PROVIDERS.get(self._pending_provider, {})
            if info.get("requires_key") and not ai.get_api_key(self._pending_provider):
                self.app.notify(
                    "This provider needs an API key — paste & Save key first",
                    severity="warning",
                )
                return
            ai.set_provider(self._pending_provider, self._pending_model)
            ai.set_model(self._pending_model, self._pending_provider)
            self._changed["ai"] = True
            self._refresh_ai_panel(rebuild_providers=True)
            self.app.notify(
                f"AI → {self._pending_provider} / {self._pending_model}",
                severity="information",
            )
        elif bid == "btn-voice-save":
            key = self.query_one("#voice-key-input", Input).value.strip()
            voice_cfg.set_api_key(self._pending_voice_provider, key)
            self._changed["voice"] = True
            self._refresh_voice_panel(rebuild_providers=True)
            self.app.notify("Voice API key saved", severity="information")
        elif bid == "btn-voice-use-id":
            if self._apply_pasted_voice():
                self._refresh_voice_panel(rebuild_providers=False)
                self.app.notify(
                    f"Custom voice → {self._pending_voice}",
                    severity="information",
                )
            else:
                self.app.notify(
                    "Paste a voice id or library URL first",
                    severity="warning",
                )
        elif bid == "btn-apply-voice":
            self._apply_pasted_voice()
            key = self.query_one("#voice-key-input", Input).value.strip()
            if key:
                voice_cfg.set_api_key(self._pending_voice_provider, key)
            info = VOICE_PROVIDERS.get(self._pending_voice_provider, {})
            if info.get("requires_key") and not voice_cfg.get_api_key(
                self._pending_voice_provider
            ):
                self.app.notify(
                    "Paste a voice API key and Save first",
                    severity="warning",
                )
                return
            voice_cfg.set_provider(
                self._pending_voice_provider, self._pending_voice
            )
            if self._pending_voice_model:
                voice_cfg.set_model(
                    self._pending_voice_model, self._pending_voice_provider
                )
            voice_cfg.set_rate(self._pending_rate)
            self._changed["voice"] = True
            self._refresh_voice_panel(rebuild_providers=True)
            self.app.notify(
                f"Voice → {self._pending_voice_provider} / "
                f"{self._pending_voice} / {self._pending_voice_model or 'default'}",
                severity="information",
            )
        elif bid == "btn-voice-test":
            self._apply_pasted_voice()
            voice_cfg.set_provider(
                self._pending_voice_provider, self._pending_voice
            )
            if self._pending_voice_model:
                voice_cfg.set_model(
                    self._pending_voice_model, self._pending_voice_provider
                )
            voice_cfg.set_rate(self._pending_rate)
            key = self.query_one("#voice-key-input", Input).value.strip()
            if key:
                voice_cfg.set_api_key(self._pending_voice_provider, key)
            self._changed["voice"] = True
            try:
                self.app.action_speak_test()
            except Exception:
                self.app.notify("Applied — press t in the reader to test", severity="information")
