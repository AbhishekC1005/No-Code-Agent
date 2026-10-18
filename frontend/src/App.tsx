import { useState, useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Play,
  Download,
  Share2,
  Sparkles,
  KeyRound,
  Code2,
  CheckCircle2,
  Database,
  Plus,
  FlaskConical,
  Layers,
  CloudUpload,
  UserCheck,
  XCircle,
  X,
  Workflow,
} from "lucide-react";

import { NODE_CATEGORIES, type NodeCategoryKey } from "./theme/nodeCategories";
import { StudioNode } from "./components/StudioNode";
import { NodeInspector } from "./components/NodeInspector";
import { AuthModal } from "./components/AuthModal";
import {
  executeGraphInBrowser,
  type BrowserRunTrace,
  type VaultKeys,
} from "./runtime/browserRunner";
import {
  executeGraphOnBackend,
  type BackendRunTrace,
} from "./runtime/backendRunner";
import {
  compileGraphInBrowser,
  downloadMicroserviceZipInBrowser,
  type StateSchemaItem,
  type EvalRow,
} from "./compiler/pythonCompiler";
import { BrowserMemoryHarness, type VectorDoc } from "./memory/browserMemory";
import { runEvalSuiteInBrowser, type EvalResultRow } from "./evals/evalHarness";

const API_BASE = ""; // Nginx proxies /api/* → backend
const nodeTypes = { studioNode: StudioNode };

const initialNodes: Node[] = [
  {
    id: "start_1",
    type: "studioNode",
    position: { x: 50, y: 180 },
    data: { label: "START Trigger", category: "triggers", config: {} },
  },
  {
    id: "rag_1",
    type: "studioNode",
    position: { x: 350, y: 80 },
    data: {
      label: "Knowledge RAG",
      category: "knowledge",
      config: { provider: "Pinecone", indexName: "enterprise_docs", topK: 2 },
    },
  },
  {
    id: "mem_1",
    type: "studioNode",
    position: { x: 350, y: 280 },
    data: {
      label: "Thread Checkpointer",
      category: "memory",
      config: { provider: "PostgreSQL (pgvector)" },
    },
  },
  {
    id: "agent_1",
    type: "studioNode",
    position: { x: 660, y: 180 },
    data: {
      label: "Support ReAct Agent",
      category: "agents",
      config: {
        llmProvider: "openai",
        model: "gpt-4o-mini",
        systemPrompt: "You are a helpful support agent. Use retrieved context.",
      },
    },
  },
  {
    id: "end_1",
    type: "studioNode",
    position: { x: 980, y: 180 },
    data: { label: "END + Eval Judge", category: "output", config: {} },
  },
];

const initialEdges: Edge[] = [
  { id: "e1", source: "start_1", target: "rag_1", animated: true },
  { id: "e2", source: "start_1", target: "mem_1", animated: true },
  { id: "e3", source: "rag_1", target: "agent_1", animated: true },
  { id: "e4", source: "agent_1", target: "end_1", animated: true },
];

interface WorkflowTab {
  id: string;
  name: string;
  nodes: Node[];
  edges: Edge[];
  userPrompt: string;
  traces: (BrowserRunTrace | BackendRunTrace)[];
}

