import { AgentResponse } from "./types";

// The backend exposes endpoints at the root (e.g. http://localhost:8000/agent/chat).
// Default to the backend root so the client works when running uvicorn locally.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function sendAgentMessage(
  message: string,
  image_b64?: string,
  web_url?: string,
  allow_web: boolean = false
): Promise<AgentResponse> {
  const body: any = { message };
  if (image_b64) body.image_b64 = image_b64;
  if (web_url) body.web_url = web_url;
  if (allow_web) body.allow_web = true;

  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Agent request failed with status ${response.status}`);
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