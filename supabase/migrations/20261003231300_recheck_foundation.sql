-- Review/apply only to the approved Recheck project; NOT executed by this backend.
-- Authenticated callers are read-only. Only a separately trusted recorder may
-- write evidence via service_role. No anonymous private access or client role grants.
BEGIN;

CREATE TABLE public.recheck_workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.recheck_memberships (
  workspace_id uuid NOT NULL REFERENCES public.recheck_workspaces(id),
  user_id uuid NOT NULL REFERENCES auth.users(id),
  role text NOT NULL CHECK (role IN ('member', 'operator')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);
CREATE TABLE public.recheck_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.recheck_workspaces(id),
  kind text NOT NULL CHECK (kind IN ('candidate', 'test_manifest', 'sanitized_log')),
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  safe_storage_reference text NOT NULL,
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id)
);
CREATE TABLE public.recheck_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.recheck_workspaces(id),
  experience_id uuid,
  candidate_artifact_id uuid NOT NULL,
  test_suite_id uuid NOT NULL,
  target_requirement_version text NOT NULL,
  environment_fingerprint text,
  artifact_hash text CHECK (artifact_hash ~ '^[0-9a-f]{64}$'),
  test_suite_hash text CHECK (test_suite_hash ~ '^[0-9a-f]{64}$'),
  required_check_count integer NOT NULL CHECK (required_check_count BETWEEN 1 AND 1000),
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'finished', 'blocked')),
  verdict text CHECK (verdict IN ('works', 'fails', 'cannot_verify')),
  execution_provider text,
  execution_id text,
  actual_model text,
  started_at timestamptz,
  completed_at timestamptz,
  duration_ms bigint CHECK (duration_ms >= 0),
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id),
  FOREIGN KEY (workspace_id, candidate_artifact_id) REFERENCES public.recheck_artifacts(workspace_id, id),
  FOREIGN KEY (workspace_id, test_suite_id) REFERENCES public.recheck_artifacts(workspace_id, id),
  CHECK (((status IN ('queued', 'running') AND verdict IS NULL) OR
         (status = 'blocked' AND verdict = 'cannot_verify') OR
         (status = 'finished' AND verdict IN ('works', 'fails') AND
          completed_at IS NOT NULL AND started_at IS NOT NULL AND duration_ms IS NOT NULL AND
          execution_provider IS NOT NULL AND execution_id IS NOT NULL AND actual_model IS NOT NULL AND
          artifact_hash IS NOT NULL AND test_suite_hash IS NOT NULL AND environment_fingerprint IS NOT NULL)) IS TRUE)
);
CREATE TABLE public.recheck_check_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  verification_id uuid NOT NULL,
  name text NOT NULL,
  expected_json jsonb NOT NULL,
  actual_json jsonb NOT NULL,
  passed boolean NOT NULL,
  diagnostic text,
  UNIQUE (verification_id, name),
  FOREIGN KEY (workspace_id, verification_id) REFERENCES public.recheck_verifications(workspace_id, id)
);
CREATE TABLE public.recheck_experiences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.recheck_workspaces(id),
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 2048),
  summary text NOT NULL CHECK (length(summary) BETWEEN 1 AND 2048),
  problem_tag text NOT NULL,
  candidate_artifact_id uuid NOT NULL,
  original_requirement_version text NOT NULL,
  original_environment_fingerprint text NOT NULL,
  verification_id uuid NOT NULL,
  parent_experience_id uuid,
  created_by_agent text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, id),
  FOREIGN KEY (workspace_id, candidate_artifact_id) REFERENCES public.recheck_artifacts(workspace_id, id),
  FOREIGN KEY (workspace_id, verification_id) REFERENCES public.recheck_verifications(workspace_id, id),
  FOREIGN KEY (workspace_id, parent_experience_id) REFERENCES public.recheck_experiences(workspace_id, id)
  -- No writable verified flag: an experience is admitted only by passing proof.
);
ALTER TABLE public.recheck_verifications ADD CONSTRAINT recheck_verification_experience_fk
  FOREIGN KEY (workspace_id, experience_id) REFERENCES public.recheck_experiences(workspace_id, id);
