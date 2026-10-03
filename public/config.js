/* Public frontend configuration. Cad fills these with VERIFIED public values only.
 * supabaseUrl: https://<project-ref>.supabase.co
 * supabaseAnonKey: the publishable/anon key. NEVER a service-role key or any provider secret.
 * apiBase: '' when /api/* is proxied on the same origin (Vercel rewrite); otherwise the backend origin (needs CORS).
 * While supabaseUrl/supabaseAnonKey are null, sign-in shows "not configured" and nothing is faked. */
window.RECHECK_CONFIG = {
  supabaseUrl: null,
  supabaseAnonKey: null,
  apiBase: ''
};
