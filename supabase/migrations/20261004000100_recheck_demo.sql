-- Dedicated synthetic demo records, separate from normalized application records.
-- Parent/operator reviews and applies this migration; the CLI never provisions tables.
BEGIN;
CREATE TABLE public.recheck_demo_runs (
  id uuid PRIMARY KEY,
  synthetic_data boolean NOT NULL CHECK (synthetic_data IS TRUE),
  payload jsonb NOT NULL CHECK ((jsonb_typeof(payload) = 'object'
    AND payload->>'id' = id::text AND payload->'syntheticData' = 'true'::jsonb) IS TRUE),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.recheck_demo_experiences (
  id uuid PRIMARY KEY,
  synthetic_data boolean NOT NULL CHECK (synthetic_data IS TRUE),
  payload jsonb NOT NULL CHECK ((jsonb_typeof(payload) = 'object'
    AND payload->>'id' = id::text AND payload->'syntheticData' = 'true'::jsonb
    AND payload->'verification'->>'status' = 'finished'
    AND payload->'verification'->>'verdict' = 'works'
    AND jsonb_typeof(payload->'candidate') = 'string') IS TRUE),
  created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.recheck_demo_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_demo_experiences ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.recheck_demo_runs, public.recheck_demo_experiences FROM anon, authenticated;
GRANT SELECT, INSERT ON public.recheck_demo_runs, public.recheck_demo_experiences TO service_role;
-- No public policies. Server-only secret key, trusted evaluator gate, exact readbacks.
COMMIT;
