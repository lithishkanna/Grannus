-- =============================================================================
-- Migration: 20261006_row_level_security.sql
-- Description: Enable Row Level Security (RLS) on all tables, deny by default,
--              create audio_retention_queue & revoked_tokens, restrict anon.
-- =============================================================================

-- 1. Create missing persistent infrastructure tables
CREATE TABLE IF NOT EXISTS public.audio_retention_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL UNIQUE,
    hospital_id UUID REFERENCES public.hospitals(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    delete_after TIMESTAMPTZ NOT NULL,
    purged BOOLEAN NOT NULL DEFAULT false,
    purged_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.revoked_tokens (
    token_jti TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    expires_at TIMESTAMPTZ NOT NULL
);

-- 2. Enable RLS on every table (deny by default)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.clinical_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.symptoms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.safety_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.priority_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.follow_up_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.doctor_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.otp_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.patient_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.persistent_voice_threads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.persistent_follow_ups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultation_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guest_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.deletion_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audio_retention_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.revoked_tokens ENABLE ROW LEVEL SECURITY;

-- 3. Deny by default: Revoke direct permissions from anon on all public tables
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;

-- Allow public read on non-sensitive facility directories only
GRANT SELECT ON public.hospitals TO anon;
GRANT SELECT ON public.departments TO anon;

DROP POLICY IF EXISTS "Public read hospitals" ON public.hospitals;
CREATE POLICY "Public read hospitals" ON public.hospitals FOR SELECT TO anon USING (true);

DROP POLICY IF EXISTS "Public read departments" ON public.departments;
CREATE POLICY "Public read departments" ON public.departments FOR SELECT TO anon USING (true);
