"""
BaseAgent — abstract foundation for every specialist agent.

Each agent:
  • Has a system prompt that defines its persona and task scope.
  • Can register tools (JSON schema + Python callable).
  • Runs the full Claude agentic loop (stream + tool execution).
  • Returns structured JSON outputs, always saved to the data store.
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from config.settings import DEFAULT_MODEL, RUN_MODE


class AgentTool:
    """Wraps a tool definition (schema) together with its Python executor."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict,
        executor: Callable[[dict], Any],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.executor = executor

    def to_anthropic_tool(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def execute(self, tool_input: dict) -> str:
        try:
            result = self.executor(tool_input)
            if isinstance(result, (dict, list)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        except Exception as exc:
            return json.dumps({"error": str(exc)})


class BaseAgent(ABC):
    """
    Abstract base class.  Subclasses must implement:
      • get_system_prompt() → str
      • get_tools()         → list[AgentTool]
      • run(inputs)         → dict
    """

    # Colour used in Rich panels for this agent (override in subclasses)
    PANEL_COLOR = "cyan"

    def __init__(
        self,
        name: str,
        model: str = DEFAULT_MODEL,
        use_thinking: bool = False,
        console: Optional[Console] = None,
    ):
        self.name = name
        self.model = model
        self.use_thinking = use_thinking
        self.console = console or Console()
        self._client = anthropic.Anthropic()
        self._tool_registry: dict[str, AgentTool] = {}
        self._usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }

        # Register the agent's tools on init
        for tool in self.get_tools():
            self._tool_registry[tool.name] = tool

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt that defines this agent's persona."""

    @abstractmethod
    def get_tools(self) -> list[AgentTool]:
        """Return the list of AgentTool objects this agent can call."""

    @abstractmethod
    def run(self, inputs: dict) -> dict:
        """Execute the agent's primary task. Returns structured JSON dict."""

    # ── Core Claude agentic loop ───────────────────────────────────────────────

    def call_claude(
        self,
        user_message: str,
        extra_context: Optional[str] = None,
        max_tokens: int = 8192,
        stream_output: bool = True,
        use_tools: bool = True,
    ) -> str:
        """
        Run the full Claude agentic loop:
          1. Send user message (+ optional context) to Claude.
          2. Stream response tokens to the console.
          3. If Claude calls a tool, execute it, feed result back, loop.
          4. Return the final accumulated text.

        Set use_tools=False for JSON-extraction phases where tool calls
        would waste tokens and pollute the response.
        """
        messages: list[dict] = []

        # Build the user turn
        content = user_message
        if extra_context:
            content = f"{extra_context}\n\n---\n\n{content}"
        messages.append({"role": "user", "content": content})

        # Assemble tools list (empty when caller opts out)
        tools = [t.to_anthropic_tool() for t in self._tool_registry.values()] if use_tools else []

        accumulated_text = ""
        iteration = 0
        max_iterations = 10  # guard against infinite loops

        while iteration < max_iterations:
            iteration += 1
            create_kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "system": self.get_system_prompt(),
                "messages": messages,
            }
            if tools:
                create_kwargs["tools"] = tools
            if self.use_thinking:
                create_kwargs["thinking"] = {"type": "adaptive"}

            if stream_output:
                response_text, stop_reason, tool_calls, full_content = (
                    self._stream_response(create_kwargs)
                )
            else:
                response_text, stop_reason, tool_calls, full_content = (
                    self._non_stream_response(create_kwargs)
                )

            accumulated_text += response_text

            # Append assistant turn (preserves tool_use blocks)
            messages.append({"role": "assistant", "content": full_content})

            if stop_reason == "end_turn" or not tool_calls:
                break

            # Execute each tool call and collect results
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_input = tc["input"]
                tool_use_id = tc["id"]

                self._print_tool_call(tool_name, tool_input)

                agent_tool = self._tool_registry.get(tool_name)
                if agent_tool:
                    result = agent_tool.execute(tool_input)
                else:
                    result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                self._print_tool_result(tool_name, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return accumulated_text.strip()

    # ── Streaming helpers ──────────────────────────────────────────────────────

    def _stream_response(
        self, create_kwargs: dict
    ) -> tuple[str, str, list[dict], list[dict]]:
        """Stream a response and return (text, stop_reason, tool_calls, full_content)."""
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        full_content: list[dict] = []
        stop_reason = "end_turn"

        with self._client.messages.stream(**create_kwargs) as stream:
            current_block_type = None
            current_tool: dict = {}

            for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    block = event.content_block
                    current_block_type = block.type
                    if block.type == "tool_use":
                        current_tool = {
                            "id": block.id,
                            "name": block.name,
                            "input_json": "",
                        }
                    elif block.type == "text":
                        pass  # text delta handled below
                    elif block.type == "thinking":
                        self.console.print(
                            Text("  [thinking...]", style="dim italic")
                        )

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        self.console.print(
                            delta.text, end="", style=self.PANEL_COLOR
                        )
                        text_parts.append(delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool["input_json"] = current_tool.get(
                            "input_json", ""
                        ) + delta.partial_json
                    elif delta.type == "thinking_delta":
                        pass  # don't print raw thinking

                elif etype == "content_block_stop":
                    if current_block_type == "tool_use" and current_tool:
                        try:
                            current_tool["input"] = json.loads(
                                current_tool.get("input_json", "{}")
                            )
                        except json.JSONDecodeError:
                            current_tool["input"] = {}
                        tool_calls.append(current_tool)
                        current_tool = {}
                    current_block_type = None

                elif etype == "message_delta":
                    stop_reason = event.delta.stop_reason or "end_turn"

            # Reconstruct full content list for appending to messages
            final_msg = stream.get_final_message()
            self._accumulate_usage(final_msg.usage)
            full_content = [
                self._content_block_to_dict(b) for b in final_msg.content
            ]
            if text_parts:
                self.console.print()  # newline after streamed text

        return "".join(text_parts), stop_reason, tool_calls, full_content

    def _non_stream_response(
        self, create_kwargs: dict
    ) -> tuple[str, str, list[dict], list[dict]]:
        """Non-streaming fallback. Returns same shape as _stream_response."""
        response = self._client.messages.create(**create_kwargs)
        self._accumulate_usage(response.usage)
        text_parts: list[str] = []
        tool_calls: list[dict] = []
        full_content = [
            self._content_block_to_dict(b) for b in response.content
        ]

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {"id": block.id, "name": block.name, "input": block.input}
                )

        return (
            "".join(text_parts),
            response.stop_reason or "end_turn",
            tool_calls,
            full_content,
        )

    def _accumulate_usage(self, usage) -> None:
        """Add token counts from an Anthropic usage object to this agent's running total."""
        if usage is None:
            return
        self._usage["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
        self._usage["output_tokens"] += getattr(usage, "output_tokens", 0) or 0
        self._usage["cache_read_tokens"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        self._usage["cache_write_tokens"] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    @staticmethod
    def _content_block_to_dict(block) -> dict:
        """Convert an SDK content block object to a plain dict for message history."""
        if block.type == "text":
            return {"type": "text", "text": block.text}
        if block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        if block.type == "thinking":
            return {
                "type": "thinking",
                "thinking": getattr(block, "thinking", ""),
                "signature": getattr(block, "signature", ""),
            }
        return {"type": block.type}

    # ── Rich output helpers ────────────────────────────────────────────────────

    def print_header(self, subtitle: str = "") -> None:
        title = f"[bold]{self.name}[/bold]"
        if subtitle:
            title += f"  [dim]·  {subtitle}[/dim]"
        self.console.print(
            Panel(title, style=self.PANEL_COLOR, expand=False)
        )

    def print_result(self, label: str, value: Any) -> None:
        self.console.print(
            f"  [bold {self.PANEL_COLOR}]{label}:[/bold {self.PANEL_COLOR}] {value}"
        )

    def _print_tool_call(self, tool_name: str, tool_input: dict) -> None:
        self.console.print(
            f"\n  [yellow]⚙  Calling tool[/yellow] [bold]{tool_name}[/bold]"
        )
        self.console.print(f"     input: [dim]{json.dumps(tool_input)[:200]}[/dim]")

    def _print_tool_result(self, tool_name: str, result: str) -> None:
        preview = result[:150].replace("\n", " ")
        self.console.print(
            f"  [green]✓  {tool_name} result:[/green] [dim]{preview}[/dim]\n"
        )

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def extract_json(text: str) -> dict:
        """
        Extract the first valid JSON object or array from a text block.

        Strategy (in order):
        1. Extract the LARGEST ```json … ``` code fence — the most reliable
           signal when agents output narrative + JSON.
        2. Strip all fences and try to parse the whole text directly.
        3. Scan from the END of the text for the last { … } or [ … ] block,
           because agents typically output explanatory prose first then JSON last.
           Only consider blocks large enough to plausibly contain campaign data
           (> 50 chars) to skip tiny JSON fragments in markdown tables.
        """
        import re as _re

        # 1. Extract from explicit ```json ... ``` fence — try ALL matches
        #    and pick the largest valid one (in case there are small inline
        #    JSON snippets before the main payload).
        best: dict | None = None
        best_len = 0
        for pattern in (
            r"```json\s*([\s\S]+?)```",
            r"```JSON\s*([\s\S]+?)```",
        ):
            for m in _re.finditer(pattern, text, _re.DOTALL):
                candidate = m.group(1).strip()
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict) and len(candidate) > best_len:
                        best = parsed
                        best_len = len(candidate)
                except json.JSONDecodeError:
                    pass
        if best is not None:
            return best

        # 2. Strip fences and try whole-text parse
        cleaned = text
        for fence in ("```json", "```JSON", "```"):
            cleaned = cleaned.replace(fence, "")
        cleaned = cleaned.strip().strip("`").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 3. Scan from the END for the last complete { … } or [ … ] block
        #    (agents put JSON at the end after narrative prose).
        #    Skip tiny fragments (< 50 chars) that are likely markdown artefacts.
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            positions = [i for i, ch in enumerate(cleaned) if ch == start_char]
            for start_pos in reversed(positions):
                depth = 0
                in_string = False
                escape = False
                for i, ch in enumerate(cleaned[start_pos:], start_pos):
                    if escape:
                        escape = False
                        continue
                    if ch == '\\' and in_string:
                        escape = True
                        continue
                    if ch == '"' and not escape:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if ch == start_char:
                        depth += 1
                    elif ch == end_char:
                        depth -= 1
                        if depth == 0:
                            block = cleaned[start_pos: i + 1]
                            if len(block) < 50:
                                break  # too small, skip
                            try:
                                return json.loads(block)
                            except json.JSONDecodeError:
                                break
        return {}

    def sleep(self, seconds: float) -> None:
        """Polite delay — used between API calls in demo mode."""
        time.sleep(seconds)
