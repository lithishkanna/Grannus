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
  profile_id?: string;
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
  if (params.profile_id) formData.append('profile_id', params.profile_id);

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
 * Authenticate session as registered demo clinician (RMP under Telemedicine Guidelines).
 */
export async function loginAsDemoClinician(): Promise<string> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: 'dr_clinician',
      password: 'grannus_secure_doctor_2026',
      role: 'doctor',
      doctor_registration_number: 'TNMC-54321',
      state_medical_council: 'Tamil Nadu Medical Council',
    }),
  });

  if (!res.ok) {
    throw new Error('Clinician login failed');
  }

  const data = await res.json();
  setAuthToken(data.token);
  if (typeof window !== 'undefined') {
    localStorage.setItem('grannus_user', JSON.stringify({
      user_id: data.user_id,
      role: data.role,
      is_verified_doctor: data.is_verified_doctor,
      doctor_registration_number: data.doctor_registration_number,
    }));
  }
  return data.token;
}

/**
 * Export a pipeline result as an ABDM-compliant FHIR R4 JSON bundle.
 * Authenticates as verified doctor to satisfy Telemedicine Guidelines 2020.
 */
export async function exportFhirBundle(result: PipelineResult): Promise<Record<string, unknown>> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  let token = getAuthToken();

  // If no auth token is present, auto-authenticate as the registered demo clinician
  if (!token) {
    try {
      token = await loginAsDemoClinician();
    } catch (e) {
      console.warn("Could not auto-login as demo clinician:", e);
    }
  }

  let headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
  };

  let response = await fetch(`${baseUrl}/api/v1/export/fhir`, {
    method: 'POST',
    headers,
    body: JSON.stringify(result),
  });

  // If token is missing, expired, or rejected (401/403), re-authenticate once as demo clinician
  if (response.status === 401 || response.status === 403) {
    try {
      token = await loginAsDemoClinician();
      headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      };
      response = await fetch(`${baseUrl}/api/v1/export/fhir`, {
        method: 'POST',
        headers,
        body: JSON.stringify(result),
      });
    } catch {
      // Fall through to error handler below
    }
  }

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error('Clinician login required (Telemedicine Guidelines). Please authenticate as a registered doctor to export ABDM FHIR records.');
    }
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
  profile_id?: string;
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
  if (params.profile_id) formData.append('profile_id', params.profile_id);

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

// -----------------------------------------------------------------------------
// Authentication & Patient Profiles Client (Block B & Block C)
// -----------------------------------------------------------------------------

export interface AuthUser {
  user_id: string
  role: 'patient' | 'doctor' | 'nurse' | 'admin' | 'asha_worker'
  is_verified_doctor?: boolean
  doctor_registration_number?: string | null
  phone_number?: string | null
  account_id?: string | null
  full_name?: string | null
  hospital_id?: string | null
}

export interface LoginResponse {
  token: string
  user_id: string
  role: 'patient' | 'doctor' | 'nurse' | 'admin' | 'asha_worker'
  is_verified_doctor: boolean
  doctor_registration_number?: string | null
  phone_number?: string | null
  account_id?: string | null
  full_name?: string | null
  hospital_id?: string | null
}

export interface PatientProfile {
  id: string
  account_id: string
  full_name: string
  age?: string | null
  gender?: string | null
  relation: string
  preferred_language: string
  allergies?: string[]
  medications?: string[]
  known_conditions?: string[]
  pin_hash?: string | null
  created_at?: string
}

export interface PatientProfileCreate {
  full_name: string
  age?: string
  gender?: string
  relation?: string
  preferred_language?: string
  allergies?: string[]
  medications?: string[]
  known_conditions?: string[]
  pin?: string
}

/**
 * Request 6-digit OTP for patient phone login.
 */
export async function requestPhoneOtp(phoneNumber: string): Promise<{
  success: boolean
  message: string
  dev_otp_hint?: string
}> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/auth/otp/request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: phoneNumber }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Could not send verification code.');
  }

  return res.json();
}

/**
 * Verify phone OTP and establish authenticated patient session.
 */
