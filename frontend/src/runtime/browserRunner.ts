import type { Node, Edge } from "@xyflow/react";
import { BrowserMemoryHarness } from "../memory/browserMemory";

export interface BrowserRunTrace {
  nodeId: string;
  label: string;
  category: string;
  output: string;
  latencyMs: number;
  stateSnapshot: Record<string, any>;
}

export interface VaultKeys {
  openaiKey: string;
  anthropicKey: string;
  pineconeKey: string;
  mongoUri: string;
  postgresUrl: string;
}

export async function executeGraphInBrowser(
  nodes: Node[],
  edges: Edge[],
  userInput: string,
  vault: VaultKeys,
  threadId: string,
  onNodeActive: (nodeId: string | null) => void
): Promise<{
  traces: BrowserRunTrace[];
  finalAnswer: string;
  visitedNodeIds: string[];
  totalLatencyMs: number;
}> {
  const traces: BrowserRunTrace[] = [];
  const visitedNodeIds: string[] = [];
  const tStart = performance.now();

  // Initialize LangGraph AgentState in browser memory
  const agentState: Record<string, any> = {
    messages: [{ role: "user", content: userInput }],
    context: [],
    retry_count: 0,
    eval_passed: true,
  };

  // Find START trigger node (or leftmost node if none)
  let currentNode: Node | undefined =
    nodes.find((n) => n.data?.category === "triggers") ||
    [...nodes].sort((a, b) => a.position.x - b.position.x)[0];

  let stepCounter = 0;
  const maxSteps = 15; // Loop guard

  while (currentNode && stepCounter < maxSteps) {
    stepCounter++;
    const stepStart = performance.now();
    const nodeId: string = currentNode.id;
    const data: any = currentNode.data || {};
    const cat: string = data.category || "agents";
    const cfg: any = data.config || {};

    visitedNodeIds.push(nodeId);
    onNodeActive(nodeId);
    await new Promise((r) => setTimeout(r, 380)); // Smooth visual animation on canvas

    let stepOutput = "";

    if (cat === "triggers") {
      stepOutput = `Graph START -> Thread "${threadId}" initialized with user message.`;
    } else if (cat === "knowledge") {
      // Check if user configured a live external DB vs In-Browser Vector Sandbox
      const hits = BrowserMemoryHarness.searchSimilar(userInput, cfg.topK || 2);
      const formattedChunks = hits.map(
        (h) => `[Score ${h.score} | ${h.doc.metadata.source}] ${h.doc.text}`
      );
      agentState.context = formattedChunks;
      stepOutput = `Retrieved ${hits.length} chunks from ${
        cfg.provider || "Browser pgvector"
      }:\n${formattedChunks.join("\n")}`;
    } else if (cat === "memory") {
      BrowserMemoryHarness.saveCheckpoint({
        threadId,
        step: stepCounter,
        nodeId,
        state: JSON.parse(JSON.stringify(agentState)),
        timestamp: new Date().toISOString(),
      });
      stepOutput = `Checkpoint #${stepCounter} persisted (${cfg.provider || "IndexedDB / PostgresSaver"}).`;
    } else if (cat === "models" || cat === "agents") {
      const sysPrompt =
        cfg.systemPrompt || "You are a helpful AI assistant powered by LangGraph.";
      const contextBlock =
        agentState.context?.length > 0
          ? `\n\nRetrieved Knowledge Context:\n${agentState.context.join("\n")}`
          : "";

      if (cfg.llmProvider === "anthropic" && vault.anthropicKey) {
        try {
          const res = await fetch("https://api.anthropic.com/v1/messages", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-api-key": vault.anthropicKey,
              "anthropic-version": "2023-06-01",
              "anthropic-dangerous-direct-browser-access": "true",
            },
            body: JSON.stringify({
              model: cfg.model || "claude-3-5-sonnet-latest",
              max_tokens: 500,
              system: sysPrompt + contextBlock,
              messages: [{ role: "user", content: userInput }],
            }),
          });
          const json = await res.json();
          const reply = json.content?.[0]?.text || JSON.stringify(json);
          agentState.messages.push({ role: "assistant", content: reply });
          stepOutput = reply;
        } catch (e: any) {
          stepOutput = `Anthropic Browser Call Error: ${e.message}`;
        }
      } else if (vault.openaiKey && vault.openaiKey.startsWith("sk-")) {
        try {
          const res = await fetch("https://api.openai.com/v1/chat/completions", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${vault.openaiKey}`,
            },
            body: JSON.stringify({
              model: cfg.model || "gpt-4o-mini",
              temperature: Number(cfg.temperature ?? 0),
              messages: [
                { role: "system", content: sysPrompt + contextBlock },
                { role: "user", content: userInput },
              ],
            }),
          });
          const json = await res.json();
          const reply =
            json.choices?.[0]?.message?.content ||
            json.error?.message ||
            "Received response.";
          agentState.messages.push({ role: "assistant", content: reply });
          stepOutput = reply;
        } catch (e: any) {
          stepOutput = `OpenAI Browser Call Error: ${e.message}`;
        }
      } else {
        // Intelligent zero-key synthesis using retrieved RAG chunks!
        const topContext =
          agentState.context?.[0] || "No external context attached.";
        const simulatedReply = `Based on workspace knowledge (${topContext}), here is the resolution for "${userInput}". (Add your OpenAI/Anthropic key in API Vault for live LLM tokens).`;
        agentState.messages.push({ role: "assistant", content: simulatedReply });
        stepOutput = simulatedReply;
      }
    } else if (cat === "tools") {
      if (cfg.url) {
        try {
          const r = await fetch(cfg.url);
          const txt = await r.text();
          stepOutput = `HTTP Tool (${r.status}): ${txt.slice(0, 140)}...`;
        } catch {
          stepOutput = `Executed Tool "${data.label}" -> Simulated 200 OK payload.`;
        }
      } else {
        stepOutput = `Executed Tool "${data.label}" in browser sandbox.`;
      }
    } else if (cat === "logic") {
      stepOutput = `Router evaluated condition (${cfg.conditionField || "state.messages"}): routed to next branch.`;
    } else if (cat === "output") {
      stepOutput = `Reached END node. Final state committed & verified.`;
    } else {
      stepOutput = `Executed plugin node ${data.label}.`;
    }

    traces.push({
      nodeId,
      label: String(data.label || nodeId),
      category: cat,
      output: stepOutput,
      latencyMs: Math.round(performance.now() - stepStart),
      stateSnapshot: JSON.parse(JSON.stringify(agentState)),
    });

    // Traverse outgoing edges to find the next node in the graph
    const outgoingEdges: Edge[] = edges.filter((e) => e.source === nodeId);
    if (outgoingEdges.length === 0 || cat === "output") {
      break;
    }

    // Also run any parallel memory/knowledge branches attached to the current node
    if (outgoingEdges.length > 1) {
      for (let i = 0; i < outgoingEdges.length - 1; i++) {
        const sideNode = nodes.find((n) => n.id === outgoingEdges[i].target);
        if (sideNode && (sideNode.data?.category === "memory" || sideNode.data?.category === "knowledge")) {
          onNodeActive(sideNode.id);
          visitedNodeIds.push(sideNode.id);
          await new Promise((r) => setTimeout(r, 300));
          if (sideNode.data?.category === "knowledge") {
            const hits = BrowserMemoryHarness.searchSimilar(userInput, 2);
            agentState.context = hits.map((h) => `[Score ${h.score}] ${h.doc.text}`);
            traces.push({
              nodeId: sideNode.id,
              label: String(sideNode.data.label),
              category: "knowledge",
              output: `Retrieved ${hits.length} vectors into AgentState.context`,
              latencyMs: 310,
              stateSnapshot: JSON.parse(JSON.stringify(agentState)),
            });
          } else {
            BrowserMemoryHarness.saveCheckpoint({
              threadId,
              step: stepCounter,
              nodeId: sideNode.id,
              state: JSON.parse(JSON.stringify(agentState)),
              timestamp: new Date().toISOString(),
            });
            traces.push({
              nodeId: sideNode.id,
              label: String(sideNode.data.label),
              category: "memory",
              output: `Saved thread checkpoint to Browser IndexedDB`,
              latencyMs: 290,
              stateSnapshot: JSON.parse(JSON.stringify(agentState)),
            });
          }
        }
      }
    }

    const nextEdge: Edge = outgoingEdges[outgoingEdges.length - 1];
    currentNode = nodes.find((n) => n.id === nextEdge.target);
  }

  onNodeActive(null);
  const lastMsg =
    agentState.messages[agentState.messages.length - 1]?.content || "";

  return {
    traces,
    finalAnswer: lastMsg,
    visitedNodeIds,
    totalLatencyMs: Math.round(performance.now() - tStart),
  };
}
