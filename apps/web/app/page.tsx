"use client";

import { useState } from "react";
import Chat from "../components/Chat";
import Filters from "../components/Filters";
import ImageDropzone from "../components/ImageDropzone";
import ProductGrid from "../components/ProductGrid";
import { AgentResponse, ProductCard } from "../lib/types";
import { sendAgentMessage, sendRecommend } from "../lib/agentClient";

export default function HomePage() {
  const [products, setProducts] = useState<ProductCard[]>([]);
  const [followUp, setFollowUp] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function handleResponse(response: AgentResponse) {
    setProducts(response.products);
    setFollowUp(response.follow_up_question ?? null);
  }

  async function handleFilterSelect(chip: string) {
    try {
      setLoading(true);
      // Map chip to a structured recommend call when possible
      const mapping: Record<string, { goal: string; constraints?: any }> = {
        "Under $50": { goal: "affordable products", constraints: { price_max: 5000 } },
        Running: { goal: "running shoes", constraints: { category: "shoes" } },
        Black: { goal: "black products", constraints: { color: ["black"] } },
        "Size M": { goal: "size M", constraints: { size: ["M"] } },
        Casual: { goal: "casual shoes" },
        Formal: { goal: "formal shoes" },
        Sneakers: { goal: "sneakers" },
        Sandals: { goal: "sandals" },
        Boots: { goal: "boots" },
        Women: { goal: "products for women" },
        Men: { goal: "products for men" },
        Unisex: { goal: "unisex products" },
        Sale: { goal: "on sale" },
        "New Arrivals": { goal: "new arrivals" },
      };

      if (mapping[chip]) {
        const payload = mapping[chip];
        const resp = await sendRecommend(payload.goal, payload.constraints ?? null, 8);
        setProducts(resp.results || []);
      } else {
        const response = await sendAgentMessage(chip);
        handleResponse(response);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleImageUpload(file: File) {
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = (reader.result as string).split(",")[1] ?? "";
      setLoading(true);
      try {
        const response = await sendAgentMessage("", base64);
        handleResponse(response);
      } finally {
        setLoading(false);
      }
    };
    reader.readAsDataURL(file);
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-6 py-10 lg:flex-row">
      <section className="lg:w-1/3">
        <div className="space-y-4">
          <h1 className="text-2xl font-bold text-slate-900">CommerceAgent</h1>
          <p className="text-sm text-slate-600">
            Chat with an AI shopping assistant. Ask for recommendations, apply quick filters, or search using an image.
          </p>
          <Filters onSelect={handleFilterSelect} />
          <ImageDropzone onUpload={handleImageUpload} />
          {followUp && <p className="text-sm text-slate-500">{followUp}</p>}
          <Chat onResponse={handleResponse} />
        </div>
      </section>
      <section className="lg:w-2/3 space-y-2">
        {loading && <p className="text-xs text-slate-400">Fetching results…</p>}
        <ProductGrid products={products} />
      </section>
    </main>
  );
}