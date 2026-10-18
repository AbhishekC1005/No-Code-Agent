import { Handle, Position } from "@xyflow/react";
import {
  AlertTriangle,
  Bot,
  Wrench,
  Code,
  GitBranch,
  Layers,
  UserCheck,
  FolderGit2,
  Cpu,
  Database,
  PauseCircle,
  CheckCircle,
} from "lucide-react";
import { useGraphStore } from "../../store/useGraphStore";

interface Props {
  id: string;
  data: {
    label: string;
    type: string;
    config?: Record<string, any>;
    policy?: Record<string, any>;
  };
  selected?: boolean;
}

const TYPE_ICONS: Record<string, any> = {
  llm: Bot,
  models: Bot,
  tool: Wrench,
  tools: Wrench,
  function: Code,
  command: GitBranch,
  logic: GitBranch,
  map: Layers,
  human: UserCheck,
  human_review: UserCheck,
  subgraph: FolderGit2,
  agent: Cpu,
  agents: Cpu,
  memory_read: Database,
  memory_write: Database,
  store: Database,
};

const TYPE_COLORS: Record<string, { bg: string; text: string; dot: string; border: string; handle: string }> = {
  llm: { bg: "bg-purple-50", text: "text-purple-600", dot: "bg-purple-500", border: "border-purple-200", handle: "#9333EA" },
  models: { bg: "bg-purple-50", text: "text-purple-600", dot: "bg-purple-500", border: "border-purple-200", handle: "#9333EA" },
  tool: { bg: "bg-teal-50", text: "text-teal-600", dot: "bg-teal-500", border: "border-teal-200", handle: "#0D9488" },
  tools: { bg: "bg-teal-50", text: "text-teal-600", dot: "bg-teal-500", border: "border-teal-200", handle: "#0D9488" },
  function: { bg: "bg-emerald-50", text: "text-emerald-600", dot: "bg-emerald-500", border: "border-emerald-200", handle: "#10B981" },
  command: { bg: "bg-pink-50", text: "text-pink-600", dot: "bg-pink-500", border: "border-pink-200", handle: "#DB2777" },
  logic: { bg: "bg-pink-50", text: "text-pink-600", dot: "bg-pink-500", border: "border-pink-200", handle: "#DB2777" },
  map: { bg: "bg-amber-50", text: "text-amber-600", dot: "bg-amber-500", border: "border-amber-200", handle: "#F59E0B" },
  human: { bg: "bg-blue-50", text: "text-blue-600", dot: "bg-blue-500", border: "border-blue-200", handle: "#3B82F6" },
  human_review: { bg: "bg-blue-50", text: "text-blue-600", dot: "bg-blue-500", border: "border-blue-200", handle: "#3B82F6" },
  subgraph: { bg: "bg-indigo-50", text: "text-indigo-600", dot: "bg-indigo-500", border: "border-indigo-200", handle: "#6366F1" },
  agent: { bg: "bg-rose-50", text: "text-rose-600", dot: "bg-rose-500", border: "border-rose-200", handle: "#E11D48" },
  agents: { bg: "bg-rose-50", text: "text-rose-600", dot: "bg-rose-500", border: "border-rose-200", handle: "#E11D48" },
  memory_read: { bg: "bg-cyan-50", text: "text-cyan-600", dot: "bg-cyan-500", border: "border-cyan-200", handle: "#0891B2" },
  memory_write: { bg: "bg-cyan-50", text: "text-cyan-600", dot: "bg-cyan-500", border: "border-cyan-200", handle: "#0891B2" },
  store: { bg: "bg-cyan-50", text: "text-cyan-600", dot: "bg-cyan-500", border: "border-cyan-200", handle: "#0891B2" },
};

