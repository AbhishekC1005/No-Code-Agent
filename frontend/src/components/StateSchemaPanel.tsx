import { useState } from "react";
import { X, Plus, Trash2, Database, HelpCircle } from "lucide-react";
import { useGraphStore } from "../store/useGraphStore";
import type { StateFieldType, ReducerType } from "../types/graph";

export function StateSchemaPanel() {
  const isStateSchemaOpen = useGraphStore((s) => s.isStateSchemaOpen);
  const setStateSchemaOpen = useGraphStore((s) => s.setStateSchemaOpen);
  const graph = useGraphStore((s) => s.graph);
  const addStateField = useGraphStore((s) => s.addStateField);
  const updateStateField = useGraphStore((s) => s.updateStateField);
  const deleteStateField = useGraphStore((s) => s.deleteStateField);
  const toggleInputField = useGraphStore((s) => s.toggleInputField);
  const toggleOutputField = useGraphStore((s) => s.toggleOutputField);

  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldType, setNewFieldType] = useState<StateFieldType>("messages");
  const [newFieldReducer, setNewFieldReducer] = useState<ReducerType>("add_messages");

  if (!isStateSchemaOpen) return null;

  const state = graph.state || { fields: [], input_fields: [], output_fields: [] };
  const fields = state.fields || [];
  const inputFields = state.input_fields || [];
  const outputFields = state.output_fields || [];

  const handleAddField = () => {
    if (!newFieldName.trim()) return;
    addStateField({
      name: newFieldName.trim(),
      type: newFieldType,
      reducer: newFieldReducer,
      default: newFieldType === "messages" ? [] : "",
    });
    setNewFieldName("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <div className="text-sm font-bold text-slate-800">LangGraph State Schema</div>
              <div className="text-xs text-slate-500">
                TypedDict structure with Annotated reducers
              </div>
            </div>
          </div>
          <button
            onClick={() => setStateSchemaOpen(false)}
            className="p-1.5 rounded-lg hover:bg-slate-200 text-slate-400 hover:text-slate-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Info Box */}
        <div className="p-4 bg-blue-50/50 border-b border-blue-100 flex items-start gap-3">
          <HelpCircle className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-blue-800 leading-relaxed">
            State fields define the graph’s memory schema. <strong>add_messages</strong> automatically
            appends and de-duplicates message history. <strong>operator.add</strong> merges parallel branch outputs.
          </div>
        </div>

        {/* Field List Table */}
        <div className="p-5 overflow-y-auto flex-1 space-y-3">
          <div className="grid grid-cols-12 gap-3 text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2">
            <div className="col-span-3">Field Name</div>
            <div className="col-span-2">Type</div>
            <div className="col-span-3">Reducer</div>
            <div className="col-span-2 text-center">Input / Output</div>
            <div className="col-span-2 text-right">Action</div>
          </div>

          <div className="space-y-2">
            {fields.map((field, idx) => (
              <div
                key={idx}
                className="grid grid-cols-12 gap-3 items-center p-2.5 rounded-xl bg-slate-50 border border-slate-200 text-xs"
              >
                {/* Field Name */}
                <div className="col-span-3">
                  <input
                    type="text"
                    value={field.name}
                    onChange={(e) =>
                      updateStateField(idx, { ...field, name: e.target.value })
                    }
                    className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white font-mono font-medium text-slate-800 focus:outline-none focus:border-blue-500"
                  />
                </div>

                {/* Type */}
                <div className="col-span-2">
                  <select
                    value={field.type}
                    onChange={(e) => {
                      const t = e.target.value as StateFieldType;
                      const defaultReducer = t === "messages" ? "add_messages" : "overwrite";
                      updateStateField(idx, { ...field, type: t, reducer: defaultReducer });
                    }}
                    className="w-full px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 focus:outline-none"
                  >
                    <option value="messages">messages</option>
                    <option value="str">str</option>
                    <option value="int">int</option>
                    <option value="float">float</option>
                    <option value="bool">bool</option>
                    <option value="list">list</option>
                    <option value="dict">dict</option>
                  </select>
                </div>

                {/* Reducer */}
                <div className="col-span-3">
                  <select
                    value={field.reducer}
                    onChange={(e) =>
                      updateStateField(idx, {
                        ...field,
                        reducer: e.target.value as ReducerType,
                      })
                    }
                    className="w-full px-2 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800 focus:outline-none"
                  >
                    <option value="overwrite">overwrite</option>
                    <option value="add_messages">add_messages</option>
                    <option value="append">operator.add (append)</option>
                    <option value="custom">custom</option>
                  </select>
                </div>

                {/* Input / Output check */}
                <div className="col-span-2 flex items-center justify-center gap-3">
                  <label className="flex items-center gap-1 cursor-pointer" title="Include in input schema">
                    <input
                      type="checkbox"
                      checked={inputFields.includes(field.name)}
                      onChange={() => toggleInputField(field.name)}
                      className="w-3.5 h-3.5 rounded text-blue-600 border-slate-300"
                    />
                    <span className="text-[10px] font-semibold text-slate-500">In</span>
                  </label>
                  <label className="flex items-center gap-1 cursor-pointer" title="Include in output schema">
                    <input
                      type="checkbox"
                      checked={outputFields.includes(field.name)}
                      onChange={() => toggleOutputField(field.name)}
                      className="w-3.5 h-3.5 rounded text-indigo-600 border-slate-300"
                    />
                    <span className="text-[10px] font-semibold text-slate-500">Out</span>
                  </label>
                </div>

                {/* Actions */}
                <div className="col-span-2 text-right">
                  <button
                    onClick={() => deleteStateField(idx)}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Add Field Form */}
          <div className="pt-4 border-t border-slate-100">
            <div className="text-xs font-semibold text-slate-700 mb-2">Add New State Field</div>
            <div className="flex items-center gap-3">
              <input
                type="text"
                placeholder="Field name (e.g. current_task)"
                value={newFieldName}
                onChange={(e) => setNewFieldName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddField()}
                className="flex-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 focus:outline-none focus:border-blue-500"
              />
              <select
                value={newFieldType}
                onChange={(e) => {
                  const t = e.target.value as StateFieldType;
                  setNewFieldType(t);
                  setNewFieldReducer(t === "messages" ? "add_messages" : "overwrite");
                }}
                className="px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800"
              >
                <option value="messages">messages</option>
                <option value="str">str</option>
                <option value="int">int</option>
                <option value="float">float</option>
                <option value="bool">bool</option>
                <option value="list">list</option>
                <option value="dict">dict</option>
              </select>
              <select
                value={newFieldReducer}
                onChange={(e) => setNewFieldReducer(e.target.value as ReducerType)}
                className="px-3 py-2 rounded-xl border border-slate-200 text-xs bg-white text-slate-800"
              >
                <option value="overwrite">overwrite</option>
                <option value="add_messages">add_messages</option>
                <option value="append">operator.add</option>
              </select>
              <button
                onClick={handleAddField}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all"
              >
                <Plus className="w-3.5 h-3.5" /> Add
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end">
          <button
            onClick={() => setStateSchemaOpen(false)}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold shadow-sm transition-all"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
