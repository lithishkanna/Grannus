/**
 * Offline Consultation Queue & Low-Bandwidth Sync for Grannus RuralCare AI.
 * 
 * Supports ASHA workers and village sub-centres operating in zero-connectivity
 * zones by queuing intake payloads locally and automatically synchronizing
 * with retry backoff when connection is restored.
 */

import { getAuthHeaders } from './api';

export interface OfflineConsultation {
  id: string;
  createdAt: number;
  payload: {
    audio: string; // base64
    language_code: string;
    doctor_preferred_language: string;
    age?: string;
    gender?: string;
    reported_duration?: string;
    known_conditions?: string;
    current_medications?: string;
    dpdp_consent_verified: boolean;
  };
  retryCount: number;
  lastError?: string;
}

const STORAGE_KEY = 'grannus_offline_queue_v1';

export function getOfflineQueue(): OfflineConsultation[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Failed to read offline queue:', e);
    return [];
  }
}

export function saveOfflineConsultation(payload: OfflineConsultation['payload']): string {
  const queue = getOfflineQueue();
  const id = `offline_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
  const item: OfflineConsultation = {
    id,
    createdAt: Date.now(),
    payload,
    retryCount: 0,
  };
  queue.push(item);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch (e) {
    console.error('Failed to save offline consultation:', e);
  }
  return id;
}

export function removeOfflineConsultation(id: string) {
  const queue = getOfflineQueue().filter((item) => item.id !== id);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(queue));
  } catch (e) {
    console.error('Failed to update offline queue:', e);
  }
}

export async function syncOfflineConsultations(
  apiUrl: string,
  onProgress?: (synced: number, total: number) => void
): Promise<{ success: number; failed: number }> {
  const queue = getOfflineQueue();
  if (queue.length === 0) return { success: 0, failed: 0 };

  let successCount = 0;
  let failedCount = 0;

  for (let i = 0; i < queue.length; i++) {
    const item = queue[i];
    try {
      // Convert base64 back to Blob for multipart upload
      const res = await fetch(item.payload.audio);
      const audioBlob = await res.blob();

      const formData = new FormData();
      formData.append('audio', audioBlob, 'patient_recording.wav');
      formData.append('language_code', item.payload.language_code || 'unknown');
      formData.append('doctor_preferred_language', item.payload.doctor_preferred_language || 'en-IN');
      if (item.payload.age) formData.append('age', item.payload.age);
      if (item.payload.gender) formData.append('gender', item.payload.gender);
      if (item.payload.reported_duration) formData.append('reported_duration', item.payload.reported_duration);
      if (item.payload.known_conditions) formData.append('known_conditions', item.payload.known_conditions);
      if (item.payload.current_medications) formData.append('current_medications', item.payload.current_medications);

      const response = await fetch(`${apiUrl}/api/v1/pipeline/process-audio`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status ${response.status}`);
      }

      removeOfflineConsultation(item.id);
      successCount++;
    } catch (err: any) {
      console.warn(`Sync failed for offline item ${item.id}:`, err);
      item.retryCount += 1;
      item.lastError = err.message || 'Network error';
      failedCount++;
    }

    if (onProgress) {
      onProgress(i + 1, queue.length);
    }
  }

  return { success: successCount, failed: failedCount };
}
