import { useState } from "react";
import { X, Check, Edit3, RotateCcw } from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function StateInspectorPanel() {
  const isStateInspectorOpen = useGraphStore((s) => s.isStateInspectorOpen);
  const setStateInspectorOpen = useGraphStore((s) => s.setStateInspectorOpen);
  const latestState = useGraphStore((s) => s.latestState);
  const updateCheckpointState = useGraphStore((s) => s.updateCheckpointState);
  const currentThreadId = useGraphStore((s) => s.currentThreadId);

  const [isEditing, setIsEditing] = useState(false);
  const [editedJson, setEditedJson] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isStateInspectorOpen) return null;

  const handleStartEdit = () => {
    setEditedJson(JSON.stringify(latestState, null, 2));
    setIsEditing(true);
    setErrorMsg(null);
  };

  const handleSaveEdit = async () => {
    try {
      const parsed = JSON.parse(editedJson);
      await updateCheckpointState(parsed, "user_edit");
      setIsEditing(false);
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(`Invalid JSON: ${err.message}`);
    }
  };

  return (
    <div className="absolute left-[300px] bottom-6 w-[480px] max-h-[440px] bg-white border border-slate-200 rounded-2xl shadow-2xl flex flex-col z-30 font-sans overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-slate-800">State Inspector</h3>
          <div className="text-[10px] text-slate-500">Thread: {currentThreadId}</div>
        </div>

        <div className="flex items-center gap-1.5">
          {!isEditing ? (
            <button
              onClick={handleStartEdit}
              className="py-1 px-2.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 text-xs font-medium flex items-center gap-1 transition cursor-pointer"
            >
              <Edit3 className="w-3.5 h-3.5" />
              Edit Values
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={handleSaveEdit}
                className="py-1 px-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium flex items-center gap-1 transition cursor-pointer"
              >
                <Check className="w-3.5 h-3.5" />
                Save (update_state)
              </button>
              <button
                onClick={() => setIsEditing(false)}
                className="p-1 rounded-lg hover:bg-slate-200 text-slate-500 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          <button
            onClick={() => setStateInspectorOpen(false)}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 overflow-y-auto">
        {errorMsg && (
          <div className="mb-3 p-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-700">
            {errorMsg}
          </div>
        )}

        {isEditing ? (
          <textarea
            rows={12}
            value={editedJson}
            onChange={(e) => setEditedJson(e.target.value)}
            className="w-full p-2.5 rounded-xl border border-blue-400 font-mono text-xs text-slate-800 bg-slate-50 focus:outline-none"
          />
        ) : (
          <div className="space-y-3">
            {Object.keys(latestState).length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400">
                State is currently empty. Execute a graph step to populate channels.
              </div>
            ) : (
              Object.entries(latestState).map(([key, val]) => (
                <div key={key} className="p-2.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1">
                  <div className="text-xs font-mono font-bold text-blue-600">{key}</div>
                  <pre className="text-[11px] font-mono text-slate-700 whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {typeof val === "object" ? JSON.stringify(val, null, 2) : String(val)}
                  </pre>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
