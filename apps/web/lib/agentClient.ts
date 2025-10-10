import { DEFAULT_BROWSE_AI_EXTRACTOR } from "./config";
import { AgentResponse } from "./types";

// The backend exposes endpoints at the root (e.g. http://localhost:8000/agent/chat).
// Default to the backend root so the client works when running uvicorn locally.
// Treat empty string as unset (Vercel can pass empty values) and normalize trailing slashes.
const _envApiBase = process.env.NEXT_PUBLIC_API_BASE;
const API_BASE = _envApiBase && _envApiBase.trim()
  ? _envApiBase.trim().replace(/\/+$/, "")
  : "http://localhost:8000";

  const _envAllowWebDefault = process.env.NEXT_PUBLIC_AGENT_ALLOW_WEB_DEFAULT;
const ENV_ALLOW_WEB_DEFAULT =
  _envAllowWebDefault !== undefined
    ? !/^false$/i.test(_envAllowWebDefault.trim())
    : true;
    
export type AgentMessageOptions = {
  image_b64?: string;
  web_url?: string;
  allow_web?: boolean;
  browse_extractor?: string;
  browse_api_key?: string;
};

export async function sendAgentMessage(
  message: string,
  options: AgentMessageOptions = {}
): Promise<AgentResponse> {
  const inferredAllowWeb =
    options.allow_web ??
    (Boolean(options.web_url) || Boolean(options.image_b64) || ENV_ALLOW_WEB_DEFAULT);
  const body: any = { message, allow_web: inferredAllowWeb };
  if (options.image_b64) body.image_b64 = options.image_b64;
  if (options.web_url) body.web_url = options.web_url;

  const extractor =
    options.browse_extractor !== undefined
      ? options.browse_extractor
      : DEFAULT_BROWSE_AI_EXTRACTOR;
  if (extractor) {
    body.browse_extractor = extractor;
    // No API key forwarded from client; backend will read BROWSEAI_API_KEY.
  }

  const url = `${API_BASE}/agent/chat`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const text = await response.text();
      detail = text ? ` - ${text.slice(0, 200)}` : "";
    } catch {}
    throw new Error(`Agent request failed with status ${response.status} ${response.statusText} at ${url}${detail}`);
  }

  return (await response.json()) as AgentResponse;
}

export async function sendRecommend(
  goal: string,
  constraints: Record<string, any> | null = null,
  limit: number = 6
): Promise<{ results: any[]; debug?: any }> {
  const body: any = { goal, limit };
  if (constraints) body.constraints = constraints;

  const response = await fetch(`${API_BASE}/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Recommend request failed with status ${response.status}`);
  }

  return (await response.json()) as { results: any[]; debug?: any };
}