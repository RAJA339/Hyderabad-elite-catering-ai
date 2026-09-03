"""Hierarchical, structure-aware chunking.

Parent chunks follow document structure (menu categories, package sections, policy headings).
Child chunks are 300–600 tokens with ~15% overlap, and every child is prefixed with its
breadcrumb + a metadata line so the embedding carries context ("Menu > Starters > Non-Veg").
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

try:
    import tiktoken

    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except Exception:  # pragma: no cover — tiktoken optional at runtime
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)


CHILD_MIN, CHILD_MAX, PARENT_MAX = 300, 600, 1800
OVERLAP_RATIO = 0.15
UNIT_TOKENS = 60   # long bullet lists are split into ~60-token units so windows can overlap


@dataclass
class ParentChunk:
    breadcrumb: str
    content: str
    ordinal: int
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return count_tokens(self.content)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


@dataclass
class ChildChunk:
    parent_ordinal: int
    ordinal: int
    content: str
    metadata: dict = field(default_factory=dict)

    @property
    def token_count(self) -> int:
        return count_tokens(self.content)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


_HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.M)


def split_markdown_sections(text: str, root_title: str) -> list[tuple[str, str]]:
    """Return (breadcrumb, body) per heading section, preserving hierarchy."""
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = [(0, root_title)]
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [(root_title, text.strip())] if text.strip() else []
    pre = text[: matches[0].start()].strip()
    if pre:
        sections.append((root_title, pre))
    for i, m in enumerate(matches):
        level, title = len(m.group(1)), m.group(2).strip()
        if level == 1:
            stack = []  # a top-level heading replaces the root title (avoids "Menu > Menu > …")
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        breadcrumb = " > ".join(t for _, t in stack)
        if body:
            sections.append((breadcrumb, body))
    return sections


def _split_paragraphs(body: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out: list[str] = []
    for p in parts:
        # Split long bullet lists into small units so windows can pack and overlap them
        if count_tokens(p) > UNIT_TOKENS * 2:
            lines = p.splitlines()
            buf: list[str] = []
            for ln in lines:
                buf.append(ln)
                if count_tokens("\n".join(buf)) >= UNIT_TOKENS:
                    out.append("\n".join(buf))
                    buf = []
            if buf:
                out.append("\n".join(buf))
        else:
            out.append(p)
    return out


def _metadata_line(meta: dict) -> str:
    keys = ("source_type", "category", "subcategory", "diet", "guest_range", "price_band", "festival_keys", "season_tags")
    bits = []
    for k in keys:
        v = meta.get(k)
        if v:
            bits.append(f"{k}={','.join(v) if isinstance(v, (list, tuple)) else v}")
    return "[" + " | ".join(bits) + "]" if bits else ""


def chunk_document(text: str, root_title: str, base_metadata: dict | None = None) -> tuple[list[ParentChunk], list[ChildChunk]]:
    base_metadata = dict(base_metadata or {})
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []
    p_ord = c_ord = 0
    for breadcrumb, body in split_markdown_sections(text, root_title):
        paras = _split_paragraphs(body)
        # Build parents up to PARENT_MAX tokens per breadcrumb
        buf: list[str] = []
        groups: list[list[str]] = []
        for para in paras:
            if buf and count_tokens("\n\n".join(buf + [para])) > PARENT_MAX:
                groups.append(buf)
                buf = []
            buf.append(para)
        if buf:
            groups.append(buf)
        for g in groups:
            meta = {**base_metadata, "breadcrumb": breadcrumb}
            parent = ParentChunk(breadcrumb=breadcrumb, content="\n\n".join(g), ordinal=p_ord, metadata=meta)
            parents.append(parent)
            header = f"{breadcrumb}\n{_metadata_line(meta)}".strip()
            for piece in _window(g, header):
                children.append(ChildChunk(parent_ordinal=p_ord, ordinal=c_ord, content=piece, metadata=meta))
                c_ord += 1
            p_ord += 1
    return parents, children


def _window(paras: list[str], header: str) -> list[str]:
    """Pack paragraphs into CHILD_MIN–CHILD_MAX windows with OVERLAP_RATIO carry-over."""
    out: list[str] = []
    buf: list[str] = []
    header_tokens = count_tokens(header)
    for para in paras:
        buf.append(para)
        size = count_tokens("\n\n".join(buf)) + header_tokens
        if size >= CHILD_MIN or size >= CHILD_MAX:
            out.append(header + "\n\n" + "\n\n".join(buf))
            # overlap: keep the tail paragraphs worth ~15% of the window
            target = int(OVERLAP_RATIO * count_tokens("\n\n".join(buf)))
            tail: list[str] = []
            for p in reversed(buf):
                tail.insert(0, p)
                if count_tokens("\n\n".join(tail)) >= target:
                    break
            buf = tail if len(tail) < len(buf) else []
    if buf and (not out or "\n\n".join(buf) not in out[-1]):
        out.append(header + "\n\n" + "\n\n".join(buf))
    return out
