"""
Prebuilt LangGraph Pattern Blocks and Starter Templates Gallery.
Pattern blocks expand into editable normal nodes and edges (not black boxes).
"""

from typing import Any
import uuid


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ── Pattern Blocks ─────────────────────────────────────────────────────────────
# Prebuilt subgraphs that insert directly into an existing graph with clean layout offsets.

def get_pattern_blocks() -> list[dict[str, Any]]:
    return [
        {
            "id": "react_agent",
            "name": "ReAct Agent",
            "category": "Agent Patterns",
            "description": "Autonomous reasoning and tool-calling loop (Reason + Act). Agent LLM binds tools and loops with ToolNode.",
            "icon": "bot",
            "builder": _build_react_pattern,
        },
        {
            "id": "supervisor_multi_agent",
            "name": "Supervisor Multi-Agent",
            "category": "Multi-Agent",
            "description": "Supervisor LLM coordinates specialized agents (e.g. Researcher, Writer) via dynamic routing.",
            "icon": "users",
            "builder": _build_supervisor_pattern,
        },
        {
            "id": "router",
            "name": "Intent / Classification Router",
            "category": "Control Flow",
            "description": "Classifier routes execution to specialized downstream branches based on user intent.",
            "icon": "git-fork",
            "builder": _build_router_pattern,
        },
        {
            "id": "reflection_loop",
            "name": "Reflection / Self-Correction Loop",
            "category": "Evaluation",
            "description": "Generator produces drafts; Evaluator critiques. Loops until quality check passes.",
            "icon": "repeat",
            "builder": _build_reflection_pattern,
        },
        {
            "id": "map_reduce",
            "name": "Map-Reduce Parallel Send",
            "category": "Parallelism",
            "description": "Dispatches parallel worker sub-tasks via Command(goto=[Send(...)]) and aggregates results.",
            "icon": "layers",
            "builder": _build_map_reduce_pattern,
        },
        {
            "id": "rag_pipeline",
            "name": "RAG Knowledge Retrieval",
            "category": "Knowledge",
            "description": "Query reformulator, document retriever tool, and contextual answer synthesizer with {state_field} templating.",
            "icon": "book-open",
            "builder": _build_rag_pattern,
        },
    ]


