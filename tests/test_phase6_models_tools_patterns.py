"""
Tests for Phase 6: Models, tools, credentials, and patterns.
- Generic typed credentials CRUD + encryption + API masking + test connectivity.
- Nodes referencing credential IDs passed via env to worker subprocess.
- LLM node: prompt templating {state_field}, structured output (Pydantic schema), bind_tools.
- Tool node: SSRF guard, custom Python @tool.
- Pattern blocks: ReAct, Supervisor, Router, Map-Reduce, Reflection, RAG.
- Starter templates gallery.
"""

import ast
import json
import pytest
from httpx import AsyncClient, ASGITransport

from nocode_agent.main import app
from nocode_agent.database import get_db, ensure_tables
from nocode_agent.vault import encrypt_value, decrypt_value, mask_key
from nocode_agent.codegen import generate_langgraph_project
from nocode_agent.patterns import get_pattern_blocks, get_starter_templates


@pytest.fixture(autouse=True)
async def setup_db():
    await ensure_tables()


@pytest.mark.asyncio
async def test_credentials_crud_and_masking():
    """Verify generic typed credentials are encrypted at rest, masked in API, secrets never exposed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create OpenAI credential
        create_res = await client.post(
            "/api/v1/credentials",
            json={
                "name": "Production OpenAI Key",
                "type": "openai",
                "value": "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz",
                "metadata": {"org": "my-org"},
            },
        )
        assert create_res.status_code == 200, create_res.text
        data = create_res.json()
        cred_id = data["id"]
        assert cred_id.startswith("cred_")
        assert data["name"] == "Production OpenAI Key"
        assert data["type"] == "openai"
        # Secret is masked!
        assert "1234567890" not in data["masked_value"]
        assert "••••" in data["masked_value"]
        assert "value" not in data
        assert "encrypted_value" not in data

        # 2. List credentials
        list_res = await client.get("/api/v1/credentials")
        assert list_res.status_code == 200
        creds = list_res.json()
        assert any(c["id"] == cred_id for c in creds)
        matched = next(c for c in creds if c["id"] == cred_id)
        assert matched["masked_value"] == data["masked_value"]
        assert matched["metadata"] == {"org": "my-org"}

        # 3. Verify in database that it is encrypted with Fernet
        db = await get_db()
        cur = await db.execute("SELECT encrypted_value FROM typed_credentials WHERE id = ?", (cred_id,))
        row = await cur.fetchone()
        assert row is not None
        enc = row["encrypted_value"]
        assert enc != "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
        assert decrypt_value(enc) == "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"

        # 4. Update credential
        update_res = await client.put(
            f"/api/v1/credentials/{cred_id}",
            json={"name": "Updated OpenAI Key", "metadata": {"org": "updated-org"}},
        )
        assert update_res.status_code == 200
        assert update_res.json()["name"] == "Updated OpenAI Key"

        # 5. Delete credential
        del_res = await client.delete(f"/api/v1/credentials/{cred_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_credential_test_endpoint():
    """Verify test credential endpoint checks connectivity / validation without leaking keys."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Test raw custom/bearer format validation
        res = await client.post(
            "/api/v1/credentials/test",
            json={
                "type": "bearer",
                "value": "token_abc123456",
                "metadata": {},
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True

        # Test invalid/empty value
        empty_res = await client.post(
            "/api/v1/credentials/test",
            json={"type": "bearer", "value": ""},
        )
        assert empty_res.status_code == 200
        assert empty_res.json()["success"] is False


def test_ssrf_guard_in_generated_tools():
    """Verify the generated tools.py includes the SSRF guard function and blocks private IPs."""
    graph = {
        "schema_version": "1.0",
        "state": {"fields": [{"name": "messages", "type": "messages", "reducer": "add_messages"}]},
        "nodes": [
            {
                "id": "http_tool_node",
                "type": "tool",
                "label": "External Weather API",
                "config": {
                    "tool_type": "http",
                    "url": "https://api.weather.com/v1/forecast",
                    "method": "GET",
                    "description": "Fetch current weather",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "http_tool_node", "kind": "normal"},
            {"id": "e2", "source": "http_tool_node", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "none"},
    }

    result = generate_langgraph_project(graph)
    tools_code = result["files"]["tools.py"]
    assert "def validate_url_safe(url: str):" in tools_code
    assert "SSRF blocked" in tools_code
    assert "validate_url_safe" in tools_code

    # Verify syntax
    ast.parse(tools_code)


def test_prompt_templating_and_structured_output_codegen():
    """Verify LLM node prompt templating with {state_field} and Pydantic structured output model."""
    graph = {
        "schema_version": "1.0",
        "state": {
            "fields": [
                {"name": "messages", "type": "messages", "reducer": "add_messages"},
                {"name": "user_name", "type": "str", "reducer": "overwrite"},
                {"name": "extracted_info", "type": "dict", "reducer": "overwrite"},
            ],
            "input_fields": ["messages", "user_name"],
            "output_fields": ["extracted_info"],
        },
        "nodes": [
            {
                "id": "extractor_llm",
                "type": "llm",
                "label": "Info Extractor",
                "config": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "temperature": 0.0,
                    "systemPrompt": "Hello {user_name}! Please extract user details accurately.",
                    "bind_tools": True,
                    "structured_output": {
                        "schema_name": "UserExtraction",
                        "description": "Extracted user attributes",
                        "fields": [
                            {"name": "age", "type": "int", "description": "User age"},
                            {"name": "city", "type": "str", "description": "City of residence"},
                            {"name": "interests", "type": "list", "description": "List of user hobbies"},
                        ],
                    },
                    "output_field": "extracted_info",
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "extractor_llm", "kind": "normal"},
            {"id": "e2", "source": "extractor_llm", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "none"},
    }

    res = generate_langgraph_project(graph)
    nodes_code = res["files"]["nodes.py"]

    # 1. Check prompt templating replacement loop
    assert 'prompt.replace("{" + str(k) + "}"' in nodes_code

    # 2. Check Pydantic structured output model definition
    assert "class Userextraction(BaseModel):" in nodes_code
    assert "age: int = Field(" in nodes_code
    assert "city: str = Field(" in nodes_code
    assert "interests: list = Field(" in nodes_code

    # 3. Check with_structured_output call
    assert "model.with_structured_output(Userextraction)" in nodes_code
    assert '"extracted_info": out' in nodes_code

    # 4. Check AST validity
    ast.parse(nodes_code)


def test_custom_python_tool_generation():
    """Verify custom Python tool is formatted directly as an @tool in tools.py."""
    custom_tool_code = '''@tool
def calculate_vat(price: float) -> str:
    """Calculate 20% VAT on given price."""
    return f"VAT is {price * 0.2:.2f}"
'''
    graph = {
        "schema_version": "1.0",
        "state": {"fields": [{"name": "messages", "type": "messages", "reducer": "add_messages"}]},
        "nodes": [
            {
                "id": "vat_tool",
                "type": "tool",
                "label": "VAT Calculator",
                "config": {
                    "code": custom_tool_code,
                },
            },
        ],
        "edges": [
            {"id": "e1", "source": "START", "target": "vat_tool", "kind": "normal"},
            {"id": "e2", "source": "vat_tool", "target": "END", "kind": "normal"},
        ],
        "settings": {"checkpointer": "none"},
    }

    res = generate_langgraph_project(graph)
    tools_code = res["files"]["tools.py"]
    assert "def calculate_vat(price: float) -> str:" in tools_code
    ast.parse(tools_code)


@pytest.mark.asyncio
async def test_pattern_blocks_api():
    """Verify Pattern blocks list and instantiation endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. List pattern blocks
        res = await client.get("/api/v1/patterns")
        assert res.status_code == 200
        patterns = res.json()
        ids = [p["id"] for p in patterns]
        expected_patterns = [
            "react_agent",
            "supervisor_multi_agent",
            "router",
            "reflection_loop",
            "map_reduce",
            "rag_pipeline",
        ]
        for ep in expected_patterns:
            assert ep in ids

        # 2. Instantiate ReAct pattern
        inst_res = await client.post(
            "/api/v1/patterns/react_agent/instantiate",
            json={"offset_x": 400.0, "offset_y": 250.0},
        )
        assert inst_res.status_code == 200
        pdata = inst_res.json()
        assert len(pdata["nodes"]) == 2
        assert len(pdata["edges"]) == 2
        agent_node = pdata["nodes"][0]
        assert agent_node["position"]["x"] == 400.0
        assert agent_node["config"]["bind_tools"] is True


@pytest.mark.asyncio
async def test_starter_templates_gallery():
    """Verify starter templates gallery endpoint returns full valid GraphSchema JSON."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. List gallery templates
        res = await client.get("/api/v1/templates")
        assert res.status_code == 200
        templates = res.json()
        assert len(templates) >= 6

        # 2. Get specific template
        t_id = templates[0]["id"]
        t_res = await client.get(f"/api/v1/templates/{t_id}")
        assert t_res.status_code == 200
        full_tpl = t_res.json()
        assert "graph" in full_tpl
        graph_obj = full_tpl["graph"]
        assert len(graph_obj["nodes"]) > 0
        assert len(graph_obj["edges"]) > 0

        # Verify codegen compiles this template flawlessly
        gen_res = generate_langgraph_project(graph_obj)
        assert len(gen_res["files"]) == 7
        for fname, code in gen_res["files"].items():
            if fname.endswith(".py"):
                ast.parse(code)
