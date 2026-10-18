import { Handle, Position } from "@xyflow/react";
import { NODE_CATEGORIES, type NodeCategoryKey } from "../theme/nodeCategories";

export function StudioNode({ data, selected }: { data: any; selected?: boolean }) {
  const categoryKey: NodeCategoryKey = data.category || "agents";
  const theme = NODE_CATEGORIES[categoryKey] || NODE_CATEGORIES.agents;
  const isRunning = data.isRunning;

  return (
    <div
      className={`w-64 rounded-2xl bg-white border transition-all duration-200 shadow-soft ${
        isRunning
          ? "ring-4 ring-blue-400/40 border-[#3B82F6] scale-[1.02]"
          : selected
          ? "border-[#3B82F6] ring-2 ring-blue-500/20"
          : "border-[#E5E7EB]"
      }`}
    >
      {/* Category Colored Header */}
      <div
        className={`px-3.5 py-2.5 rounded-t-2xl border-b flex items-center justify-between ${theme.headerBg}`}
      >
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${theme.dotColor}`} />
          <span className={`text-xs font-semibold uppercase tracking-wider ${theme.badgeText}`}>
            {theme.label}
          </span>
        </div>
        {isRunning && (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-[#3B82F6] animate-pulse">
            Running...
          </span>
        )}
      </div>

      {/* Node Body */}
      <div className="p-3.5 space-y-2">
        <div className="text-sm font-semibold text-[#0F172A]">{data.label}</div>
        <p className="text-xs text-[#94A3B8] leading-relaxed">{theme.description}</p>

        {/* Dynamic Config Preview Pill */}
        {data.config?.model && (
          <div className="pt-1 flex items-center gap-1.5">
            <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#F8FAFC] border border-[#E5E7EB] text-[#475569]">
              Model: {data.config.model}
            </span>
          </div>
        )}
        {data.config?.provider && (
          <div className="pt-1 flex items-center gap-1.5">
            <span className="text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-[#F8FAFC] border border-[#E5E7EB] text-[#475569]">
              DB: {data.config.provider}
            </span>
          </div>
        )}
      </div>

      {/* Target Handle (Left) */}
      {categoryKey !== "triggers" && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            width: 11,
            height: 11,
            background: "#FFFFFF",
            border: `2px solid ${theme.handleHex}`,
          }}
        />
      )}

      {/* Source Handle (Right) */}
      {categoryKey !== "output" && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            width: 11,
            height: 11,
            background: theme.handleHex,
            border: "2px solid #FFFFFF",
          }}
        />
      )}
    </div>
  );
}
