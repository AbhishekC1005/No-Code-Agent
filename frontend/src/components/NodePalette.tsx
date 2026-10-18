import {
  Bot,
  Wrench,
  Code,
  GitBranch,
  Layers,
  UserCheck,
  FolderGit2,
  Cpu,
  Plus,
  Search,
  X,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

const ICON_MAP: Record<string, any> = {
  llm: Bot,
  tool: Wrench,
  function: Code,
  command: GitBranch,
  map: Layers,
  human: UserCheck,
  subgraph: FolderGit2,
  agent: Cpu,
};

export function NodePalette() {
  const nodeTypes = useGraphStore((s) => s.nodeTypes);
  const addNode = useGraphStore((s) => s.addNode);
  const searchQuery = useGraphStore((s) => s.paletteSearchQuery);
  const setSearchQuery = useGraphStore((s) => s.setPaletteSearchQuery);

  const filteredTypes = nodeTypes.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.label.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      t.type.toLowerCase().includes(q)
    );
  });

  const handleAdd = (type: string) => {
    // Generate a slightly randomized position near center
    const x = 320 + Math.floor(Math.random() * 80) - 40;
    const y = 200 + Math.floor(Math.random() * 80) - 40;
    addNode(type, { x, y });
  };

  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="w-56 bg-white border-r border-slate-200 flex flex-col justify-between shadow-sm z-10 flex-shrink-0">
      <div className="p-4 space-y-3 overflow-y-auto">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
            Node Library
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            Click or drag into canvas
          </div>
        </div>

        {/* Node Search Bar */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes..."
            className="w-full pl-8 pr-7 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        <div className="space-y-1.5">
          {filteredTypes.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-400">
              No matching nodes found
            </div>
          ) : (
            filteredTypes.map((t) => {
              const Icon = ICON_MAP[t.type] || Cpu;
              return (
                <div
                  key={t.type}
                  draggable
                  onDragStart={(e) => onDragStart(e, t.type)}
                onClick={() => handleAdd(t.type)}
                className="group p-2.5 rounded-xl border border-slate-200/80 hover:border-blue-500/60 hover:bg-blue-50/40 bg-white cursor-pointer transition-all flex items-start gap-2.5 shadow-2xs hover:shadow-sm"
              >
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 transition-transform group-hover:scale-105"
                  style={{ backgroundColor: `${t.color}15`, color: t.color }}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-slate-800 flex items-center justify-between">
                    <span>{t.label}</span>
                    <Plus className="w-3 h-3 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  <div className="text-[10px] text-slate-400 leading-tight truncate">
                    {t.description}
                  </div>
                </div>
              </div>
            );
          }))}
        </div>
      </div>

      <div className="p-3 border-t border-slate-100 text-[10px] text-slate-400 text-center">
        LangGraph 1.0 Runtime
      </div>
    </div>
  );
}
