import { PipelineResult } from './api';

/**
 * Persist consultation result (F1.1).
 * In Grannus, the authenticated backend is the single source of truth and writes to
 * the database automatically during pipeline triage execution.
 */
export async function storeResultToSupabase(result: PipelineResult, _doctorId: string | null = null): Promise<string | null> {
  // Backend automatically handles persistence and routing during pipeline execution.
  return result.request_id || null;
}
