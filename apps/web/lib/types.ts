export type ProductCard = {
  id: string;
  title: string;
  image?: string | null;
  price_cents: number;
  currency: string;
  badges: string[];
  rationale?: string | null;
  source?: "web" | "catalog" | string;
  url?: string | null;
};

export type AgentResponse = {
  intent: "smalltalk" | "text_recommendation" | "image_search";
  text: string;
  products: ProductCard[];
  follow_up_question?: string | null;
};