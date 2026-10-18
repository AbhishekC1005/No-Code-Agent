import { useState, useEffect } from "react";
import {
  Play,
  Square,
  CheckCircle2,
  Clock,
  GitFork,
  Database,
  MessageSquare,
  RotateCcw,
  Send,
  Plus,
  AlertCircle,
  X,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function RunChatPanel() {
  const isRunPanelOpen = useGraphStore((s) => s.isRunPanelOpen);
  const setRunPanelOpen = useGraphStore((s) => s.setRunPanelOpen);
  const setStateInspectorOpen = useGraphStore((s) => s.setStateInspectorOpen);

  const isRunning = useGraphStore((s) => s.isRunning);
  const isInterrupted = useGraphStore((s) => s.isInterrupted);
  const streamMode = useGraphStore((s) => s.streamMode);
  const setStreamMode = useGraphStore((s) => s.setStreamMode);
  const chatMessages = useGraphStore((s) => s.chatMessages);
  const streamedTokens = useGraphStore((s) => s.streamedTokens);
  const interruptRequest = useGraphStore((s) => s.interruptRequest);

  const currentThreadId = useGraphStore((s) => s.currentThreadId);
  const threadsList = useGraphStore((s) => s.threadsList);
  const checkpointsHistory = useGraphStore((s) => s.checkpointsHistory);
  const storeItems = useGraphStore((s) => s.storeItems);

  const startRun = useGraphStore((s) => s.startRun);
  const resumeRun = useGraphStore((s) => s.resumeRun);
  const cancelRun = useGraphStore((s) => s.cancelRun);
  const switchThread = useGraphStore((s) => s.switchThread);
  const createNewThread = useGraphStore((s) => s.createNewThread);
  const forkThread = useGraphStore((s) => s.forkThread);
  const loadThreadHistory = useGraphStore((s) => s.loadThreadHistory);
  const loadStore = useGraphStore((s) => s.loadStore);
  const saveStoreItem = useGraphStore((s) => s.saveStoreItem);

  const [activeTab, setActiveTab] = useState<"chat" | "timeline" | "store">("chat");
  const [inputText, setInputText] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  // Store tab state
  const [storeNamespace, setStoreNamespace] = useState("memories");
  const [newStoreKey, setNewStoreKey] = useState("");
  const [newStoreVal, setNewStoreVal] = useState("");

  useEffect(() => {
    loadThreadHistory();
    loadStore(storeNamespace);
  }, []);

  if (!isRunPanelOpen) return null;

  const handleSendMessage = () => {
    if (!inputText.trim() || isRunning) return;
    const msg = inputText.trim();
    setInputText("");
    startRun(msg);
  };

  const handleApprove = () => {
    resumeRun("approved");
  };

  const handleReject = () => {
    resumeRun({ rejected: true, reason: rejectReason || "Rejected by user" });
    setShowRejectInput(false);
    setRejectReason("");
  };

  const handleSaveStore = () => {
    if (!newStoreKey.trim()) return;
    let parsedVal = newStoreVal;
    try {
      parsedVal = JSON.parse(newStoreVal);
    } catch {
      // Keep as string
    }
    saveStoreItem(storeNamespace, newStoreKey.trim(), parsedVal);
    setNewStoreKey("");
    setNewStoreVal("");
  };

  return (
    <div className="absolute right-0 top-0 bottom-0 w-[420px] bg-white border-l border-slate-200 shadow-xl flex flex-col z-30 font-sans">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-100 text-blue-600">
            <Play className="w-4 h-4 fill-current" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-800">Runner & Execution</h3>
            <div className="text-[10px] text-slate-500">Live LangGraph Subprocess Stream</div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Thread Switcher Dropdown */}
          <select
            value={currentThreadId}
            onChange={(e) => switchThread(e.target.value)}
            className="px-2 py-1 rounded-lg border border-slate-200 text-[11px] font-mono bg-white text-slate-700 focus:outline-none"
          >
            {threadsList.map((t) => (
              <option key={t.thread_id} value={t.thread_id}>
                {t.thread_id}
              </option>
            ))}
          </select>

          <button
            onClick={createNewThread}
            title="New Thread"
            className="p-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-slate-600 text-xs transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setRunPanelOpen(false)}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-slate-50/50 px-3 pt-2 gap-2 text-xs">
        <button
          onClick={() => setActiveTab("chat")}
          className={`pb-2 px-2.5 font-medium flex items-center gap-1.5 border-b-2 transition cursor-pointer ${
            activeTab === "chat"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Chat & Run
        </button>
        <button
          onClick={() => setActiveTab("timeline")}
          className={`pb-2 px-2.5 font-medium flex items-center gap-1.5 border-b-2 transition cursor-pointer ${
            activeTab === "timeline"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          Time Travel ({checkpointsHistory.length})
        </button>
        <button
          onClick={() => {
            setActiveTab("store");
            loadStore(storeNamespace);
          }}
          className={`pb-2 px-2.5 font-medium flex items-center gap-1.5 border-b-2 transition cursor-pointer ${
            activeTab === "store"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Store
        </button>
      </div>

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* TAB 1: CHAT & RUN */}
        {activeTab === "chat" && (
          <div className="flex flex-col h-full justify-between">
            {/* Stream Mode & Controls Banner */}
            <div className="mb-3 flex items-center justify-between text-xs bg-slate-50 p-2 rounded-xl border border-slate-200">
              <span className="text-slate-500 font-medium">Stream Mode:</span>
              <select
                value={streamMode}
                onChange={(e) => setStreamMode(e.target.value as any)}
                className="px-2 py-0.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-700"
              >
                <option value="updates">updates (per-step diffs)</option>
                <option value="messages">messages (token chunks)</option>
                <option value="values">values (full state)</option>
                <option value="custom">custom</option>
                <option value="debug">debug</option>
              </select>
            </div>

            {/* Chat Messages Log */}
            <div className="flex-1 overflow-y-auto space-y-3 pr-1">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-slate-100 text-slate-800 border border-slate-200/80"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 px-1">
                    {msg.ts}
                  </span>
                </div>
              ))}

              {/* Streaming Tokens Bubble */}
              {streamedTokens && (
                <div className="flex flex-col items-start">
                  <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-xs bg-slate-100 text-slate-800 border border-blue-200 animate-pulse">
                    <div className="whitespace-pre-wrap">{streamedTokens}</div>
                  </div>
                </div>
              )}

              {/* Running Status Pill */}
              {isRunning && (
                <div className="flex items-center gap-2 p-2 rounded-xl bg-blue-50 border border-blue-200 text-blue-700 text-xs">
                  <div className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-ping" />
                  <span>Subprocess running graph execution...</span>
                </div>
              )}

              {/* Human-in-the-Loop Interrupt Approval Card */}
              {isInterrupted && interruptRequest && (
                <div className="p-4 rounded-2xl bg-amber-50 border border-amber-300 shadow-sm space-y-3">
                  <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    Human Review Required (Paused)
                  </div>

                  <p className="text-xs text-amber-900 font-medium">
                    {interruptRequest.prompt}
                  </p>

                  {/* Summary / Fields */}
                  {interruptRequest.state_summary && (
                    <div className="p-2 rounded-xl bg-white border border-amber-200 text-[11px] font-mono text-slate-700 max-h-28 overflow-y-auto">
                      {JSON.stringify(interruptRequest.state_summary, null, 2)}
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={handleApprove}
                      className="flex-1 py-1.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition cursor-pointer"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Approve
                    </button>

                    <button
                      onClick={() => setShowRejectInput(!showRejectInput)}
                      className="py-1.5 px-3 rounded-xl bg-rose-100 hover:bg-rose-200 text-rose-700 font-semibold text-xs transition cursor-pointer"
                    >
                      Reject
                    </button>

                    <button
                      onClick={() => setStateInspectorOpen(true)}
                      className="py-1.5 px-3 rounded-xl bg-white border border-amber-300 hover:bg-amber-100 text-amber-800 text-xs transition cursor-pointer"
                    >
                      Edit State
                    </button>
                  </div>

                  {showRejectInput && (
                    <div className="space-y-2 pt-2">
                      <input
                        type="text"
                        placeholder="Rejection reason..."
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        className="w-full px-3 py-1.5 rounded-xl border border-rose-200 bg-white text-xs text-slate-800 focus:outline-none"
                      />
                      <button
                        onClick={handleReject}
                        className="w-full py-1 rounded-lg bg-rose-600 text-white text-xs font-semibold cursor-pointer"
                      >
                        Confirm Reject
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Input Box Footer */}
            <div className="pt-3 border-t border-slate-200 flex items-center gap-2">
              <input
                type="text"
                placeholder="Type input message or click Run..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                disabled={isRunning}
                className="flex-1 px-3.5 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 bg-white focus:outline-none focus:border-blue-500"
              />

              {isRunning ? (
                <button
                  onClick={cancelRun}
                  title="Stop Execution"
                  className="p-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white transition cursor-pointer"
                >
                  <Square className="w-4 h-4 fill-current" />
                </button>
              ) : (
                <button
                  onClick={handleSendMessage}
                  title="Send & Run"
                  className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition cursor-pointer"
                >
                  <Send className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: TIME TRAVEL TIMELINE */}
        {activeTab === "timeline" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-700">Checkpoints Tree</span>
              <button
                onClick={() => loadThreadHistory()}
                className="text-xs text-blue-600 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" /> Refresh
              </button>
            </div>

            {checkpointsHistory.length === 0 ? (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
                No checkpoints in thread '{currentThreadId}' yet. Run the graph to record snapshots.
              </div>
            ) : (
              <div className="space-y-2.5">
                {checkpointsHistory.map((cp, idx) => (
                  <div
                    key={cp.checkpoint_id}
                    className="p-3 rounded-xl border border-slate-200 bg-white hover:border-blue-400 transition shadow-xs space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold text-slate-800">
                        #{checkpointsHistory.length - idx} {cp.checkpoint_id.slice(0, 8)}...
                      </span>
                      {cp.next && cp.next.length > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-semibold text-[10px]">
                          next: {cp.next.join(", ")}
                        </span>
                      )}
                    </div>

                    <div className="text-[11px] text-slate-500">
                      Step {cp.metadata?.step ?? idx} · source: {cp.metadata?.source || "loop"}
                    </div>

                    <div className="flex items-center gap-2 pt-1 border-t border-slate-100 text-xs">
                      <button
                        onClick={() => forkThread(cp.checkpoint_id)}
                        className="py-1 px-2.5 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-medium text-[11px] flex items-center gap-1 cursor-pointer"
                      >
                        <GitFork className="w-3 h-3" />
                        Fork from here
                      </button>

                      <button
                        onClick={() => {
                          useGraphStore.setState({ latestState: cp.values });
                          setStateInspectorOpen(true);
                        }}
                        className="py-1 px-2.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-[11px] cursor-pointer"
                      >
                        Inspect State
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: SHARED STORE */}
        {activeTab === "store" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-700">Namespace</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={storeNamespace}
                  onChange={(e) => setStoreNamespace(e.target.value)}
                  className="flex-1 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-mono"
                />
                <button
                  onClick={() => loadStore(storeNamespace)}
                  className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-xs font-semibold cursor-pointer"
                >
                  Load
                </button>
              </div>
            </div>

            {/* Put Item Form */}
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <div className="text-xs font-bold text-slate-800">Add Memory Item</div>
              <input
                type="text"
                placeholder="Key (e.g. user_prefs)"
                value={newStoreKey}
                onChange={(e) => setNewStoreKey(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs"
              />
              <textarea
                rows={2}
                placeholder="JSON Value (e.g. {'theme': 'dark'})"
                value={newStoreVal}
                onChange={(e) => setNewStoreVal(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-mono"
              />
              <button
                onClick={handleSaveStore}
                className="w-full py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs cursor-pointer"
              >
                Save to Store
              </button>
            </div>

            {/* List of items */}
            <div className="space-y-2">
              <div className="text-xs font-bold text-slate-700">Stored Items ({storeItems.length})</div>
              {storeItems.length === 0 ? (
                <div className="text-xs text-slate-400">No items found in namespace '{storeNamespace}'.</div>
              ) : (
                storeItems.map((it) => (
                  <div
                    key={it.key}
                    className="p-2.5 rounded-xl border border-slate-200 bg-white space-y-1"
                  >
                    <div className="text-xs font-mono font-bold text-slate-800">{it.key}</div>
                    <pre className="text-[10px] font-mono text-slate-600 bg-slate-50 p-1.5 rounded overflow-x-auto">
                      {JSON.stringify(it.value, null, 2)}
                    </pre>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
