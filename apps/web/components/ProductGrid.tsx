import { ProductCard } from "../lib/types";

function formatPrice(priceCents: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency
  }).format(priceCents / 100);
}

export default function ProductGrid({ products }: { products: ProductCard[] }) {
  if (!products.length) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300">
        <p className="text-sm text-slate-500">Products will appear here after you chat with the agent.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {products.map(product => (
        <article key={product.id} className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          {product.image && (
            <img src={product.image} alt={product.title} className="h-40 w-full rounded-md object-cover" />
          )}
          <h3 className="mt-3 text-base font-semibold text-slate-900">{product.title}</h3>
          <p className="mt-1 text-sm text-slate-600">{formatPrice(product.price_cents, product.currency)}</p>
          {product.badges.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {product.badges.map(badge => (
                <span key={badge} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                  {badge}
                </span>
              ))}
            </div>
          )}
          {product.rationale && <p className="mt-3 text-sm text-slate-500">{product.rationale}</p>}
        </article>
      ))}
    </div>
  );
}