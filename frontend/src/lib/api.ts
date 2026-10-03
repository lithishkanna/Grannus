// Types matching backend schemas.py
export type Severity = 'mild' | 'moderate' | 'severe' | 'unbearable' | 'slight'
export type Frequency = 'continuous' | 'intermittent' | 'occasional' | 'frequent'
export type DurationUnit = 'minutes' | 'hours' | 'days' | 'weeks' | 'months'
export type PriorityLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'PENDING_REVIEW'

export interface Duration {
  value: number | null
  unit: DurationUnit | null
  raw_text: string | null
}

export interface Symptom {
  name: string
  raw_text: string | null
  body_location: string | null
  duration: Duration | null
  onset_relation: string | null
  severity: Severity | null
  frequency: Frequency | null
  negated: boolean
  source: string
  confidence: number
}

export interface RedFlag {
  phrase: string
  related_symptom: string | null
  source: string
  confidence: number
}

export interface SafetyRedFlag {
  potential_red_flag: boolean
  symptom: string
  reason: string
  action: string
  severity: string
}

export interface FieldConfidence {
  chief_complaint: number
  symptoms: number
  existing_conditions: number
  medications: number
  allergies: number
}

export interface MissingInformationItem {
  field: string
  description: string
  question: string
  translated_question: string | null
  priority: number
}

export interface HomeRemedyCareStep {
  step: string
  translated_step: string | null
}

export interface HomeRemedyGuidance {
  care_steps: HomeRemedyCareStep[]
  monitoring_signs: string[]
  seek_doctor_if: string[]
  translated_care_steps: string[] | null
  translated_seek_doctor_if: string[] | null
  disclaimer: string
  language: string | null
}

export interface DoctorTranslatedSummary {
  chief_complaint: string | null
  symptoms_summary: string | null
  red_flags_summary: string | null
  audio_base64: string | null
  language: string
}

export type UrgencyTier = 'emergency' | 'doctor_today' | 'doctor_soon' | 'self_care'

export interface PriorityAssessment {
  level: PriorityLevel
  urgency_tier?: UrgencyTier
  follow_up_days?: number
  emergency_call_numbers?: string[]
  confidence: number
  emergency_override: boolean
  triggered_rules: string[]
  reasons: string[]
  score: number
  model_used: string
}

export interface PatientInput {
  language: string | null
  transcript_original: string
  transcript_english: string
  language_confidence: number | null
  language_verification_required: boolean
}

export interface ClinicalSummary {
  chief_complaint: string
  symptoms: Symptom[]
  existing_conditions: string[]
  medications: string[]
  allergies: string[]
  relevant_history: string | null
  field_confidence: FieldConfidence
  extraction_notes: string | null
}

export interface SafetyScreeningOutput {
  red_flags: SafetyRedFlag[]
  missing_information: MissingInformationItem[]
  follow_up_questions: string[]
}

export interface AcousticBiomarkerResult {
  cough_count: number
  wheeze_detected: boolean
  wheeze_ratio: number
  breathlessness_pauses: number
  speech_dyspnea_index: number
  respiratory_distress_score: number
  distress_level: 'none' | 'mild' | 'moderate' | 'severe'
}

export interface PipelineResult {
  request_id: string
  patient_input: PatientInput
  clinical_summary: ClinicalSummary
  safety_screening: SafetyScreeningOutput
  priority: PriorityAssessment
  clinician_review_required: boolean
  diagnosis: null
  disclaimer: string
  home_remedy_guidance: HomeRemedyGuidance | null
  doctor_translated_summary: DoctorTranslatedSummary | null
  acoustic_biomarkers: AcousticBiomarkerResult | null
  audio_preprocessing: Record<string, unknown> | null
  pipeline_stages: Record<string, unknown> | null
}

export interface VoicePrescriptionResponse {
  english_text: string
  translated_text: string
  back_translated_text?: string | null
  translation_verified?: boolean
  patient_audio_base64: string | null
  patient_language: string
  consultation_id: string | null
}

