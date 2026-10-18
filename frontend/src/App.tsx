import { useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { NodePalette } from "./components/NodePalette";
import { Canvas } from "./components/Canvas";
import { NodeInspector } from "./components/NodeInspector";
import { EdgeInspector } from "./components/EdgeInspector";
import { LiveCodePanel } from "./components/LiveCodePanel";
import { StateSchemaPanel } from "./components/StateSchemaPanel";
import { GraphSettingsDrawer } from "./components/GraphSettingsDrawer";
import { RunChatPanel } from "./components/RunChatPanel";
import { StateInspectorPanel } from "./components/StateInspectorPanel";
import { CredentialsModal } from "./components/CredentialsModal";
import { PatternsGalleryModal } from "./components/PatternsGalleryModal";
import { TriggersModal } from "./components/TriggersModal";
import { RunHistoryModal } from "./components/RunHistoryModal";
import { useGraphStore } from "./store/useGraphStore";

export default function App() {
  const init = useGraphStore((s) => s.init);
  const selectedNodeId = useGraphStore((s) => s.selectedNodeId);
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);

  useEffect(() => {
    init();
  }, [init]);

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-slate-50 font-sans select-none">
      {/* Top Navigation */}
      <Navbar />

      {/* Main Studio Area */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Node Library Palette */}
        <NodePalette />

        {/* Visual Graph Canvas */}
        <Canvas />

        {/* Inspectors */}
        {selectedNodeId && <NodeInspector />}
        {selectedEdgeId && <EdgeInspector />}

        {/* Live LangGraph Code Panel */}
        <LiveCodePanel />

        {/* Execution Runner & Chat Panel */}
        <RunChatPanel />

        {/* State Inspector Drawer */}
        <StateInspectorPanel />
      </div>

      {/* Modals & Drawers */}
      <StateSchemaPanel />
      <GraphSettingsDrawer />
      <CredentialsModal />
      <PatternsGalleryModal />
      <TriggersModal />
      <RunHistoryModal />
    </div>
  );
}
