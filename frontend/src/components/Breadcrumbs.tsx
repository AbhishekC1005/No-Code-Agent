import { ChevronRight, ArrowLeft, FolderGit2 } from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function Breadcrumbs() {
  const activeSubgraphId = useGraphStore((s) => s.activeSubgraphId);
  const exitSubgraph = useGraphStore((s) => s.exitSubgraph);
  const graph = useGraphStore((s) => s.graph);
  const workflowName = useGraphStore((s) => s.workflowName);

  if (!activeSubgraphId) return null;

  const parentNode = graph.nodes.find((n) => n.id === activeSubgraphId);
  const subgraphName = parentNode?.label || parentNode?.config?.subgraph_name || activeSubgraphId;

  return (
    <div className="absolute top-4 left-6 z-20 flex items-center gap-2 p-1.5 px-3 rounded-xl bg-white border border-slate-200 shadow-md">
      <button
        onClick={exitSubgraph}
        className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 transition-colors cursor-pointer"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>{workflowName || "Root Workflow"}</span>
      </button>

      <ChevronRight className="w-3.5 h-3.5 text-slate-300" />

      <div className="flex items-center gap-1.5 text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-lg border border-indigo-100">
        <FolderGit2 className="w-3.5 h-3.5" />
        <span>{subgraphName}</span>
      </div>
    </div>
  );
}
