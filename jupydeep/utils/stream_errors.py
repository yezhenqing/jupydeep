import asyncio
import re
from enum import StrEnum


class StreamErrorCode(StrEnum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    UNSUPPORTED_IMAGE_INPUT = "UNSUPPORTED_IMAGE_INPUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_NOISE_LINE_PATTERNS = (
    re.compile(r"^\s*traceback \(most recent call last\):\s*$", re.IGNORECASE),
    re.compile(r"^\s*file \".*\", line \d+, in .+$", re.IGNORECASE),
    re.compile(r"^\s*for more information visit\b.+$", re.IGNORECASE),
    re.compile(r"^\s*during handling of the above exception, another exception occurred:\s*$", re.IGNORECASE),
    re.compile(r"^\s*the above exception was the direct cause of the following exception:\s*$", re.IGNORECASE),
)

_HIGH_SIGNAL_PATTERN = re.compile(
    r"\b(429|502|503|504|timeout|timed out|rate limit|quota|connection|network|unavailable|vision|multimodal|image)\b",
    re.IGNORECASE,
)


def _clean_single_message(msg: str) -> str:
    """Strip common boilerplate and traceback noise lines while preserving useful details."""
    cleaned_lines: list[str] = []
    seen_lines: set[str] = set()

    for line in msg.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pat.match(stripped) for pat in _NOISE_LINE_PATTERNS):
            continue
        if len(stripped) > 300:
            stripped = stripped[:300]
        if stripped not in seen_lines:
            seen_lines.add(stripped)
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines)


def extract_error_text(exc: BaseException) -> str:
    """Extract root cause, outer wrapper, and high-signal middle nodes without noise."""
    chain: list[str] = []
    seen_ids: set[int] = set()
    curr: BaseException | None = exc

    while curr is not None and id(curr) not in seen_ids:
        seen_ids.add(id(curr))
        cleaned = _clean_single_message(str(curr))
        if cleaned:
            chain.append(cleaned)
        curr = curr.__cause__ or curr.__context__

    if not chain:
        return ""

    selected: list[str] = []
    seen_blocks: set[str] = set()

    def _add_block(block: str) -> None:
        if block and block not in seen_blocks:
            seen_blocks.add(block)
            selected.append(block)

    _add_block(chain[-1])

    for middle_msg in reversed(chain[1:-1]):
        if _HIGH_SIGNAL_PATTERN.search(middle_msg):
            _add_block(middle_msg)

    _add_block(chain[0])

    return "\n".join(selected).lower()


def sanitize_stream_error(exc: BaseException) -> tuple[StreamErrorCode, str]:
    """Map a streaming exception to (error_code, safe_message) for the client."""
    raw = extract_error_text(exc)
    
    if "timeout" in raw or "timed out" in raw or isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return (StreamErrorCode.TIMEOUT, "Request timed out. Please try again.")
    if "rate limit" in raw or "429" in raw or "quota" in raw:
        return (
            StreamErrorCode.RATE_LIMITED,
            "Rate limit or usage quota reached. Please try again later.",
        )
    if any(
        token in raw
        for token in ("connection", "network", "unavailable", "502", "503", "504")
    ):
        return (
            StreamErrorCode.UPSTREAM_UNAVAILABLE,
            "Upstream service is temporarily unavailable. Please try again.",
        )
    if any(
        token in raw
        for token in (
            "image",
            "vision",
            "multimodal",
            "does not support image",
            "image input is not supported",
            "unsupported content",
        )
    ):
        return (
            StreamErrorCode.UNSUPPORTED_IMAGE_INPUT,
            "The selected model does not support image input. Please remove the image or switch to a vision-capable model.",
        )

    return (
        StreamErrorCode.INTERNAL_ERROR,
        "Internal error. Please check or submit an issue.",
    )