export function LangGraphNode({ id, data, selected }: Props) {
  const enterSubgraph = useGraphStore((s) => s.enterSubgraph);
  const diagnostics = useGraphStore((s) => s.diagnostics);
  const settings = useGraphStore((s) => s.graph.settings);
  const nodeStatuses = useGraphStore((s) => s.nodeStatuses);

  const nodeType = (data.type || "agent").toLowerCase();
  const theme = TYPE_COLORS[nodeType] || TYPE_COLORS.agent;
  const IconComponent = TYPE_ICONS[nodeType] || Cpu;

  // Live status from SSE
  const execStatus = nodeStatuses[id] || "idle";

  // Diagnostics for this specific node
  const nodeDiagnostics = diagnostics.filter((d) => d.node_id === id);
  const hasErrors = nodeDiagnostics.some((d) => d.level === "error");
  const hasWarnings = nodeDiagnostics.some((d) => d.level === "warning");

  // Breakpoints / HITL Interrupt indicator
  const hasBreakpoint =
    (settings.interrupt_before || []).includes(id) ||
    (settings.interrupt_after || []).includes(id) ||
    Boolean(data.policy?.interrupt_before) ||
    Boolean(data.policy?.interrupt_after);

  const cfg = data.config || {};
  const isSubgraph = nodeType === "subgraph";

  const handleDoubleClick = () => {
    if (isSubgraph) {
      enterSubgraph(id);
    }
  };

  return (
    <div
      onDoubleClick={handleDoubleClick}
      className={`w-64 rounded-2xl bg-white border transition-all duration-200 shadow-sm ${
        execStatus === "running"
          ? "border-blue-500 ring-4 ring-blue-500/30 shadow-md"
          : execStatus === "interrupted"
          ? "border-amber-500 ring-4 ring-amber-500/30 animate-pulse shadow-md"
          : execStatus === "error" || hasErrors
          ? "border-rose-500 ring-2 ring-rose-500/30"
          : execStatus === "success"
          ? "border-emerald-500 ring-2 ring-emerald-500/20"
          : hasWarnings
          ? "border-amber-400 ring-2 ring-amber-400/20"
          : selected
          ? "border-blue-500 ring-2 ring-blue-500/20"
          : "border-slate-200 hover:border-slate-300"
      }`}
    >
      {/* Node Header */}
      <div
        className={`px-3.5 py-2 rounded-t-2xl border-b flex items-center justify-between ${theme.bg} ${theme.border}`}
      >
        <div className="flex items-center gap-2">
          <IconComponent className={`w-3.5 h-3.5 ${theme.text}`} />
          <span className={`text-[11px] font-bold uppercase tracking-wider ${theme.text}`}>
            {nodeType}
          </span>
        </div>

        <div className="flex items-center gap-1">
          {execStatus === "running" && (
            <span className="px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold animate-pulse">
              Running
            </span>
          )}
          {execStatus === "interrupted" && (
            <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold flex items-center gap-0.5">
              <PauseCircle className="w-2.5 h-2.5" /> Paused
            </span>
          )}
          {execStatus === "success" && (
            <span className="px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-bold flex items-center gap-0.5">
              <CheckCircle className="w-2.5 h-2.5" /> Done
            </span>
          )}
          {hasBreakpoint && (
            <span
              title="Breakpoint configured (Pause execution)"
              className="px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 text-[10px] font-bold flex items-center gap-0.5"
            >
              <PauseCircle className="w-2.5 h-2.5" /> BP
            </span>
          )}
          {data.policy?.defer && (
            <span
              title="Deferred node execution"
              className="px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-semibold"
            >
              defer
            </span>
          )}
          {hasErrors && (
            <span
              title={nodeDiagnostics.map((d) => d.message).join("\n")}
              className="text-rose-500 animate-bounce"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
            </span>
          )}
          {!hasErrors && hasWarnings && (
            <span
              title={nodeDiagnostics.map((d) => d.message).join("\n")}
              className="text-amber-500"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
            </span>
          )}
        </div>
      </div>

      {/* Node Content */}
      <div className="p-3.5 space-y-2">
        <div className="text-sm font-semibold text-slate-800 leading-snug truncate">
          {data.label || id}
        </div>

        {/* Dynamic Context Preview */}
        <div className="flex flex-wrap gap-1">
          {cfg.model && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-slate-50 border border-slate-200 text-slate-600 truncate max-w-[190px]">
              {cfg.model}
            </span>
          )}
          {cfg.provider && !cfg.model && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-slate-50 border border-slate-200 text-slate-600">
              {cfg.provider}
            </span>
          )}
          {cfg.items_field && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-amber-50 border border-amber-200 text-amber-700">
              items: {cfg.items_field}
            </span>
          )}
          {cfg.goto_true && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-pink-50 border border-pink-200 text-pink-700">
              goto: {cfg.goto_true}
            </span>
          )}
          {isSubgraph && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-indigo-50 border border-indigo-200 text-indigo-700">
              Double-click to open
            </span>
          )}
        </div>
      </div>

      {/* Handles */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 10,
          height: 10,
          background: "#FFFFFF",
          border: `2px solid ${theme.handle}`,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 10,
          height: 10,
          background: theme.handle,
          border: "2px solid #FFFFFF",
        }}
      />
    </div>
  );
}
