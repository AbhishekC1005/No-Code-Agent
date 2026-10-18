import { Handle, Position } from "@xyflow/react";
import { Square } from "lucide-react";

export function EndNode({ selected }: { selected?: boolean }) {
  return (
    <div
      className={`px-4 py-3 rounded-2xl bg-white border shadow-sm transition-all flex items-center gap-3 ${
        selected ? "border-rose-500 ring-2 ring-rose-500/20" : "border-slate-200"
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 10,
          height: 10,
          background: "#FFFFFF",
          border: "2px solid #E11D48",
        }}
      />
      <div className="w-8 h-8 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
        <Square className="w-3.5 h-3.5 fill-rose-600" />
      </div>
      <div>
        <div className="text-xs font-bold text-slate-800 tracking-wide uppercase">END</div>
        <div className="text-[11px] text-slate-400">Terminal State</div>
      </div>
    </div>
  );
}
