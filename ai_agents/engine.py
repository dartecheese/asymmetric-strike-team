"""Shared LLM engines — backs the four agents with local inference.

Two backends:
  - OllamaEngine: talks to local Ollama HTTP API
  - MLXEngine: uses Apple's MLX framework directly (best on M-series)

Both implement the same interface: .chat(), .chat_structured(), .ensure_loaded()
Fall back to rules-based agents if neither is available.
"""

import json
import time
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("ModelEngine")

OLLAMA_BASE = "http://localhost:11434"
# Default: MLX 7B model for Apple Silicon.
# Falls back to Ollama if MLX unavailable.
DEFAULT_MODEL = "mlx-community/Qwen2.5-7B-Instruct-4bit"
MAX_RETRIES = 3
RETRY_DELAY = 2


class OllamaEngine:
    """Local inference via Ollama's HTTP API.

    Keeps the model loaded across sequential agent calls.
    Each call is a separate request; no context bleeds between agents.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._loaded = False
        logger.info(f"OllamaEngine initialized with model: {model}")

    def ensure_loaded(self) -> bool:
        """Check Ollama is reachable and the model exists."""
        if self._loaded:
            return True

        try:
            req = urllib.request.Request(f"{OLLAMA_BASE}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                available = [m["name"] for m in data.get("models", [])]
                if not any(self.model in m for m in available):
                    logger.warning(
                        f"Model '{self.model}' not found in Ollama. "
                        f"Available: {available[:5]}..."
                    )
                    return False
        except Exception as e:
            logger.error(f"Ollama unreachable at {OLLAMA_BASE}: {e}")
            return False

        self._loaded = True
        return True

    def chat(self,
             system_prompt: str,
             user_prompt: str,
             temperature: float = 0.3,
             max_tokens: int = 1024) -> Optional[str]:
        """Send a chat request. Returns response text or None on failure."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        body = json.dumps(payload).encode()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    f"{OLLAMA_BASE}/api/chat",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())
                content = result.get("message", {}).get("content", "")
                return content.strip()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                logger.warning(f"Ollama attempt {attempt}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
            except json.JSONDecodeError as e:
                logger.error(f"Ollama bad response: {e}")
                return None

        logger.error(f"Ollama request failed after {MAX_RETRIES} attempts")
        return None

    def chat_structured(self,
                        system_prompt: str,
                        user_prompt: str,
                        temperature: float = 0.2) -> Optional[dict]:
        """Like chat(), but parses JSON from the response."""
        structured_prompt = (
            user_prompt
            + "\n\nRespond with ONLY valid JSON. No markdown, no explanation, no backticks."
        )
        raw = self.chat(system_prompt, structured_prompt, temperature=temperature)
        if not raw:
            return None

        raw = _strip_fences(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Model returned invalid JSON: {raw[:200]}")
            return None

    @property
    def info(self) -> str:
        return f"OllamaEngine({self.model}, loaded={self._loaded})"


class MLXEngine:
    """Local inference via Apple's MLX framework.

    Loads models from HuggingFace via mlx-lm. Runs natively on
    M-series Metal (no CPU fallback). Best choice for M5 Macs.
    """

    def __init__(self, model: str = "mlx-community/Qwen2.5-7B-4bit"):
        self.model = model
        self._model = None
        self._tokenizer = None
        self._loaded = False
        logger.info(f"MLXEngine initialized with model: {model}")

    def ensure_loaded(self) -> bool:
        """Load the model into memory. Idempotent."""
        if self._loaded:
            return True

        try:
            from mlx_lm import load
            logger.info(f"MLX: Loading {self.model}...")
            print(f"  [MLX] Loading {self.model} (this may take a moment on first run)...")
            self._model, self._tokenizer = load(self.model)
            self._loaded = True
            logger.info(f"MLX: {self.model} loaded.")
            return True
        except ImportError:
            logger.error("mlx-lm not installed. Run: pip install mlx-lm")
            return False
        except Exception as e:
            logger.error(f"MLX failed to load {self.model}: {e}")
            return False

    def chat(self,
             system_prompt: str,
             user_prompt: str,
             temperature: float = 0.3,
             max_tokens: int = 1024) -> Optional[str]:
        """Generate a response via MLX."""
        if not self._loaded:
            if not self.ensure_loaded():
                return None

        try:
            from mlx_lm import generate

            # Use the tokenizer's chat template for correct formatting
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            response = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                verbose=False,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"MLX generation error: {e}")
            return None

    def chat_structured(self,
                        system_prompt: str,
                        user_prompt: str,
                        temperature: float = 0.2) -> Optional[dict]:
        """Like chat(), but parses JSON from the response."""
        structured_prompt = (
            user_prompt
            + "\n\nRespond with ONLY valid JSON. No markdown, no explanation, no backticks."
        )
        raw = self.chat(system_prompt, structured_prompt, temperature=temperature)
        if not raw:
            return None

        raw = _strip_fences(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"MLX returned invalid JSON: {raw[:200]}")
            return None

    @property
    def info(self) -> str:
        return f"MLXEngine({self.model}, loaded={self._loaded})"


# --- Shared helpers ---

def _strip_fences(text: str) -> str:
    """Strip markdown code fences from a model response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n", 1)
        text = lines[1] if len(lines) > 1 else text[3:]
    if text.endswith("```"):
        text = text.rsplit("\n", 1)[0] if "\n" in text else text[:-3]
    return text.strip()


def auto_select_engine(model: str = DEFAULT_MODEL) -> Optional[object]:
    """Try Ollama first, fall back to MLX. Returns an engine instance or None."""
    # Try Ollama
    eng = OllamaEngine(model)
    if eng.ensure_loaded():
        print(f"  [Engine] Using Ollama ({model})")
        return eng

    # Try MLX
    mlx_model = _ollama_to_mlx_model(model)
    eng = MLXEngine(mlx_model)
    if eng.ensure_loaded():
        print(f"  [Engine] Using MLX ({mlx_model})")
        return eng

    print("  [Engine] No local inference available. Will use rules-based fallback.")
    return None


def _ollama_to_mlx_model(ollama_name: str) -> str:
    """Map common Ollama model names to their MLX equivalents on HF."""
    mapping = {
        "qwen3:8b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "qwen3:30b": "mlx-community/Qwen2.5-32B-4bit",
        "llama3.1:8b": "mlx-community/Llama-3.1-8B-Instruct-4bit",
        "llama3:8b": "mlx-community/Meta-Llama-3-8B-4bit",
        "deepseek-r1:latest": "mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit",
        "phi4-mini:latest": None,  # not available in MLX format
        "gemma3:12b": "mlx-community/gemma-3-12b-4bit",
    }
    result = mapping.get(ollama_name)
    if result is None and ollama_name.startswith("mlx-"):
        return ollama_name
    return result or "mlx-community/Qwen2.5-7B-Instruct-4bit"
