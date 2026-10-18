import { X, Trash2, Plus, GitFork, ArrowRight } from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function EdgeInspector() {
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
  const selectEdge = useGraphStore((s) => s.selectEdge);
  const graph = useGraphStore((s) => s.graph);
  const activeSubgraphId = useGraphStore((s) => s.activeSubgraphId);
  const updateEdge = useGraphStore((s) => s.updateEdge);
  const deleteEdge = useGraphStore((s) => s.deleteEdge);

  const edges = activeSubgraphId && graph.subgraphs[activeSubgraphId]
    ? graph.subgraphs[activeSubgraphId].edges
    : graph.edges;

  const nodes = activeSubgraphId && graph.subgraphs[activeSubgraphId]
    ? graph.subgraphs[activeSubgraphId].nodes
    : graph.nodes;

  const edge = edges.find((e) => e.id === selectedEdgeId);

  if (!selectedEdgeId || !edge) return null;

  const condition = edge.condition || {};
  const branches: Record<string, string> =
    condition.branches || condition.path_map || { continue: edge.target, end: "END" };

  const handleKindChange = (newKind: "normal" | "conditional") => {
    if (newKind === "conditional") {
      updateEdge(edge.id, {
        kind: "conditional",
        condition: {
          branches: { continue: edge.target, end: "END" },
          code: "return 'continue' if len(state.get('messages', [])) > 0 else 'end'",
        },
      });
    } else {
      updateEdge(edge.id, {
        kind: "normal",
        condition: null,
      });
    }
  };

  const handleUpdateBranch = (branchKey: string, targetId: string) => {
    const updatedBranches = { ...branches, [branchKey]: targetId };
    updateEdge(edge.id, {
      condition: {
        ...condition,
        branches: updatedBranches,
      },
    });
  };

  const handleAddBranch = () => {
    const newKey = `branch_${Object.keys(branches).length + 1}`;
    const updatedBranches = { ...branches, [newKey]: edge.target };
    updateEdge(edge.id, {
      condition: {
        ...condition,
        branches: updatedBranches,
      },
    });
  };

  const handleDeleteBranch = (branchKey: string) => {
    const updatedBranches = { ...branches };
    delete updatedBranches[branchKey];
    updateEdge(edge.id, {
      condition: {
        ...condition,
        branches: updatedBranches,
      },
    });
  };

  const handleCodeChange = (code: string) => {
    updateEdge(edge.id, {
      condition: {
        ...condition,
        code,
      },
    });
  };

  return (
    <div className="w-80 bg-white border-l border-slate-200 p-5 flex flex-col justify-between shadow-lg z-20 overflow-y-auto">
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <GitFork className="w-4 h-4 text-indigo-600" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Edge Inspector
            </span>
          </div>
          <button
            onClick={() => selectEdge(null)}
            className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Transition Summary */}
        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <span className="font-semibold text-slate-800 truncate max-w-[90px]">{edge.source}</span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
          <span className="font-semibold text-slate-800 truncate max-w-[90px]">{edge.target}</span>
        </div>

        {/* Edge Type Toggle */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">Edge Type</label>
          <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl">
            <button
              onClick={() => handleKindChange("normal")}
              className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                edge.kind === "normal"
                  ? "bg-white text-slate-800 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Normal (Solid)
            </button>
            <button
              onClick={() => handleKindChange("conditional")}
              className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                edge.kind === "conditional"
                  ? "bg-white text-indigo-700 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              Conditional (Dashed)
            </button>
          </div>
        </div>

        {/* Conditional Routing Configuration */}
        {edge.kind === "conditional" && (
          <div className="space-y-4 pt-2 border-t border-slate-100">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">
                Router Logic (Python code)
              </label>
              <textarea
                rows={3}
                value={condition.code || ""}
                onChange={(e) => handleCodeChange(e.target.value)}
                placeholder="return 'end' if state.get('retry_count', 0) > 2 else 'continue'"
                className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-mono text-slate-800 bg-slate-50 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {/* Path Map / Branches */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-700">
                  Path Map (Branches)
                </label>
                <button
                  onClick={handleAddBranch}
                  className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" /> Add Branch
                </button>
              </div>

              <div className="space-y-2">
                {Object.entries(branches).map(([key, target]) => (
                  <div
                    key={key}
                    className="p-2 rounded-xl bg-slate-50 border border-slate-200 flex items-center gap-2"
                  >
                    <span className="text-xs font-mono font-medium text-indigo-700 w-20 truncate">
                      {key}
                    </span>
                    <ArrowRight className="w-3 h-3 text-slate-400 flex-shrink-0" />
                    <select
                      value={target}
                      onChange={(e) => handleUpdateBranch(key, e.target.value)}
                      className="flex-1 py-1 px-2 rounded-lg border border-slate-200 text-xs bg-white text-slate-800 focus:outline-none"
                    >
                      <option value="END">END</option>
                      {nodes.map((n) => (
                        <option key={n.id} value={n.id}>
                          {n.label || n.id}
                        </option>
                      ))}
                    </select>
                    {Object.keys(branches).length > 1 && (
                      <button
                        onClick={() => handleDeleteBranch(key)}
                        className="text-slate-400 hover:text-rose-500 p-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Delete Edge Footer */}
      <div className="pt-4 border-t border-slate-100">
        <button
          onClick={() => {
            deleteEdge(edge.id);
            selectEdge(null);
          }}
          className="w-full py-2 px-3 rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-600 text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Delete Edge
        </button>
      </div>
    </div>
  );
}
