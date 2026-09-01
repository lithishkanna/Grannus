import { supabase } from './supabase';
import { PipelineResult } from './api';

export async function storeResultToSupabase(result: PipelineResult, doctorId: string | null = null) {
  try {
    // 1. Create a consultation record
    const { data: consultation, error: consultationError } = await supabase
      .from('consultations')
      .insert({
        doctor_id: doctorId,
        patient_id: null,
        status: 'triage',
      })
      .select()
      .single();

    if (consultationError) throw consultationError;

    const consultationId = consultation.id;

    // 2. Insert into pipeline_results
    const { error: prError } = await supabase
      .from('pipeline_results')
      .insert({
        consultation_id: consultationId,
        request_id: result.request_id,
        full_result: result as any,
        priority_level: result.priority?.level,
        chief_complaint: result.clinical_summary?.chief_complaint,
        patient_language: result.patient_input?.language,
        has_red_flags: result.safety_screening?.red_flags?.length > 0,
        confidence: result.priority?.confidence
      });

    if (prError) throw prError;

    // 3. Insert into clinical_summaries
    const relevantHistory = [
      ...(result.clinical_summary.existing_conditions || []),
      ...(result.clinical_summary.medications || []),
      ...(result.clinical_summary.allergies || [])
    ].join(', ');

    const { error: csError } = await supabase
      .from('clinical_summaries')
      .insert({
        consultation_id: consultationId,
        chief_complaint: result.clinical_summary.chief_complaint,
        relevant_history: relevantHistory || null,
        doctor_translated_summary: result.translation || null,
        home_remedy_guidance: result.home_remedy || null
      });

    if (csError) throw csError;

    // 4. Insert symptoms
    if (result.clinical_summary.symptoms && result.clinical_summary.symptoms.length > 0) {
      const symptomsToInsert = result.clinical_summary.symptoms.map(s => ({
        consultation_id: consultationId,
        name: s.name,
        severity: s.severity,
        duration_value: s.duration?.value ? parseInt(s.duration.value) : null,
        duration_unit: s.duration?.unit || null,
        body_location: s.body_location,
        is_negated: s.negated
      }));
      
      const { error: symError } = await supabase
        .from('symptoms')
        .insert(symptomsToInsert);
        
      if (symError) throw symError;
    }

    // 5. Insert safety_assessments
    const hasRedFlags = result.safety_screening.red_flags.length > 0;
    const { error: saError } = await supabase
      .from('safety_assessments')
      .insert({
        consultation_id: consultationId,
        has_critical_flags: hasRedFlags
      });

    if (saError) throw saError;

    // 6. Insert priority_assessments
    const allowedPriorityLevels = ['LOW', 'MEDIUM', 'HIGH'];
    const priorityLevelForAssessment = allowedPriorityLevels.includes(result.priority?.level)
      ? result.priority.level
      : 'MEDIUM';

    const { error: paError } = await supabase
      .from('priority_assessments')
      .insert({
        consultation_id: consultationId,
        level: priorityLevelForAssessment,
        confidence: result.priority?.confidence,
        reasons: result.priority?.reasons as any
      });

    if (paError) throw paError;

    // 7. Insert follow_up_questions
    if (result.safety_screening.follow_up_questions && result.safety_screening.follow_up_questions.length > 0) {
      const questionsToInsert = result.safety_screening.follow_up_questions.map(q => ({
        consultation_id: consultationId,
        english_question: q
      }));
      
      const { error: fqError } = await supabase
        .from('follow_up_questions')
        .insert(questionsToInsert);
        
      if (fqError) throw fqError;
    }

    return consultationId;
  } catch (error) {
    console.error('Failed to store result to Supabase:', error);
    throw error;
  }
}
