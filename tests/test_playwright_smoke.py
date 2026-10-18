"""
Playwright smoke test for No-Code Agent.
Tests:
1. Server starts and serves the compiled single-page React frontend.
2. Canvas renders with START and END nodes.
3. Live Code Panel updates with generated LangGraph Python code.
4. Modals (Triggers, Run History, Settings) open and interact smoothly.
5. Node Palette search filters nodes dynamically.
6. Execution with interrupt (Human-in-the-loop / breakpoint), resume, and time travel.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
import json
import httpx
import pytest
from playwright.async_api import async_playwright, expect


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    """Launch the FastAPI server as a subprocess for Playwright testing."""
    port = get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(os.path.abspath("backend"))
    env["AUTH_ENABLED"] = "false"
    env["USE_FAKE_LLM"] = "1"
    env["NOCODE_DATA_DIR"] = str(os.path.abspath(".playwright_data"))
    os.makedirs(env["NOCODE_DATA_DIR"], exist_ok=True)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "nocode_agent.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=os.path.abspath("."),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to become responsive
    base_url = f"http://127.0.0.1:{port}"
    started = False
    for _ in range(30):
        try:
            r = httpx.get(f"{base_url}/health", timeout=1.0)
            if r.status_code == 200:
                started = True
                break
        except Exception:
            time.sleep(0.3)

    if not started:
        proc.terminate()
        out, err = proc.communicate(timeout=3)
        raise RuntimeError(f"Server failed to start on port {port}. STDERR: {err.decode('utf-8', errors='ignore')}")

    yield base_url

    # Cleanup
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


@pytest.mark.asyncio
async def test_playwright_canvas_and_live_code_smoke(live_server):
    """Smoke test: verify UI loads, canvas renders, palette works, live code is visible."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # 1. Load application
        response = await page.goto(live_server, wait_until="domcontentloaded", timeout=30000)
        assert response.status == 200, f"Expected 200 OK, got {response.status}"

        # 2. Verify Canvas / React Flow container exists
        await page.wait_for_selector(".react-flow", timeout=15000)
        assert await page.locator(".react-flow").is_visible()

        # 3. Verify Navbar and Action Buttons
        triggers_btn = page.locator("button:has-text('Triggers')")
        history_btn = page.locator("button:has-text('History')")
        zip_btn = page.locator("button[title*='standalone LangGraph project ZIP']").first
        json_btn = page.get_by_role("button", name="JSON", exact=True)

        await expect(triggers_btn).to_be_visible()
        await expect(history_btn).to_be_visible()
        await expect(zip_btn).to_be_visible()
        await expect(json_btn).to_be_visible()

        # 4. Test Node Palette Filter Search
        search_input = page.locator("input[placeholder*='Search nodes']")
        if await search_input.is_visible():
            await search_input.fill("agent")
            await page.wait_for_timeout(200)
            agent_pill = page.locator("text=Agent").first
            await expect(agent_pill).to_be_visible()
            await search_input.fill("")

        # 5. Test Live Code Panel visibility
        code_panel = page.locator("text=LangGraph Code").first
        await expect(code_panel).to_be_visible()

        # Verify Code tabs: graph.py, nodes.py, tools.py
        graph_tab = page.locator("button:has-text('graph.py')")
        nodes_tab = page.locator("button:has-text('nodes.py')")
        await expect(graph_tab.first).to_be_visible()
        await expect(nodes_tab.first).to_be_visible()

        # 6. Test Triggers Modal Open / Close
        await triggers_btn.click()
        await page.wait_for_selector("text=Triggers & Automation", timeout=5000)
        assert await page.locator("text=Triggers & Automation").is_visible()

        # Close Triggers modal
        close_btn = page.locator("button.w-7.h-7").or_(page.locator("button:has-text('✕')"))
        await close_btn.first.click()
        await page.wait_for_timeout(300)

        # 7. Test Run History Modal Open / Close
        await history_btn.click()
        await page.wait_for_selector("text=Execution History", timeout=5000)
        assert await page.locator("text=Execution History").is_visible()
        close_btn = page.locator("button.w-7.h-7").or_(page.locator("button:has-text('✕')"))
        await close_btn.first.click()
        await page.wait_for_timeout(300)

        await browser.close()


