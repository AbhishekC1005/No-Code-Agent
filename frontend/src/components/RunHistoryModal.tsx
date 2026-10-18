import { useState } from "react";
import {
  X,
  History,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  ArrowRight,
  RefreshCw,
  GitBranch,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function RunHistoryModal() {
  const isRunHistoryOpen = useGraphStore((s) => s.isRunHistoryOpen);
  const setRunHistoryOpen = useGraphStore((s) => s.setRunHistoryOpen);
  const executions = useGraphStore((s) => s.executions);
  const loadExecutions = useGraphStore((s) => s.loadExecutions);
  const switchThread = useGraphStore((s) => s.switchThread);
  const setRunPanelOpen = useGraphStore((s) => s.setRunPanelOpen);

  const [filterStatus, setFilterStatus] = useState<string>("all");

  if (!isRunHistoryOpen) return null;

  const filteredExecutions = executions.filter((ex) => {
    if (filterStatus === "all") return true;
    return ex.status === filterStatus;
  });

  const handleSelectRun = async (threadId: string) => {
    await switchThread(threadId);
    setRunPanelOpen(true);
    setRunHistoryOpen(false);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3" /> Success
          </span>
        );
      case "error":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3" /> Error
          </span>
        );
      case "interrupted":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertCircle className="w-3 h-3" /> Paused (HITL)
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200 animate-pulse">
            <Clock className="w-3 h-3" /> Running
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-50 text-slate-700 border border-slate-200">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl flex flex-col max-h-[85vh] overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-600 flex items-center justify-center">
              <History className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Execution History</h2>
              <p className="text-[11px] text-slate-400">
                Inspect past runs, superstep timings, threads, and state snapshots
              </p>
            </div>
          </div>
          <button
            onClick={() => setRunHistoryOpen(false)}
            className="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Filter Bar */}
        <div className="px-6 py-2.5 border-b border-slate-100 bg-slate-50/60 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mr-1">
              Filter:
            </span>
            {["all", "success", "error", "interrupted", "running"].map((st) => (
              <button
                key={st}
                onClick={() => setFilterStatus(st)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold capitalize transition-all cursor-pointer ${
                  filterStatus === st
                    ? "bg-indigo-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          <button
            onClick={() => loadExecutions()}
            title="Refresh execution history"
            className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-200/50 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Executions Table */}
        <div className="flex-1 overflow-y-auto">
          {filteredExecutions.length === 0 ? (
            <div className="text-center py-16 space-y-2">
              <History className="w-8 h-8 text-slate-300 mx-auto" />
              <div className="text-xs font-semibold text-slate-600">No execution records found</div>
              <div className="text-[11px] text-slate-400">
                Execute runs from the canvas or trigger webhooks to view execution history.
              </div>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-50">
                  <th className="py-2.5 px-6">Run ID</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Thread ID</th>
                  <th className="py-2.5 px-4">Started</th>
                  <th className="py-2.5 px-4">Duration</th>
                  <th className="py-2.5 px-6 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {filteredExecutions.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-6 font-mono text-[11px] text-slate-700 font-semibold">
                      {run.id}
                      {run.error_message && (
                        <div className="text-[10px] text-rose-600 truncate max-w-xs mt-0.5 font-sans">
                          {run.error_message}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">{getStatusBadge(run.status)}</td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-600">
                      <div className="flex items-center gap-1">
                        <GitBranch className="w-3 h-3 text-slate-400" />
                        <span>{run.thread_id}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-slate-500 text-[11px]">
                      {run.start_time ? new Date(run.start_time).toLocaleString() : "—"}
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                      {run.total_ms ? `${(run.total_ms / 1000).toFixed(2)}s` : "—"}
                    </td>
                    <td className="py-3 px-6 text-right">
                      <button
                        onClick={() => handleSelectRun(run.thread_id)}
                        className="px-2.5 py-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 border border-indigo-200/80 rounded-lg transition-colors inline-flex items-center gap-1 cursor-pointer"
                      >
                        <span>Inspect</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
