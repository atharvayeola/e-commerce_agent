"use client";

import { useState } from "react";
import Chat, { ExternalMessage } from "../components/Chat";
import Filters from "../components/Filters";
import ImageDropzone from "../components/ImageDropzone";
import ProductGrid from "../components/ProductGrid";
import Cart from "../components/Cart";
import { CartProvider } from "../lib/CartContext";
import { AgentResponse, ProductCard } from "../lib/types";
import { sendAgentMessage } from "../lib/agentClient";

export default function HomePage() {
  const [products, setProducts] = useState<ProductCard[]>([]);
  const [filteredProducts, setFilteredProducts] = useState<ProductCard[]>([]);
  const [followUp, setFollowUp] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [priceRange, setPriceRange] = useState<{ min: number; max: number }>({ min: 0, max: 2000 });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [chatExternalMessages, setChatExternalMessages] = useState<ExternalMessage[]>([]);
  const [chatExternalLoading, setChatExternalLoading] = useState(false);

  function handleResponse(response: AgentResponse, source: "text" | "image" = "text") {
    setProducts(response.products);
    const filtered = response.products.filter(product => {
      const priceInDollars = product.price_cents / 100;
      return priceInDollars >= priceRange.min && priceInDollars <= priceRange.max;
    });
    setFilteredProducts(filtered);
    setFollowUp(response.follow_up_question ?? null);
    if (source === "image") {
      setChatExternalMessages(prev => [...prev, { role: "assistant", content: response.text }]);
    }
  }

  async function handleImageUpload(file: File) {
    const reader = new FileReader();
    reader.onload = async () => {
      const base64 = (reader.result as string).split(",")[1] ?? "";
      setLoading(true);
      setChatExternalMessages([{ role: "user", content: "Uploaded an image for visual search." }]);
      setChatExternalLoading(true);
      try {
        const response = await sendAgentMessage("", { image_b64: base64 });
        handleResponse(response, "image");
      } finally {
        setLoading(false);
        setChatExternalLoading(false);
      }
    };
    reader.readAsDataURL(file);
  }

  return (
    <CartProvider>
      <main className="min-h-screen bg-slate-50 py-10">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 lg:flex-row">
          <section className="space-y-6 lg:w-1/3">
            <div className="flex items-center justify-between">
              <h1 className="text-3xl font-bold text-slate-900">CommerceAgent</h1>
              <button
                onClick={() => setIsCartOpen(true)}
                className="rounded-full bg-primary p-2 text-primary-foreground hover:brightness-110"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
                </svg>
              </button>
            </div>
            <div className="space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-100">
              <div className="space-y-2">
                <p className="text-sm leading-relaxed text-slate-600">
                  Discover products with conversational search, quick filters, and visual inspiration—now with automatic web results
                  when the catalog runs out of matches.
                </p>
              </div>
              <ImageDropzone onUpload={handleImageUpload} />
              {followUp && <p className="text-sm text-slate-500">{followUp}</p>}
            </div>
            <Filters onPriceChange={range => {
              setPriceRange(range);
              const filtered = products.filter(product => {
                const priceInDollars = product.price_cents / 100;
                return priceInDollars >= range.min && priceInDollars <= range.max;
              });
              setFilteredProducts(filtered);
            }} />
            <Chat
              onResponse={handleResponse}
              externalMessages={chatExternalMessages}
              onExternalMessagesConsumed={() => setChatExternalMessages([])}
              externalLoading={chatExternalLoading}
            />
          </section>
          <section className="space-y-4 lg:w-2/3">
            {loading && <p className="text-xs text-slate-500">Fetching results…</p>}
            <ProductGrid products={filteredProducts} />
          </section>
        </div>
        <Cart isOpen={isCartOpen} onClose={() => setIsCartOpen(false)} />
      </main>
    </CartProvider>
  );
}