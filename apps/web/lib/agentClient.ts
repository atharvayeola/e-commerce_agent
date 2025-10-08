import { AgentResponse } from "./types";

// The backend exposes endpoints at the root (e.g. http://localhost:8000/agent/chat).
// Default to the backend root so the client works when running uvicorn locally.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function sendAgentMessage(message: string, image_b64?: string): Promise<AgentResponse> {
  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, image_b64 })
  });

  if (!response.ok) {
    throw new Error(`Agent request failed with status ${response.status}`);
  }

  return (await response.json()) as AgentResponse;
}