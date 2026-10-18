import { useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Connection,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Undo2, Redo2, LayoutGrid, Copy, ClipboardPaste } from "lucide-react";

import { StartNode } from "./nodes/StartNode";
import { EndNode } from "./nodes/EndNode";
import { LangGraphNode } from "./nodes/LangGraphNode";
import { NormalEdge } from "./edges/NormalEdge";
import { ConditionalEdge } from "./edges/ConditionalEdge";
import { useGraphStore } from "../store/useGraphStore";
import { Breadcrumbs } from "./Breadcrumbs";

export function Canvas() {
  const graph = useGraphStore((s) => s.graph);
  const activeSubgraphId = useGraphStore((s) => s.activeSubgraphId);
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
  const selectNode = useGraphStore((s) => s.selectNode);
  const selectEdge = useGraphStore((s) => s.selectEdge);
  const addNode = useGraphStore((s) => s.addNode);
  const addGraphEdge = useGraphStore((s) => s.addEdge);
  const updateNodePosition = useGraphStore((s) => s.updateNodePosition);
  const undo = useGraphStore((s) => s.undo);
  const redo = useGraphStore((s) => s.redo);
  const canUndo = useGraphStore((s) => s.canUndo());
  const canRedo = useGraphStore((s) => s.canRedo());
  const copySelectedNodes = useGraphStore((s) => s.copySelectedNodes);
  const pasteNodes = useGraphStore((s) => s.pasteNodes);
  const autoLayoutGraph = useGraphStore((s) => s.autoLayoutGraph);
  const deleteNode = useGraphStore((s) => s.deleteNode);
  const deleteEdge = useGraphStore((s) => s.deleteEdge);
  const saveWorkflow = useGraphStore((s) => s.saveWorkflow);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement;
      const isInput =
        activeEl &&
        (activeEl.tagName === "INPUT" ||
          activeEl.tagName === "TEXTAREA" ||
          (activeEl as HTMLElement).isContentEditable);

      const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
      const modKey = isMac ? e.metaKey : e.ctrlKey;

      if (modKey && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (e.shiftKey) {
          redo();
        } else {
          undo();
        }
        return;
      }

      if (modKey && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        redo();
        return;
      }

      if (modKey && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        saveWorkflow();
        return;
      }

      if (modKey && (e.key === "c" || e.key === "C")) {
        if (!isInput && selectedNodeId) {
          e.preventDefault();
          copySelectedNodes();
        }
        return;
      }

      if (modKey && (e.key === "v" || e.key === "V")) {
        if (!isInput) {
          e.preventDefault();
          pasteNodes();
        }
        return;
      }

      if ((e.key === "Delete" || e.key === "Backspace") && !isInput) {
        if (selectedNodeId && selectedNodeId !== "start" && selectedNodeId !== "end") {
          e.preventDefault();
          deleteNode(selectedNodeId);
        } else if (selectedEdgeId) {
          e.preventDefault();
          deleteEdge(selectedEdgeId);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedNodeId,
    selectedEdgeId,
    undo,
    redo,
    copySelectedNodes,
    pasteNodes,
    saveWorkflow,
    deleteNode,
    deleteEdge,
  ]);

  // Active graph or subgraph data
  const activeData = activeSubgraphId && graph.subgraphs[activeSubgraphId]
    ? graph.subgraphs[activeSubgraphId]
    : graph;

  const nodeTypes = useMemo(
    () => ({
      start: StartNode,
      end: EndNode,
      triggers: StartNode,
      output: EndNode,
      langgraphNode: LangGraphNode,
    }),
    []
  );

  const edgeTypes = useMemo(
    () => ({
      normal: NormalEdge,
      conditional: ConditionalEdge,
    }),
    []
  );

  // Convert GraphNode -> xyflow Node
  const flowNodes: Node[] = useMemo(() => {
    return activeData.nodes.map((n) => {
      let type = "langgraphNode";
      if (n.type === "triggers" || n.id === "start" || n.type === "start") {
        type = "start";
      } else if (n.type === "output" || n.id === "end" || n.type === "end") {
        type = "end";
      }

      return {
        id: n.id,
        type,
        position: n.position || { x: 0, y: 0 },
        selected: n.id === selectedNodeId,
        data: {
          label: n.label,
          type: n.type,
          config: n.config,
          policy: n.policy,
        },
      };
    });
  }, [activeData.nodes, selectedNodeId]);

  // Convert GraphEdge -> xyflow Edge
  const flowEdges: Edge[] = useMemo(() => {
    return activeData.edges.map((e) => {
      const isConditional = e.kind === "conditional";
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: isConditional ? "conditional" : "normal",
        selected: e.id === selectedEdgeId,
        animated: isConditional,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: isConditional ? "#6366F1" : "#94A3B8",
        },
        data: {
          condition: e.condition,
        },
      };
    });
  }, [activeData.edges, selectedEdgeId]);

  const onConnect = useCallback(
    (params: Connection) => {
      if (!params.source || !params.target) return;
      const newEdgeId = `e_${params.source}_${params.target}_${Date.now().toString(36)}`;
      addGraphEdge({
        id: newEdgeId,
        source: params.source,
        target: params.target,
        kind: "normal",
        condition: null,
      });
    },
    [addGraphEdge]
  );

  const onNodeDragStop = useCallback(
    (_: any, node: Node) => {
      updateNodePosition(node.id, node.position);
    },
    [updateNodePosition]
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData("application/reactflow");
      if (!type) return;

      const bounds = event.currentTarget.getBoundingClientRect();
      const position = {
        x: event.clientX - bounds.left - 100,
        y: event.clientY - bounds.top - 40,
      };

      addNode(type, position);
    },
    [addNode]
  );

  return (
    <div className="flex-1 h-full relative bg-[#F8FAFC] overflow-hidden">
      <Breadcrumbs />

      {/* Canvas Top Bar: Quick Actions (Undo, Redo, Copy, Paste, Auto-Layout) */}
      <div className="absolute top-3 right-4 z-20 flex items-center gap-1 bg-white/90 backdrop-blur-xs p-1 rounded-xl border border-slate-200/90 shadow-sm">
        <button
          onClick={undo}
          disabled={!canUndo}
          title="Undo (Ctrl+Z)"
          className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
            canUndo
              ? "text-slate-700 hover:bg-slate-100 cursor-pointer"
              : "text-slate-300 cursor-not-allowed"
          }`}
        >
          <Undo2 className="w-4 h-4" />
        </button>
        <button
          onClick={redo}
          disabled={!canRedo}
          title="Redo (Ctrl+Y)"
          className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
            canRedo
              ? "text-slate-700 hover:bg-slate-100 cursor-pointer"
              : "text-slate-300 cursor-not-allowed"
          }`}
        >
          <Redo2 className="w-4 h-4" />
        </button>
        <div className="h-4 w-px bg-slate-200 mx-0.5" />
        <button
          onClick={copySelectedNodes}
          disabled={!selectedNodeId}
          title="Copy selected node (Ctrl+C)"
          className={`p-1.5 rounded-lg text-xs font-medium transition-all ${
            selectedNodeId
              ? "text-slate-700 hover:bg-slate-100 cursor-pointer"
              : "text-slate-300 cursor-not-allowed"
          }`}
        >
          <Copy className="w-4 h-4" />
        </button>
        <button
          onClick={pasteNodes}
          title="Paste node (Ctrl+V)"
          className="p-1.5 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-100 transition-all cursor-pointer"
        >
          <ClipboardPaste className="w-4 h-4" />
        </button>
        <div className="h-4 w-px bg-slate-200 mx-0.5" />
        <button
          onClick={autoLayoutGraph}
          title="Auto-Layout Graph"
          className="px-2 py-1.5 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-100 flex items-center gap-1.5 transition-all cursor-pointer"
        >
          <LayoutGrid className="w-4 h-4 text-indigo-600" />
          <span>Auto Layout</span>
        </button>
      </div>

      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={(_, node) => selectNode(node.id)}
        onEdgeClick={(_, edge) => selectEdge(edge.id)}
        onPaneClick={() => {
          selectNode(null);
          selectEdge(null);
        }}
        onDragOver={onDragOver}
        onDrop={onDrop}
        fitView
        snapToGrid
        snapGrid={[16, 16]}
        minZoom={0.2}
        maxZoom={2.0}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1.2} color="#CBD5E1" />
        <Controls position="bottom-left" showInteractive={false} />
        <MiniMap
          position="bottom-left"
          style={{ marginBottom: 44, borderRadius: 12, border: "1px solid #E2E8F0" }}
          nodeColor={(n) => {
            if (n.type === "start") return "#10B981";
            if (n.type === "end") return "#E11D48";
            return "#94A3B8";
          }}
        />
      </ReactFlow>
    </div>
  );
}
