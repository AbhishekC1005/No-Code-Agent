import { useState } from "react";
import {
  X,
  Zap,
  Clock,
  Globe,
  Plus,
  Trash2,
  Copy,
  Check,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";
import type { TriggerDefinition } from "../types/graph";

export function TriggersModal() {
  const isTriggersOpen = useGraphStore((s) => s.isTriggersOpen);
  const setTriggersOpen = useGraphStore((s) => s.setTriggersOpen);
  const workflowId = useGraphStore((s) => s.workflowId);
  const triggers = useGraphStore((s) => s.triggers);
  const loadTriggers = useGraphStore((s) => s.loadTriggers);
  const createTrigger = useGraphStore((s) => s.createTrigger);
  const updateTrigger = useGraphStore((s) => s.updateTrigger);
  const deleteTrigger = useGraphStore((s) => s.deleteTrigger);

  const [activeTab, setActiveTab] = useState<"list" | "create">("list");
  const [triggerType, setTriggerType] = useState<"webhook" | "cron">("webhook");
  const [name, setName] = useState("");
  const [webhookPath, setWebhookPath] = useState("incoming");
  const [webhookToken, setWebhookToken] = useState("");
  const [cronExpression, setCronExpression] = useState("*/15 * * * *");
  const [threadIdRule, setThreadIdRule] = useState("uuid");
  const [customPayload, setCustomPayload] = useState('{\n  "query": "Hello from trigger"\n}');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isTriggersOpen) return null;

  const currentWfId = workflowId || "default";

  const handleCreate = async () => {
    setError(null);
    if (!name.trim()) {
      setError("Please provide a trigger name");
      return;
    }

    let parsedPayload = {};
    if (customPayload.trim()) {
      try {
        parsedPayload = JSON.parse(customPayload);
      } catch {
        setError("Invalid JSON in custom payload");
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const config: any = {
        thread_id_rule: threadIdRule,
      };

      if (triggerType === "webhook") {
        config.path = webhookPath.trim() || "incoming";
        if (webhookToken.trim()) config.token = webhookToken.trim();
        config.payload_mapping = parsedPayload;
      } else {
        config.cron_expression = cronExpression.trim() || "*/15 * * * *";
        config.payload = parsedPayload;
      }

      await createTrigger(name.trim(), triggerType, config, true);
      setName("");
      setWebhookPath("incoming");
      setWebhookToken("");
      setActiveTab("list");
    } catch (err: any) {
      setError(err?.message || "Failed to create trigger");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (trigger: TriggerDefinition) => {
    try {
      await updateTrigger(trigger.id, { is_active: !trigger.is_active });
    } catch (e: any) {
      setError(e?.message || "Failed to toggle trigger status");
    }
  };

  const copyWebhookUrl = (path: string, token?: string) => {
    const origin = window.location.origin;
    const cleanPath = path.startsWith("/") ? path.slice(1) : path;
    let url = `${origin}/api/v1/webhook/${currentWfId}/${cleanPath}`;
    if (token) url += `?token=${encodeURIComponent(token)}`;
    navigator.clipboard.writeText(url);
    setCopiedId(path);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl flex flex-col max-h-[88vh] overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Triggers & Automation</h2>
              <p className="text-[11px] text-slate-400">
                Trigger this workflow via external Webhooks or APScheduler Cron
              </p>
            </div>
          </div>
          <button
            onClick={() => setTriggersOpen(false)}
            className="w-7 h-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex items-center justify-center transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Selector */}
        <div className="px-6 pt-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
          <div className="flex gap-2">
            <button
              onClick={() => {
                setActiveTab("list");
                setError(null);
              }}
              className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
                activeTab === "list"
                  ? "border-amber-500 text-amber-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              Active Triggers ({triggers.length})
            </button>
            <button
              onClick={() => {
                setActiveTab("create");
                setError(null);
              }}
              className={`pb-2.5 px-3 text-xs font-semibold border-b-2 transition-all cursor-pointer ${
                activeTab === "create"
                  ? "border-amber-500 text-amber-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              + New Trigger
            </button>
          </div>

          <button
            onClick={() => loadTriggers()}
            title="Refresh triggers"
            className="mb-2 text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-200/50 rounded-md transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-3 px-3 py-2 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 font-medium">
            {error}
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {activeTab === "list" ? (
            triggers.length === 0 ? (
              <div className="text-center py-12 space-y-3">
                <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-500 mx-auto flex items-center justify-center">
                  <Zap className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-700">No triggers configured</h3>
                  <p className="text-[11px] text-slate-400 max-w-sm mx-auto mt-0.5">
                    Configure webhooks to receive external HTTP events, or cron schedules to run automatically.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab("create")}
                  className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add First Trigger</span>
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {triggers.map((trig) => {
                  const isWebhook = trig.type === "webhook";
                  const path = trig.config?.path || "incoming";
                  const token = trig.config?.token;
                  const cronExpr = trig.config?.cron_expression || "*/15 * * * *";

                  return (
                    <div
                      key={trig.id}
                      className={`p-4 rounded-xl border transition-all ${
                        trig.is_active
                          ? "bg-white border-slate-200 shadow-2xs hover:border-slate-300"
                          : "bg-slate-50/70 border-slate-200/60 opacity-60"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2.5">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                              isWebhook
                                ? "bg-blue-50 text-blue-600 border border-blue-100"
                                : "bg-purple-50 text-purple-600 border border-purple-100"
                            }`}
                          >
                            {isWebhook ? <Globe className="w-4 h-4" /> : <Clock className="w-4 h-4" />}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-800">{trig.name}</span>
                              <span
                                className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                                  isWebhook
                                    ? "bg-blue-50 text-blue-700 border border-blue-200"
                                    : "bg-purple-50 text-purple-700 border border-purple-200"
                                }`}
                              >
                                {trig.type}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-400 mt-0.5">
                              {isWebhook ? `Path: /${path}` : `Cron: ${cronExpr}`}
                              {trig.last_run && (
                                <span className="ml-2 font-medium text-slate-500">
                                  Last run: {new Date(trig.last_run).toLocaleTimeString()}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {/* Active Toggle */}
                          <button
                            onClick={() => handleToggleActive(trig)}
                            title={trig.is_active ? "Disable trigger" : "Enable trigger"}
                            className="cursor-pointer text-slate-500 hover:text-slate-700 transition-colors"
                          >
                            {trig.is_active ? (
                              <ToggleRight className="w-6 h-6 text-emerald-500" />
                            ) : (
                              <ToggleLeft className="w-6 h-6 text-slate-300" />
                            )}
                          </button>

                          {/* Delete Trigger */}
                          <button
                            onClick={() => deleteTrigger(trig.id)}
                            title="Delete trigger"
                            className="p-1 text-slate-300 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* Webhook URL Helper */}
                      {isWebhook && (
                        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between bg-slate-50 p-2.5 rounded-lg">
                          <code className="text-[11px] font-mono text-slate-600 truncate max-w-md">
                            /api/v1/webhook/{currentWfId}/{path}
                            {token && `?token=${token}`}
                          </code>
                          <button
                            onClick={() => copyWebhookUrl(path, token)}
                            className="px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded-md text-[11px] font-semibold text-slate-700 flex items-center gap-1 shadow-2xs transition-colors cursor-pointer flex-shrink-0"
                          >
                            {copiedId === path ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-600" />
                                <span className="text-emerald-600">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3 text-slate-500" />
                                <span>Copy URL</span>
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )
          ) : (
            /* Create Trigger Form */
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">Trigger Type</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setTriggerType("webhook")}
                    className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                      triggerType === "webhook"
                        ? "border-blue-500 bg-blue-50/40 text-blue-900 shadow-2xs"
                        : "border-slate-200 hover:border-slate-300 bg-white text-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Globe className="w-4 h-4 text-blue-600" />
                      <span className="text-xs font-bold">Webhook</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Invoked by incoming HTTP POST/GET requests from GitHub, Stripe, or custom clients.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setTriggerType("cron")}
                    className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                      triggerType === "cron"
                        ? "border-purple-500 bg-purple-50/40 text-purple-900 shadow-2xs"
                        : "border-slate-200 hover:border-slate-300 bg-white text-slate-700"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Clock className="w-4 h-4 text-purple-600" />
                      <span className="text-xs font-bold">Cron Schedule</span>
                    </div>
                    <p className="text-[10px] text-slate-500 leading-tight">
                      Runs automatically in background on fixed intervals via APScheduler.
                    </p>
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">Trigger Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Daily Sync or GitHub Push Webhook"
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
                />
              </div>

              {triggerType === "webhook" ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-slate-700 block mb-1">Endpoint Path</label>
                      <div className="flex items-center">
                        <span className="px-2.5 py-2 bg-slate-100 border border-r-0 border-slate-200 rounded-l-lg text-[11px] text-slate-500">
                          /
                        </span>
                        <input
                          type="text"
                          value={webhookPath}
                          onChange={(e) => setWebhookPath(e.target.value)}
                          placeholder="incoming"
                          className="w-full px-3 py-2 text-xs border border-slate-200 rounded-r-lg text-slate-800 focus:outline-none focus:border-blue-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-xs font-bold text-slate-700 block mb-1">
                        Secret Token (Optional)
                      </label>
                      <input
                        type="password"
                        value={webhookToken}
                        onChange={(e) => setWebhookToken(e.target.value)}
                        placeholder="Secret for X-Webhook-Token"
                        className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg text-slate-800 placeholder-slate-400 focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <label className="text-xs font-bold text-slate-700 block mb-1">
                    Cron Expression (5-part format)
                  </label>
                  <input
                    type="text"
                    value={cronExpression}
                    onChange={(e) => setCronExpression(e.target.value)}
                    placeholder="*/15 * * * *"
                    className="w-full px-3 py-2 font-mono text-xs border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-purple-500"
                  />
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    Standard format: minute hour day month day-of-week (e.g. 0 9 * * 1-5 for weekdays at 9am)
                  </span>
                </div>
              )}

              {/* Thread ID Resolution */}
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">Thread ID Rule</label>
                <select
                  value={threadIdRule}
                  onChange={(e) => setThreadIdRule(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-amber-500"
                >
                  <option value="uuid">New Thread per run (uuid)</option>
                  <option value="static:main_stream">Static thread (static:main_stream)</option>
                  <option value="field:thread_id">From payload field (field:thread_id)</option>
                  <option value="field:user_id">From payload user (field:user_id)</option>
                </select>
              </div>

              {/* Payload Configuration */}
              <div>
                <label className="text-xs font-bold text-slate-700 block mb-1">
                  Default Input Payload (JSON)
                </label>
                <textarea
                  value={customPayload}
                  onChange={(e) => setCustomPayload(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 font-mono text-xs border border-slate-200 rounded-lg text-slate-800 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab("list")}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={isSubmitting}
                  className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl text-xs font-bold shadow-xs transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isSubmitting ? "Creating..." : "Save Trigger"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
