
"use client";

import { FormEvent, useState } from "react";
import { AgentResponse } from "../lib/types";
import { sendAgentMessage } from "../lib/agentClient";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

export default function Chat({ onResponse }: { onResponse: (response: AgentResponse) => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [webUrl, setWebUrl] = useState("");
  const [allowWeb, setAllowWeb] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim()) return;
    const userMessage: ChatMessage = { id: createId(), role: "user", content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const response = await sendAgentMessage(userMessage.content, undefined, webUrl || undefined, allowWeb);
      onResponse(response);
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        content: response.text
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <p className="text-sm text-slate-500">Ask CommerceAgent for a product recommendation.</p>
        ) : (
          messages.map(message => (
            <div key={message.id} className="space-y-1">
              <p className="text-xs uppercase tracking-wide text-slate-400">{message.role}</p>
              <p className="rounded-md bg-slate-100 p-2 text-sm text-slate-800">{message.content}</p>
            </div>
          ))
        )}
        {loading && <p className="text-xs text-slate-400">Thinking…</p>}
      </div>
      <form onSubmit={handleSubmit} className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder="Ask for a running shoe under $100"
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <input
            type="text"
            value={webUrl}
            onChange={e => setWebUrl(e.target.value)}
            placeholder="Optional: provide a web URL to use"
            className="w-64 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <label className="flex items-center gap-2 text-xs">
            <input type="checkbox" checked={allowWeb} onChange={e => setAllowWeb(e.target.checked)} />
            <span>Allow fetching web content</span>
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}