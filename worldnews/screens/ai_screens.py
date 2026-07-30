"""AI provider, result, and chat modals."""
from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from worldnews.ai import PROVIDERS, ai


class AIProviderScreen(ModalScreen[dict | None]):
    """Configure AI provider, model, and API key."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._pending_provider = ai.get_provider()
        self._pending_model = ai.get_model()
        self._model_id_map: dict[str, str] = {}
        self._saved = False

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-setup-box"):
            yield Label("AI setup", classes="modal-title")
            yield Static(self._status(), id="ai-setup-status")
            with VerticalScroll(id="ai-setup-scroll"):
                yield Label("1. Provider  (Enter to pick)")
                yield OptionList(*self._provider_options(), id="ai-prov-list")
                yield Label("2. Model  (Enter to pick)")
                yield OptionList(*self._model_options(), id="ai-model-list")
                yield Label("3. API key")
                yield Static(self._key_hint(), id="ai-key-hint")
                yield Input(
                    placeholder="paste API key here…",
                    password=True,
                    id="ai-key-input",
                    value=ai.get_api_key(self._pending_provider) or "",
                )
            with Horizontal(id="ai-setup-footer"):
                yield Button("Save key", id="ai-btn-save")
                yield Button("Clear key", id="ai-btn-clear")
                yield Button("Apply", variant="primary", id="ai-btn-apply")
                yield Button("Close", id="ai-btn-close")

    def _status(self) -> str:
        info = ai.get_provider_info()
        return (
            f"Active: [b]{info['name']}[/] · {info['model']}\n"
            f"Editing: [b]{PROVIDERS.get(self._pending_provider, {}).get('name', self._pending_provider)}[/] · "
            f"{self._pending_model}\n"
            f"{ai.get_status()}"
        )

    def _key_hint(self) -> str:
        info = PROVIDERS.get(self._pending_provider, {})
        if not info.get("requires_key"):
            return f"{info.get('name', '')} — no API key needed"
        has = bool(ai.get_api_key(self._pending_provider))
        return (
            f"{'Key saved ✓' if has else '⚠ Key required'} · {info.get('setup_cmd', '')}\n"
            f"{info.get('setup_url', '')}"
        )

    def _provider_options(self) -> list[Option]:
        opts = []
        for pk, pv in PROVIDERS.items():
            free = "free" if pv.get("free") else "paid"
            key_ok = (
                "key·ok"
                if (ai.get_api_key(pk) or not pv.get("requires_key"))
                else "needs·key"
            )
            mark = "›" if pk == self._pending_provider else " "
            opts.append(
                Option(f"{mark} {pv['name']}  [{free}] [{key_ok}]", id=f"ap-{pk}")
            )
        return opts

    def _model_options(self) -> list[Option]:
        models = PROVIDERS.get(self._pending_provider, {}).get("models", [])
        self._model_id_map = {}
        opts = []
        for i, m in enumerate(models):
            oid = f"am-{i}"
            self._model_id_map[oid] = m
            mark = "›" if m == self._pending_model else " "
            opts.append(Option(f"{mark} {m}", id=oid))
        if not opts:
            opts.append(Option("(no models)", id="am-none", disabled=True))
        return opts

    def _refresh(self) -> None:
        try:
            pl = self.query_one("#ai-prov-list", OptionList)
            pl.clear_options()
            pl.add_options(self._provider_options())
            ml = self.query_one("#ai-model-list", OptionList)
            ml.clear_options()
            ml.add_options(self._model_options())
            self.query_one("#ai-key-hint", Static).update(self._key_hint())
            self.query_one("#ai-key-input", Input).value = (
                ai.get_api_key(self._pending_provider) or ""
            )
            self.query_one("#ai-setup-status", Static).update(self._status())
        except Exception:
            pass

    def _pick_provider(self, pk: str) -> None:
        if pk not in PROVIDERS:
            return
        self._pending_provider = pk
        self._pending_model = (
            ai.config.get("providers", {}).get(pk, {}).get("model")
            or PROVIDERS[pk]["default_model"]
        )
        self._refresh()

    @on(OptionList.OptionSelected, "#ai-prov-list")
    def on_prov(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self._pick_provider(str(event.option_id).removeprefix("ap-"))

    @on(OptionList.OptionHighlighted, "#ai-prov-list")
    def on_prov_hi(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id:
            self._pick_provider(str(event.option_id).removeprefix("ap-"))

    @on(OptionList.OptionSelected, "#ai-model-list")
    def on_model(self, event: OptionList.OptionSelected) -> None:
        mid = self._model_id_map.get(str(event.option_id or ""))
        if mid:
            self._pending_model = mid
            self._refresh()

    @on(Button.Pressed)
    def on_btn(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "ai-btn-close":
            self.dismiss({"saved": self._saved} if self._saved else None)
        elif bid == "ai-btn-save":
            key = self.query_one("#ai-key-input", Input).value.strip()
            ai.set_api_key(self._pending_provider, key)
            self._saved = True
            self._refresh()
            try:
                self.app.notify("API key saved", severity="information")
            except Exception:
                pass
        elif bid == "ai-btn-clear":
            ai.set_api_key(self._pending_provider, "")
            self.query_one("#ai-key-input", Input).value = ""
            self._saved = True
            self._refresh()
        elif bid == "ai-btn-apply":
            key = self.query_one("#ai-key-input", Input).value.strip()
            if key:
                ai.set_api_key(self._pending_provider, key)
            info = PROVIDERS.get(self._pending_provider, {})
            if info.get("requires_key") and not ai.get_api_key(self._pending_provider):
                try:
                    self.app.notify(
                        "Paste an API key and press Save key first",
                        severity="warning",
                    )
                except Exception:
                    pass
                return
            ai.set_provider(self._pending_provider, self._pending_model)
            ai.set_model(self._pending_model, self._pending_provider)
            self._saved = True
            self._refresh()
            try:
                self.app.notify(
                    f"AI → {self._pending_provider} / {self._pending_model}",
                    severity="information",
                )
            except Exception:
                pass
            self.dismiss(
                {
                    "saved": True,
                    "provider": self._pending_provider,
                    "model": self._pending_model,
                }
            )


class AIResultModal(ModalScreen[None]):
    """Shows immediately with a spinner, then fills in the AI reply."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, title: str, body: str = "", *, working: bool = False) -> None:
        super().__init__()
        self._title = title
        self._body = body
        self._working = working

    def compose(self) -> ComposeResult:
        from textual.widgets import LoadingIndicator

        with Vertical(id="ai-result-box"):
            yield Label(self._title, id="ai-title", classes="modal-title")
            yield Static(
                f"Provider: {ai.get_provider()} · {ai.get_model()}",
                id="ai-meta",
            )
            yield LoadingIndicator(id="ai-spinner")
            with VerticalScroll(id="ai-scroll"):
                yield Markdown(
                    self._body or "_Working… fetching summary from AI._",
                    id="ai-md",
                )
            yield Button("Close", variant="primary", id="ai-close")

    def on_mount(self) -> None:
        self._sync_working()

    def _sync_working(self) -> None:
        try:
            spin = self.query_one("#ai-spinner")
            spin.display = self._working
        except Exception:
            pass

    def set_working(self, title: str, hint: str = "") -> None:
        self._working = True
        try:
            self.query_one("#ai-title", Label).update(title)
            meta = f"Provider: {ai.get_provider()} · {ai.get_model()}"
            if hint:
                meta = f"{meta}\n{hint}"
            self.query_one("#ai-meta", Static).update(meta)
            self.query_one("#ai-md", Markdown).update(
                "_Working… please wait. This can take a few seconds._"
            )
            self._sync_working()
        except Exception:
            pass

    def set_result(self, title: str, body: str, *, error: bool = False) -> None:
        self._working = False
        try:
            self.query_one("#ai-title", Label).update(title)
            self.query_one("#ai-md", Markdown).update(body or "_No response_")
            if error:
                self.query_one("#ai-meta", Static).update("Failed — see details below")
            else:
                self.query_one("#ai-meta", Static).update(
                    f"Done · {ai.get_provider()} · {ai.get_model()}"
                )
            self._sync_working()
        except Exception:
            pass

    @on(Button.Pressed, "#ai-close")
    def close(self) -> None:
        self.dismiss()


class AIChatScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict] = [
            {
                "role": "system",
                "content": "You are a helpful news assistant. Be concise and factual.",
            }
        ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Label(f"AI Chat · {ai.get_provider()}", classes="modal-title")
            with VerticalScroll(id="chat-scroll"):
                yield Markdown("_Ask anything about the news…_", id="chat-md")
            yield Input(placeholder="Message…", id="chat-input")
            with Horizontal():
                yield Button("Send", variant="primary", id="chat-send")
                yield Button("Close", id="chat-close")

    def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def _chat_markdown(self) -> str:
        lines = []
        for m in self.messages:
            if m["role"] == "system":
                continue
            who = "**You**" if m["role"] == "user" else "**AI**"
            lines.append(f"{who}\n\n{m['content']}\n")
        return "\n---\n".join(lines) or "_Empty_"

    def _render_chat(self) -> None:
        self.query_one("#chat-md", Markdown).update(self._chat_markdown())

    @work(exclusive=True, thread=True)
    def _ask(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

        def _busy() -> None:
            try:
                self.query_one("#chat-md", Markdown).update(
                    self._chat_markdown() + "\n\n---\n\n**AI**\n\n_Thinking…_"
                )
            except Exception:
                pass

        self.app.call_from_thread(_busy)
        try:
            reply = ai.chat(self.messages)
        except Exception as exc:
            reply = f"Error: {exc}"
        self.messages.append({"role": "assistant", "content": reply})
        self.app.call_from_thread(self._render_chat)

    @on(Input.Submitted, "#chat-input")
    def submit(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._ask(text)

    @on(Button.Pressed, "#chat-send")
    def send(self) -> None:
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if text:
            inp.value = ""
            self._ask(text)

    @on(Button.Pressed, "#chat-close")
    def close(self) -> None:
        self.dismiss()
