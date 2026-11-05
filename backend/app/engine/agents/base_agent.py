"""The one place the backend calls an LLM: Anthropic's Messages API, returning the model's JSON reply as a dict.
On any failure it returns {"error": "..."} so callers fall back to deterministic text; it never raises.
"""
import json

import anthropic

from app.engine import config
from app.engine.utils.logger import get_logger

log = get_logger(__name__)
_client: anthropic.Anthropic | None = None

MAX_TOKENS = 2048


def get_client() -> anthropic.Anthropic:
    """Created once, lazily, so importing this module needs no key."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _strip_code_fence(text: str) -> str:
    """Accept a reply wrapped in a ```json fence; the prompts ask for bare JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def call_llm(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    if not config.ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    try:
        response = get_client().beta.messages.create(
            model=model or config.NARRATION_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            output_config={"effort": "low"},
            # Server-side fallback: if the safety layer declines, the API re-runs the request on another model.
            # Harmless for narrating stock numbers; delete these two lines to turn it off.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        log.error(f"LLM call failed (AuthenticationError): {e}")
        return {"error": str(e)}
    except anthropic.RateLimitError as e:
        log.error(f"LLM call failed (RateLimitError): {e}")
        return {"error": str(e)}
    except anthropic.APIStatusError as e:
        log.error(f"LLM call failed (APIStatusError {e.status_code}): {e}")
        return {"error": str(e)}
    except anthropic.APIConnectionError as e:
        log.error(f"LLM call failed (APIConnectionError): {e}")
        return {"error": str(e)}

    if response.stop_reason == "refusal":  # whole fallback chain declined; content is not a usable answer
        log.warning("LLM call declined (stop_reason=refusal)")
        return {"error": "refusal"}
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        result = json.loads(_strip_code_fence(text))
    except ValueError:
        log.warning("LLM reply was not JSON; using deterministic fallback")
        return {"error": "non-JSON narration"}
    if not isinstance(result, dict):
        return {"error": "non-JSON narration"}
    return result
