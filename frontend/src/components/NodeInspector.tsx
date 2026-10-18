import type { Node } from "@xyflow/react";
import { X, Trash2 } from "lucide-react";
import { NODE_CATEGORIES, type NodeCategoryKey } from "../theme/nodeCategories";

interface Props {
  selectedNode: Node | null;
  onUpdateNode: (nodeId: string, newData: Record<string, any>) => void;
  onDeleteNode: (nodeId: string) => void;
  onClose: () => void;
}

export function NodeInspector({
  selectedNode,
  onUpdateNode,
  onDeleteNode,
  onClose,
}: Props) {
  if (!selectedNode) return null;

  const data: any = selectedNode.data || {};
  const catKey: NodeCategoryKey = data.category || "agents";
  const theme = NODE_CATEGORIES[catKey];
  const cfg = data.config || {};

  const updateConfig = (key: string, value: any) => {
    onUpdateNode(selectedNode.id, {
      ...data,
      config: { ...cfg, [key]: value },
    });
  };

  return (
    <div className="w-80 bg-white border-l border-[#E5E7EB] p-5 flex flex-col justify-between shadow-soft z-20">
      <div className="space-y-4 overflow-y-auto pr-1">
        <div className="flex items-center justify-between pb-3 border-b border-[#E5E7EB]">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${theme.dotColor}`} />
            <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A]">
              {theme.label} Inspector
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-100 text-[#94A3B8]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Node Label */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-[#0F172A]">Node Name</label>
          <input
            value={data.label || ""}
            onChange={(e) =>
              onUpdateNode(selectedNode.id, { ...data, label: e.target.value })
            }
            className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A] focus:outline-none focus:border-[#3B82F6]"
          />
        </div>

        {/* Models & Agents Settings */}
        {(catKey === "models" || catKey === "agents") && (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                LLM Provider
              </label>
              <select
                value={cfg.llmProvider || "openai"}
                onChange={(e) => updateConfig("llmProvider", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A] bg-white"
              >
                <option value="openai">OpenAI (Direct Browser HTTPS)</option>
                <option value="anthropic">Anthropic Claude (Direct Browser)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                Model ID
              </label>
              <input
                value={cfg.model || "gpt-4o-mini"}
                onChange={(e) => updateConfig("model", e.target.value)}
                placeholder="gpt-4o-mini or claude-3-5-sonnet-latest"
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                System Prompt
              </label>
              <textarea
                rows={4}
                value={cfg.systemPrompt || ""}
                onChange={(e) => updateConfig("systemPrompt", e.target.value)}
                placeholder="You are a LangGraph specialist agent..."
                className="w-full p-3 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
          </>
        )}

        {/* Knowledge (Vector DB) & Memory Settings */}
        {(catKey === "knowledge" || catKey === "memory") && (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                Database / Vector Provider
              </label>
              <select
                value={cfg.provider || "Pinecone"}
                onChange={(e) => updateConfig("provider", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A] bg-white"
              >
                <option value="Browser PGlite (pgvector)">
                  Browser Sandbox (PGlite / IndexedDB)
                </option>
                <option value="Pinecone">Pinecone Vector Store</option>
                <option value="PostgreSQL (pgvector)">
                  PostgreSQL (pgvector / PostgresSaver)
                </option>
                <option value="MongoDB Atlas">
                  MongoDB Atlas Vector / MongoDBSaver
                </option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                Index / Collection Name
              </label>
              <input
                value={cfg.indexName || "agent_knowledge"}
                onChange={(e) => updateConfig("indexName", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
          </>
        )}

        {/* Tool Settings (HTTP or Custom Python Code) */}
        {catKey === "tools" && (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                REST Endpoint URL
              </label>
              <input
                value={cfg.url || ""}
                onChange={(e) => updateConfig("url", e.target.value)}
                placeholder="https://api.github.com/zen"
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                Or Custom Python @tool Body (For Export)
              </label>
              <textarea
                rows={4}
                value={cfg.customPythonCode || ""}
                onChange={(e) =>
                  updateConfig("customPythonCode", e.target.value)
                }
                placeholder={'return {"messages": [{"role": "assistant", "content": "Custom Python output"}]}'}
                className="w-full p-2.5 rounded-xl border border-[#E5E7EB] font-mono text-[11px] text-[#0F172A]"
              />
            </div>
          </>
        )}

        {/* Logic / Conditional Router Settings */}
        {catKey === "logic" && (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-[#0F172A]">
                State Key to Inspect
              </label>
              <input
                value={cfg.conditionField || "retry_count"}
                onChange={(e) => updateConfig("conditionField", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-[#E5E7EB] text-xs text-[#0F172A]"
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-[#0F172A] pt-2 cursor-pointer">
              <input
                type="checkbox"
                checked={Boolean(cfg.humanApproval)}
                onChange={(e) =>
                  updateConfig("humanApproval", e.target.checked)
                }
                className="rounded border-[#E5E7EB]"
              />
              Pause for Human-in-the-Loop (LangGraph <code>interrupt()</code>)
            </label>
          </>
        )}
      </div>

      <button
        onClick={() => onDeleteNode(selectedNode.id)}
        className="w-full py-2.5 rounded-full border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-600 text-xs font-semibold flex items-center justify-center gap-1.5 transition"
      >
        <Trash2 className="w-3.5 h-3.5" />
        Delete Node from Graph
      </button>
    </div>
  );
}
