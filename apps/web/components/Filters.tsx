"use client";

import { useState, useEffect } from "react";

const MAX_PRICE = 2000; // $2000 as max price

export type PriceRange = {
  min: number;
  max: number;
};

export default function Filters({ onPriceChange }: { onPriceChange: (range: PriceRange) => void }) {
  const [priceRange, setPriceRange] = useState<number>(MAX_PRICE);

  useEffect(() => {
    onPriceChange({ min: 0, max: priceRange });
  }, [priceRange, onPriceChange]);

  return (
    <div className="w-full space-y-2 px-4">
      <div className="flex justify-between text-sm text-slate-600">
        <span>Price Range: $0 - ${priceRange}</span>
      </div>
      <input
        type="range"
        min="0"
        max={MAX_PRICE}
        value={priceRange}
        onChange={(e) => setPriceRange(Number(e.target.value))}
        className="w-full accent-primary cursor-pointer"
      />
    </div>
  );
}