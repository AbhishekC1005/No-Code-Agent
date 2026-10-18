import { useState, useEffect } from "react";
import {
  X,
  Layers,
  Sparkles,
  Bot,
  Users,
  GitFork,
  Repeat,
  BookOpen,
  ArrowRight,
  Loader2,
  Check,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function PatternsGalleryModal() {
  const isPatternsGalleryOpen = useGraphStore((s) => s.isPatternsGalleryOpen);
  const setPatternsGalleryOpen = useGraphStore((s) => s.setPatternsGalleryOpen);
  const insertPattern = useGraphStore((s) => s.insertPattern);
  const loadStarterTemplate = useGraphStore((s) => s.loadStarterTemplate);

  const [activeTab, setActiveTab] = useState<"patterns" | "templates">("patterns");
  const [patternsList, setPatternsList] = useState<any[]>([]);
  const [templatesList, setTemplatesList] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionDone, setActionDone] = useState<string | null>(null);

  useEffect(() => {
    if (!isPatternsGalleryOpen) return;
    setLoading(true);
    Promise.all([
      fetch("/api/v1/patterns").then((r) => r.json()).catch(() => []),
      fetch("/api/v1/templates").then((r) => r.json()).catch(() => []),
    ]).then(([patterns, templates]) => {
      setPatternsList(patterns);
      setTemplatesList(templates);
      setLoading(false);
    });
  }, [isPatternsGalleryOpen]);

  if (!isPatternsGalleryOpen) return null;

  const handleInsertPattern = async (pid: string) => {
    setActionDone(pid);
    await insertPattern(pid);
    setTimeout(() => {
      setActionDone(null);
      setPatternsGalleryOpen(false);
    }, 400);
  };

  const handleLoadTemplate = async (tid: string) => {
    setActionDone(tid);
    await loadStarterTemplate(tid);
    setTimeout(() => {
      setActionDone(null);
      setPatternsGalleryOpen(false);
    }, 400);
  };

  const getPatternIcon = (iconName: string) => {
    switch (iconName) {
      case "bot":
        return <Bot className="w-5 h-5 text-blue-600" />;
      case "users":
        return <Users className="w-5 h-5 text-indigo-600" />;
      case "git-fork":
        return <GitFork className="w-5 h-5 text-purple-600" />;
      case "repeat":
        return <Repeat className="w-5 h-5 text-amber-600" />;
      case "layers":
        return <Layers className="w-5 h-5 text-emerald-600" />;
      case "book-open":
        return <BookOpen className="w-5 h-5 text-teal-600" />;
      default:
        return <Sparkles className="w-5 h-5 text-blue-600" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-sm">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Patterns & Starter Templates</h2>
              <p className="text-[11px] text-slate-500">
                Insert prebuilt LangGraph subgraphs or start fresh with production-ready templates.
              </p>
            </div>
          </div>
          <button
            onClick={() => setPatternsGalleryOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-6 border-b border-slate-200 bg-white flex gap-6">
          <button
            onClick={() => setActiveTab("patterns")}
            className={`py-3 text-xs font-bold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === "patterns"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Pattern Blocks (Insert Subgraphs)</span>
          </button>
          <button
            onClick={() => setActiveTab("templates")}
            className={`py-3 text-xs font-bold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
              activeTab === "templates"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Starter Templates Gallery</span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              <span className="text-xs">Loading prebuilt flows...</span>
            </div>
          ) : activeTab === "patterns" ? (
            <div className="grid grid-cols-2 gap-3.5">
              {patternsList.map((p) => (
                <div
                  key={p.id}
                  className="p-4 rounded-xl border border-slate-200 hover:border-indigo-300 hover:shadow-xs bg-white transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center gap-2.5 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0">
                        {getPatternIcon(p.icon)}
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-800">{p.name}</h4>
                        <span className="text-[10px] uppercase font-semibold text-indigo-600 bg-indigo-50 px-1.5 py-0.2 rounded">
                          {p.category}
                        </span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed mb-4">{p.description}</p>
                  </div>

                  <button
                    onClick={() => handleInsertPattern(p.id)}
                    className="w-full py-2 px-3 rounded-lg bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 text-slate-700 hover:text-indigo-700 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                  >
                    {actionDone === p.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                        <span className="text-emerald-700 font-bold">Inserted!</span>
                      </>
                    ) : (
                      <>
                        <span>Insert into Canvas</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3.5">
              {templatesList.map((t) => (
                <div
                  key={t.id}
                  className="p-4 rounded-xl border border-slate-200 hover:border-blue-300 hover:shadow-xs bg-white transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] uppercase font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                        {t.category}
                      </span>
                      <span className="text-[10px] font-semibold text-slate-400">
                        {t.node_count} nodes • {t.edge_count} edges
                      </span>
                    </div>
                    <h4 className="text-xs font-bold text-slate-800 mb-1">{t.name}</h4>
                    <p className="text-[11px] text-slate-500 leading-relaxed mb-4">{t.description}</p>
                  </div>

                  <button
                    onClick={() => handleLoadTemplate(t.id)}
                    className="w-full py-2 px-3 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-2xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                  >
                    {actionDone === t.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-white" />
                        <span>Loaded!</span>
                      </>
                    ) : (
                      <>
                        <span>Load Template</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-[11px] text-slate-500">
          <span>Each pattern expands into editable normal nodes, not an opaque black box.</span>
          <button
            onClick={() => setPatternsGalleryOpen(false)}
            className="px-4 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-100 text-xs font-semibold text-slate-700 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