const DEFAULT_WORKFLOWS: WorkflowTab[] = [
  {
    id: "tab_1",
    name: "Enterprise Support RAG",
    nodes: initialNodes,
    edges: initialEdges,
    userPrompt: "How do I reset my enterprise API token?",
    traces: [],
  },
  {
    id: "tab_2",
    name: "Web API Fetch & Summarize",
    nodes: [
      {
        id: "start_2",
        type: "studioNode",
        position: { x: 50, y: 180 },
        data: { label: "START Webhook", category: "triggers", config: {} },
      },
      {
        id: "tool_2",
        type: "studioNode",
        position: { x: 350, y: 180 },
        data: {
          label: "Fetch API Tool",
          category: "tools",
          config: { url: "https://api.github.com/zen", method: "GET" },
        },
      },
      {
        id: "agent_2",
        type: "studioNode",
        position: { x: 650, y: 180 },
        data: {
          label: "Summarizer Agent",
          category: "agents",
          config: {
            llmProvider: "openai",
            model: "gpt-4o-mini",
            systemPrompt: "Summarize the fetched data and extract insights.",
          },
        },
      },
      {
        id: "end_2",
        type: "studioNode",
        position: { x: 950, y: 180 },
        data: { label: "END State", category: "output", config: {} },
      },
    ],
    edges: [
      { id: "e2_1", source: "start_2", target: "tool_2", animated: true },
      { id: "e2_2", source: "tool_2", target: "agent_2", animated: true },
      { id: "e2_3", source: "agent_2", target: "end_2", animated: true },
    ],
    userPrompt: "Fetch the latest data and provide a concise summary.",
    traces: [],
  },
  {
    id: "tab_3",
    name: "Code Review & Logic Agent",
    nodes: [
      {
        id: "start_3",
        type: "studioNode",
        position: { x: 50, y: 180 },
        data: { label: "START PR Trigger", category: "triggers", config: {} },
      },
      {
        id: "agent_3",
        type: "studioNode",
        position: { x: 350, y: 180 },
        data: {
          label: "Code Reviewer Agent",
          category: "agents",
          config: {
            llmProvider: "openai",
            model: "gpt-4o-mini",
            systemPrompt: "Review code for security, efficiency, and cleanliness.",
          },
        },
      },
      {
        id: "logic_3",
        type: "studioNode",
        position: { x: 650, y: 180 },
        data: {
          label: "Approval Router",
          category: "logic",
          config: { conditionField: "review_passed" },
        },
      },
      {
        id: "end_3",
        type: "studioNode",
        position: { x: 950, y: 180 },
        data: { label: "END Response", category: "output", config: {} },
      },
    ],
    edges: [
      { id: "e3_1", source: "start_3", target: "agent_3", animated: true },
      { id: "e3_2", source: "agent_3", target: "logic_3", animated: true },
      { id: "e3_3", source: "logic_3", target: "end_3", animated: true },
    ],
    userPrompt: "def fib(n): return fib(n-1) + fib(n-2) if n > 1 else n",
    traces: [],
  },
];

