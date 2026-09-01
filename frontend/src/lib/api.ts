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

export interface PriorityAssessment {
  level: PriorityLevel
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
  audio_preprocessing: Record<string, unknown> | null
  pipeline_stages: Record<string, unknown> | null
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
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  return response.json();
}
