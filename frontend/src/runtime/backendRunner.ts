/**
 * Backend Runner — SSE client for n8n-style server-side execution.
 *
 * Sends the graph (nodes + edges + prompt) to the FastAPI backend,
 * then reads the Server-Sent Events stream to drive real-time
 * canvas node highlighting and trace population.
 */

import type { Node, Edge } from "@xyflow/react";

export interface BackendRunTrace {
  nodeId: string;
  label: string;
  category: string;
  output: string;
  latencyMs: number;
}

export interface BackendRunResult {
  finalAnswer: string;
  visitedNodes: string[];
  totalMs: number;
}

/**
 * Execute the current canvas graph on the backend via SSE.
 *
 * @param nodes     - ReactFlow nodes array (current canvas state)
 * @param edges     - ReactFlow edges array
 * @param message   - User prompt / input
 * @param jwtToken  - Auth token (can be empty for open self-hosted)
 * @param onNodeActive - Called with node ID when a node starts executing (null when done)
 * @param onTrace   - Called when a node finishes, with its trace data
 * @returns         - Final answer + metadata once the full graph completes
 */
export async function executeGraphOnBackend(
  nodes: Node[],
  edges: Edge[],
  message: string,
  jwtToken: string,
  onNodeActive: (nodeId: string | null) => void,
  onTrace: (trace: BackendRunTrace) => void
): Promise<BackendRunResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (jwtToken) {
    headers["Authorization"] = `Bearer ${jwtToken}`;
  }

  const response = await fetch("/api/v1/execute", {
    method: "POST",
    headers,
    body: JSON.stringify({
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        position: n.position,
        data: n.data,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
      })),
      message,
      thread_id: `tab_${Date.now()}`,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Backend execution failed (${response.status}): ${err}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: BackendRunResult = { finalAnswer: "", visitedNodes: [], totalMs: 0 };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE format: lines starting with "data: " separated by double newlines
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      for (const line of part.split("\n")) {
        if (!line.startsWith("data: ")) continue;

        let event: any;
        try {
          event = JSON.parse(line.slice(6));
        } catch {
          continue;
        }

        switch (event.event) {
          case "node_start":
            onNodeActive(event.node_id);
            break;

          case "node_end":
            onTrace({
              nodeId: event.node_id,
              label: event.label,
              category: event.category,
              output: event.output,
              latencyMs: event.latencyMs,
            });
            // Brief pause before clearing highlight so the user sees it
            break;

          case "error":
            onTrace({
              nodeId: event.node_id,
              label: event.node_id,
              category: "error",
              output: `Error: ${event.error}`,
              latencyMs: 0,
            });
            break;

          case "done":
            onNodeActive(null);
            result = {
              finalAnswer: event.finalAnswer || "",
              visitedNodes: event.visitedNodes || [],
              totalMs: event.totalMs || 0,
            };
            break;
        }
      }
    }
  }

  onNodeActive(null);
  return result;
}
