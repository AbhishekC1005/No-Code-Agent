import { X, Sliders, Database, PauseCircle } from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function GraphSettingsDrawer() {
  const isSettingsOpen = useGraphStore((s) => s.isSettingsOpen);
  const setSettingsOpen = useGraphStore((s) => s.setSettingsOpen);
  const graph = useGraphStore((s) => s.graph);
  const updateSettings = useGraphStore((s) => s.updateSettings);

  if (!isSettingsOpen) return null;

  const settings = graph.settings || {
    checkpointer: "sqlite",
    recursion_limit: 25,
    interrupt_before: [],
    interrupt_after: [],
    store: {},
    config_fields: [],
  };

  const nodes = graph.nodes || [];

  const toggleInterruptBefore = (nodeId: string) => {
    const current = settings.interrupt_before || [];
    const updated = current.includes(nodeId)
      ? current.filter((id) => id !== nodeId)
      : [...current, nodeId];
    updateSettings({ interrupt_before: updated });
  };

  const toggleInterruptAfter = (nodeId: string) => {
    const current = settings.interrupt_after || [];
    const updated = current.includes(nodeId)
      ? current.filter((id) => id !== nodeId)
      : [...current, nodeId];
    updateSettings({ interrupt_after: updated });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30 backdrop-blur-xs">
      <div className="w-full max-w-md bg-white h-full shadow-2xl border-l border-slate-200 flex flex-col justify-between overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-800">Graph Compilation Settings</div>
              <div className="text-xs text-slate-500">
                LangGraph StateGraph compile parameters
              </div>
            </div>
          </div>
          <button
            onClick={() => setSettingsOpen(false)}
            className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* Checkpointer */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-blue-600" /> State Checkpointer
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "sqlite", label: "SqliteSaver", desc: "checkpoints.db" },
                { id: "memory", label: "MemorySaver", desc: "In-memory" },
                { id: "none", label: "None", desc: "Stateless" },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => updateSettings({ checkpointer: opt.id as any })}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    settings.checkpointer === opt.id
                      ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-500/20"
                      : "border-slate-200 bg-white hover:border-slate-300 text-slate-700"
                  }`}
                >
                  <div className="text-xs font-bold">{opt.label}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Recursion Limit */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-800 flex items-center justify-between">
              <span>Recursion Limit</span>
              <span className="text-slate-400 font-normal">Default: 25 steps</span>
            </label>
            <input
              type="number"
              min={1}
              max={100}
              value={settings.recursion_limit ?? 25}
              onChange={(e) =>
                updateSettings({ recursion_limit: parseInt(e.target.value, 10) || 25 })
              }
              className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs font-medium text-slate-800 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Human-in-the-Loop Interrupt Toggles */}
          <div className="space-y-3 pt-4 border-t border-slate-100">
            <div>
              <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <PauseCircle className="w-3.5 h-3.5 text-amber-600" /> Human-in-the-Loop Interrupts
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Pause execution before or after specified nodes for human inspection or approval
              </div>
            </div>

            {/* Interrupt Before */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-700">Interrupt Before Nodes:</div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto p-1.5 bg-slate-50 rounded-xl border border-slate-200">
                {nodes.map((n) => {
                  const checked = (settings.interrupt_before || []).includes(n.id);
                  return (
                    <label
                      key={n.id}
                      className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-white cursor-pointer text-xs"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleInterruptBefore(n.id)}
                        className="w-3.5 h-3.5 rounded text-blue-600 border-slate-300"
                      />
                      <span className="font-medium text-slate-800">{n.label || n.id}</span>
                      <span className="text-[10px] text-slate-400">({n.type})</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Interrupt After */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-slate-700">Interrupt After Nodes:</div>
              <div className="space-y-1.5 max-h-36 overflow-y-auto p-1.5 bg-slate-50 rounded-xl border border-slate-200">
                {nodes.map((n) => {
                  const checked = (settings.interrupt_after || []).includes(n.id);
                  return (
                    <label
                      key={n.id}
                      className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-white cursor-pointer text-xs"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleInterruptAfter(n.id)}
                        className="w-3.5 h-3.5 rounded text-blue-600 border-slate-300"
                      />
                      <span className="font-medium text-slate-800">{n.label || n.id}</span>
                      <span className="text-[10px] text-slate-400">({n.type})</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end">
          <button
            onClick={() => setSettingsOpen(false)}
            className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-all"
          >
            Apply Settings
          </button>
        </div>
      </div>
    </div>
  );
}
