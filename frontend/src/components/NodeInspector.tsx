import { useState } from "react";
import {
  X,
  Trash2,
  Settings2,
  Sliders,
  AlertTriangle,
  Key,
  ShieldCheck,
  Plus,
  Braces,
  Code2,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";
import type { NodeTypeField } from "../types/graph";

export function NodeInspector() {
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const selectNode = useGraphStore((s) => s.selectNode);
  const graph = useGraphStore((s) => s.graph);
  const activeSubgraphId = useGraphStore((s) => s.activeSubgraphId);
  const nodeTypes = useGraphStore((s) => s.nodeTypes);
  const updateNode = useGraphStore((s) => s.updateNode);
  const updateNodeConfig = useGraphStore((s) => s.updateNodeConfig);
  const updateNodePolicy = useGraphStore((s) => s.updateNodePolicy);
  const deleteNode = useGraphStore((s) => s.deleteNode);
  const diagnostics = useGraphStore((s) => s.diagnostics);
  const credentials = useGraphStore((s) => s.credentials);
  const setCredentialsOpen = useGraphStore((s) => s.setCredentialsOpen);

  const [activeTab, setActiveTab] = useState<"config" | "advanced">("config");

  const nodes = activeSubgraphId && graph.subgraphs[activeSubgraphId]
    ? graph.subgraphs[activeSubgraphId].nodes
    : graph.nodes;

  const node = nodes.find((n) => n.id === selectedNodeId);

  if (!selectedNodeId || !node) return null;

  const nodeType = (node.type || "agent").toLowerCase();
  const typeDef = nodeTypes.find((t) => t.type.toLowerCase() === nodeType);
  const fields: NodeTypeField[] = typeDef?.fields || [];
  const cfg = node.config || {};
  const policy = node.policy || {};
  const retry = policy.retry || {};
  const cache = policy.cache || {};

  const nodeDiagnostics = diagnostics.filter((d) => d.node_id === node.id);

  const renderField = (f: NodeTypeField) => {
    const val = cfg[f.name] !== undefined ? cfg[f.name] : f.default ?? "";

    if (f.type === "select") {
      return (
        <div key={f.name} className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">{f.label}</label>
          <select
            value={val}
            onChange={(e) => updateNodeConfig(node.id, { [f.name]: e.target.value })}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 bg-white focus:outline-none focus:border-blue-500"
          >
            {(f.options || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (f.type === "textarea") {
      return (
        <div key={f.name} className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">{f.label}</label>
          <textarea
            rows={3}
            value={val}
            placeholder={f.placeholder}
            onChange={(e) => updateNodeConfig(node.id, { [f.name]: e.target.value })}
            className="w-full p-2.5 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
          />
        </div>
      );
    }

    if (f.type === "code") {
      return (
        <div key={f.name} className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">{f.label}</label>
          <textarea
            rows={5}
            value={val}
            placeholder={f.placeholder}
            onChange={(e) => updateNodeConfig(node.id, { [f.name]: e.target.value })}
            className="w-full p-2.5 rounded-xl border border-slate-200 text-xs font-mono text-slate-800 bg-slate-50 focus:outline-none focus:border-blue-500"
          />
        </div>
      );
    }

    if (f.type === "boolean") {
      return (
        <div key={f.name} className="flex items-center justify-between py-1">
          <label className="text-xs font-semibold text-slate-700">{f.label}</label>
          <input
            type="checkbox"
            checked={Boolean(val)}
            onChange={(e) => updateNodeConfig(node.id, { [f.name]: e.target.checked })}
            className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
          />
        </div>
      );
    }

    if (f.type === "number") {
      return (
        <div key={f.name} className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-700">{f.label}</label>
          <input
            type="number"
            min={f.min}
            max={f.max}
            step={f.step || 1}
            value={val}
            onChange={(e) =>
              updateNodeConfig(node.id, { [f.name]: parseFloat(e.target.value) || 0 })
            }
            className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
          />
        </div>
      );
    }

    // Default text input
    return (
      <div key={f.name} className="space-y-1.5">
        <label className="text-xs font-semibold text-slate-700">{f.label}</label>
        <input
          type="text"
          value={val}
          placeholder={f.placeholder}
          onChange={(e) => updateNodeConfig(node.id, { [f.name]: e.target.value })}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
        />
      </div>
    );
  };

  return (
    <div className="w-80 bg-white border-l border-slate-200 p-5 flex flex-col justify-between shadow-lg z-20 overflow-y-auto">
      <div className="space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
              {nodeType}
            </div>
            <div className="text-sm font-bold text-slate-800 truncate max-w-[190px]">
              {node.label || node.id}
            </div>
          </div>
          <button
            onClick={() => selectNode(null)}
            className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Diagnostics Banner */}
        {nodeDiagnostics.length > 0 && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-bold text-amber-800">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> Diagnostics
            </div>
            {nodeDiagnostics.map((d, i) => (
              <div key={i} className="text-[11px] text-amber-700 leading-tight">
                • {d.message}
              </div>
            ))}
          </div>
        )}

        {/* Tab Switcher */}
        <div className="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 rounded-xl">
          <button
            onClick={() => setActiveTab("config")}
            className={`py-1.5 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeTab === "config"
                ? "bg-white text-slate-800 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Settings2 className="w-3.5 h-3.5" /> Config
          </button>
          <button
            onClick={() => setActiveTab("advanced")}
            className={`py-1.5 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-all ${
              activeTab === "advanced"
                ? "bg-white text-slate-800 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" /> Advanced
          </button>
        </div>

        {/* Tab 1: Config */}
        {activeTab === "config" && (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">Display Label</label>
              <input
                type="text"
                value={node.label || ""}
                onChange={(e) => updateNode(node.id, { label: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              />
            </div>

            {fields.map(renderField)}

            {/* Specialized Human Node Form */}
            {(nodeType === "human" || nodeType === "human_review") && (
              <div className="space-y-3 pt-2 border-t border-slate-100">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700">Approval Prompt</label>
                  <textarea
                    rows={2}
                    value={cfg.prompt || "Please review and approve this action."}
                    onChange={(e) => updateNodeConfig(node.id, { prompt: e.target.value })}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            )}

            {/* Specialized LLM Node Configuration (Phase 6) */}
            {["llm", "agent", "model"].includes(nodeType) && (
              <div className="space-y-3.5 pt-2 border-t border-slate-100">
                {/* Credential ID Selector */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                      <Key className="w-3.5 h-3.5 text-blue-600" />
                      <span>API Credential</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => setCredentialsOpen(true)}
                      className="text-[11px] text-blue-600 hover:underline font-medium cursor-pointer"
                    >
                      + Manage
                    </button>
                  </div>
                  <select
                    value={cfg.credential_id || ""}
                    onChange={(e) => updateNodeConfig(node.id, { credential_id: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 bg-white"
                  >
                    <option value="">Default (Environment variables)</option>
                    {credentials.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.type}) • {c.masked_value}
                      </option>
                    ))}
                  </select>
                </div>

                {/* System Prompt with State Token Chips */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-slate-700">System Prompt</label>
                    <span className="text-[10px] text-slate-400">Tokens:</span>
                  </div>
                  {/* Token chips */}
                  {graph.state?.fields && graph.state.fields.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {graph.state.fields.map((f) => (
                        <button
                          key={f.name}
                          type="button"
                          onClick={() => {
                            const cur = cfg.systemPrompt || "";
                            const token = `{${f.name}}`;
                            updateNodeConfig(node.id, { systemPrompt: cur ? `${cur} ${token}` : token });
                          }}
                          className="px-1.5 py-0.5 rounded bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 font-mono text-[10px] transition-colors cursor-pointer"
                          title={`Insert {${f.name}}`}
                        >
                          +{f.name}
                        </button>
                      ))}
                    </div>
                  )}
                  <textarea
                    rows={3}
                    value={cfg.systemPrompt || ""}
                    placeholder="You are a helpful assistant..."
                    onChange={(e) => updateNodeConfig(node.id, { systemPrompt: e.target.value })}
                    className="w-full p-2.5 rounded-xl border border-slate-200 text-xs text-slate-800 font-sans focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* Bind Tools Toggle */}
                <div className="flex items-center justify-between py-1 border-t border-slate-100">
                  <div>
                    <div className="text-xs font-semibold text-slate-700">Bind Tools</div>
                    <div className="text-[11px] text-slate-500">Provide tools to model for tool calling</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={Boolean(cfg.bind_tools)}
                    onChange={(e) => updateNodeConfig(node.id, { bind_tools: e.target.checked })}
                    className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
                  />
                </div>

                {/* Structured Output Builder */}
                <div className="space-y-2.5 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                        <Braces className="w-3.5 h-3.5 text-purple-600" />
                        <span>Structured Output</span>
                      </div>
                      <div className="text-[11px] text-slate-500">Pydantic schema generation</div>
                    </div>
                    <input
                      type="checkbox"
                      checked={Boolean(cfg.structured_output)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          updateNodeConfig(node.id, {
                            structured_output: {
                              schema_name: `${node.label?.replace(/[^a-zA-Z0-9]/g, "") || "Node"}Output`,
                              description: "Structured extraction schema",
                              fields: [{ name: "response", type: "str", description: "Output text" }],
                            },
                          });
                        } else {
                          updateNodeConfig(node.id, { structured_output: null });
                        }
                      }}
                      className="w-4 h-4 rounded text-purple-600 focus:ring-purple-500 border-slate-300"
                    />
                  </div>

                  {cfg.structured_output && (
                    <div className="p-3 rounded-xl bg-purple-50/50 border border-purple-200 space-y-3">
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold uppercase text-purple-800">Schema Class</label>
                          <input
                            type="text"
                            value={cfg.structured_output.schema_name || ""}
                            onChange={(e) => {
                              const so = { ...cfg.structured_output, schema_name: e.target.value };
                              updateNodeConfig(node.id, { structured_output: so });
                            }}
                            className="w-full px-2 py-1 rounded-lg border border-purple-200 text-xs bg-white text-slate-800"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] font-bold uppercase text-purple-800">Output Field</label>
                          <input
                            type="text"
                            placeholder="e.g. extracted_data"
                            value={cfg.output_field || ""}
                            onChange={(e) => updateNodeConfig(node.id, { output_field: e.target.value })}
                            className="w-full px-2 py-1 rounded-lg border border-purple-200 text-xs bg-white text-slate-800"
                          />
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold uppercase text-purple-800">Schema Fields</span>
                          <button
                            type="button"
                            onClick={() => {
                              const currentFields = cfg.structured_output.fields || [];
                              const so = {
                                ...cfg.structured_output,
                                fields: [...currentFields, { name: `field_${currentFields.length + 1}`, type: "str", description: "" }],
                              };
                              updateNodeConfig(node.id, { structured_output: so });
                            }}
                            className="text-[10px] font-bold text-purple-700 hover:text-purple-900 flex items-center gap-0.5 cursor-pointer"
                          >
                            <Plus className="w-3 h-3" /> Add
                          </button>
                        </div>

                        <div className="space-y-2">
                          {(cfg.structured_output.fields || []).map((f: any, idx: number) => (
                            <div key={idx} className="p-2 rounded-lg bg-white border border-purple-200 space-y-1 text-xs">
                              <div className="flex items-center gap-1.5">
                                <input
                                  type="text"
                                  placeholder="field_name"
                                  value={f.name}
                                  onChange={(e) => {
                                    const nextFields = [...cfg.structured_output.fields];
                                    nextFields[idx] = { ...nextFields[idx], name: e.target.value };
                                    updateNodeConfig(node.id, { structured_output: { ...cfg.structured_output, fields: nextFields } });
                                  }}
                                  className="flex-1 px-1.5 py-0.5 rounded border border-slate-200 font-mono text-[11px]"
                                />
                                <select
                                  value={f.type}
                                  onChange={(e) => {
                                    const nextFields = [...cfg.structured_output.fields];
                                    nextFields[idx] = { ...nextFields[idx], type: e.target.value };
                                    updateNodeConfig(node.id, { structured_output: { ...cfg.structured_output, fields: nextFields } });
                                  }}
                                  className="w-16 px-1 py-0.5 rounded border border-slate-200 text-[11px] bg-white"
                                >
                                  <option value="str">str</option>
                                  <option value="int">int</option>
                                  <option value="float">float</option>
                                  <option value="bool">bool</option>
                                  <option value="list">list</option>
                                  <option value="dict">dict</option>
                                </select>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const nextFields = cfg.structured_output.fields.filter((_: any, i: number) => i !== idx);
                                    updateNodeConfig(node.id, { structured_output: { ...cfg.structured_output, fields: nextFields } });
                                  }}
                                  className="text-slate-400 hover:text-rose-600 px-1 cursor-pointer"
                                >
                                  ✕
                                </button>
                              </div>
                              <input
                                type="text"
                                placeholder="Description for LLM..."
                                value={f.description}
                                onChange={(e) => {
                                  const nextFields = [...cfg.structured_output.fields];
                                  nextFields[idx] = { ...nextFields[idx], description: e.target.value };
                                  updateNodeConfig(node.id, { structured_output: { ...cfg.structured_output, fields: nextFields } });
                                }}
                                className="w-full px-1.5 py-0.5 rounded border border-slate-100 text-[10px] text-slate-500"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Specialized Tool Node Configuration (Phase 6) */}
            {["tool", "tools"].includes(nodeType) && (
              <div className="space-y-3 pt-2 border-t border-slate-100">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-slate-700">Tool Type</label>
                  <select
                    value={cfg.tool_type || "http"}
                    onChange={(e) => updateNodeConfig(node.id, { tool_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 bg-white"
                  >
                    <option value="http">HTTP Webhook / Endpoint</option>
                    <option value="python">Custom Python @tool</option>
                  </select>
                </div>

                {cfg.tool_type !== "python" ? (
                  <div className="space-y-2.5">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase">Method</label>
                        <select
                          value={cfg.method || "GET"}
                          onChange={(e) => updateNodeConfig(node.id, { method: e.target.value })}
                          className="w-full px-2 py-1.5 rounded-lg border border-slate-200 text-xs bg-white"
                        >
                          <option value="GET">GET</option>
                          <option value="POST">POST</option>
                          <option value="PUT">PUT</option>
                          <option value="DELETE">DELETE</option>
                        </select>
                      </div>
                      <div className="col-span-2 space-y-1">
                        <label className="text-[10px] font-bold text-slate-500 uppercase">Endpoint URL</label>
                        <input
                          type="text"
                          placeholder="https://api.example.com/..."
                          value={cfg.url || ""}
                          onChange={(e) => updateNodeConfig(node.id, { url: e.target.value })}
                          className="w-full px-2 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-800"
                        />
                      </div>
                    </div>

                    {/* SSRF Guard Indicator */}
                    <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-2 text-emerald-800 text-[11px]">
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>SSRF Guard active: Requests to private, loopback, or cloud metadata IPs are strictly blocked.</span>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 flex items-center gap-1.5">
                      <Code2 className="w-3.5 h-3.5 text-blue-600" />
                      <span>Python @tool Definition</span>
                    </label>
                    <textarea
                      rows={8}
                      placeholder={`@tool\ndef my_tool(query: str) -> str:\n    """Tool description."""\n    return f"Result: {query}"`}
                      value={cfg.code || ""}
                      onChange={(e) => updateNodeConfig(node.id, { code: e.target.value })}
                      className="w-full p-2.5 rounded-xl border border-slate-200 font-mono text-xs text-slate-800 bg-slate-50 focus:outline-none focus:border-blue-500"
                    />
                  </div>
                )}
              </div>
            )}

            {/* Specialized Memory Store Forms */}
            {(nodeType === "memory_read" || nodeType === "memory_write") && (
              <div className="space-y-3 pt-2 border-t border-slate-100">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700">Store Key</label>
                  <input
                    type="text"
                    value={cfg.key || "user_prefs"}
                    onChange={(e) => updateNodeConfig(node.id, { key: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800"
                  />
                </div>
                {nodeType === "memory_read" && (
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700">State Output Field</label>
                    <input
                      type="text"
                      value={cfg.output_field || "memory"}
                      onChange={(e) => updateNodeConfig(node.id, { output_field: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Advanced (Policies & Breakpoints) */}
        {activeTab === "advanced" && (
          <div className="space-y-5">
            {/* Breakpoints */}
            <div className="space-y-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
              <div className="text-xs font-bold text-slate-800">Breakpoints</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <div className="font-semibold text-slate-700">Pause Before</div>
                    <div className="text-[11px] text-slate-500">Halt graph before executing this node</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={Boolean(policy.interrupt_before)}
                    onChange={(e) =>
                      updateNodePolicy(node.id, { interrupt_before: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
                  />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <div>
                    <div className="font-semibold text-slate-700">Pause After</div>
                    <div className="text-[11px] text-slate-500">Halt graph after executing this node</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={Boolean(policy.interrupt_after)}
                    onChange={(e) =>
                      updateNodePolicy(node.id, { interrupt_after: e.target.checked })
                    }
                    className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
                  />
                </div>
              </div>
            </div>
            {/* Retry Policy */}
            <div className="space-y-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
              <div className="text-xs font-bold text-slate-800">Retry Policy</div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Max Attempts</span>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    value={retry.max_retries ?? 0}
                    onChange={(e) =>
                      updateNodePolicy(node.id, {
                        retry: { ...retry, max_retries: parseInt(e.target.value, 10) || 0 },
                      })
                    }
                    className="w-16 px-2 py-1 rounded-lg border border-slate-200 text-xs bg-white text-right"
                  />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Initial Delay (sec)</span>
                  <input
                    type="number"
                    min={0.1}
                    step={0.5}
                    value={retry.delay ?? 1.0}
                    onChange={(e) =>
                      updateNodePolicy(node.id, {
                        retry: { ...retry, delay: parseFloat(e.target.value) || 1.0 },
                      })
                    }
                    className="w-16 px-2 py-1 rounded-lg border border-slate-200 text-xs bg-white text-right"
                  />
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-600">Backoff Factor</span>
                  <input
                    type="number"
                    min={1.0}
                    step={0.5}
                    value={retry.backoff_factor ?? 2.0}
                    onChange={(e) =>
                      updateNodePolicy(node.id, {
                        retry: { ...retry, backoff_factor: parseFloat(e.target.value) || 2.0 },
                      })
                    }
                    className="w-16 px-2 py-1 rounded-lg border border-slate-200 text-xs bg-white text-right"
                  />
                </div>
              </div>
            </div>

            {/* Cache Policy */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-slate-800">Cache Node Output</div>
                <div className="text-[11px] text-slate-500">Reuse output if state input matches</div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(cache.enabled)}
                onChange={(e) =>
                  updateNodePolicy(node.id, {
                    cache: { enabled: e.target.checked },
                  })
                }
                className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
              />
            </div>

            {/* Defer Execution */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-slate-800">Defer Execution</div>
                <div className="text-[11px] text-slate-500">Wait for other parallel branches before running</div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(policy.defer)}
                onChange={(e) =>
                  updateNodePolicy(node.id, {
                    defer: e.target.checked,
                  })
                }
                className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 border-slate-300"
              />
            </div>
          </div>
        )}
      </div>

      {/* Delete Node Footer */}
      <div className="pt-4 border-t border-slate-100">
        <button
          onClick={() => {
            deleteNode(node.id);
            selectNode(null);
          }}
          className="w-full py-2 px-3 rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-600 text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Delete Node
        </button>
      </div>
    </div>
  );
}
