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


class AnthropicLLM:
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(self, *, system: str, messages: list[dict], tools: Sequence[dict], max_tokens: int, temperature: float) -> LLMResponse:
        r = await self.client.messages.create(
            model=self.model, system=system, messages=messages, max_tokens=max_tokens, temperature=temperature,
            tools=[{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools] or None,
        )
        text, calls = [], []
        for block in r.content:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        return LLMResponse("".join(text).strip(), calls, r.usage.input_tokens, r.usage.output_tokens, r.stop_reason or "end_turn")

    def assistant_turn(self, resp: LLMResponse) -> dict:
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

    async def complete_short(self, prompt: str, max_tokens: int = 200) -> str:
        r = await self.client.messages.create(model=self.model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if b.type == "text").strip()


class OpenAILLM:
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(self, *, system: str, messages: list[dict], tools: Sequence[dict], max_tokens: int, temperature: float) -> LLMResponse:
        r = await self.client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature,
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

    async def complete_short(self, prompt: str, max_tokens: int = 200) -> str:
        r = await self.client.chat.completions.create(model=self.model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return (r.choices[0].message.content or "").strip()


_llm = None


def get_llm():
    global _llm
    if _llm is not None:
        return _llm or None
    s = get_settings()
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        _llm = AnthropicLLM(s.anthropic_api_key, s.resolved_llm_model)
    elif s.llm_provider == "openai" and s.openai_api_key:
        _llm = OpenAILLM(s.openai_api_key, s.resolved_llm_model)
    else:
        _llm = False
    return _llm or None