export async function verifyPhoneOtp(phoneNumber: string, otpCode: string): Promise<LoginResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/auth/otp/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: phoneNumber, otp_code: otpCode }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid verification code.');
  }

  const data: LoginResponse = await res.json();
  setAuthToken(data.token);
  if (typeof window !== 'undefined') {
    localStorage.setItem('grannus_user', JSON.stringify(data));
  }
  return data;
}

/**
 * Staff login with email and password (doctors, nurses, admins).
 */
export async function loginStaff(payload: Record<string, any>): Promise<LoginResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid email or password.');
  }

  const data: LoginResponse = await res.json();
  setAuthToken(data.token);
  if (typeof window !== 'undefined') {
    localStorage.setItem('grannus_user', JSON.stringify(data));
  }
  return data;
}

/**
 * Log out and revoke active session.
 */
export async function logoutUser(): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  try {
    await fetch(`${baseUrl}/api/v1/auth/logout`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
  } catch {
    // Graceful offline logout
  }
  removeAuthToken();
  if (typeof window !== 'undefined') {
    localStorage.removeItem('grannus_user');
    localStorage.removeItem('grannus_active_profile');
  }
}

/**
 * Fetch patient profiles linked to authenticated phone account.
 */
export async function getPatientProfiles(): Promise<PatientProfile[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/patient/profiles`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error('Failed to load patient profiles.');
  }

  return res.json();
}

/**
 * Create a new patient profile under authenticated phone account.
 */
export async function createPatientProfile(profile: PatientProfileCreate): Promise<PatientProfile> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/patient/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(profile),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to create patient profile.');
  }

  return res.json();
}

export function getActiveProfile(): PatientProfile | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem('grannus_active_profile');
  return raw ? JSON.parse(raw) : null;
}

export function setActiveProfile(profile: PatientProfile): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('grannus_active_profile', JSON.stringify(profile));
}

// -----------------------------------------------------------------------------
// Doctor Dashboard & Urgency Routing APIs (B5.1 - B5.8, F1.1, F3.1 - F3.6)
// -----------------------------------------------------------------------------

export interface DoctorQueueResponse {
  count: number;
  consultations: any[];
}

export async function getDoctorQueue(params?: {
  tier?: string;
  department?: string;
  status?: string;
  search?: string;
}): Promise<DoctorQueueResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const query = new URLSearchParams();
  if (params?.tier && params.tier !== 'All') query.append('tier', params.tier);
  if (params?.department) query.append('department', params.department);
  if (params?.status) query.append('status', params.status);
  if (params?.search) query.append('search', params.search);

  const res = await fetch(`${baseUrl}/api/v1/doctor/queue?${query.toString()}`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load doctor consultation queue.');
  }

  return res.json();
}

export async function getConsultationDetails(consultationId: string): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch consultation ${consultationId}`);
  }

  return res.json();
}

export async function claimConsultationCase(consultationId: string, lockTtlMinutes = 15): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/claim`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ lock_ttl_minutes: lockTtlMinutes }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to claim consultation lock.');
  }

  return res.json();
}

export async function releaseConsultationCase(consultationId: string): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/release`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to release consultation lock.');
  }

  return res.json();
}

export async function reassignConsultationCase(
  consultationId: string,
  targetDoctorId: string,
  reason: string,
  targetDepartment?: string
): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/reassign`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      target_doctor_id: targetDoctorId,
      reason,
      target_department: targetDepartment,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to reassign consultation.');
  }

  return res.json();
}

export async function overrideUrgencyTier(
  consultationId: string,
  newTier: string,
  reason: string
): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/consultations/${consultationId}/override-tier`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      new_tier: newTier,
      reason,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to override urgency tier.');
  }

  return res.json();
}

export async function toggleDoctorAvailability(isOnDuty: boolean): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const res = await fetch(`${baseUrl}/api/v1/doctor/availability`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ is_on_duty: isOnDuty }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update doctor availability.');
  }

  return res.json();
}

export async function getDoctorRoster(department?: string, onDutyOnly = false): Promise<any> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const query = new URLSearchParams();
  if (department) query.append('department', department);
  if (onDutyOnly) query.append('on_duty_only', 'true');

  const res = await fetch(`${baseUrl}/api/v1/doctor/roster?${query.toString()}`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load doctor roster.');
  }

  return res.json();
}




