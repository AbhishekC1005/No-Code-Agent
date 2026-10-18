import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import { GitFork } from "lucide-react";
import { useGraphStore } from "../../store/useGraphStore";

export function ConditionalEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
  selected,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 16,
  });

  const selectEdge = useGraphStore((s) => s.selectEdge);

  const condition = (data as any)?.condition || {};
  const branches = condition.branches || condition.path_map || {};
  const branchCount = Object.keys(branches).length;
  const labelText = branchCount > 0 ? `${branchCount} branches` : "Router";

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          strokeWidth: selected ? 2.5 : 1.75,
          stroke: selected ? "#3B82F6" : "#6366F1",
          strokeDasharray: "5, 5",
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: "all",
          }}
          className="nodrag nopan"
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              selectEdge(id);
            }}
            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border flex items-center gap-1 shadow-sm transition-all cursor-pointer ${
              selected
                ? "bg-blue-600 text-white border-blue-700 ring-2 ring-blue-400/30"
                : "bg-white text-indigo-700 border-indigo-200 hover:border-indigo-400"
            }`}
          >
            <GitFork className="w-2.5 h-2.5" />
            <span>{labelText}</span>
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
