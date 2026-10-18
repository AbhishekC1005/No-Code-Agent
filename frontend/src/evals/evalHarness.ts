import type { Node, Edge } from "@xyflow/react";
import type { EvalRow } from "../compiler/pythonCompiler";
import { executeGraphInBrowser, type VaultKeys } from "../runtime/browserRunner";

export interface EvalResultRow {
  id: string;
  input: string;
  actualOutput: string;
  visitedNodes: string[];
  trajectoryMatched: boolean;
  keywordMatched: boolean;
  latencyMs: number;
  latencyPassed: boolean;
  overallPassed: boolean;
}

export async function runEvalSuiteInBrowser(
  nodes: Node[],
  edges: Edge[],
  evalRows: EvalRow[],
  vault: VaultKeys,
  onNodeActive: (nodeId: string | null) => void
): Promise<EvalResultRow[]> {
  const results: EvalResultRow[] = [];

  for (const row of evalRows) {
    const run = await executeGraphInBrowser(
      nodes,
      edges,
      row.input,
      vault,
      `eval_thread_${row.id}`,
      onNodeActive
    );

    const trajectoryMatched =
      row.expectedTrajectory.length === 0 ||
      row.expectedTrajectory.every((reqNodeId) =>
        run.visitedNodeIds.includes(reqNodeId)
      );

    const keywordMatched =
      !row.expectedKeyword ||
      run.finalAnswer.toLowerCase().includes(row.expectedKeyword.toLowerCase());

    const latencyPassed = run.totalLatencyMs <= (row.maxLatencyMs || 10000);

    results.push({
      id: row.id,
      input: row.input,
      actualOutput: run.finalAnswer,
      visitedNodes: run.visitedNodeIds,
      trajectoryMatched,
      keywordMatched,
      latencyMs: run.totalLatencyMs,
      latencyPassed,
      overallPassed: trajectoryMatched && keywordMatched && latencyPassed,
    });
  }

  return results;
}
