import { Handle, Position } from "@xyflow/react";
import { Play } from "lucide-react";

export function StartNode({ selected }: { selected?: boolean }) {
  return (
    <div
      className={`px-4 py-3 rounded-2xl bg-white border shadow-sm transition-all flex items-center gap-3 ${
        selected ? "border-emerald-500 ring-2 ring-emerald-500/20" : "border-slate-200"
      }`}
    >
      <div className="w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600">
        <Play className="w-4 h-4 fill-emerald-600" />
      </div>
      <div>
        <div className="text-xs font-bold text-slate-800 tracking-wide uppercase">START</div>
        <div className="text-[11px] text-slate-400">Workflow Entry</div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 10,
          height: 10,
          background: "#10B981",
          border: "2px solid #FFFFFF",
        }}
      />
    </div>
  );
}