CREATE TABLE public.recheck_run_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.recheck_workspaces(id),
  demo_run_id uuid,
  verification_id uuid,
  stage text CHECK (stage IN ('learn', 'replay', 'repair')),
  type text NOT NULL CHECK (type IN ('info', 'pass', 'fail', 'blocked')),
  message text NOT NULL,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (workspace_id, verification_id) REFERENCES public.recheck_verifications(workspace_id, id)
);

CREATE FUNCTION public.recheck_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
  RAISE EXCEPTION 'recheck immutable evidence';
END;
$$;
CREATE TRIGGER recheck_artifact_immutable BEFORE UPDATE OR DELETE ON public.recheck_artifacts
  FOR EACH ROW EXECUTE FUNCTION public.recheck_immutable();
CREATE TRIGGER recheck_experience_immutable BEFORE UPDATE OR DELETE ON public.recheck_experiences
  FOR EACH ROW EXECUTE FUNCTION public.recheck_immutable();
CREATE TRIGGER recheck_event_append_only BEFORE UPDATE OR DELETE ON public.recheck_run_events
  FOR EACH ROW EXECUTE FUNCTION public.recheck_immutable();

CREATE FUNCTION public.recheck_guard_check() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE v public.recheck_verifications;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'recheck immutable check';
  END IF;
  -- Serializes completion against check insertion. Candidate never supplies results.
  SELECT * INTO v FROM public.recheck_verifications
    WHERE id = NEW.verification_id AND workspace_id = NEW.workspace_id FOR UPDATE;
  IF NOT FOUND OR v.status NOT IN ('queued', 'running') THEN
    RAISE EXCEPTION 'recheck check requires nonterminal verification';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER recheck_check_guard BEFORE INSERT OR UPDATE OR DELETE ON public.recheck_check_results
  FOR EACH ROW EXECUTE FUNCTION public.recheck_guard_check();

CREATE FUNCTION public.recheck_guard_verification() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE n integer; passing integer; candidate public.recheck_artifacts; suite public.recheck_artifacts;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'recheck immutable verification';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF OLD.status IN ('finished', 'blocked') THEN
      RAISE EXCEPTION 'recheck terminal verification is immutable';
    END IF;
    IF NEW.workspace_id <> OLD.workspace_id OR NEW.id <> OLD.id OR
       NEW.candidate_artifact_id <> OLD.candidate_artifact_id OR NEW.test_suite_id <> OLD.test_suite_id OR
       NEW.required_check_count <> OLD.required_check_count OR
       NEW.target_requirement_version <> OLD.target_requirement_version OR
       NEW.experience_id IS DISTINCT FROM OLD.experience_id OR
       (OLD.status = 'running' AND NEW.status = 'queued') THEN
      RAISE EXCEPTION 'recheck immutable verification target';
    END IF;
  END IF;
  IF NEW.status = 'finished' THEN
    SELECT count(*), count(*) FILTER (WHERE passed) INTO n, passing
      FROM public.recheck_check_results WHERE verification_id = NEW.id AND workspace_id = NEW.workspace_id;
    IF n <> NEW.required_check_count OR
       (NEW.verdict = 'works' AND passing <> n) OR
       (NEW.verdict = 'fails' AND passing = n) THEN
      RAISE EXCEPTION 'recheck verdict requires complete independent checks';
    END IF;
    SELECT * INTO candidate FROM public.recheck_artifacts WHERE id = NEW.candidate_artifact_id AND workspace_id = NEW.workspace_id;
    SELECT * INTO suite FROM public.recheck_artifacts WHERE id = NEW.test_suite_id AND workspace_id = NEW.workspace_id;
    IF candidate.kind <> 'candidate' OR suite.kind <> 'test_manifest' OR
       candidate.sha256 <> NEW.artifact_hash OR suite.sha256 <> NEW.test_suite_hash THEN
      RAISE EXCEPTION 'recheck receipt must match immutable artifacts';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER recheck_verification_guard BEFORE INSERT OR UPDATE OR DELETE ON public.recheck_verifications
  FOR EACH ROW EXECUTE FUNCTION public.recheck_guard_verification();

