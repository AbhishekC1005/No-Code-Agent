import { useState, useRef } from "react";
import {
  Sparkles,
  Database,
  Sliders,
  Code,
  Download,
  CloudUpload,
  Check,
  Key,
  Layers,
  Zap,
  History,
  FileJson,
  Upload,
} from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";

export function Navbar() {
  const workflowName = useGraphStore((s) => s.workflowName);
  const setWorkflowName = useGraphStore((s) => s.setWorkflowName);
  const isSaving = useGraphStore((s) => s.isSaving);
  const lastSaved = useGraphStore((s) => s.lastSaved);
  const setStateSchemaOpen = useGraphStore((s) => s.setStateSchemaOpen);
  const setSettingsOpen = useGraphStore((s) => s.setSettingsOpen);
  const setCredentialsOpen = useGraphStore((s) => s.setCredentialsOpen);
  const setPatternsGalleryOpen = useGraphStore((s) => s.setPatternsGalleryOpen);
  const setTriggersOpen = useGraphStore((s) => s.setTriggersOpen);
  const setRunHistoryOpen = useGraphStore((s) => s.setRunHistoryOpen);
  const exportGraphJson = useGraphStore((s) => s.exportGraphJson);
  const importGraphJson = useGraphStore((s) => s.importGraphJson);
  const isCodePanelOpen = useGraphStore((s) => s.isCodePanelOpen);
  const setCodePanelOpen = useGraphStore((s) => s.setCodePanelOpen);
  const isRunPanelOpen = useGraphStore((s) => s.isRunPanelOpen);
  const setRunPanelOpen = useGraphStore((s) => s.setRunPanelOpen);
  const isStateInspectorOpen = useGraphStore((s) => s.isStateInspectorOpen);
  const setStateInspectorOpen = useGraphStore((s) => s.setStateInspectorOpen);
  const isRunning = useGraphStore((s) => s.isRunning);
  const isInterrupted = useGraphStore((s) => s.isInterrupted);
  const workflowId = useGraphStore((s) => s.workflowId);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState(workflowName);

  const handleTitleBlur = () => {
    setIsEditingTitle(false);
    if (titleInput.trim()) {
      setWorkflowName(titleInput.trim());
    }
  };

  const handleDownload = () => {
    const id = workflowId || "default";
    window.open(`/api/v1/workflows/${id}/export/project`, "_blank");
  };

  const handleImportFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      const content = event.target?.result as string;
      if (content) {
        const res = await importGraphJson(content);
        if (!res.success) {
          alert(`Import failed: ${res.message}`);
        }
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <header className="h-14 bg-white border-b border-slate-200 px-4 flex items-center justify-between z-30 shadow-2xs flex-shrink-0">
      {/* Brand & Workflow Title */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <span className="text-xs font-black uppercase tracking-wider text-slate-800">
              LangGraph
            </span>
            <span className="text-[10px] font-semibold text-blue-600 ml-1.5 px-1.5 py-0.2 rounded-full bg-blue-50 border border-blue-100">
              Visual Studio
            </span>
          </div>
        </div>

        <div className="h-4 w-px bg-slate-200 mx-1" />

        {/* Editable Workflow Title */}
        {isEditingTitle ? (
          <input
            type="text"
            value={titleInput}
            onChange={(e) => setTitleInput(e.target.value)}
            onBlur={handleTitleBlur}
            onKeyDown={(e) => e.key === "Enter" && handleTitleBlur()}
            autoFocus
            className="px-2.5 py-1 text-xs font-semibold text-slate-800 border border-blue-500 rounded-lg focus:outline-none"
          />
        ) : (
          <button
            onClick={() => {
              setTitleInput(workflowName);
              setIsEditingTitle(true);
            }}
            className="px-2 py-1 text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
          >
            {workflowName || "Untitled Workflow"}
          </button>
        )}

        {/* Autosave Status */}
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
          {isSaving ? (
            <span className="flex items-center gap-1 text-amber-600 font-medium animate-pulse">
              <CloudUpload className="w-3.5 h-3.5" /> Saving...
            </span>
          ) : lastSaved ? (
            <span className="flex items-center gap-1 text-emerald-600 font-medium">
              <Check className="w-3.5 h-3.5" /> Saved
            </span>
          ) : null}
        </div>
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-2">
        {/* State Inspector Toggle */}
        <button
          onClick={() => setStateInspectorOpen(!isStateInspectorOpen)}
          className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
            isStateInspectorOpen
              ? "bg-slate-100 border-slate-300 text-slate-900"
              : "border-slate-200 bg-white hover:bg-slate-50 text-slate-700"
          }`}
        >
          <Database className="w-3.5 h-3.5 text-indigo-600" />
          <span>State Inspector</span>
        </button>

        {/* State Schema Modal Button */}
        <button
          onClick={() => setStateSchemaOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Sliders className="w-3.5 h-3.5 text-blue-600" />
          <span>Schema</span>
        </button>

        {/* Compilation Settings Drawer Button */}
        <button
          onClick={() => setSettingsOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Sliders className="w-3.5 h-3.5 text-purple-600" />
          <span>Settings</span>
        </button>

        {/* Patterns & Templates Gallery Button */}
        <button
          onClick={() => setPatternsGalleryOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-indigo-200 hover:border-indigo-300 bg-indigo-50/50 hover:bg-indigo-50 text-indigo-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Layers className="w-3.5 h-3.5 text-indigo-600" />
          <span>Patterns</span>
        </button>

        {/* Credentials Manager Modal Button */}
        <button
          onClick={() => setCredentialsOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Key className="w-3.5 h-3.5 text-amber-600" />
          <span>Credentials</span>
        </button>

        {/* Triggers & Automation Modal Button */}
        <button
          onClick={() => setTriggersOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-amber-200 hover:border-amber-300 bg-amber-50/50 hover:bg-amber-50 text-amber-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Zap className="w-3.5 h-3.5 text-amber-600" />
          <span>Triggers</span>
        </button>

        {/* Execution Run History Modal Button */}
        <button
          onClick={() => setRunHistoryOpen(true)}
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <History className="w-3.5 h-3.5 text-indigo-600" />
          <span>History</span>
        </button>

        <div className="h-4 w-px bg-slate-200 mx-0.5" />

        {/* Export Project ZIP */}
        <button
          onClick={handleDownload}
          title="Download standalone LangGraph project ZIP with README and .env"
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer"
        >
          <Download className="w-3.5 h-3.5 text-slate-600" />
          <span>ZIP</span>
        </button>

        {/* Export Graph JSON */}
        <button
          onClick={exportGraphJson}
          title="Export Graph JSON schema"
          className="px-2.5 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1 shadow-2xs transition-all cursor-pointer"
        >
          <FileJson className="w-3.5 h-3.5 text-blue-600" />
          <span>JSON</span>
        </button>

        {/* Import Graph JSON */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleImportFileChange}
          accept=".json,application/json"
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          title="Import Graph JSON schema"
          className="px-2.5 py-1.5 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1 shadow-2xs transition-all cursor-pointer"
        >
          <Upload className="w-3.5 h-3.5 text-emerald-600" />
          <span>Import</span>
        </button>

        <div className="h-4 w-px bg-slate-200 mx-1" />

        {/* Live Code Toggle */}
        <button
          onClick={() => setCodePanelOpen(!isCodePanelOpen)}
          className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
            isCodePanelOpen
              ? "bg-slate-900 text-white shadow-sm"
              : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          }`}
        >
          <Code className="w-3.5 h-3.5 text-blue-400" />
          <span>Code</span>
        </button>

        {/* Run & Chat Toggle Button */}
        <button
          onClick={() => setRunPanelOpen(!isRunPanelOpen)}
          className={`px-3.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer ${
            isRunPanelOpen
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
          }`}
        >
          {isRunning ? (
            <div className="w-2.5 h-2.5 rounded-full bg-white animate-ping" />
          ) : isInterrupted ? (
            <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-bounce" />
          ) : (
            <div className="w-2 h-2 rounded-full bg-emerald-400" />
          )}
          <span>{isInterrupted ? "Review Paused" : isRunning ? "Running..." : "Run & Chat"}</span>
        </button>
      </div>
    </header>
  );
}
