"""
Autonomous Agent Node with Tool-Calling Loop:
- Discovers connected Tool nodes
- Configurable max iterations
- Loops between LLM reasoning and Tool execution
- Streams tokens and emits tool execution events
"""

import json
import re
from typing import Any, Callable, Coroutine

from .expressions import ExpressionContext, evaluate_string
from .models import make_item
from .nodes_llm import execute_llm_node
from .nodes_tools import execute_tool_node


TOOL_CALL_REGEX = re.compile(r"```(?:json)?\s*(\{\s*\"tool\"[\s\S]*?\})\s*```", re.IGNORECASE)


async def execute_agent_node(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    connected_tools: list[dict[str, Any]],
    node_context: dict[str, Any],
    credentials: dict[str, str],
    on_token: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    on_tool_call: Callable[[str, Any, Any], Coroutine[Any, Any, None]] | None = None,
) -> dict[int | str, list[dict[str, Any]]]:
    """
    Executes an autonomous agent with a multi-step tool-calling loop.
    LLM can call connected tools up to max_iterations times before yielding final answer.
    """
    first_item = items[0] if items else make_item({})
    first_json = first_item.get("json", {})

    max_iterations = int(cfg.get("maxIterations", 5))
    sys_prompt_base = cfg.get("systemPrompt") or "You are an intelligent autonomous agent."

    user_input = (
        first_json.get("message")
        or first_json.get("input")
        or first_json.get("query")
        or json.dumps(first_json)
    )

    # Document available connected tools for the LLM
    tools_by_name: dict[str, dict[str, Any]] = {}
    tool_descriptions = []
    for t_node in connected_tools:
        t_data = t_node.get("data", {})
        t_label = t_data.get("label", t_node.get("id"))
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", t_label.lower()).strip("_")
        tools_by_name[clean_name] = t_node
        tools_by_name[t_label] = t_node
        tool_descriptions.append(f"- Tool '{clean_name}': {t_label}")

    tools_doc = "\n".join(tool_descriptions) if tool_descriptions else "No external tools connected."

    agent_system_prompt = (
        f"{sys_prompt_base}\n\n"
        f"Available Tools:\n{tools_doc}\n\n"
        "Instructions:\n"
        "If you need to invoke a tool, respond with ONLY a JSON block like:\n"
        "```json\n"
        '{"tool": "<tool_name>", "arguments": {"query": "<query>"}}\n'
        "```\n"
        "When you have enough information to answer the user directly, write your final response clearly without any tool blocks."
    )

    conversation_messages: list[dict[str, str]] = [
        {"role": "user", "content": user_input}
    ]

    iteration = 0
    final_answer = ""
    tool_calls_executed = 0

    while iteration < max_iterations:
        iteration += 1

        # Configure LLM call for this iteration
        llm_cfg = dict(cfg)
        llm_cfg["systemPrompt"] = agent_system_prompt

        # Pass conversation messages into the input item
        step_item = make_item({"messages": conversation_messages, "input": user_input})

        llm_result = await execute_llm_node(
            cfg=llm_cfg,
            items=[step_item],
            node_context=node_context,
            credentials=credentials,
            on_token=on_token,
        )

        response_text = llm_result.get(0, [{}])[0].get("json", {}).get("response", "")

        # Check for tool call in response
        tool_call_match = TOOL_CALL_REGEX.search(response_text)
        if not tool_call_match and '{"tool":' in response_text:
            # Fallback direct JSON search
            try:
                start = response_text.find('{"tool":')
                end = response_text.rfind('}') + 1
                candidate = response_text[start:end]
                json.loads(candidate)
                tool_call_match = re.search(r"(\{[\s\S]*\})", candidate)
            except Exception:
                pass

        if tool_call_match and connected_tools:
            try:
                call_data = json.loads(tool_call_match.group(1))
                tool_name = call_data.get("tool", "").lower()
                arguments = call_data.get("arguments", {})

                # Find tool node
                target_tool = tools_by_name.get(tool_name)
                if not target_tool:
                    # Match by substring
                    for k, v in tools_by_name.items():
                        if tool_name in k or k in tool_name:
                            target_tool = v
                            break

                if target_tool:
                    tool_calls_executed += 1
                    t_label = target_tool.get("data", {}).get("label", tool_name)
                    t_cfg = target_tool.get("data", {}).get("config", {})

                    if on_tool_call:
                        await on_tool_call(tool_name, arguments, "running")

                    # Execute tool
                    tool_input = [make_item(arguments)]
                    tool_output = await execute_tool_node(
                        cfg=t_cfg,
                        label=t_label,
                        items=tool_input,
                        node_context=node_context,
                    )
                    tool_data = tool_output.get(0, [{}])[0].get("json", {})

                    # Append tool call and observation to conversation
                    conversation_messages.append({"role": "assistant", "content": response_text})
                    conversation_messages.append({
                        "role": "user",
                        "content": f"Observation from tool '{tool_name}': {json.dumps(tool_data)}",
                    })

                    if on_tool_call:
                        await on_tool_call(tool_name, arguments, tool_data)

                    # Continue loop to let LLM process the tool's observation
                    continue
            except Exception as e:
                conversation_messages.append({
                    "role": "user",
                    "content": f"Tool execution failed with error: {e}. Please answer without this tool.",
                })
                continue

        # No tool call was made or final response reached
        final_answer = response_text
        break

    if not final_answer:
        final_answer = response_text or f"Agent reached max iterations ({max_iterations})."

    output_json = dict(first_json)
    output_json.update({
        "response": final_answer,
        "text": final_answer,
        "tool_calls_count": tool_calls_executed,
        "iterations": iteration,
    })

    return {0: [make_item(output_json)]}