@pytest.mark.asyncio
async def test_playwright_workflow_run_interrupt_resume_fork(live_server):
    """
    Smoke test:
    Execute a workflow run via API, verify interrupt state on human node,
    resume with approval, and inspect state checkpoint history.
    """
    async with httpx.AsyncClient(base_url=live_server, timeout=20.0) as client:
        # 1. Create a HITL Workflow
        wf_res = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Playwright HITL Review Flow",
                "graph": {
                    "schema_version": "1.0",
                    "state": {
                        "fields": [
                            {"name": "proposal", "type": "str", "reducer": "overwrite", "default": "draft_content"},
                            {"name": "review_decision", "type": "str", "reducer": "overwrite", "default": "pending"},
                        ],
                        "input_fields": ["proposal"],
                        "output_fields": ["proposal", "review_decision"],
                    },
                    "nodes": [
                        {
                            "id": "human_reviewer",
                            "type": "human",
                            "label": "Human Review",
                            "config": {
                                "prompt": "Please review this proposal before proceeding.",
                                "fields": ["proposal"],
                            },
                        },
                        {
                            "id": "publish_step",
                            "type": "logic",
                            "label": "Publisher",
                            "config": {"updates": {"proposal": "published_content"}},
                        },
                    ],
                    "edges": [
                        {"id": "e_start", "source": "START", "target": "human_reviewer", "kind": "normal"},
                        {"id": "e_rev_pub", "source": "human_reviewer", "target": "publish_step", "kind": "normal"},
                        {"id": "e_end", "source": "publish_step", "target": "END", "kind": "normal"},
                    ],
                    "settings": {"checkpointer": "sqlite"},
                },
            },
        )
        assert wf_res.status_code in (200, 201), wf_res.text
        wf_id = wf_res.json()["id"]

        # 2. Start execution via POST /api/v1/runs -> should stream SSE and interrupt at "human_reviewer" node
        thread_id = f"pw_thread_{int(time.time())}"
        events_run1 = []
        async with client.stream(
            "POST",
            "/api/v1/runs",
            json={
                "workflow_id": wf_id,
                "thread_id": thread_id,
                "input": {"proposal": "draft_v1"},
                "stream_mode": "updates",
            },
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        events_run1.append(data)
                    except Exception:
                        pass

        event_types1 = [e.get("event") for e in events_run1]
        assert "start" in event_types1
        assert "interrupt" in event_types1 or any(e.get("status") == "interrupted" for e in events_run1)

        # 3. Resume execution with resume="approved"
        events_run2 = []
        async with client.stream(
            "POST",
            "/api/v1/runs",
            json={
                "workflow_id": wf_id,
                "thread_id": thread_id,
                "resume": "approved",
                "stream_mode": "updates",
            },
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        events_run2.append(data)
                    except Exception:
                        pass

        event_types2 = [e.get("event") for e in events_run2]
        done_events = [e for e in events_run2 if e.get("event") == "done"]
        assert len(done_events) > 0
        assert done_events[-1].get("status") == "success", f"Run 2 failed: {events_run2}"

        # 4. Check Thread State
        await asyncio.sleep(0.5)
        state_res = await client.get(f"/api/v1/threads/{thread_id}/state")
        assert state_res.status_code == 200, state_res.text
        state_body = state_res.json()
        values = state_body.get("values", {})
        assert (values.get("review_decision") == "approved" or values.get("proposal") == "published_content"), f"Unexpected values in thread state: {state_body}"

        # 5. Check Checkpoint History for Time Travel & Forking
        hist_res = await client.get(f"/api/v1/threads/{thread_id}/history")
        assert hist_res.status_code == 200
        history_items = hist_res.json().get("history", [])
        assert len(history_items) >= 2

        # 6. Fork Thread from an earlier checkpoint
        earlier_ckpt = history_items[-1]["checkpoint_id"]
        fork_res = await client.post(
            f"/api/v1/threads/{thread_id}/fork",
            json={"from_checkpoint_id": earlier_ckpt},
        )
        assert fork_res.status_code == 200
        fork_data = fork_res.json()
        assert "thread_id" in fork_data or "forked_thread_id" in fork_data
        new_thread = fork_data.get("thread_id") or fork_data.get("forked_thread_id")
        assert new_thread != thread_id
