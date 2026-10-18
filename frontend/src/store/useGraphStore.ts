import { create } from "zustand";
import type {
  GraphSchemaData,
  GraphNode,
  GraphEdge,
  StateField,
  GraphSettings,
  CodegenResult,
  NodeTypeDefinition,
  Diagnostic,
  SourcemapEntry,
  TriggerDefinition,
  ExecutionRecord,
} from "../types/graph";

const DEFAULT_GRAPH: GraphSchemaData = {
  schema_version: "1.0",
  state: {
    fields: [
      { name: "messages", type: "messages", reducer: "add_messages", default: [] },
    ],
    input_fields: ["messages"],
    output_fields: ["messages"],
  },
  nodes: [
    {
      id: "start",
      type: "triggers",
      label: "START",
      position: { x: 100, y: 260 },
      config: {},
      policy: { retry: {}, cache: {}, defer: false },
    },
    {
      id: "agent",
      type: "agent",
      label: "Reasoning Agent",
      position: { x: 380, y: 260 },
      config: {
        provider: "openai",
        model: "gpt-4o-mini",
        systemPrompt: "You are a helpful AI assistant.",
      },
      policy: { retry: {}, cache: {}, defer: false },
    },
    {
      id: "end",
      type: "output",
      label: "END",
      position: { x: 680, y: 260 },
      config: {},
      policy: { retry: {}, cache: {}, defer: false },
    },
  ],
  edges: [
    { id: "e_start_agent", source: "start", target: "agent", kind: "normal" },
    { id: "e_agent_end", source: "agent", target: "end", kind: "normal" },
  ],
  subgraphs: {},
  settings: {
    checkpointer: "sqlite",
    recursion_limit: 25,
    interrupt_before: [],
    interrupt_after: [],
    store: {},
    config_fields: [],
  },
};

interface GraphStore {
  // Persistence
  workflowId: string | null;
  workflowName: string;
  isSaving: boolean;
  lastSaved: string | null;

  // Graph single source of truth
  graph: GraphSchemaData;
  activeSubgraphId: string | null; // null = root canvas

  // Palette & Inspection
  nodeTypes: NodeTypeDefinition[];
  selectedNodeId: string | null;
  selectedEdgeId: string | null;

  // Live Code & Diagnostics
  generatedFiles: Record<string, string>;
  sourcemap: Record<string, SourcemapEntry>;
  diagnostics: Diagnostic[];
  activeFile: string;
  isCodePanelOpen: boolean;
  codePanelWidth: number;
  highlightedLines: { file: string; startLine: number; endLine: number } | null;
  flashLines: { file: string; startLine: number; endLine: number } | null;

  // Modals / Drawers
  isSettingsOpen: boolean;
  isStateSchemaOpen: boolean;

  // Execution & Streaming State
  isRunning: boolean;
  isInterrupted: boolean;
  activeRunId: string | null;
  nodeStatuses: Record<string, "idle" | "running" | "success" | "error" | "interrupted">;
  nodeOutputs: Record<string, any>;
  latestState: Record<string, any>;
  streamMode: "updates" | "values" | "messages" | "custom" | "debug";
  chatMessages: Array<{ id: string; role: "user" | "assistant" | "system"; content: string; ts: string }>;
  streamedTokens: string;
  interruptRequest: { prompt: string; fields: string[]; state_summary: any; run_id: string } | null;

  // Threads & Time Travel
  currentThreadId: string;
  threadsList: Array<{ thread_id: string; last_active?: string; run_count?: number; last_status?: string }>;
  checkpointsHistory: Array<{ checkpoint_id: string; parent_checkpoint_id?: string | null; values: any; next: string[]; metadata?: any }>;
  selectedCheckpointId: string | null;

  // Store Items
  storeItems: Array<{ key: string; value: any; updated_at?: string }>;

  // Panels
  isRunPanelOpen: boolean;
  isStateInspectorOpen: boolean;

  // Actions
  init: () => Promise<void>;
  loadWorkflow: (id?: string) => Promise<void>;
  saveWorkflow: () => Promise<void>;
  setWorkflowName: (name: string) => void;

  // Node Mutations
  addNode: (type: string, position: { x: number; y: number }, label?: string) => void;
  updateNode: (id: string, updates: Partial<GraphNode>) => void;
  updateNodeConfig: (id: string, config: Record<string, any>) => void;
  updateNodePolicy: (id: string, policy: Partial<GraphNode["policy"]>) => void;
  updateNodePosition: (id: string, position: { x: number; y: number }) => void;
  deleteNode: (id: string) => void;

  // Edge Mutations
  addEdge: (edge: GraphEdge) => void;
  updateEdge: (id: string, updates: Partial<GraphEdge>) => void;
  deleteEdge: (id: string) => void;

  // State Schema Mutations
  addStateField: (field: StateField) => void;
  updateStateField: (index: number, field: StateField) => void;
  deleteStateField: (index: number) => void;
  toggleInputField: (fieldName: string) => void;
  toggleOutputField: (fieldName: string) => void;

  // Settings
  updateSettings: (settings: Partial<GraphSettings>) => void;

  // Subgraph navigation
  enterSubgraph: (nodeId: string) => void;
  exitSubgraph: () => void;

  // Selection
  selectNode: (id: string | null) => void;
  selectEdge: (id: string | null) => void;
  selectCodeLine: (file: string, lineNumber: number) => void;

  // Panels & Views
  setActiveFile: (file: string) => void;
  setCodePanelOpen: (open: boolean) => void;
  setCodePanelWidth: (width: number) => void;
  setSettingsOpen: (open: boolean) => void;
  setStateSchemaOpen: (open: boolean) => void;
  setRunPanelOpen: (open: boolean) => void;
  setStateInspectorOpen: (open: boolean) => void;
  setStreamMode: (mode: "updates" | "values" | "messages" | "custom" | "debug") => void;
  toggleBreakpoint: (nodeId: string, position: "before" | "after") => void;

