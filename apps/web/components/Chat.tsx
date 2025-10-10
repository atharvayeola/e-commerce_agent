
"use client";

import { FormEvent, useEffect, useState } from "react";
import { AgentResponse } from "../lib/types";
import { sendAgentMessage } from "../lib/agentClient";
import { DEFAULT_BROWSE_AI_EXTRACTOR } from "../lib/config";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};
export type ExternalMessage = Omit<ChatMessage, "id">;

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

type ChatProps = {
  onResponse: (response: AgentResponse, source?: "text" | "image") => void;
  externalMessages?: ExternalMessage[];
  externalLoading?: boolean;
  onExternalMessagesConsumed?: () => void;
};

export default function Chat({
  onResponse,
  externalMessages,
  externalLoading = false,
  onExternalMessagesConsumed,
}: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [webUrl, setWebUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const browseConfigured = Boolean(DEFAULT_BROWSE_AI_EXTRACTOR);
    const combinedLoading = loading || externalLoading;

  useEffect(() => {
    if (externalMessages && externalMessages.length > 0) {
      setMessages(prev => [
        ...prev,
        ...externalMessages.map(message => ({
          id: createId(),
          role: message.role,
          content: message.content,
        })),
      ]);
      onExternalMessagesConsumed?.();
    }
  }, [externalMessages, onExternalMessagesConsumed]);
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = input.trim();
    const trimmedUrl = webUrl.trim();
    if (!trimmedMessage) return;
    const userMessage: ChatMessage = { id: createId(), role: "user", content: trimmedMessage };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const response = await sendAgentMessage(userMessage.content, { web_url: trimmedUrl || undefined });
      onResponse(response, "text");
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        content: response.text,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  return (
  <div className="flex h-full flex-col rounded-2xl bg-white shadow-sm ring-1 ring-slate-100">
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.length === 0 ? (
          <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">
            Ask CommerceAgent for a product recommendation or paste a link for additional context.
          </div>
        ) : (
        messages.map(message => {
            const isUser = message.role === "user";
            return (
              <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] space-y-1 text-sm ${isUser ? "text-right" : "text-left"}`}>
                  <span className="text-xs uppercase tracking-wide text-slate-400">
                    {isUser ? "You" : "Assistant"}
                  </span>
                  <p
                    className={`rounded-2xl px-3 py-2 shadow-sm ${
                      isUser ? "bg-primary text-primary-foreground" : "bg-slate-100 text-slate-800"
                    }`}
                  >
                    {message.content}
                  </p>
                </div>
              </div>
            );
          })
        )}
        {combinedLoading && <p className="text-xs text-slate-400">Thinking…</p>}
      </div>
      <form onSubmit={handleSubmit} className="space-y-3 border-t border-slate-200 p-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="sr-only" htmlFor="agent-message">
            Ask CommerceAgent for a product
          </label>
          <input
            id="agent-message"
            type="text"
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder="Search for gadgets under $700 or ask for styling tips"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-primary focus:outline-none"
          />

          <button
            type="submit"
            disabled={combinedLoading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Send
          </button>
        </div>
        <div className="space-y-1">
          <label className="sr-only" htmlFor="agent-url">
            Optional web URL for context
          </label>
          <input
            id="agent-url"
            type="url"
            value={webUrl}
            onChange={e => setWebUrl(e.target.value)}
            placeholder="Optional: paste a product URL to include its details"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-primary focus:outline-none"
          />
          <p className="text-xs text-slate-400">
            {browseConfigured
              ? "Browse.ai extractor configured. API key is managed server-side."
              : "Set NEXT_PUBLIC_BROWSE_AI_EXTRACTOR_ID (frontend) and BROWSEAI_API_KEY (backend) to enable Browse.ai."}
          </p>
        </div>
      </form>
    </div>
  );
}