CREATE FUNCTION public.recheck_require_passing_verification() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE v public.recheck_verifications; n integer; passing integer;
BEGIN
  SELECT * INTO v FROM public.recheck_verifications
    WHERE id = NEW.verification_id AND workspace_id = NEW.workspace_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'recheck passing verification required'; END IF;
  IF v.status <> 'finished' OR v.verdict <> 'works' OR
     v.candidate_artifact_id <> NEW.candidate_artifact_id OR
     v.environment_fingerprint <> NEW.original_environment_fingerprint OR
     v.target_requirement_version <> NEW.original_requirement_version THEN
    RAISE EXCEPTION 'recheck passing verification required';
  END IF;
  SELECT count(*), count(*) FILTER (WHERE passed) INTO n, passing
    FROM public.recheck_check_results WHERE verification_id = v.id AND workspace_id = NEW.workspace_id;
  IF n <> v.required_check_count OR n <> passing THEN
    RAISE EXCEPTION 'recheck complete passing checks required';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER recheck_experience_passing BEFORE INSERT ON public.recheck_experiences
  FOR EACH ROW EXECUTE FUNCTION public.recheck_require_passing_verification();

ALTER TABLE public.recheck_workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_experiences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_check_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recheck_run_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY recheck_memberships_self_read ON public.recheck_memberships FOR SELECT TO authenticated
  USING (user_id = auth.uid());
CREATE POLICY recheck_workspace_read ON public.recheck_workspaces FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_workspaces.id AND m.user_id = auth.uid()));
CREATE POLICY recheck_artifact_read ON public.recheck_artifacts FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_artifacts.workspace_id AND m.user_id = auth.uid()));
CREATE POLICY recheck_verification_read ON public.recheck_verifications FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_verifications.workspace_id AND m.user_id = auth.uid()));
CREATE POLICY recheck_experience_read ON public.recheck_experiences FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_experiences.workspace_id AND m.user_id = auth.uid()));
CREATE POLICY recheck_check_read ON public.recheck_check_results FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_check_results.workspace_id AND m.user_id = auth.uid()));
CREATE POLICY recheck_event_read ON public.recheck_run_events FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.recheck_memberships m WHERE m.workspace_id = recheck_run_events.workspace_id AND m.user_id = auth.uid()));

REVOKE ALL ON public.recheck_workspaces, public.recheck_memberships, public.recheck_artifacts,
  public.recheck_verifications, public.recheck_experiences, public.recheck_check_results, public.recheck_run_events
  FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.recheck_workspaces, public.recheck_memberships, public.recheck_artifacts,
  public.recheck_verifications, public.recheck_experiences, public.recheck_check_results, public.recheck_run_events TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.recheck_workspaces, public.recheck_memberships, public.recheck_artifacts,
  public.recheck_verifications, public.recheck_experiences, public.recheck_check_results, public.recheck_run_events TO service_role;
REVOKE ALL ON FUNCTION public.recheck_immutable(), public.recheck_guard_check(),
  public.recheck_guard_verification(), public.recheck_require_passing_verification() FROM PUBLIC, anon, authenticated;

CREATE INDEX recheck_verifications_workspace_created ON public.recheck_verifications(workspace_id, created_at);
CREATE INDEX recheck_experiences_workspace_created ON public.recheck_experiences(workspace_id, created_at);
CREATE INDEX recheck_checks_workspace_verification ON public.recheck_check_results(workspace_id, verification_id);
CREATE INDEX recheck_events_workspace_time ON public.recheck_run_events(workspace_id, occurred_at);
COMMIT;
