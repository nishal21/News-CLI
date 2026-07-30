import os
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

PROVIDERS = {
    "opencode": {
        "name": "OpenCode Zen (BigPickle) · default free",
        "type": "cloud",
        "free": True,
        "requires_key": False,
        "setup_url": "https://opencode.ai",
        "setup_cmd": "No API key — free default provider",
        "default_model": "big-pickle",
        "base_url": "https://opencode.ai/zen",
        "models": [
            "big-pickle",
            "kimi-k2.5",
            "kimi-k2.6",
            "ling-2.6-flash",
            "hy3-preview-free",
            "nemotron-3-super-free",
            "minimax-m2.5-free",
        ],
        "rate_limit": {"requests_per_minute": 20, "retry_max": 5, "retry_backoff": 2},
    },
    "hackclub": {
        "name": "Hack Club AI (Free)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://ai.hackclub.com/",
        "setup_cmd": "Sign in at ai.hackclub.com and create an API key",
        "default_model": "qwen/qwen3-32b",
        "base_url": "https://ai.hackclub.com/proxy",
        "models": [
            "qwen/qwen3-32b",
            "moonshotai/kimi-k2.6",
            "moonshotai/kimi-k2.5",
            "google/gemini-2.5-flash",
            "google/gemini-3-flash-preview",
            "openai/gpt-5-mini",
            "deepseek/deepseek-v3.2",
            "deepseek/deepseek-r1-0528",
            "minimax/minimax-m2.5",
            "z-ai/glm-4.7",
            "qwen/qwen3-235b-a22b",
            "x-ai/grok-4.1-fast",
        ],
    },
    "ollama": {
        "name": "Ollama (Local)",
        "type": "local",
        "free": True,
        "requires_key": False,
        "setup_url": "https://ollama.ai",
        "setup_cmd": "ollama pull llama3.2 && ollama serve",
        "default_model": "llama3.2",
        "base_url": "http://localhost:11434",
        "models": ["llama3.2", "llama3.1:8b", "llama3.1:70b", "mistral", "qwen2.5", "gemma2", "phi3", "codellama", "deepseek-coder", "mixtral"],
    },
    "lmstudio": {
        "name": "LM Studio (Local)",
        "type": "local",
        "free": True,
        "requires_key": False,
        "setup_url": "https://lmstudio.ai",
        "setup_cmd": "Start LM Studio and load a model",
        "default_model": "local-model",
        "base_url": "http://localhost:1234",
        "models": ["local-model"],
    },
    "groq": {
        "name": "Groq (Free, Fast)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://console.groq.com/keys",
        "setup_cmd": "Get free API key from Groq console",
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama-guard-3-8b", "llama3-70b-8192", "llama3-8b-8192", "mixtral-8x7b-32768", "gemma-7b-it", "gemma2-9b-it", "whisper-large-v3"],
    },
    "gemini": {
        "name": "Google Gemini (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://aistudio.google.com/apikey",
        "setup_cmd": "Get free API key from Google AI Studio",
        "default_model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com",
        "models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
    },
    "openrouter": {
        "name": "OpenRouter (Free Models)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://openrouter.ai/keys",
        "setup_cmd": "Get free API key, many models have free tier",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.1-8b-instruct", "google/gemini-2.0-flash", "mistralai/mistral-7b-instruct", "qwen/qwen-2.5-72b-instruct", "deepseek/deepseek-chat", "microsoft/phi-3-medium-128k-instruct", "nousresearch/hermes-3-llama-3.1-70b", "openai/gpt-4o-mini", "anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet", "anthropic/claude-3.5-sonnet:beta", "cohere/command-r-plus", "databricks/dbrx-instruct"],
    },
    "together": {
        "name": "Together AI (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://api.together.ai/settings/api-keys",
        "setup_cmd": "Get free API key with $25 credit",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "base_url": "https://api.together.xyz/v1",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "meta-llama/Llama-3.1-8B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1", "Qwen/Qwen2.5-72B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3", "google/gemma-2-27b-it", "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF"],
    },
    "cerebras": {
        "name": "Cerebras (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://cloud.cerebras.ai/",
        "setup_cmd": "Get free API key, extremely fast inference",
        "default_model": "llama3.1-70b",
        "base_url": "https://api.cerebras.ai/v1",
        "models": ["llama3.1-70b", "llama3.1-8b"],
    },
    "deepseek": {
        "name": "DeepSeek (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://platform.deepseek.com/api_keys",
        "setup_cmd": "Get free API key with generous limits",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-coder"],
    },
    "mistral": {
        "name": "Mistral (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://console.mistral.ai/api-keys/",
        "setup_cmd": "Get free API key from Mistral console",
        "default_model": "mistral-small-latest",
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-small-latest", "mistral-large-latest", "codestral-latest", "open-mistral-nemo", "open-codestral-mamba", "ministral-8b-latest", "ministral-3b-latest", "pixtral-12b-2409", "mistral-embed"],
    },
    "huggingface": {
        "name": "HuggingFace (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://huggingface.co/settings/tokens",
        "setup_cmd": "Get free API token from HF settings",
        "default_model": "mistralai/Mistral-7B-Instruct-v0.3",
        "base_url": "https://api-inference.huggingface.co",
        "models": ["mistralai/Mistral-7B-Instruct-v0.3", "HuggingFaceH4/zephyr-7b-beta", "meta-llama/Llama-3.1-8B-Instruct", "microsoft/Phi-3-mini-4k-instruct", "Qwen/Qwen2.5-7B-Instruct"],
    },
    "novita": {
        "name": "Novita AI (Free Tier)",
        "type": "cloud",
        "free": True,
        "requires_key": True,
        "setup_url": "https://novita.ai/settings",
        "setup_cmd": "Get free API key with generous limits",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "base_url": "https://api.novita.ai/v3/openai",
        "models": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.1-8b-instruct", "mistralai/mistral-nemo", "deepseek/deepseek_v3", "qwen/qwen-2.5-72b-instruct"],
    },
    "openai": {
        "name": "OpenAI (Paid)",
        "type": "cloud",
        "free": False,
        "requires_key": True,
        "setup_url": "https://platform.openai.com/api-keys",
        "setup_cmd": "Get API key, gpt-4o-mini is very cheap",
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "o1-mini", "o1-preview"],
    },
    "anthropic": {
        "name": "Anthropic Claude (Paid)",
        "type": "cloud",
        "free": False,
        "requires_key": True,
        "setup_url": "https://console.anthropic.com/settings/keys",
        "setup_cmd": "Get API key from Anthropic console",
        "default_model": "claude-3-haiku-20240307",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-3-haiku-20240307", "claude-3-sonnet-20240229", "claude-3-opus-20240229", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    },
    "localai": {
        "name": "LocalAI (Self-hosted)",
        "type": "local",
        "free": True,
        "requires_key": False,
        "setup_url": "https://localai.io",
        "setup_cmd": "docker run -p 8080:8080 localai/localai",
        "default_model": "gpt-4",
        "base_url": "http://localhost:8080",
        "models": ["gpt-4", "gpt-3.5-turbo"],
    },
    "vllm": {
        "name": "vLLM (Self-hosted)",
        "type": "local",
        "free": True,
        "requires_key": False,
        "setup_url": "https://docs.vllm.ai",
        "setup_cmd": "vllm serve meta-llama/Llama-3.2-3B-Instruct",
        "default_model": "meta-llama/Llama-3.2-3B-Instruct",
        "base_url": "http://localhost:8000",
        "models": ["meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
    },
}

class AIProvider:
    def __init__(self):
        from worldnews.paths import resolve_config_file

        self.settings_path = str(
            resolve_config_file("ai.json", ".news-cli-ai.json")
        )
        self.config = self._load()
    def _load(self):
        saved = {}
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path) as f: saved = json.load(f)
            except: pass
        default = self._default_config()
        for k in ["provider", "model", "temperature", "max_tokens", "auto_images"]:
            if k not in saved:
                saved[k] = default[k]
        if "providers" not in saved:
            saved["providers"] = default["providers"]
        else:
            for pk, pv in default["providers"].items():
                if pk not in saved["providers"]:
                    saved["providers"][pk] = pv
        # Always keep a valid free default — OpenCode needs no API key
        prov = saved.get("provider") or "opencode"
        if prov not in PROVIDERS:
            saved["provider"] = "opencode"
            saved["model"] = "big-pickle"
        return saved

    def _default_config(self):
        providers = {}
        for pk, pv in PROVIDERS.items():
            providers[pk] = {
                "api_key": "",
                "model": pv["default_model"],
                "base_url": pv.get("base_url", ""),
                "enabled": not pv.get("requires_key", True) or pk == "ollama",
            }
        return {
            "provider": "opencode",
            "model": "big-pickle",
            "temperature": 0.7,
            "max_tokens": 2048,
            "auto_images": False,
            "providers": providers,
        }

    def save(self):
        from pathlib import Path

        from worldnews.paths import migrate_to_modern, write_json

        self.settings_path = str(
            migrate_to_modern(Path(self.settings_path), "ai.json", private=True)
        )
        write_json(self.settings_path, self.config, private=True)

    def get_provider(self):
        p = self.config.get("provider") or "opencode"
        return p if p in PROVIDERS else "opencode"
    def get_model(self):
        p = self.get_provider()
        return self.config["providers"].get(p, {}).get("model", PROVIDERS.get(p, {}).get("default_model", ""))
    def get_api_key(self, provider=None):
        p = provider or self.get_provider()
        return self.config["providers"].get(p, {}).get("api_key", "")
    def get_base_url(self, provider=None):
        p = provider or self.get_provider()
        cfg = self.config["providers"].get(p, {})
        return cfg.get("base_url", PROVIDERS.get(p, {}).get("base_url", ""))
    def set_provider(self, provider, model=None):
        if provider in PROVIDERS:
            self.config["provider"] = provider
            if model: self.config["providers"][provider]["model"] = model
            else: self.config["providers"][provider]["model"] = PROVIDERS[provider]["default_model"]
            self.save()
    def set_model(self, model, provider=None):
        p = provider or self.get_provider()
        if p in PROVIDERS and model:
            if p not in self.config["providers"]:
                self.config["providers"][p] = {
                    "api_key": "",
                    "model": model,
                    "base_url": PROVIDERS[p].get("base_url", ""),
                    "enabled": True,
                }
            self.config["providers"][p]["model"] = model
            self.save()

    def set_api_key(self, provider, key):
        if provider in PROVIDERS:
            if provider not in self.config["providers"]:
                self.config["providers"][provider] = {
                    "api_key": "",
                    "model": PROVIDERS[provider]["default_model"],
                    "base_url": PROVIDERS[provider].get("base_url", ""),
                    "enabled": True,
                }
            self.config["providers"][provider]["api_key"] = key.strip()
            self.save()

    def set_base_url(self, provider, url):
        if provider in PROVIDERS:
            self.config["providers"][provider]["base_url"] = url
            self.save()
    def get_provider_info(self, provider=None):
        p = provider or self.get_provider()
        info = PROVIDERS.get(p, {})
        has_key = bool(self.get_api_key(p)) or not info.get("requires_key", True)
        return {
            "name": info.get("name", p),
            "type": info.get("type", "cloud"),
            "free": info.get("free", False),
            "requires_key": info.get("requires_key", True),
            "has_key": has_key,
            "model": self.get_model() if not provider else self.config["providers"].get(provider, {}).get("model", PROVIDERS.get(provider, {}).get("default_model", "")),
            "setup_url": info.get("setup_url", ""),
            "setup_cmd": info.get("setup_cmd", ""),
            "models": info.get("models", []),
        }
    def list_providers(self, free_only=False, local_only=False, cloud_only=False):
        result = []
        for pk, pv in PROVIDERS.items():
            if free_only and not pv.get("free"): continue
            if local_only and pv.get("type") != "local": continue
            if cloud_only and pv.get("type") != "cloud": continue
            info = self.get_provider_info(pk)
            result.append({
                "id": pk,
                "name": info["name"],
                "type": info["type"],
                "free": info["free"],
                "has_key": info["has_key"],
                "model": info["model"],
                "setup_url": info["setup_url"],
            })
        return result
    def _post_json(self, url, headers, data, timeout=120, max_retries=5, backoff=2):
        last_error = None
        if "User-Agent" not in headers:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
                ctx = __import__("ssl").create_default_context()
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                if e.code == 429 and attempt < max_retries - 1:
                    wait = backoff * (attempt + 1)
                    last_error = f"Rate limited. Retrying in {wait}s... (Attempt {attempt+1}/{max_retries})"
                    time.sleep(wait)
                    continue
                return {"error": f"HTTP {e.code}: {body}"}
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait = backoff * (attempt + 1)
                    time.sleep(wait)
                    continue
                return {"error": str(e)}
        return {"error": last_error or "Max retries exceeded"}
    def _ollama_chat(self, messages, timeout=120):
        base = self.get_base_url("ollama")
        model = self.config["providers"]["ollama"]["model"]
        url = f"{base}/api/chat"
        data = {"model": model, "messages": messages, "stream": False}
        headers = {"Content-Type": "application/json"}
        resp = self._post_json(url, headers, data, timeout)
        if "error" in resp:
            return f"Error: Ollama not running. Start: ollama pull {model} && ollama serve\n({resp['error']})"
        return resp.get("message", {}).get("content", "")
    def _openai_compat_chat(self, base_url, api_key, model, messages, timeout=120, max_retries=3, backoff=1):
        base = (base_url or "").rstrip("/")
        if base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        data = {
            "model": model,
            "messages": messages,
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": self.config.get("max_tokens", 2048),
            "stream": False,
        }
        resp = self._post_json(url, headers, data, timeout, max_retries, backoff)
        if "error" in resp: return f"Error: {resp['error']}"
        try: return resp["choices"][0]["message"]["content"]
        except: return f"Unexpected response: {resp}"
    def _gemini_chat(self, api_key, model, messages, timeout=120):
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system": system = m["content"]
            else: user_msgs.append(m)
        prompt = ""
        if system: prompt += f"{system}\n\n"
        for m in user_msgs:
            prompt += f"{m['role']}: {m['content']}\n\n"
        prompt += "assistant: "
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        data = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": self.config.get("temperature", 0.7)}}
        resp = self._post_json(url, headers, data, timeout)
        if "error" in resp: return f"Error: {resp['error']}"
        try: return resp["candidates"][0]["content"]["parts"][0]["text"]
        except: return f"Unexpected response: {resp}"
    def _anthropic_chat(self, api_key, model, messages, timeout=120):
        url = "https://api.anthropic.com/v1/messages"
        headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
        system = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system": system = m["content"]
            else: user_msgs.append({"role": m["role"], "content": m["content"]})
        data = {"model": model, "system": system, "messages": user_msgs, "max_tokens": self.config.get("max_tokens", 4096), "stream": False}
        resp = self._post_json(url, headers, data, timeout)
        if "error" in resp: return f"Error: {resp['error']}"
        try: return resp["content"][0]["text"]
        except: return f"Unexpected response: {resp}"
    def chat(self, messages, timeout=120):
        provider = self.get_provider()
        api_key = self.get_api_key()
        model = self.get_model()
        base_url = self.get_base_url()
        # Free fallback: OpenCode needs no key
        info = PROVIDERS.get(provider, {})
        if info.get("requires_key") and not (api_key or "").strip():
            provider = "opencode"
            model = (
                self.config.get("providers", {})
                .get("opencode", {})
                .get("model")
                or PROVIDERS["opencode"]["default_model"]
            )
            api_key = ""
            base_url = PROVIDERS["opencode"]["base_url"]
        if provider == "opencode":
            return self._openai_compat_chat("https://opencode.ai/zen", "", model, messages, timeout, max_retries=5, backoff=2)
        elif provider == "hackclub":
            return self._openai_compat_chat(
                base_url or "https://ai.hackclub.com/proxy",
                api_key,
                model,
                messages,
                timeout,
            )
        elif provider == "ollama": return self._ollama_chat(messages, timeout)
        elif provider == "lmstudio": return self._openai_compat_chat(base_url, "", model, messages, timeout)
        elif provider == "localai": return self._openai_compat_chat(base_url, "", model, messages, timeout)
        elif provider == "vllm": return self._openai_compat_chat(base_url, "", model, messages, timeout)
        elif provider == "groq": return self._openai_compat_chat("https://api.groq.com/openai/v1", api_key, model, messages, timeout)
        elif provider == "openrouter": return self._openai_compat_chat("https://openrouter.ai/api/v1", api_key, model, messages, timeout)
        elif provider == "together": return self._openai_compat_chat("https://api.together.xyz/v1", api_key, model, messages, timeout)
        elif provider == "cerebras": return self._openai_compat_chat("https://api.cerebras.ai/v1", api_key, model, messages, timeout)
        elif provider == "deepseek": return self._openai_compat_chat("https://api.deepseek.com/v1", api_key, model, messages, timeout)
        elif provider == "mistral": return self._openai_compat_chat("https://api.mistral.ai/v1", api_key, model, messages, timeout)
        elif provider == "novita": return self._openai_compat_chat("https://api.novita.ai/v3/openai", api_key, model, messages, timeout)
        elif provider == "openai": return self._openai_compat_chat("https://api.openai.com/v1", api_key, model, messages, timeout)
        elif provider == "anthropic": return self._anthropic_chat(api_key, model, messages, timeout)
        elif provider == "huggingface":
            model_id = model
            url = f"https://api-inference.huggingface.co/models/{model_id}/v1/chat/completions"
            return self._openai_compat_chat(f"https://api-inference.huggingface.co/models/{model_id}", api_key, model_id, messages, timeout)
        elif provider == "gemini":
            return self._gemini_chat(api_key, model, messages, timeout)
        return f"Unknown provider: {provider}"
    def summarize_article(self, title, description, source):
        messages = [
            {"role": "system", "content": "You are a news assistant. Summarize the following article in 2-3 bullet points. Be concise and factual."},
            {"role": "user", "content": f"Title: {title}\nSource: {source}\nDescription: {description}\n\nSummarize in 2-3 bullet points:"}
        ]
        return self.chat(messages)
    def explain_article(self, title, description, question):
        messages = [
            {"role": "system", "content": "You are a news assistant. Help readers understand the context and background of news articles."},
            {"role": "user", "content": f"Article: {title}\n{description}\n\nQuestion: {question}\n\nProvide context and explanation:"}
        ]
        return self.chat(messages)
    def translate_text(self, text, target_lang="English"):
        messages = [
            {"role": "system", "content": f"You are a translator. Translate the following text to {target_lang}. Only output the translation."},
            {"role": "user", "content": text}
        ]
        return self.chat(messages)
    def get_status(self):
        provider = self.get_provider()
        info = self.get_provider_info()
        if provider == "ollama":
            base = self.get_base_url("ollama")
            try:
                url = f"{base}/api/tags"
                req = urllib.request.Request(url, method="GET")
                ctx = __import__("ssl").create_default_context()
                with urllib.request.urlopen(req, timeout=3, context=ctx) as r:
                    resp = json.loads(r.read().decode())
                    models = [m["name"] for m in resp.get("models", [])]
                    model = self.get_model()
                    if model in models or any(model in m for m in models):
                        return f"Connected to Ollama ({base}) - Model: {model}"
                    return f"Ollama running but model '{model}' not found. Install: ollama pull {model}\nAvailable: {', '.join(models) if models else 'none'}"
            except: return f"Ollama not running at {base}. Start: ollama serve"
        if not info["has_key"]:
            return f"{info['name']} API key not set. Setup: {info['setup_url']}"
        return f"Provider: {info['name']} | Model: {info['model']} | Free: {'Yes' if info['free'] else 'No'}"

ai = AIProvider()

