// Browse.ai extractor configuration (public). This ID may be exposed to the client.
// Keep the API key ONLY on the server (set BROWSEAI_API_KEY in the backend env).
// Do NOT expose the API key through NEXT_PUBLIC_* variables to avoid leaking it.
export const DEFAULT_BROWSE_AI_EXTRACTOR =
  process.env.NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID || ""; // empty string disables by default

// Intentionally no DEFAULT_BROWSE_AI_API_KEY export any more – secrets must stay server-side.