  // Execution & Time Travel Actions
  startRun: (inputMessage?: string, inputData?: Record<string, any>) => Promise<void>;
  resumeRun: (decision: any) => Promise<void>;
  cancelRun: () => Promise<void>;
  switchThread: (threadId: string) => Promise<void>;
  createNewThread: () => void;
  forkThread: (checkpointId: string) => Promise<void>;
  loadThreadHistory: (threadId?: string) => Promise<void>;
  updateCheckpointState: (values: Record<string, any>, asNode?: string) => Promise<void>;
  loadStore: (namespace?: string) => Promise<void>;
  saveStoreItem: (namespace: string, key: string, value: any) => Promise<void>;

  // Code Generation
  triggerCodegen: () => Promise<void>;

  // Generic Typed Credentials (Phase 6)
  credentials: Array<{
    id: string;
    name: string;
    type: string;
    masked_value: string;
    metadata: Record<string, any>;
    created_at: string;
  }>;
  isCredentialsOpen: boolean;
  setCredentialsOpen: (open: boolean) => void;
  loadCredentials: () => Promise<void>;
  createCredential: (name: string, type: string, value: string, metadata?: Record<string, any>) => Promise<any>;
  deleteCredential: (id: string) => Promise<void>;
  testCredential: (id: string) => Promise<{ success: boolean; message: string }>;
  testRawCredential: (type: string, value: string, metadata?: Record<string, any>) => Promise<{ success: boolean; message: string }>;

  // Pattern Blocks & Starter Templates (Phase 6)
  isPatternsGalleryOpen: boolean;
  setPatternsGalleryOpen: (open: boolean) => void;
  insertPattern: (patternId: string) => Promise<void>;
  loadStarterTemplate: (templateId: string) => Promise<void>;

  // Canvas Polish: Undo/Redo & Clipboard & Layout (Phase 7)
  past: GraphSchemaData[];
  future: GraphSchemaData[];
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  copiedNodes: GraphNode[];
  copySelectedNodes: () => void;
  pasteNodes: () => void;
  autoLayoutGraph: () => void;
  paletteSearchQuery: string;
  setPaletteSearchQuery: (query: string) => void;

  // Triggers (Webhooks & Cron) (Phase 7)
  triggers: TriggerDefinition[];
  isTriggersOpen: boolean;
  setTriggersOpen: (open: boolean) => void;
  loadTriggers: () => Promise<void>;
  createTrigger: (name: string, type: "webhook" | "cron", config: any, is_active?: boolean) => Promise<any>;
  updateTrigger: (id: string, updates: Partial<TriggerDefinition>) => Promise<any>;
  deleteTrigger: (id: string) => Promise<void>;

  // Executions Run History (Phase 7)
  executions: ExecutionRecord[];
  isRunHistoryOpen: boolean;
  setRunHistoryOpen: (open: boolean) => void;
  loadExecutions: () => Promise<void>;

  // JSON Import & Export (Phase 7)
  exportGraphJson: () => void;
  importGraphJson: (jsonStr: string) => Promise<{ success: boolean; message?: string }>;
}

let codegenTimer: any = null;
let autosaveTimer: any = null;

const scheduleAutosave = () => {
  if (autosaveTimer) clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    useGraphStore.getState().saveWorkflow();
  }, 800);
};

const scheduleCodegen = () => {
  if (codegenTimer) clearTimeout(codegenTimer);
  codegenTimer = setTimeout(() => {
    useGraphStore.getState().triggerCodegen();
    scheduleAutosave();
  }, 250);
};

const saveHistory = (get: () => GraphStore, set: any) => {
  const { graph, past } = get();
  try {
    const clone = JSON.parse(JSON.stringify(graph));
    set({
      past: [...past.slice(-29), clone],
      future: [],
    });
  } catch {
    // Ignore
  }
};