def _build_react_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    agent_id = f"agent_{_uid()}"
    tool_id = f"tools_{_uid()}"
    edge_id1 = f"edge_{_uid()}"
    edge_id2 = f"edge_{_uid()}"

    nodes = [
        {
            "id": agent_id,
            "type": "llm",
            "label": "ReAct Agent LLM",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.1,
                "system_prompt": "You are an expert AI assistant. Use the available tools when you need external information or calculations. Think step-by-step.",
                "bind_tools": True,
            },
            "policy": {"retry": {"max_retries": 1, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": tool_id,
            "type": "tool",
            "label": "ToolNode (Action Tools)",
            "position": {"x": offset_x + 320, "y": offset_y},
            "config": {
                "tool_type": "http",
                "method": "GET",
                "url": "https://api.duckduckgo.com/?q={query}&format=json",
                "description": "Search DuckDuckGo for real-time web context.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {
            "id": edge_id1,
            "source": agent_id,
            "target": tool_id,
            "kind": "conditional",
            "condition": {
                "router": "tools_condition",
                "path_map": {"tools": tool_id, "__end__": "END"},
            },
        },
        {
            "id": edge_id2,
            "source": tool_id,
            "target": agent_id,
            "kind": "normal",
        },
    ]
    return {"nodes": nodes, "edges": edges}


def _build_supervisor_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    sup_id = f"supervisor_{_uid()}"
    res_id = f"researcher_{_uid()}"
    wri_id = f"writer_{_uid()}"

    nodes = [
        {
            "id": sup_id,
            "type": "llm",
            "label": "Supervisor Agent",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.0,
                "system_prompt": "You are a team supervisor. Review the request and conversation history. Choose the next specialist: 'researcher', 'writer', or 'FINISH' if complete.",
                "structured_output": {
                    "schema_name": "SupervisorDecision",
                    "fields": [
                        {"name": "next_worker", "type": "str", "description": "Next worker to execute ('researcher', 'writer', or 'FINISH')"},
                        {"name": "instructions", "type": "str", "description": "Instructions for the worker"},
                    ],
                },
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": res_id,
            "type": "llm",
            "label": "Researcher Specialist",
            "position": {"x": offset_x + 340, "y": offset_y - 120},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.2,
                "system_prompt": "You are a research specialist. Analyze facts, gather relevant findings, and report back clearly.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": wri_id,
            "type": "llm",
            "label": "Writer Specialist",
            "position": {"x": offset_x + 340, "y": offset_y + 120},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.7,
                "system_prompt": "You are a writing specialist. Synthesize information into polished prose, reports, or articles.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {
            "id": f"edge_{_uid()}",
            "source": sup_id,
            "target": res_id,
            "kind": "conditional",
            "condition": {
                "router": "eval(decision.get('next_worker'))",
                "path_map": {"researcher": res_id, "writer": wri_id, "FINISH": "END"},
            },
        },
        {
            "id": f"edge_{_uid()}",
            "source": res_id,
            "target": sup_id,
            "kind": "normal",
        },
        {
            "id": f"edge_{_uid()}",
            "source": wri_id,
            "target": sup_id,
            "kind": "normal",
        },
    ]
    return {"nodes": nodes, "edges": edges}


def _build_router_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    router_id = f"router_{_uid()}"
    sup_branch_id = f"support_branch_{_uid()}"
    sal_branch_id = f"sales_branch_{_uid()}"
    gen_branch_id = f"general_branch_{_uid()}"

    nodes = [
        {
            "id": router_id,
            "type": "llm",
            "label": "Intent Router",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "system_prompt": "Classify the input into exactly one category: 'support', 'sales', or 'general'.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": sup_branch_id,
            "type": "llm",
            "label": "Support Specialist",
            "position": {"x": offset_x + 320, "y": offset_y - 120},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "system_prompt": "Resolve customer technical and account issues with patience and detail.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": sal_branch_id,
            "type": "llm",
            "label": "Sales Specialist",
            "position": {"x": offset_x + 320, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "system_prompt": "Assist customer with plan options, product features, and enterprise inquiries.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": gen_branch_id,
            "type": "llm",
            "label": "General QA",
            "position": {"x": offset_x + 320, "y": offset_y + 120},
            "config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "system_prompt": "Answer general inquiries clearly and concisely.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {
            "id": f"edge_{_uid()}",
            "source": router_id,
            "target": sup_branch_id,
            "kind": "conditional",
            "condition": {
                "router": "route_intent",
                "path_map": {
                    "support": sup_branch_id,
                    "sales": sal_branch_id,
                    "general": gen_branch_id,
                },
            },
        },
        {"id": f"edge_{_uid()}", "source": sup_branch_id, "target": "END", "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": sal_branch_id, "target": "END", "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": gen_branch_id, "target": "END", "kind": "normal"},
    ]
    return {"nodes": nodes, "edges": edges}


def _build_reflection_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    gen_id = f"generator_{_uid()}"
    eval_id = f"evaluator_{_uid()}"

    nodes = [
        {
            "id": gen_id,
            "type": "llm",
            "label": "Draft Generator",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.7,
                "system_prompt": "You are a code and content creator. Produce a detailed first draft addressing all constraints. If critique is provided, incorporate it thoroughly.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": eval_id,
            "type": "llm",
            "label": "Critic & Evaluator",
            "position": {"x": offset_x + 320, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.0,
                "system_prompt": "You are a strict reviewer. Evaluate the draft for errors, missing edge cases, and clarity. If excellent, reply 'ACCEPTED'. Otherwise provide constructive critique.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {
            "id": f"edge_{_uid()}",
            "source": gen_id,
            "target": eval_id,
            "kind": "normal",
        },
        {
            "id": f"edge_{_uid()}",
            "source": eval_id,
            "target": gen_id,
            "kind": "conditional",
            "condition": {
                "router": "review_decision",
                "path_map": {
                    "ACCEPTED": "END",
                    "REVISE": gen_id,
                },
            },
        },
    ]
    return {"nodes": nodes, "edges": edges}


def _build_map_reduce_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    map_id = f"map_dispatch_{_uid()}"
    worker_id = f"map_worker_{_uid()}"
    reduce_id = f"reducer_{_uid()}"

    nodes = [
        {
            "id": map_id,
            "type": "map",
            "label": "Map Item Dispatcher",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "items_field": "documents",
                "send_target": worker_id,
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": worker_id,
            "type": "llm",
            "label": "Document Worker (Parallel)",
            "position": {"x": offset_x + 280, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "system_prompt": "Analyze this specific document chunk and extract key takeaways.",
            },
            "policy": {"retry": {"max_retries": 1, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": reduce_id,
            "type": "python",
            "label": "Aggregate Reducer",
            "position": {"x": offset_x + 560, "y": offset_y},
            "config": {
                "updates": {"final_summary": "Aggregated all parallel workers."},
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {"id": f"edge_{_uid()}", "source": map_id, "target": worker_id, "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": worker_id, "target": reduce_id, "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": reduce_id, "target": "END", "kind": "normal"},
    ]
    return {"nodes": nodes, "edges": edges}


def _build_rag_pattern(offset_x: float = 300.0, offset_y: float = 200.0) -> dict[str, Any]:
    parser_id = f"query_parser_{_uid()}"
    retriever_id = f"retriever_{_uid()}"
    synth_id = f"synthesizer_{_uid()}"

    nodes = [
        {
            "id": parser_id,
            "type": "llm",
            "label": "Query Parser & Expansion",
            "position": {"x": offset_x, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "system_prompt": "Refine the user query into a clean, keyword-dense search query for semantic vector search.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": retriever_id,
            "type": "tool",
            "label": "Document Retriever Tool",
            "position": {"x": offset_x + 300, "y": offset_y},
            "config": {
                "tool_type": "http",
                "method": "GET",
                "url": "https://api.duckduckgo.com/?q={query}&format=json",
                "description": "Fetch relevant documents and snippets from external knowledge source.",
            },
            "policy": {"retry": {"max_retries": 1, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
        {
            "id": synth_id,
            "type": "llm",
            "label": "Contextual Synthesizer",
            "position": {"x": offset_x + 600, "y": offset_y},
            "config": {
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.3,
                "system_prompt": "Answer the user question using ONLY the retrieved context below:\n{retrieved_docs}\n\nIf the information is not in the context, politely state so.",
            },
            "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
        },
    ]

    edges = [
        {"id": f"edge_{_uid()}", "source": parser_id, "target": retriever_id, "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": retriever_id, "target": synth_id, "kind": "normal"},
        {"id": f"edge_{_uid()}", "source": synth_id, "target": "END", "kind": "normal"},
    ]
    return {"nodes": nodes, "edges": edges}


# ── Starter Templates Gallery ──────────────────────────────────────────────────
# Complete, fully configured and runnable LangGraph workflows.

def get_starter_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "tpl_react_agent",
            "name": "ReAct Agent with Action Tools",
            "category": "Agents",
            "description": "Production ReAct agent loop equipped with HTTP search tools and LangGraph tools_condition routing.",
            "complexity": "Intermediate",
            "graph": _template_react_agent(),
        },
        {
            "id": "tpl_customer_support_hitl",
            "name": "Customer Support with Human Escalation",
            "category": "Human-in-the-Loop",
            "description": "Routes routine questions to AI support bot, escalates complex inquiries to human agent via interrupt().",
            "complexity": "Intermediate",
            "graph": _template_customer_support(),
        },
        {
            "id": "tpl_reflection_code_gen",
            "name": "Code Generator with Reflection Loop",
            "category": "Quality & Review",
            "description": "Iterative code generation where a Critic reviews drafts and routes back for revisions until passing tests.",
            "complexity": "Advanced",
            "graph": _template_reflection_loop(),
        },
        {
            "id": "tpl_supervisor_team",
            "name": "Multi-Agent Research & Writing Team",
            "category": "Multi-Agent",
            "description": "Supervisor LLM coordinates Researcher and Writer agents with structured state handoffs.",
            "complexity": "Advanced",
            "graph": _template_supervisor_team(),
        },
        {
            "id": "tpl_rag_pipeline",
            "name": "Production RAG Question-Answering",
            "category": "Knowledge",
            "description": "Query reformulation, external search tool retrieval, and contextual LLM answer synthesis.",
            "complexity": "Beginner",
            "graph": _template_rag_pipeline(),
        },
        {
            "id": "tpl_map_reduce_batch",
            "name": "Map-Reduce Parallel Processor",
            "category": "Parallelism",
            "description": "Splits batch data and executes parallel worker tasks via Send() with Annotated operator.add aggregation.",
            "complexity": "Advanced",
            "graph": _template_map_reduce(),
        },
    ]


def _template_react_agent() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {
                "id": "agent",
                "type": "llm",
                "label": "ReAct Agent",
                "position": {"x": 260, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "system_prompt": "You are an intelligent ReAct agent. Answer the user's questions. Call tools whenever you require additional context.",
                    "bind_tools": True,
                },
                "policy": {"retry": {"max_retries": 1, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "tools",
                "type": "tool",
                "label": "Web Search Tool",
                "position": {"x": 580, "y": 200},
                "config": {
                    "tool_type": "http",
                    "method": "GET",
                    "url": "https://api.duckduckgo.com/?q={query}&format=json",
                    "description": "Search DuckDuckGo for live information.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "agent", "kind": "normal"},
            {
                "id": "e_agent_tools",
                "source": "agent",
                "target": "tools",
                "kind": "conditional",
                "condition": {
                    "router": "tools_condition",
                    "path_map": {"tools": "tools", "__end__": "END"},
                },
            },
            {"id": "e_tools_agent", "source": "tools", "target": "agent", "kind": "normal"},
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 25,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }


def _template_customer_support() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "escalation_required", "type": "bool", "reducer": "overwrite", "default": False},
                {"name": "customer_tier", "type": "str", "reducer": "overwrite", "default": "standard"},
            ],
            "input_fields": ["messages", "customer_tier"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {
                "id": "support_agent",
                "type": "llm",
                "label": "AI Support Bot",
                "position": {"x": 260, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "system_prompt": "You are a customer support agent. Answer the customer query accurately and warmly. If user is frustrated or asks for a human, mark escalation_required: true.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "human_escalation",
                "type": "human",
                "label": "Human Supervisor Review",
                "position": {"x": 560, "y": 200},
                "config": {
                    "prompt": "Customer requires senior human assistance. Please review messages and approve response or provide custom resolution.",
                    "fields": ["resolution_notes", "approval"],
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "support_agent", "kind": "normal"},
            {
                "id": "e_check_escalate",
                "source": "support_agent",
                "target": "human_escalation",
                "kind": "conditional",
                "condition": {
                    "router": "lambda state: 'human' if state.get('escalation_required') else 'end'",
                    "path_map": {"human": "human_escalation", "end": "END"},
                },
            },
            {"id": "e_human_end", "source": "human_escalation", "target": "END", "kind": "normal"},
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 15,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }


def _template_reflection_loop() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "draft", "type": "str", "reducer": "overwrite", "default": ""},
                {"name": "critique", "type": "str", "reducer": "overwrite", "default": ""},
                {"name": "iteration", "type": "int", "reducer": "overwrite", "default": 0},
            ],
            "input_fields": ["messages"],
            "output_fields": ["draft", "messages"],
        },
        "nodes": [
            {
                "id": "coder",
                "type": "llm",
                "label": "Code Generator",
                "position": {"x": 240, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.4,
                    "system_prompt": "You are an expert Python engineer. Write concise, production-ready code with complete type hints and docstrings. Previous critique: {critique}",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "critic",
                "type": "llm",
                "label": "Code Reviewer",
                "position": {"x": 540, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.0,
                    "system_prompt": "You are a principal software architect. Review the draft code thoroughly. If it passes all criteria and edge cases, respond with exactly 'APPROVED'. Otherwise provide concise critique points.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "coder", "kind": "normal"},
            {"id": "e_to_critic", "source": "coder", "target": "critic", "kind": "normal"},
            {
                "id": "e_critic_branch",
                "source": "critic",
                "target": "coder",
                "kind": "conditional",
                "condition": {
                    "router": "lambda state: 'done' if 'APPROVED' in str(state.get('critique', '')) or state.get('iteration', 0) >= 3 else 'revise'",
                    "path_map": {"done": "END", "revise": "coder"},
                },
            },
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 20,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }


def _template_supervisor_team() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "research_notes", "type": "list", "reducer": "operator.add", "default": []},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {
                "id": "supervisor",
                "type": "llm",
                "label": "Supervisor Agent",
                "position": {"x": 240, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.0,
                    "system_prompt": "You are the manager of an AI team. Given the task, choose next worker: 'researcher', 'writer', or 'FINISH'.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "researcher",
                "type": "llm",
                "label": "Researcher Agent",
                "position": {"x": 520, "y": 100},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "system_prompt": "Conduct research and extract verifiable facts for the supervisor.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "writer",
                "type": "llm",
                "label": "Writer Agent",
                "position": {"x": 520, "y": 300},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.7,
                    "system_prompt": "Draft engaging and comprehensive output using the research notes.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "supervisor", "kind": "normal"},
            {
                "id": "e_sup_route",
                "source": "supervisor",
                "target": "researcher",
                "kind": "conditional",
                "condition": {
                    "router": "route_supervisor",
                    "path_map": {"researcher": "researcher", "writer": "writer", "FINISH": "END"},
                },
            },
            {"id": "e_res_to_sup", "source": "researcher", "target": "supervisor", "kind": "normal"},
            {"id": "e_wri_to_sup", "source": "writer", "target": "supervisor", "kind": "normal"},
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 25,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }


def _template_rag_pipeline() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages", "default": []},
                {"name": "retrieved_docs", "type": "list", "reducer": "operator.add", "default": []},
            ],
            "input_fields": ["messages"],
            "output_fields": ["messages"],
        },
        "nodes": [
            {
                "id": "query_analyzer",
                "type": "llm",
                "label": "Query Analyzer",
                "position": {"x": 200, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.0,
                    "system_prompt": "Extract the core topic and formulate an optimal search query from the user message.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "retriever",
                "type": "tool",
                "label": "Knowledge Retriever",
                "position": {"x": 480, "y": 200},
                "config": {
                    "tool_type": "http",
                    "method": "GET",
                    "url": "https://api.duckduckgo.com/?q={query}&format=json",
                    "description": "Fetch documentation snippets and references.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "synthesizer",
                "type": "llm",
                "label": "Contextual Synthesizer",
                "position": {"x": 760, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.3,
                    "system_prompt": "Answer the question using the following context:\n{retrieved_docs}\n\nProvide direct references and remain truthful to the context.",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "query_analyzer", "kind": "normal"},
            {"id": "e_ana_ret", "source": "query_analyzer", "target": "retriever", "kind": "normal"},
            {"id": "e_ret_syn", "source": "retriever", "target": "synthesizer", "kind": "normal"},
            {"id": "e_syn_end", "source": "synthesizer", "target": "END", "kind": "normal"},
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 15,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }


def _template_map_reduce() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "items", "type": "list", "reducer": "overwrite", "default": ["report_A", "report_B", "report_C"]},
                {"name": "summaries", "type": "list", "reducer": "operator.add", "default": []},
            ],
            "input_fields": ["items"],
            "output_fields": ["summaries"],
        },
        "nodes": [
            {
                "id": "dispatcher",
                "type": "map",
                "label": "Map Item Dispatcher",
                "position": {"x": 220, "y": 200},
                "config": {
                    "items_field": "items",
                    "send_target": "worker",
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "worker",
                "type": "llm",
                "label": "Parallel Worker",
                "position": {"x": 500, "y": 200},
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "system_prompt": "Process this single item and return key extraction.",
                },
                "policy": {"retry": {"max_retries": 1, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
            {
                "id": "reducer",
                "type": "python",
                "label": "Aggregate Reducer",
                "position": {"x": 780, "y": 200},
                "config": {
                    "updates": {"final_result": "Map-reduce aggregation complete."},
                },
                "policy": {"retry": {"max_retries": 0, "delay": 1.0, "backoff_factor": 2.0}, "cache": {"enabled": False}, "defer": False},
            },
        ],
        "edges": [
            {"id": "e_start", "source": "START", "target": "dispatcher", "kind": "normal"},
            {"id": "e_disp_work", "source": "dispatcher", "target": "worker", "kind": "normal"},
            {"id": "e_work_red", "source": "worker", "target": "reducer", "kind": "normal"},
            {"id": "e_red_end", "source": "reducer", "target": "END", "kind": "normal"},
        ],
        "subgraphs": {},
        "settings": {
            "checkpointer": "sqlite",
            "recursion_limit": 20,
            "interrupt_before": [],
            "interrupt_after": [],
            "store": {"type": "none"},
            "config_fields": [],
        },
    }
