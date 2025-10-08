"use client";

import { useState } from "react";

const QUICK_FILTERS = [
  "Under $50",
  "Running",
  "Black",
  "Size M",
  // broader/general filters
  "Casual",
  "Formal",
  "Sneakers",
  "Sandals",
  "Boots",
  "Women",
  "Men",
  "Unisex",
  "Sale",
  "New Arrivals"
];

export default function Filters({ onSelect }: { onSelect: (chip: string) => void }) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="flex flex-wrap gap-2">
      {QUICK_FILTERS.map(chip => (
        <button
          key={chip}
          onClick={() => {
            setSelected(chip);
            onSelect(chip);
          }}
          className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
            selected === chip
              ? "border-primary bg-primary text-primary-foreground"
              : "border-slate-200 bg-white text-slate-600 hover:border-primary hover:text-primary"
          }`}
        >
          {chip}
        </button>
      ))}
    </div>
  );
}