export const useGraphStore = create<GraphStore>((set, get) => ({
  workflowId: null,
  workflowName: "My Agent Flow",
  isSaving: false,
  lastSaved: null,

  graph: DEFAULT_GRAPH,
  activeSubgraphId: null,

  nodeTypes: [],
  selectedNodeId: null,
  selectedEdgeId: null,

  generatedFiles: {},
  sourcemap: {},
  diagnostics: [],
  activeFile: "graph.py",
  isCodePanelOpen: true,
  codePanelWidth: 460,
  highlightedLines: null,
  flashLines: null,

  isSettingsOpen: false,
  isStateSchemaOpen: false,

  // Execution & Streaming State
  isRunning: false,
  isInterrupted: false,
  activeRunId: null,
  nodeStatuses: {},
  nodeOutputs: {},
  latestState: {},
  streamMode: "updates",
  chatMessages: [
    {
      id: "m_welcome",
      role: "assistant",
      content: "Ready to run. Type a message or click 'Run' to execute the LangGraph workflow.",
      ts: new Date().toLocaleTimeString(),
    },
  ],
  streamedTokens: "",
  interruptRequest: null,

  // Threads & Time Travel
  currentThreadId: "default",
  threadsList: [{ thread_id: "default", run_count: 0, last_status: "idle" }],
  checkpointsHistory: [],
  selectedCheckpointId: null,

  // Store Items
  storeItems: [],

  // Panels
  isRunPanelOpen: true,
  isStateInspectorOpen: false,

  // Generic Typed Credentials (Phase 6)
  credentials: [],
  isCredentialsOpen: false,
  setCredentialsOpen: (open) => set({ isCredentialsOpen: open }),

  // Pattern Blocks & Starter Templates (Phase 6)
  isPatternsGalleryOpen: false,
  setPatternsGalleryOpen: (open) => set({ isPatternsGalleryOpen: open }),

  // Canvas Polish (Phase 7)
  past: [],
  future: [],
  canUndo: () => get().past.length > 0,
  canRedo: () => get().future.length > 0,
  copiedNodes: [],
  paletteSearchQuery: "",
  setPaletteSearchQuery: (query) => set({ paletteSearchQuery: query }),

  // Triggers (Phase 7)
  triggers: [],
  isTriggersOpen: false,
  setTriggersOpen: (open) => {
    set({ isTriggersOpen: open });
    if (open) {
      get().loadTriggers();
    }
  },

  // Executions (Phase 7)
  executions: [],
  isRunHistoryOpen: false,
  setRunHistoryOpen: (open) => {
    set({ isRunHistoryOpen: open });
    if (open) {
      get().loadExecutions();
    }
  },

  init: async () => {
    try {
      // Fetch node types
      const typesRes = await fetch("/api/v1/node-types");
      if (typesRes.ok) {
        const typesData = await typesRes.json();
        set({ nodeTypes: typesData });
      }
    } catch {
      // Ignore
    }

    // Load initial workflow and credentials
    await Promise.all([get().loadWorkflow(), get().loadCredentials()]);
  },

  loadWorkflow: async (id?: string) => {
    try {
      let wf: any = null;
      if (id) {
        const res = await fetch(`/api/v1/workflows/${id}`);
        if (res.ok) wf = await res.json();
      } else {
        const res = await fetch("/api/v1/workflows");
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list) && list.length > 0) {
            wf = list[0];
          }
        }
      }

      if (wf) {
        const graphData: GraphSchemaData = wf.graph && wf.graph.nodes ? wf.graph : DEFAULT_GRAPH;
        set({
          workflowId: wf.id,
          workflowName: wf.name || "My Agent Flow",
          graph: graphData,
          selectedNodeId: null,
          selectedEdgeId: null,
          activeSubgraphId: null,
        });
      } else {
        // Fallback default
        set({
          workflowId: "default",
          workflowName: "My Agent Flow",
          graph: DEFAULT_GRAPH,
        });
      }
    } catch {
      set({
        workflowId: "default",
        workflowName: "My Agent Flow",
        graph: DEFAULT_GRAPH,
      });
    }

    // Trigger codegen on initial load
    get().triggerCodegen();
  },

  saveWorkflow: async () => {
    const { workflowId, workflowName, graph } = get();
    if (!workflowId) return;

    set({ isSaving: true });
    try {
      const res = await fetch(`/api/v1/workflows/${workflowId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: workflowName,
          graph,
        }),
      });
      if (res.ok) {
        set({ isSaving: false, lastSaved: new Date().toLocaleTimeString() });
      } else {
        set({ isSaving: false });
      }
    } catch {
      set({ isSaving: false });
    }
  },

  setWorkflowName: (name: string) => {
    set({ workflowName: name });
    scheduleAutosave();
  },

  triggerCodegen: async () => {
    const { graph, selectedNodeId, activeFile } = get();
    try {
      const res = await fetch("/api/v1/codegen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(graph),
      });
      if (res.ok) {
        const data: CodegenResult = await res.json();
        const sourcemap = data.sourcemap || {};
        const files = data.files || {};
        const diagnostics = data.diagnostics || [];

        // Update highlighted lines if selected node exists
        let highlighted = null;
        if (selectedNodeId && sourcemap[selectedNodeId]) {
          const entry = sourcemap[selectedNodeId];
          highlighted = {
            file: entry.file,
            startLine: entry.start_line,
            endLine: entry.end_line,
          };
        }

        set({
          generatedFiles: files,
          sourcemap,
          diagnostics,
          highlightedLines: highlighted,
          activeFile: files[activeFile] ? activeFile : Object.keys(files)[0] || "graph.py",
        });
      }
    } catch {
      // Ignore
    }
  },

  addNode: (type: string, position: { x: number; y: number }, label?: string) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId, nodeTypes } = get();
    const id = `node_${Date.now().toString(36)}`;
    const typeDef = nodeTypes.find((t) => t.type === type);
    const defaultLabel = label || typeDef?.label || type.toUpperCase();
    const defaultConfig = typeDef?.default_config ? JSON.parse(JSON.stringify(typeDef.default_config)) : {};

    const newNode: GraphNode = {
      id,
      type,
      label: defaultLabel,
      position,
      config: defaultConfig,
      policy: { retry: {}, cache: {}, defer: false },
    };

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      const updatedSub = {
        ...sub,
        nodes: [...sub.nodes, newNode],
      };
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: updatedSub,
          },
        },
        selectedNodeId: id,
        selectedEdgeId: null,
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: [...graph.nodes, newNode],
        },
        selectedNodeId: id,
        selectedEdgeId: null,
      });
    }

    scheduleCodegen();
  },

  updateNode: (id: string, updates: Partial<GraphNode>) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      const updatedNodes = sub.nodes.map((n) => (n.id === id ? { ...n, ...updates } : n));
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: { ...sub, nodes: updatedNodes },
          },
        },
      });
    } else {
      const updatedNodes = graph.nodes.map((n) => (n.id === id ? { ...n, ...updates } : n));
      set({
        graph: {
          ...graph,
          nodes: updatedNodes,
        },
      });
    }

    scheduleCodegen();
  },

  updateNodeConfig: (id: string, config: Record<string, any>) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId } = get();

    const updater = (n: GraphNode) => {
      if (n.id !== id) return n;
      return { ...n, config: { ...n.config, ...config } };
    };

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: { ...sub, nodes: sub.nodes.map(updater) },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: graph.nodes.map(updater),
        },
      });
    }

    scheduleCodegen();
  },

  updateNodePolicy: (id: string, policy: Partial<GraphNode["policy"]>) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId } = get();

    const updater = (n: GraphNode) => {
      if (n.id !== id) return n;
      return { ...n, policy: { ...n.policy, ...policy } };
    };

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: { ...sub, nodes: sub.nodes.map(updater) },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: graph.nodes.map(updater),
        },
      });
    }

    scheduleCodegen();
  },

  updateNodePosition: (id: string, position: { x: number; y: number }) => {
    const { graph, activeSubgraphId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: {
              ...sub,
              nodes: sub.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
            },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: graph.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
        },
      });
    }

    // Schedule autosave only (position change does not change generated Python code)
    scheduleAutosave();
  },

  deleteNode: (id: string) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId, selectedNodeId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      const updatedNodes = sub.nodes.filter((n) => n.id !== id);
      const updatedEdges = sub.edges.filter((e) => e.source !== id && e.target !== id);
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: { ...sub, nodes: updatedNodes, edges: updatedEdges },
          },
        },
        selectedNodeId: selectedNodeId === id ? null : selectedNodeId,
      });
    } else {
      const updatedNodes = graph.nodes.filter((n) => n.id !== id);
      const updatedEdges = graph.edges.filter((e) => e.source !== id && e.target !== id);
      set({
        graph: {
          ...graph,
          nodes: updatedNodes,
          edges: updatedEdges,
        },
        selectedNodeId: selectedNodeId === id ? null : selectedNodeId,
      });
    }

    scheduleCodegen();
  },

  addEdge: (edge: GraphEdge) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: {
              ...sub,
              edges: [...sub.edges, edge],
            },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          edges: [...graph.edges, edge],
        },
      });
    }

    scheduleCodegen();
  },

  updateEdge: (id: string, updates: Partial<GraphEdge>) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: {
              ...sub,
              edges: sub.edges.map((e) => (e.id === id ? { ...e, ...updates } : e)),
            },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          edges: graph.edges.map((e) => (e.id === id ? { ...e, ...updates } : e)),
        },
      });
    }

    scheduleCodegen();
  },

  deleteEdge: (id: string) => {
    saveHistory(get, set);
    const { graph, activeSubgraphId, selectedEdgeId } = get();

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: {
              ...sub,
              edges: sub.edges.filter((e) => e.id !== id),
            },
          },
        },
        selectedEdgeId: selectedEdgeId === id ? null : selectedEdgeId,
      });
    } else {
      set({
        graph: {
          ...graph,
          edges: graph.edges.filter((e) => e.id !== id),
        },
        selectedEdgeId: selectedEdgeId === id ? null : selectedEdgeId,
      });
    }

    scheduleCodegen();
  },

  addStateField: (field: StateField) => {
    saveHistory(get, set);
    const { graph } = get();
    const existing = graph.state.fields || [];
    set({
      graph: {
        ...graph,
        state: {
          ...graph.state,
          fields: [...existing, field],
        },
      },
    });
    scheduleCodegen();
  },

  updateStateField: (index: number, field: StateField) => {
    saveHistory(get, set);
    const { graph } = get();
    const updated = [...graph.state.fields];
    updated[index] = field;
    set({
      graph: {
        ...graph,
        state: {
          ...graph.state,
          fields: updated,
        },
      },
    });
    scheduleCodegen();
  },

  deleteStateField: (index: number) => {
    saveHistory(get, set);
    const { graph } = get();
    const updated = graph.state.fields.filter((_, i) => i !== index);
    set({
      graph: {
        ...graph,
        state: {
          ...graph.state,
          fields: updated,
        },
      },
    });
    scheduleCodegen();
  },

  toggleInputField: (fieldName: string) => {
    saveHistory(get, set);
    const { graph } = get();
    const current = graph.state.input_fields || [];
    const updated = current.includes(fieldName)
      ? current.filter((f) => f !== fieldName)
      : [...current, fieldName];
    set({
      graph: {
        ...graph,
        state: {
          ...graph.state,
          input_fields: updated,
        },
      },
    });
    scheduleCodegen();
  },

  toggleOutputField: (fieldName: string) => {
    saveHistory(get, set);
    const { graph } = get();
    const current = graph.state.output_fields || [];
    const updated = current.includes(fieldName)
      ? current.filter((f) => f !== fieldName)
      : [...current, fieldName];
    set({
      graph: {
        ...graph,
        state: {
          ...graph.state,
          output_fields: updated,
        },
      },
    });
    scheduleCodegen();
  },

  updateSettings: (settings: Partial<GraphSettings>) => {
    saveHistory(get, set);
    const { graph } = get();
    set({
      graph: {
        ...graph,
        settings: {
          ...graph.settings,
          ...settings,
        },
      },
    });
    scheduleCodegen();
  },

  enterSubgraph: (nodeId: string) => {
    const { graph } = get();
    // Ensure subgraph entry exists
    if (!graph.subgraphs[nodeId]) {
      const subgraphs = {
        ...graph.subgraphs,
        [nodeId]: {
          nodes: [
            { id: "sub_start", type: "triggers", label: "START", position: { x: 80, y: 200 }, config: {}, policy: {} },
            { id: "sub_task", type: "agent", label: "Subflow Step", position: { x: 300, y: 200 }, config: {}, policy: {} },
            { id: "sub_end", type: "output", label: "END", position: { x: 540, y: 200 }, config: {}, policy: {} },
          ],
          edges: [
            { id: "sub_e1", source: "sub_start", target: "sub_task", kind: "normal" as const },
            { id: "sub_e2", source: "sub_task", target: "sub_end", kind: "normal" as const },
          ],
        },
      };
      set({ graph: { ...graph, subgraphs }, activeSubgraphId: nodeId, selectedNodeId: null, selectedEdgeId: null });
    } else {
      set({ activeSubgraphId: nodeId, selectedNodeId: null, selectedEdgeId: null });
    }
  },

  exitSubgraph: () => {
    set({ activeSubgraphId: null, selectedNodeId: null, selectedEdgeId: null });
  },

  selectNode: (id: string | null) => {
    const { sourcemap } = get();
    set({ selectedNodeId: id, selectedEdgeId: null });

    if (id && sourcemap[id]) {
      const entry = sourcemap[id];
      set({
        activeFile: entry.file,
        highlightedLines: {
          file: entry.file,
          startLine: entry.start_line,
          endLine: entry.end_line,
        },
      });
    }
  },

  selectEdge: (id: string | null) => {
    const { sourcemap } = get();
    set({ selectedEdgeId: id, selectedNodeId: null });

    const key = `edge:${id}`;
    if (id && sourcemap[key]) {
      const entry = sourcemap[key];
      set({
        activeFile: entry.file,
        highlightedLines: {
          file: entry.file,
          startLine: entry.start_line,
          endLine: entry.end_line,
        },
      });
    }
  },

  selectCodeLine: (file: string, lineNumber: number) => {
    const { sourcemap, graph } = get();
    // Search sourcemap for entry covering lineNumber in file
    for (const [key, entry] of Object.entries(sourcemap)) {
      if (entry.file === file && lineNumber >= entry.start_line && lineNumber <= entry.end_line) {
        if (key.startsWith("edge:")) {
          const edgeId = key.replace("edge:", "");
          set({ selectedEdgeId: edgeId, selectedNodeId: null });
          return;
        } else if (key !== "state") {
          // Node ID
          const nodeExists = graph.nodes.some((n) => n.id === key);
          if (nodeExists) {
            set({ selectedNodeId: key, selectedEdgeId: null });
            return;
          }
        }
      }
    }
  },

  setActiveFile: (file: string) => {
    set({ activeFile: file });
  },

  setCodePanelOpen: (open: boolean) => {
    set({ isCodePanelOpen: open });
  },

  setCodePanelWidth: (width: number) => {
    set({ codePanelWidth: Math.max(300, Math.min(800, width)) });
  },

  setSettingsOpen: (open: boolean) => {
    set({ isSettingsOpen: open });
  },

  setStateSchemaOpen: (open: boolean) => {
    set({ isStateSchemaOpen: open });
  },

  setRunPanelOpen: (open: boolean) => {
    set({ isRunPanelOpen: open });
  },

  setStateInspectorOpen: (open: boolean) => {
    set({ isStateInspectorOpen: open });
  },

  setStreamMode: (mode) => {
    set({ streamMode: mode });
  },

  toggleBreakpoint: (nodeId: string, position: "before" | "after") => {
    const { graph } = get();
    const settings = graph.settings || { interrupt_before: [], interrupt_after: [] };
    const key = position === "before" ? "interrupt_before" : "interrupt_after";
    const current = settings[key] || [];
    const exists = current.includes(nodeId);
    const updatedList = exists ? current.filter((id) => id !== nodeId) : [...current, nodeId];

    const updatedNodes = graph.nodes.map((n) => {
      if (n.id !== nodeId) return n;
      const pol = n.policy || {};
      return {
        ...n,
        policy: {
          ...pol,
          [position === "before" ? "interrupt_before" : "interrupt_after"]: !exists,
        },
      };
    });

    set({
      graph: {
        ...graph,
        nodes: updatedNodes,
        settings: {
          ...settings,
          [key]: updatedList,
        },
      },
    });
    scheduleCodegen();
  },

  startRun: async (inputMessage?: string, inputData?: Record<string, any>) => {
    const { graph, currentThreadId, streamMode, chatMessages } = get();
    const newChat = [...chatMessages];
    if (inputMessage) {
      newChat.push({
        id: `msg_${Date.now()}`,
        role: "user",
        content: inputMessage,
        ts: new Date().toLocaleTimeString(),
      });
    }

    // Reset node execution statuses
    const initialStatuses: Record<string, "idle"> = {};
    for (const n of graph.nodes) {
      initialStatuses[n.id] = "idle";
    }

    set({
      isRunning: true,
      isInterrupted: false,
      interruptRequest: null,
      streamedTokens: "",
      chatMessages: newChat,
      nodeStatuses: initialStatuses,
    });

    try {
      const res = await fetch("/api/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          graph,
          thread_id: currentThreadId,
          stream_mode: streamMode,
          message: inputMessage,
          input: inputData || {},
        }),
      });

      if (!res.ok) {
        set({ isRunning: false });
        return;
      }

      await readStreamEvents(res, get, set);
    } catch {
      set({ isRunning: false });
    }
  },

  resumeRun: async (decision: any) => {
    const { graph, currentThreadId, streamMode, chatMessages } = get();
    const decisionStr = typeof decision === "string" ? decision : JSON.stringify(decision);
    const newChat = [
      ...chatMessages,
      {
        id: `msg_resume_${Date.now()}`,
        role: "user" as const,
        content: `[Decision Submitted] ${decisionStr}`,
        ts: new Date().toLocaleTimeString(),
      },
    ];

    set({
      isRunning: true,
      isInterrupted: false,
      interruptRequest: null,
      streamedTokens: "",
      chatMessages: newChat,
    });

    try {
      const res = await fetch("/api/v1/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          graph,
          thread_id: currentThreadId,
          stream_mode: streamMode,
          resume: decision,
        }),
      });

      if (!res.ok) {
        set({ isRunning: false });
        return;
      }

      await readStreamEvents(res, get, set);
    } catch {
      set({ isRunning: false });
    }
  },

  cancelRun: async () => {
    const { activeRunId } = get();
    if (!activeRunId) return;
    try {
      await fetch(`/api/v1/runs/${activeRunId}/cancel`, { method: "POST" });
    } catch {
      // Ignore
    }
    set({ isRunning: false });
  },

  switchThread: async (threadId: string) => {
    set({ currentThreadId: threadId, selectedCheckpointId: null });
    await get().loadThreadHistory(threadId);
  },

  createNewThread: () => {
    const newId = `th_${Date.now().toString(36)}`;
    const { threadsList } = get();
    set({
      currentThreadId: newId,
      threadsList: [{ thread_id: newId, run_count: 0, last_status: "idle" }, ...threadsList],
      checkpointsHistory: [],
      selectedCheckpointId: null,
      latestState: {},
      nodeStatuses: {},
      chatMessages: [
        {
          id: `msg_new_${Date.now()}`,
          role: "assistant",
          content: `Switched to new thread: ${newId}. Type a message to execute.`,
          ts: new Date().toLocaleTimeString(),
        },
      ],
    });
  },

  forkThread: async (checkpointId: string) => {
    const { currentThreadId, threadsList } = get();
    const forkedId = `fork_${Date.now().toString(36)}`;
    try {
      const res = await fetch(`/api/v1/threads/${currentThreadId}/fork`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          from_checkpoint_id: checkpointId,
          new_thread_id: forkedId,
        }),
      });
      if (res.ok) {
        set({
          currentThreadId: forkedId,
          threadsList: [{ thread_id: forkedId, run_count: 0, last_status: "idle" }, ...threadsList],
        });
        await get().loadThreadHistory(forkedId);
      }
    } catch {
      // Ignore
    }
  },

  loadThreadHistory: async (threadId?: string) => {
    const tid = threadId || get().currentThreadId;
    try {
      // Fetch history checkpoints
      const res = await fetch(`/api/v1/threads/${tid}/history`);
      if (res.ok) {
        const data = await res.json();
        set({ checkpointsHistory: data.history || [] });
      }

      // Fetch latest state
      const stateRes = await fetch(`/api/v1/threads/${tid}/state`);
      if (stateRes.ok) {
        const stateData = await stateRes.json();
        if (stateData.values) {
          set({ latestState: stateData.values });
        }
      }

      // Fetch threads list
      const listRes = await fetch("/api/v1/threads");
      if (listRes.ok) {
        const listData = await listRes.json();
        if (Array.isArray(listData) && listData.length > 0) {
          set({ threadsList: listData });
        }
      }
    } catch {
      // Ignore
    }
  },

  updateCheckpointState: async (values: Record<string, any>, asNode = "user_edit") => {
    const { currentThreadId, selectedCheckpointId } = get();
    try {
      const res = await fetch(`/api/v1/threads/${currentThreadId}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          values,
          as_node: asNode,
          checkpoint_id: selectedCheckpointId || undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        set({ latestState: data.values || values });
        await get().loadThreadHistory();
      }
    } catch {
      // Ignore
    }
  },

  loadStore: async (namespace = "memories") => {
    try {
      const res = await fetch(`/api/v1/store?namespace=${encodeURIComponent(namespace)}`);
      if (res.ok) {
        const data = await res.json();
        set({ storeItems: data.items || [] });
      }
    } catch {
      // Ignore
    }
  },

  saveStoreItem: async (namespace: string, key: string, value: any) => {
    try {
      const res = await fetch("/api/v1/store", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ namespace, key, value }),
      });
      if (res.ok) {
        await get().loadStore(namespace);
      }
    } catch {
      // Ignore
    }
  },

  loadCredentials: async () => {
    try {
      const res = await fetch("/api/v1/credentials");
      if (res.ok) {
        const data = await res.json();
        set({ credentials: data });
      }
    } catch (e) {
      console.error("Failed to load credentials:", e);
    }
  },

  createCredential: async (name: string, type: string, value: string, metadata: Record<string, any> = {}) => {
    const res = await fetch("/api/v1/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, type, value, metadata }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to create credential" }));
      throw new Error(err.detail || "Failed to create credential");
    }
    const created = await res.json();
    set((s) => ({ credentials: [created, ...s.credentials] }));
    return created;
  },

  deleteCredential: async (id: string) => {
    const res = await fetch(`/api/v1/credentials/${id}`, { method: "DELETE" });
    if (res.ok) {
      set((s) => ({ credentials: s.credentials.filter((c) => c.id !== id) }));
    }
  },

  testCredential: async (id: string) => {
    const res = await fetch(`/api/v1/credentials/${id}/test`, { method: "POST" });
    return await res.json();
  },

  testRawCredential: async (type: string, value: string, metadata: Record<string, any> = {}) => {
    const res = await fetch("/api/v1/credentials/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, value, metadata }),
    });
    return await res.json();
  },

  insertPattern: async (patternId: string) => {
    try {
      saveHistory(get, set);
      const currentNodes = get().graph.nodes;
      const maxX = currentNodes.reduce((max, n) => Math.max(max, n.position.x), 200);
      const res = await fetch(`/api/v1/patterns/${patternId}/instantiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offset_x: maxX + 280, offset_y: 200 }),
      });
      if (res.ok) {
        const { nodes: newNodes, edges: newEdges } = await res.json();
        set((s) => ({
          graph: {
            ...s.graph,
            nodes: [...s.graph.nodes, ...newNodes],
            edges: [...s.graph.edges, ...newEdges],
          },
        }));
        scheduleCodegen();
      }
    } catch (e) {
      console.error("Failed to insert pattern:", e);
    }
  },

  loadStarterTemplate: async (templateId: string) => {
    try {
      saveHistory(get, set);
      const res = await fetch(`/api/v1/templates/${templateId}`);
      if (res.ok) {
        const tpl = await res.json();
        set({
          workflowName: tpl.name,
          graph: tpl.graph,
          selectedNodeId: null,
          selectedEdgeId: null,
          isPatternsGalleryOpen: false,
        });
        scheduleCodegen();
      }
    } catch (e) {
      console.error("Failed to load template:", e);
    }
  },

  // ── Canvas Polish: Undo / Redo (Phase 7) ──────────────────────────────────
  undo: () => {
    const { past, future, graph } = get();
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    const newPast = past.slice(0, past.length - 1);
    set({
      graph: previous,
      past: newPast,
      future: [JSON.parse(JSON.stringify(graph)), ...future.slice(0, 29)],
      selectedNodeId: null,
      selectedEdgeId: null,
    });
    scheduleCodegen();
  },

  redo: () => {
    const { past, future, graph } = get();
    if (future.length === 0) return;
    const next = future[0];
    const newFuture = future.slice(1);
    set({
      graph: next,
      past: [...past.slice(-29), JSON.parse(JSON.stringify(graph))],
      future: newFuture,
      selectedNodeId: null,
      selectedEdgeId: null,
    });
    scheduleCodegen();
  },

  // ── Canvas Polish: Clipboard (Phase 7) ────────────────────────────────────
  copySelectedNodes: () => {
    const { graph, activeSubgraphId, selectedNodeId } = get();
    if (!selectedNodeId) return;
    const activeNodes = activeSubgraphId && graph.subgraphs[activeSubgraphId]
      ? graph.subgraphs[activeSubgraphId].nodes
      : graph.nodes;
    const targetNode = activeNodes.find((n) => n.id === selectedNodeId);
    if (targetNode) {
      set({ copiedNodes: [JSON.parse(JSON.stringify(targetNode))] });
    }
  },

  pasteNodes: () => {
    const { copiedNodes, graph, activeSubgraphId } = get();
    if (!copiedNodes || copiedNodes.length === 0) return;
    const nodeToCopy = copiedNodes[0];
    const newId = `node_${Date.now().toString(36)}`;
    const newNode: GraphNode = {
      ...JSON.parse(JSON.stringify(nodeToCopy)),
      id: newId,
      label: `${nodeToCopy.label} (Copy)`,
      position: {
        x: (nodeToCopy.position?.x || 240) + 40,
        y: (nodeToCopy.position?.y || 200) + 40,
      },
    };

    saveHistory(get, set);

    if (activeSubgraphId && graph.subgraphs[activeSubgraphId]) {
      const sub = graph.subgraphs[activeSubgraphId];
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId]: {
              ...sub,
              nodes: [...sub.nodes, newNode],
            },
          },
        },
        selectedNodeId: newId,
        selectedEdgeId: null,
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: [...graph.nodes, newNode],
        },
        selectedNodeId: newId,
        selectedEdgeId: null,
      });
    }
    scheduleCodegen();
  },

  // ── Canvas Polish: Auto-Layout (Phase 7) ──────────────────────────────────
  autoLayoutGraph: () => {
    const { graph, activeSubgraphId } = get();
    const isSub = Boolean(activeSubgraphId && graph.subgraphs[activeSubgraphId]);
    const activeData = isSub ? graph.subgraphs[activeSubgraphId!] : graph;
    const { nodes, edges } = activeData;
    if (!nodes || nodes.length === 0) return;

    saveHistory(get, set);

    // Build adjacency and in-degrees
    const adj: Record<string, string[]> = {};
    const inDegree: Record<string, number> = {};
    nodes.forEach((n) => {
      adj[n.id] = [];
      inDegree[n.id] = 0;
    });
    edges.forEach((e) => {
      if (adj[e.source]) adj[e.source].push(e.target);
      if (inDegree[e.target] !== undefined) {
        inDegree[e.target] = (inDegree[e.target] || 0) + 1;
      }
    });

    const ranks: Record<string, number> = {};
    const queue: string[] = [];

    // Root nodes: inDegree === 0 or 'start'
    nodes.forEach((n) => {
      if (n.id === "start" || n.type === "triggers" || (inDegree[n.id] === 0 && n.id !== "end")) {
        ranks[n.id] = 0;
        queue.push(n.id);
      }
    });

    if (queue.length === 0 && nodes.length > 0) {
      ranks[nodes[0].id] = 0;
      queue.push(nodes[0].id);
    }

    while (queue.length > 0) {
      const curr = queue.shift()!;
      const currRank = ranks[curr] || 0;
      const neighbors = adj[curr] || [];
      for (const nbr of neighbors) {
        const nextRank = currRank + 1;
        if (ranks[nbr] === undefined || ranks[nbr] < nextRank) {
          ranks[nbr] = nextRank;
          queue.push(nbr);
        }
      }
    }

    // Default unranked nodes to rank 1
    nodes.forEach((n) => {
      if (ranks[n.id] === undefined) {
        ranks[n.id] = n.id === "end" || n.type === "output" ? 3 : 1;
      }
    });

    // End node gets the max rank + 1
    let maxRank = Math.max(...Object.values(ranks), 0);
    nodes.forEach((n) => {
      if (n.id === "end" || n.type === "output") {
        ranks[n.id] = maxRank + 1;
      }
    });

    // Group nodes by assigned rank
    const rankGroups: Record<number, GraphNode[]> = {};
    nodes.forEach((n) => {
      const r = ranks[n.id] || 0;
      if (!rankGroups[r]) rankGroups[r] = [];
      rankGroups[r].push(n);
    });

    const updatedNodes = nodes.map((n) => {
      const r = ranks[n.id] || 0;
      const group = rankGroups[r] || [n];
      const indexInGroup = group.findIndex((gn) => gn.id === n.id);
      const totalInGroup = group.length;

      const x = 120 + r * 280;
      const totalHeight = (totalInGroup - 1) * 140;
      const startY = 240 - totalHeight / 2;
      const y = Math.max(80, startY + (indexInGroup >= 0 ? indexInGroup : 0) * 140);

      return {
        ...n,
        position: { x, y },
      };
    });

    if (isSub) {
      set({
        graph: {
          ...graph,
          subgraphs: {
            ...graph.subgraphs,
            [activeSubgraphId!]: {
              ...activeData,
              nodes: updatedNodes,
            },
          },
        },
      });
    } else {
      set({
        graph: {
          ...graph,
          nodes: updatedNodes,
        },
      });
    }
    scheduleCodegen();
  },

  // ── Triggers (Webhooks & Cron) (Phase 7) ───────────────────────────────────
  loadTriggers: async () => {
    const { workflowId } = get();
    if (!workflowId) return;
    try {
      const res = await fetch(`/api/v1/workflows/${workflowId}/triggers`);
      if (res.ok) {
        const data = await res.json();
        set({ triggers: data });
      }
    } catch {
      // Ignore
    }
  },

  createTrigger: async (name: string, type: "webhook" | "cron", config: any, is_active: boolean = true) => {
    const { workflowId } = get();
    if (!workflowId) return;
    const res = await fetch(`/api/v1/workflows/${workflowId}/triggers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, type, config, is_active }),
    });
    if (res.ok) {
      const created = await res.json();
      set((s) => ({ triggers: [created, ...s.triggers] }));
      return created;
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to create trigger");
  },

  updateTrigger: async (id: string, updates: Partial<TriggerDefinition>) => {
    const res = await fetch(`/api/v1/triggers/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (res.ok) {
      const updated = await res.json();
      set((s) => ({
        triggers: s.triggers.map((t) => (t.id === id ? updated : t)),
      }));
      return updated;
    }
    const err = await res.json();
    throw new Error(err.detail || "Failed to update trigger");
  },

  deleteTrigger: async (id: string) => {
    const res = await fetch(`/api/v1/triggers/${id}`, { method: "DELETE" });
    if (res.ok) {
      set((s) => ({
        triggers: s.triggers.filter((t) => t.id !== id),
      }));
    }
  },

  // ── Executions Run History (Phase 7) ───────────────────────────────────────
  loadExecutions: async () => {
    const { workflowId } = get();
    if (!workflowId) return;
    try {
      const res = await fetch(`/api/v1/workflows/${workflowId}/executions`);
      if (res.ok) {
        const data = await res.json();
        set({ executions: data });
      }
    } catch {
      // Ignore
    }
  },

  // ── Import & Export Graph JSON (Phase 7) ──────────────────────────────────
  exportGraphJson: () => {
    const { graph, workflowName } = get();
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(graph, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${(workflowName || "workflow").replace(/\s+/g, "_")}_graph.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  },

  importGraphJson: async (jsonStr: string) => {
    try {
      const parsed = JSON.parse(jsonStr);
      if (!parsed || typeof parsed !== "object") {
        return { success: false, message: "Invalid JSON format" };
      }
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        return { success: false, message: "JSON must contain 'nodes' and 'edges' arrays" };
      }
      saveHistory(get, set);
      set({
        graph: {
          schema_version: parsed.schema_version || "1.0",
          state: parsed.state || { fields: [], input_fields: [], output_fields: [] },
          nodes: parsed.nodes,
          edges: parsed.edges,
          subgraphs: parsed.subgraphs || {},
          settings: parsed.settings || {
            checkpointer: "sqlite",
            recursion_limit: 25,
            interrupt_before: [],
            interrupt_after: [],
            store: {},
            config_fields: [],
          },
        },
        selectedNodeId: null,
        selectedEdgeId: null,
      });
      scheduleCodegen();
      return { success: true };
    } catch (err: any) {
      return { success: false, message: err?.message || "Failed to parse JSON" };
    }
  },
}));

async function readStreamEvents(
  response: Response,
  get: () => GraphStore,
  set: (partial: Partial<GraphStore> | ((state: GraphStore) => Partial<GraphStore>)) => void
) {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice(5).trim();
      if (!jsonStr) continue;

      try {
        const ev = JSON.parse(jsonStr);
        const { nodeStatuses, nodeOutputs, latestState, chatMessages, streamedTokens } = get();

        if (ev.event === "start") {
          set({ activeRunId: ev.run_id, isRunning: true });
        } else if (ev.event === "node_start") {
          set({ nodeStatuses: { ...nodeStatuses, [ev.node]: "running" } });
        } else if (ev.event === "node_end") {
          set({
            nodeStatuses: { ...nodeStatuses, [ev.node]: "success" },
            nodeOutputs: { ...nodeOutputs, [ev.node]: ev.output },
          });
        } else if (ev.event === "state_update") {
          if (ev.node && ev.update) {
            set({
              nodeOutputs: { ...nodeOutputs, [ev.node]: ev.update },
              latestState: { ...latestState, ...(typeof ev.update === "object" ? ev.update : {}) },
            });
          } else if (ev.values) {
            set({ latestState: ev.values });
          }
        } else if (ev.event === "token") {
          set({ streamedTokens: streamedTokens + (ev.token || "") });
        } else if (ev.event === "interrupt") {
          const interrupts = ev.interrupts || [];
          const firstInt = interrupts[0] || {};
          const nextNodes = ev.next || [];
          const updatedStatuses = { ...nodeStatuses };
          for (const nid of nextNodes) {
            updatedStatuses[nid] = "interrupted";
          }
          set({
            isInterrupted: true,
            nodeStatuses: updatedStatuses,
            interruptRequest: {
              prompt: typeof firstInt === "object" ? firstInt.prompt || "Review required" : String(firstInt),
              fields: typeof firstInt === "object" ? firstInt.fields || [] : [],
              state_summary: typeof firstInt === "object" ? firstInt.state_summary || latestState : latestState,
              run_id: ev.run_id || get().activeRunId || "",
            },
          });
        } else if (ev.event === "final_state") {
          if (ev.values) set({ latestState: ev.values });
        } else if (ev.event === "done") {
          const isInter = ev.status === "interrupted";
          set({ isRunning: false, isInterrupted: isInter });
          if (streamedTokens) {
            set({
              chatMessages: [
                ...chatMessages,
                { id: `msg_${Date.now()}`, role: "assistant", content: streamedTokens, ts: new Date().toLocaleTimeString() },
              ],
              streamedTokens: "",
            });
          }
          get().loadThreadHistory();
        }
      } catch {
        // Ignore unparseable lines
      }
    }
  }
}