export default function App() {
  // ── Multiple Workflow Tabs (n8n Style) ──
  const [tabs, setTabs] = useState<WorkflowTab[]>(() => {
    const cached = localStorage.getItem("N8N_WORKFLOW_TABS");
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch {}
    }
    return DEFAULT_WORKFLOWS;
  });

  const [activeTabId, setActiveTabId] = useState<string>(() => tabs[0]?.id || "tab_1");

  const [nodes, setNodes, onNodesChange] = useNodesState(tabs[0]?.nodes || initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(tabs[0]?.edges || initialEdges);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const [workspaceName, setWorkspaceName] = useState(tabs[0]?.name || "Enterprise Support RAG");
  const [activeTab, setActiveTab] = useState<"canvas" | "memory" | "evals" | "code">("canvas");
  const [userPrompt, setUserPrompt] = useState(tabs[0]?.userPrompt || "How do I reset my enterprise API token?");

  // State Schema managed in browser
  const [stateSchema] = useState<StateSchemaItem[]>([
    { key: "messages", type: "messages", reducer: "add_messages" },
    { key: "context", type: "list", reducer: "overwrite" },
    { key: "retry_count", type: "int", reducer: "overwrite" },
  ]);

  // In-Browser Vector Store state
  const [vectorDocs, setVectorDocs] = useState<VectorDoc[]>(() =>
    BrowserMemoryHarness.getDocuments()
  );
  const [newDocText, setNewDocText] = useState("");

  // In-Browser Eval Dataset & Results
  const [evalRows] = useState<EvalRow[]>([
    {
      id: "case_1",
      input: "How do I reset my enterprise API token?",
      expectedTrajectory: ["start_1", "rag_1", "agent_1", "end_1"],
      expectedKeyword: "90 days",
      maxLatencyMs: 5000,
    },
    {
      id: "case_2",
      input: "How are annual SaaS refunds processed?",
      expectedTrajectory: ["start_1", "rag_1", "agent_1", "end_1"],
      expectedKeyword: "14 days",
      maxLatencyMs: 5000,
    },
  ]);
  const [evalResults, setEvalResults] = useState<EvalResultRow[]>([]);

  // Client-Side BYOK Vault
  const [vault, setVault] = useState<VaultKeys>(() => ({
    openaiKey: localStorage.getItem("VAULT_OPENAI") || "",
    anthropicKey: localStorage.getItem("VAULT_ANTHROPIC") || "",
    pineconeKey: localStorage.getItem("VAULT_PINECONE") || "",
    mongoUri: localStorage.getItem("VAULT_MONGO") || "",
    postgresUrl: localStorage.getItem("VAULT_POSTGRES") || "",
  }));
  const [showVaultModal, setShowVaultModal] = useState(false);

  // FastAPI JWT Auth + MongoDB Sync
  const [jwtToken, setJwtToken] = useState<string | null>(() =>
    localStorage.getItem("STUDIO_JWT")
  );
  const [currentUser, setCurrentUser] = useState<{ full_name: string; email: string } | null>(
    () => {
      const raw = localStorage.getItem("STUDIO_USER");
      return raw ? JSON.parse(raw) : null;
    }
  );
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [syncStatus, setSyncStatus] = useState("");

  // Execution & Compiler Preview
  const [traces, setTraces] = useState<(BrowserRunTrace | BackendRunTrace)[]>(tabs[0]?.traces || []);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedFile, setSelectedFile] = useState("graph.py");

  // Keep active tab state synced
  useEffect(() => {
    setTabs((prev) => {
      const updated = prev.map((t) =>
        t.id === activeTabId
          ? { ...t, name: workspaceName, nodes, edges, userPrompt, traces }
          : t
      );
      localStorage.setItem("N8N_WORKFLOW_TABS", JSON.stringify(updated));
      return updated;
    });
  }, [workspaceName, nodes, edges, userPrompt, traces, activeTabId]);

  // Tab Switcher
  const handleSwitchTab = (newTabId: string) => {
    if (newTabId === activeTabId) return;

    const target = tabs.find((t) => t.id === newTabId);
    if (target) {
      setActiveTabId(newTabId);
      setWorkspaceName(target.name);
      setNodes(target.nodes);
      setEdges(target.edges);
      setUserPrompt(target.userPrompt);
      setTraces(target.traces || []);
      setSelectedNodeId(null);
    }
  };

  // Create New Tab
  const handleCreateNewTab = () => {
    const newTabNumber = tabs.length + 1;
    const newTabId = `tab_${Date.now()}`;
    const newTab: WorkflowTab = {
      id: newTabId,
      name: `Agent Workflow ${newTabNumber}`,
      nodes: [
        {
          id: `start_${newTabNumber}`,
          type: "studioNode",
          position: { x: 50, y: 180 },
          data: { label: "START Trigger", category: "triggers", config: {} },
        },
        {
          id: `agent_${newTabNumber}`,
          type: "studioNode",
          position: { x: 450, y: 180 },
          data: {
            label: "Reasoning Agent",
            category: "agents",
            config: {
              llmProvider: "openai",
              model: "gpt-4o-mini",
              systemPrompt: "You are an autonomous agent.",
            },
          },
        },
        {
          id: `end_${newTabNumber}`,
          type: "studioNode",
          position: { x: 850, y: 180 },
          data: { label: "END Output", category: "output", config: {} },
        },
      ],
      edges: [
        { id: `e_${newTabNumber}_1`, source: `start_${newTabNumber}`, target: `agent_${newTabNumber}`, animated: true },
        { id: `e_${newTabNumber}_2`, source: `agent_${newTabNumber}`, target: `end_${newTabNumber}`, animated: true },
      ],
      userPrompt: "Analyze the data and provide actionable recommendations.",
      traces: [],
    };

    const updated = [...tabs, newTab];
    setTabs(updated);
    localStorage.setItem("N8N_WORKFLOW_TABS", JSON.stringify(updated));

    setActiveTabId(newTabId);
    setWorkspaceName(newTab.name);
    setNodes(newTab.nodes);
    setEdges(newTab.edges);
    setUserPrompt(newTab.userPrompt);
    setTraces([]);
    setSelectedNodeId(null);
  };

  // Close Tab
  const handleCloseTab = (e: React.MouseEvent, tabIdToClose: string) => {
    e.stopPropagation();
    if (tabs.length <= 1) return;

    const remaining = tabs.filter((t) => t.id !== tabIdToClose);
    setTabs(remaining);
    localStorage.setItem("N8N_WORKFLOW_TABS", JSON.stringify(remaining));

    if (activeTabId === tabIdToClose) {
      const nextTab = remaining[0];
      setActiveTabId(nextTab.id);
      setWorkspaceName(nextTab.name);
      setNodes(nextTab.nodes);
      setEdges(nextTab.edges);
      setUserPrompt(nextTab.userPrompt);
      setTraces(nextTab.traces || []);
      setSelectedNodeId(null);
    }
  };

  // 100% In-Browser Live Code Compilation
  const compiledFiles = useMemo(
    () =>
      compileGraphInBrowser(workspaceName, nodes, edges, stateSchema, evalRows),
    [workspaceName, nodes, edges, stateSchema, evalRows]
  );

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) || null,
    [nodes, selectedNodeId]
  );

  const onConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) => addEdge({ ...params, animated: true }, eds)),
    [setEdges]
  );

  const addCategoryNode = (catKey: NodeCategoryKey) => {
    const theme = NODE_CATEGORIES[catKey];
    const id = `${catKey}_${Date.now().toString().slice(-3)}`;
    const newNode: Node = {
      id,
      type: "studioNode",
      position: { x: 250 + Math.random() * 250, y: 120 + Math.random() * 180 },
      data: {
        label: theme.defaultTitle,
        category: catKey,
        config:
          catKey === "models" || catKey === "agents"
            ? { llmProvider: "openai", model: "gpt-4o-mini" }
            : catKey === "knowledge"
            ? { provider: "Pinecone", indexName: "agent_knowledge", topK: 2 }
            : {},
      },
    };
    setNodes((nds) => [...nds, newNode]);
    setSelectedNodeId(id);
  };

  const updateNodeData = (nodeId: string, newData: Record<string, any>) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: newData } : n))
    );
  };

  const deleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) =>
      eds.filter((e) => e.source !== nodeId && e.target !== nodeId)
    );
    setSelectedNodeId(null);
  };

  // ── n8n-Style Backend Execution with Live SSE & Fallback ──
  const handleRunWorkflow = async () => {
    setIsRunning(true);
    setTraces([]);

    try {
      // 1. Execute on Python Docker Backend with real-time SSE stream
      await executeGraphOnBackend(
        nodes,
        edges,
        userPrompt,
        jwtToken || "",
        (activeId) => {
          setNodes((nds) =>
            nds.map((n) => ({
              ...n,
              data: { ...n.data, isRunning: n.id === activeId },
            }))
          );
        },
        (trace) => {
          setTraces((prev) => [...prev, trace]);
        }
      );
    } catch (err: any) {
      console.warn("Backend execution notice, using browser fallback:", err);
      // 2. Client-side fallback if backend is momentarily unreachable
      const res = await executeGraphInBrowser(
        nodes,
        edges,
        userPrompt,
        vault,
        `tab_${activeTabId}`,
        (activeId) => {
          setNodes((nds) =>
            nds.map((n) => ({
              ...n,
              data: { ...n.data, isRunning: n.id === activeId },
            }))
          );
        }
      );
      setTraces(res.traces);
    } finally {
      setIsRunning(false);
    }
  };

  const handleRunBatchEvals = async () => {
    setIsRunning(true);
    const results = await runEvalSuiteInBrowser(
      nodes,
      edges,
      evalRows,
      vault,
      (activeId) => {
        setNodes((nds) =>
          nds.map((n) => ({
            ...n,
            data: { ...n.data, isRunning: n.id === activeId },
          }))
        );
      }
    );
    setEvalResults(results);
    setIsRunning(false);
  };

  const handleSaveToMongoBackend = async () => {
    if (!jwtToken) {
      setShowAuthModal(true);
      return;
    }
    setSyncStatus("Syncing...");
    try {
      const res = await fetch(`${API_BASE}/api/v1/workspaces`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${jwtToken}`,
        },
        body: JSON.stringify({
          name: workspaceName,
          nodes,
          edges,
        }),
      });
      if (res.ok) {
        setSyncStatus("Saved to MongoDB!");
        setTimeout(() => setSyncStatus(""), 3000);
      } else {
        setSyncStatus("Auth expired");
        setShowAuthModal(true);
      }
    } catch {
      setSyncStatus("Offline (Saved in Browser)");
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#F8FAFC] text-[#475569]">
      {/* ─── TOP SAAS LIGHT HEADER ─── */}
      <header className="h-16 bg-white border-b border-[#E5E7EB] px-6 flex items-center justify-between shadow-soft z-30">
        <div className="flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-green-50 border border-green-200 flex items-center justify-center text-[#16A34A] font-bold">
            LG
          </div>
          <div>
            <div className="flex items-center gap-2">
              <input
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                className="text-base font-bold text-[#0F172A] bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500/20 rounded px-1"
              />
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-100 text-[#94A3B8] font-medium">
                Build LangGraph{" "}
                <span className="bg-gradient-to-r from-blue-500 via-purple-500 via-pink-500 to-orange-500 bg-clip-text text-transparent font-bold">
                  visually
                </span>
              </span>
            </div>
          </div>
        </div>

        {/* Center Navigation Pills */}
        <div className="flex items-center bg-[#F8FAFC] p-1 rounded-full border border-[#E5E7EB]">
          <button
            onClick={() => setActiveTab("canvas")}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === "canvas"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569]"
            }`}
          >
            <Layers className="w-3.5 h-3.5 inline mr-1.5" />
            Canvas ({nodes.length})
          </button>
          <button
            onClick={() => setActiveTab("memory")}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === "memory"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569]"
            }`}
          >
            <Database className="w-3.5 h-3.5 inline mr-1.5" />
            Browser RAG & Memory ({vectorDocs.length})
          </button>
          <button
            onClick={() => setActiveTab("evals")}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === "evals"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569]"
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5 inline mr-1.5" />
            Eval Harness ({evalRows.length})
          </button>
          <button
            onClick={() => setActiveTab("code")}
            className={`px-4 py-1.5 rounded-full text-xs font-semibold transition ${
              activeTab === "code"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#475569]"
            }`}
          >
            <Code2 className="w-3.5 h-3.5 inline mr-1.5" />
            Python LangGraph Code
          </button>
        </div>

        {/* Right Action Pill Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowVaultModal(true)}
            className="px-3.5 py-2 rounded-full border border-[#E5E7EB] bg-white hover:bg-slate-50 text-xs font-semibold text-[#0F172A] flex items-center gap-1.5"
          >
            <KeyRound className="w-3.5 h-3.5 text-[#94A3B8]" />
            Vault
          </button>

          <button
            onClick={handleSaveToMongoBackend}
            className="px-3.5 py-2 rounded-full border border-[#E5E7EB] bg-white hover:bg-slate-50 text-xs font-semibold text-[#0F172A] flex items-center gap-1.5"
          >
            {currentUser ? (
              <UserCheck className="w-3.5 h-3.5 text-[#16A34A]" />
            ) : (
              <CloudUpload className="w-3.5 h-3.5 text-[#3B82F6]" />
            )}
            {syncStatus || (currentUser ? currentUser.full_name.split(" ")[0] : "Cloud Sync")}
          </button>

          {/* Blue #3B82F6 Primary Run Button (Runs on Docker Backend via SSE) */}
          <button
            onClick={handleRunWorkflow}
            disabled={isRunning}
            className="px-5 py-2 rounded-full bg-[#3B82F6] hover:bg-blue-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            {isRunning ? "Executing..." : "Run"}
          </button>

          {/* Green #16A34A Browser-Native ZIP Export Button */}
          <button
            onClick={() =>
              downloadMicroserviceZipInBrowser(workspaceName, compiledFiles)
            }
            className="px-5 py-2 rounded-full bg-[#16A34A] hover:bg-green-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Download className="w-3.5 h-3.5" />
            Export Python ZIP
          </button>

          {/* Purple #7C3AED Publish Button */}
          <button
            onClick={() => setActiveTab("code")}
            className="px-4 py-2 rounded-full bg-[#7C3AED] hover:bg-purple-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
          >
            <Share2 className="w-3.5 h-3.5" />
            Publish
          </button>
        </div>
      </header>

      {/* ─── N8N-STYLE WORKFLOW TABS BAR ─── */}
      <div className="h-11 bg-white border-b border-[#E5E7EB] px-6 flex items-center gap-1.5 overflow-x-auto shadow-xs z-20">
        <div className="flex items-center gap-1 text-[11px] font-bold text-[#94A3B8] uppercase tracking-wider mr-2 shrink-0">
          <Workflow className="w-3.5 h-3.5 text-[#3B82F6]" />
          <span>Workflows:</span>
        </div>

        {tabs.map((tab) => {
          const isActive = tab.id === activeTabId;
          return (
            <div
              key={tab.id}
              onClick={() => handleSwitchTab(tab.id)}
              className={`group flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition border shrink-0 ${
                isActive
                  ? "bg-blue-50/70 border-blue-300 text-[#0F172A] shadow-xs"
                  : "bg-[#F8FAFC] border-[#E5E7EB] text-[#64748B] hover:bg-slate-100 hover:text-[#0F172A]"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isActive ? "bg-[#3B82F6]" : "bg-slate-300"
                }`}
              />
              <span className="max-w-[170px] truncate">{tab.name}</span>
              {tabs.length > 1 && (
                <button
                  onClick={(e) => handleCloseTab(e, tab.id)}
                  title="Close tab"
                  className="opacity-0 group-hover:opacity-100 hover:text-rose-500 rounded p-0.5 transition ml-0.5"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          );
        })}

        <button
          onClick={handleCreateNewTab}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-dashed border-[#CBD5E1] hover:border-[#3B82F6] hover:text-[#3B82F6] text-xs font-medium text-[#94A3B8] transition ml-1 shrink-0"
          title="Create New Workflow Tab"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Workflow</span>
        </button>
      </div>

      {/* ─── WORKSPACE BODY ─── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left 9-Category Node Palette */}
        <aside className="w-64 bg-white border-r border-[#E5E7EB] p-4 overflow-y-auto space-y-3">
          <div className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">
            9 Node Categories
          </div>
          <div className="space-y-2">
            {(Object.keys(NODE_CATEGORIES) as NodeCategoryKey[]).map((catKey) => {
              const cat = NODE_CATEGORIES[catKey];
              return (
                <button
                  key={cat.key}
                  onClick={() => addCategoryNode(cat.key)}
                  className="w-full p-2.5 rounded-xl border border-[#E5E7EB] bg-white hover:border-blue-300 hover:shadow-soft transition flex items-center justify-between text-left group"
                >
                  <div className="flex items-center gap-2.5">
                    <span className={`w-3 h-3 rounded-full ${cat.dotColor}`} />
                    <div>
                      <div className="text-xs font-semibold text-[#0F172A]">
                        {cat.label}
                      </div>
                      <div className="text-[11px] text-[#94A3B8]">
                        {cat.defaultTitle}
                      </div>
                    </div>
                  </div>
                  <Plus className="w-4 h-4 text-[#94A3B8] group-hover:text-[#3B82F6]" />
                </button>
              );
            })}
          </div>
        </aside>

        {/* Center Main View */}
        <main className="flex-1 relative overflow-y-auto">
          {activeTab === "canvas" && (
            <div className="w-full h-[calc(100vh-4rem)]">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={(_, node) => setSelectedNodeId(node.id)}
                nodeTypes={nodeTypes}
                fitView
              >
                <Background color="#CBD5E1" gap={20} size={1.2} />
                <Controls className="!bg-white !border-[#E5E7EB] !rounded-xl !shadow-soft" />
              </ReactFlow>

              <div className="absolute bottom-6 right-6">
                <button
                  onClick={() => addCategoryNode("logic")}
                  className="px-5 py-3 rounded-full bg-[#3B82F6] hover:bg-blue-600 text-white text-xs font-semibold shadow-lg flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  + Add Conditional Router
                </button>
              </div>
            </div>
          )}

          {/* ─── TAB 2: IN-BROWSER VECTOR RAG & MEMORY HARNESS ─── */}
          {activeTab === "memory" && (
            <div className="p-8 max-w-4xl mx-auto space-y-6">
              <div className="bg-white rounded-2xl border border-[#E5E7EB] p-6 shadow-soft space-y-4">
                <h2 className="text-lg font-bold text-[#0F172A]">
                  In-Browser Vector Store & Thread Checkpointer
                </h2>
                <p className="text-xs text-[#475569]">
                  Add documents below. Your browser automatically computes embeddings and retrieves top-K chunks during live agent runs—and compiles to Pinecone, MongoDB Atlas, or PGVector on export.
                </p>
                <div className="flex gap-2">
                  <input
                    value={newDocText}
                    onChange={(e) => setNewDocText(e.target.value)}
                    placeholder="Paste a knowledge paragraph or policy rule to index in browser..."
                    className="flex-1 px-4 py-2.5 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
                  />
                  <button
                    onClick={() => {
                      if (!newDocText.trim()) return;
                      BrowserMemoryHarness.addDocument(newDocText);
                      setVectorDocs(BrowserMemoryHarness.getDocuments());
                      setNewDocText("");
                    }}
                    className="px-5 py-2.5 rounded-full bg-[#3B82F6] text-white text-xs font-semibold"
                  >
                    + Index Chunk in Browser
                  </button>
                </div>

                <div className="space-y-2 pt-2">
                  {vectorDocs.map((doc) => (
                    <div
                      key={doc.id}
                      className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] flex items-start justify-between gap-4"
                    >
                      <div className="space-y-1">
                        <div className="text-xs font-semibold text-[#0F172A]">
                          {doc.text}
                        </div>
                        <div className="text-[11px] text-[#94A3B8]">
                          Source: {doc.metadata.source} • Vector Dim: {doc.embedding.length}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ─── TAB 3: IN-BROWSER TRAJECTORY & OUTPUT EVAL HARNESS ─── */}
          {activeTab === "evals" && (
            <div className="p-8 max-w-5xl mx-auto space-y-6">
              <div className="bg-white rounded-2xl border border-[#E5E7EB] p-6 shadow-soft space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-[#0F172A]">
                      Trajectory & Output Evaluation Suite
                    </h2>
                    <p className="text-xs text-[#475569]">
                      Executes all dataset rows in-browser, verifying that the agent visits the expected nodes and matches target assertions.
                    </p>
                  </div>
                  <button
                    onClick={handleRunBatchEvals}
                    disabled={isRunning}
                    className="px-6 py-2.5 rounded-full bg-[#3B82F6] text-white text-xs font-semibold shadow-sm"
                  >
                    {isRunning ? "Running Suite..." : "Run Full Eval Suite"}
                  </button>
                </div>

                <div className="space-y-3 pt-2">
                  {evalRows.map((row) => {
                    const res = evalResults.find((r) => r.id === row.id);
                    return (
                      <div
                        key={row.id}
                        className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-[#0F172A]">
                            Query: "{row.input}"
                          </span>
                          {res && (
                            <span
                              className={`text-xs font-semibold px-3 py-0.5 rounded-full flex items-center gap-1 ${
                                res.overallPassed
                                  ? "bg-green-100 text-[#16A34A]"
                                  : "bg-rose-100 text-rose-600"
                              }`}
                            >
                              {res.overallPassed ? (
                                <CheckCircle2 className="w-3.5 h-3.5" />
                              ) : (
                                <XCircle className="w-3.5 h-3.5" />
                              )}
                              {res.overallPassed ? "PASSED" : "FAILED"} ({res.latencyMs}ms)
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#94A3B8]">
                          Expected Trajectory: {row.expectedTrajectory.join(" → ")} | Must Contain:{" "}
                          <b>"{row.expectedKeyword}"</b>
                        </div>
                        {res && (
                          <div className="text-xs text-[#475569] bg-white p-2.5 rounded-lg border border-[#E5E7EB]">
                            <b>Actual Output:</b> {res.actualOutput}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ─── TAB 4: 100% IN-BROWSER LIVE PYTHON COMPILER PREVIEW ─── */}
          {activeTab === "code" && (
            <div className="p-8 max-w-5xl mx-auto space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-2">
                  {Object.keys(compiledFiles).map((fname) => (
                    <button
                      key={fname}
                      onClick={() => setSelectedFile(fname)}
                      className={`px-4 py-1.5 rounded-full text-xs font-semibold border transition ${
                        selectedFile === fname
                          ? "bg-[#0F172A] text-white border-[#0F172A]"
                          : "bg-white text-[#475569] border-[#E5E7EB]"
                      }`}
                    >
                      {fname}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() =>
                    downloadMicroserviceZipInBrowser(workspaceName, compiledFiles)
                  }
                  className="px-5 py-2 rounded-full bg-[#16A34A] text-white text-xs font-semibold flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Microservice (.zip)
                </button>
              </div>

              <pre className="bg-white border border-[#E5E7EB] rounded-2xl p-6 text-xs text-[#0F172A] overflow-x-auto shadow-soft leading-relaxed font-mono">
                {compiledFiles[selectedFile]}
              </pre>
            </div>
          )}
        </main>

        {/* Right Side: Node Inspector (if node clicked) OR Live Execution Trace Drawer */}
        {selectedNode ? (
          <NodeInspector
            selectedNode={selectedNode}
            onUpdateNode={updateNodeData}
            onDeleteNode={deleteNode}
            onClose={() => setSelectedNodeId(null)}
          />
        ) : (
          <aside className="w-80 bg-white border-l border-[#E5E7EB] p-4 flex flex-col justify-between">
            <div className="space-y-4 overflow-y-auto">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">
                  In-Browser Live Runner
                </h3>
                <div className="mt-2 space-y-2">
                  <textarea
                    rows={2}
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
                  />
                </div>
              </div>

              <div className="space-y-2.5">
                <div className="text-xs font-bold uppercase tracking-wider text-[#94A3B8]">
                  Live Step Traces ({traces.length})
                </div>
                {traces.length === 0 ? (
                  <div className="p-4 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] text-xs text-[#94A3B8]">
                    Click any node on the canvas to configure its prompt/DB, or click <b>Run</b> to execute in-browser.
                  </div>
                ) : (
                  traces.map((t, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-[#F8FAFC] border border-[#E5E7EB] space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[#0F172A] flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#16A34A]" />
                          {t.label}
                        </span>
                        <span className="text-[10px] text-[#94A3B8]">{t.latencyMs}ms</span>
                      </div>
                      <p className="text-xs text-[#475569] whitespace-pre-wrap break-words">
                        {t.output}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </aside>
        )}
      </div>

      {/* ─── N8N SERVER-SIDE CREDENTIAL VAULT MODAL ─── */}
      {showVaultModal && (
        <div className="fixed inset-0 bg-slate-900/20 backdrop-blur-xs flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl border border-[#E5E7EB] p-6 w-96 shadow-soft space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-[#0F172A]">
                API & DB Credential Vault
              </h3>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                Fernet Encrypted
              </span>
            </div>
            <p className="text-xs text-[#475569]">
              Keys are encrypted at rest on the backend for Docker execution, and cached in browser for offline runs.
            </p>
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-[#64748B]">OpenAI API Key</label>
              <input
                type="password"
                value={vault.openaiKey}
                onChange={(e) => setVault({ ...vault, openaiKey: e.target.value })}
                placeholder="sk-proj-..."
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-[#64748B]">Anthropic Claude Key</label>
              <input
                type="password"
                value={vault.anthropicKey}
                onChange={(e) => setVault({ ...vault, anthropicKey: e.target.value })}
                placeholder="sk-ant-..."
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-[#64748B]">Pinecone Key</label>
              <input
                type="password"
                value={vault.pineconeKey}
                onChange={(e) => setVault({ ...vault, pineconeKey: e.target.value })}
                placeholder="pcsk_..."
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowVaultModal(false)}
                className="px-4 py-2 rounded-full text-xs font-semibold text-[#475569]"
              >
                Close
              </button>
              <button
                onClick={async () => {
                  localStorage.setItem("VAULT_OPENAI", vault.openaiKey);
                  localStorage.setItem("VAULT_ANTHROPIC", vault.anthropicKey);
                  localStorage.setItem("VAULT_PINECONE", vault.pineconeKey);

                  try {
                    await fetch("/api/v1/vault", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        openai_key: vault.openaiKey,
                        anthropic_key: vault.anthropicKey,
                        pinecone_key: vault.pineconeKey,
                      }),
                    });
                  } catch (e) {
                    console.warn("Could not sync to backend vault:", e);
                  }

                  setShowVaultModal(false);
                }}
                className="px-5 py-2 rounded-full bg-[#3B82F6] text-white text-xs font-semibold hover:bg-blue-600 transition"
              >
                Save Credentials
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── JWT + BCRYPT CLOUD AUTH MODAL ─── */}
      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
        apiBase={API_BASE}
        onAuthSuccess={(tok, usr) => {
          setJwtToken(tok);
          setCurrentUser(usr);
        }}
      />
    </div>
  );
}