export const SUPPORTED_LANGUAGES = [
  { code: 'unknown', name: 'Auto-detect' },
  { code: 'hi-IN', name: 'Hindi', nativeName: 'हिन्दी' },
  { code: 'ta-IN', name: 'Tamil', nativeName: 'தமிழ்' },
  { code: 'te-IN', name: 'Telugu', nativeName: 'తెలుగు' },
  { code: 'bn-IN', name: 'Bengali', nativeName: 'বাংলা' },
  { code: 'kn-IN', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
  { code: 'ml-IN', name: 'Malayalam', nativeName: 'മലയാളം' },
  { code: 'mr-IN', name: 'Marathi', nativeName: 'मराठी' },
  { code: 'gu-IN', name: 'Gujarati', nativeName: 'ગુજરાતી' },
  { code: 'pa-IN', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ' },
  { code: 'od-IN', name: 'Odia', nativeName: 'ଓଡ଼ିଆ' },
  { code: 'en-IN', name: 'English', nativeName: 'English' }
];

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('grannus_auth_token');
}

export function setAuthToken(token: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('grannus_auth_token', token);
}

export function removeAuthToken(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('grannus_auth_token');
}

export function getAuthHeaders(): Record<string, string> {
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function processAudio(params: {
  audio: Blob;
  language_code?: string;
  doctor_preferred_language?: string;
  age?: string;
  gender?: string;
  reported_duration?: string;
  known_conditions?: string;
  current_medications?: string;
}): Promise<PipelineResult> {
  const formData = new FormData();
  formData.append('audio', params.audio, 'recording.webm');
  if (params.language_code) formData.append('language_code', params.language_code);
  if (params.doctor_preferred_language) formData.append('doctor_preferred_language', params.doctor_preferred_language);
  if (params.age) formData.append('age', params.age);
  if (params.gender) formData.append('gender', params.gender);
  if (params.reported_duration) formData.append('reported_duration', params.reported_duration);
  if (params.known_conditions) formData.append('known_conditions', params.known_conditions);
  if (params.current_medications) formData.append('current_medications', params.current_medications);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/pipeline/process-audio`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Send doctor's voice recording to be translated and synthesized
 * into the patient's native language as a voice note.
 */
export async function sendVoicePrescription(params: {
  audio: Blob;
  patient_language: string;
  consultation_id?: string;
}): Promise<VoicePrescriptionResponse> {
  const formData = new FormData();
  formData.append('audio', params.audio, 'doctor_advice.webm');
  formData.append('patient_language', params.patient_language);
  if (params.consultation_id) formData.append('consultation_id', params.consultation_id);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/doctor/voice-prescription`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Voice Prescription API Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Export a pipeline result as an ABDM-compliant FHIR R4 JSON bundle.
 */
export async function exportFhirBundle(result: PipelineResult): Promise<Record<string, unknown>> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/export/fhir`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(result),
  });

  if (!response.ok) {
    throw new Error(`FHIR Export API Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Non-blocking asynchronous audio intake for low-bandwidth networks.
 */
export async function submitAudioAsync(params: {
  audio: Blob;
  language_code?: string;
  doctor_preferred_language?: string;
  age?: string;
  gender?: string;
  reported_duration?: string;
  known_conditions?: string;
  current_medications?: string;
}): Promise<{ job_id: string; status: string; poll_url: string; message: string }> {
  const formData = new FormData();
  formData.append('audio', params.audio, 'recording.webm');
  if (params.language_code) formData.append('language_code', params.language_code);
  if (params.doctor_preferred_language) formData.append('doctor_preferred_language', params.doctor_preferred_language);
  if (params.age) formData.append('age', params.age);
  if (params.gender) formData.append('gender', params.gender);
  if (params.reported_duration) formData.append('reported_duration', params.reported_duration);
  if (params.known_conditions) formData.append('known_conditions', params.known_conditions);
  if (params.current_medications) formData.append('current_medications', params.current_medications);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/pipeline/submit-audio`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Submit Audio Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Poll status and progress of an asynchronous pipeline triage job.
 */
export async function getJobStatus(jobId: string): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/pipeline/job-status/${jobId}`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Job Status Error: ${response.statusText}`);
  }

  return response.json();
}

export interface VoiceThreadMessage {
  message_id: string
  sender: 'doctor' | 'patient'
  original_text: string
  translated_text: string
  back_translated_text?: string | null
  original_language: string
  target_language: string
  audio_base64?: string | null
  created_at: string
}

export interface VoiceThread {
  thread_id: string
  consultation_id: string
  patient_language: string
  doctor_language: string
  messages: VoiceThreadMessage[]
}

export interface CheckInResponse {
  consultation_id: string
  previous_tier: UrgencyTier
  new_tier: UrgencyTier
  status: string
  message: string
  is_escalated: boolean
  escalation_reason?: string | null
  emergency_call_numbers: string[]
  next_follow_up_days: number
}

/**
 * Record scheduled 2-3 day follow-up check-in.
 */
export async function checkInConsultation(
  consultationId: string,
  status: 'improving' | 'same' | 'worse',
  notes?: string
): Promise<CheckInResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/check-in`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ status, notes }),
  });

  if (!response.ok) {
    throw new Error(`Check-in Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * One-tap "I feel worse" escalation endpoint.
 */
export async function escalateConsultation(
  consultationId: string,
  reason?: string
): Promise<CheckInResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/escalate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ reason: reason || "Patient tapped 'I feel worse'" }),
  });

  if (!response.ok) {
    throw new Error(`Escalate Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Retrieve asynchronous bilingual voice thread.
 */
export async function getVoiceThread(consultationId: string): Promise<VoiceThread> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/thread`, {
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    throw new Error(`Get Voice Thread Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Patient sends a spoken reply to the voice thread.
 */
export async function replyToVoiceThread(params: {
  consultationId: string
  audio: Blob
  patientLanguage?: string
}): Promise<VoiceThreadMessage> {
  const formData = new FormData();
  formData.append('audio', params.audio, 'patient_reply.webm');
  if (params.patientLanguage) formData.append('patient_language', params.patientLanguage);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const response = await fetch(
    `${baseUrl}/api/v1/consultations/${params.consultationId}/thread/patient-reply`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error(`Voice Thread Reply Error: ${response.statusText}`);
  }

  return response.json();
}


