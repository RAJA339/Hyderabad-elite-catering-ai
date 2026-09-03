"""Provider-agnostic LLM client with native tool calling (Anthropic default, OpenAI optional)."""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    stop_reason: str = "end_turn"
    raw_content: Any = None          # replayed verbatim so thinking blocks survive the loop
    refusal_category: str | None = None


def anthropic_headers(workspace_id: str | None) -> dict[str, str]:
    """Identity-linked API keys are rejected with a 400 unless every request names the
    workspace it acts in. A plain key needs no header, so send it only when configured."""
    return {"anthropic-workspace-id": workspace_id} if workspace_id else {}


class AnthropicLLM:
    """Messages API client.

    Current models (Opus 5, Sonnet 5, the 4.6+ family) reject `temperature`/`top_p`/`top_k`
    with a 400 and run adaptive thinking, so spend is steered with `output_config.effort`
    instead. Thinking blocks are echoed back untouched, which is what the API expects when a
    conversation continues on the same model."""

    def __init__(self, api_key: str, model: str, effort: str = "medium", workspace_id: str | None = None):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key, default_headers=anthropic_headers(workspace_id))
        self.model = model
        self.effort = effort

    async def chat(self, *, system: str, messages: list[dict], tools: Sequence[dict], max_tokens: int, temperature: float | None = None) -> LLMResponse:
        r = await self.client.messages.create(
            model=self.model, system=system, messages=messages, max_tokens=max_tokens,
            output_config={"effort": self.effort},
            tools=[{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools] or None,
        )
        if r.stop_reason == "refusal":
            category = getattr(getattr(r, "stop_details", None), "category", None)
            return LLMResponse("", [], r.usage.input_tokens, r.usage.output_tokens, "refusal", refusal_category=category)
        text, calls = [], []
        for block in r.content:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        return LLMResponse("".join(text).strip(), calls, r.usage.input_tokens, r.usage.output_tokens,
                           r.stop_reason or "end_turn", raw_content=r.content)

    def assistant_turn(self, resp: LLMResponse) -> dict:
        # Replay the response verbatim: rebuilding it from text + tool calls would drop the
        # thinking blocks the API expects back on the next request.
        if resp.raw_content is not None:
            return {"role": "assistant", "content": resp.raw_content}
        content: list[dict] = []
        if resp.text:
            content.append({"type": "text", "text": resp.text})
        for c in resp.tool_calls:
            content.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
        return {"role": "assistant", "content": content}

    def tool_results_turn(self, results: list[tuple[ToolCall, Any]]) -> dict:
        return {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": json.dumps(r, default=str)} for c, r in results
        ]}

    async def complete_short(self, prompt: str, max_tokens: int = 2000) -> str:
        # Thinking is billed against max_tokens, so a 200-token cap would return an empty
        # string. Low effort keeps these helper calls cheap and quick.
        r = await self.client.messages.create(
            model=self.model, max_tokens=max_tokens, output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if r.stop_reason == "refusal":
            return ""
        return "".join(b.text for b in r.content if b.type == "text").strip()


class OpenAILLM:
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(self, *, system: str, messages: list[dict], tools: Sequence[dict], max_tokens: int, temperature: float | None = None) -> LLMResponse:
        r = await self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature if temperature is not None else 0.3,
            messages=[{"role": "system", "content": system}, *messages],
            tools=[{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in tools] or None,
        )
        m = r.choices[0].message
        calls = [ToolCall(tc.id, tc.function.name, json.loads(tc.function.arguments or "{}")) for tc in (m.tool_calls or [])]
        return LLMResponse((m.content or "").strip(), calls, r.usage.prompt_tokens if r.usage else 0, r.usage.completion_tokens if r.usage else 0,
                           "tool_use" if calls else "end_turn")

    def assistant_turn(self, resp: LLMResponse) -> dict:
        return {"role": "assistant", "content": resp.text or None, "tool_calls": [
            {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in resp.tool_calls
        ] or None}

    def tool_results_turn(self, results: list[tuple[ToolCall, Any]]) -> list[dict]:
        return [{"role": "tool", "tool_call_id": c.id, "content": json.dumps(r, default=str)} for c, r in results]

    async def complete_short(self, prompt: str, max_tokens: int = 500) -> str:
        r = await self.client.chat.completions.create(model=self.model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return (r.choices[0].message.content or "").strip()


_llm = None


def get_llm():
    global _llm
    if _llm is not None:
        return _llm or None
    s = get_settings()
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        _llm = AnthropicLLM(s.anthropic_api_key, s.resolved_llm_model, s.llm_effort, s.anthropic_workspace_id)
    elif s.llm_provider == "openai" and s.openai_api_key:
        _llm = OpenAILLM(s.openai_api_key, s.resolved_llm_model)
    else:
        _llm = False
    return _llm or None
