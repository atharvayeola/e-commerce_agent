import { ProductCard } from "../lib/types";
import { useCart } from "../lib/CartContext";

function formatPrice(priceCents: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency
  }).format(priceCents / 100);
}

function formatCategoryLabel(category?: string | null) {
  if (!category) return null;
  return category
    .split(/[-_]/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export default function ProductGrid({ products }: { products: ProductCard[] }) {
  const { addToCart, state } = useCart();

  if (!products.length) {
    return (
    <div className="flex min-h-[320px] items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
        <p className="max-w-sm text-sm text-slate-500">
          Products will appear here after you chat with the agent, apply a quick filter, or upload an image.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {products.map(product => {
        const categoryLabel = formatCategoryLabel(product.category);
        return (
          <article key={product.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              {product.url ? (
                <a href={product.url} target="_blank" rel="noreferrer" className="mt-3 text-base font-semibold text-slate-900 hover:underline">
                  {product.title}
                </a>
              ) : (
                <h3 className="mt-3 text-base font-semibold text-slate-900">{product.title}</h3>
              )}
              {product.source && (
                <span
                  className={`ml-2 rounded-full px-2 py-1 text-xs font-medium ${
                    product.source === "web"
                      ? "bg-sky-50 text-sky-600"
                      : "bg-emerald-50 text-emerald-600"
                  }`}
                >
                  {product.source.charAt(0).toUpperCase() + product.source.slice(1)}
                </span>
              )}
            </div>

            {product.image && (
              <div className="mt-3 aspect-[4/3] w-full overflow-hidden rounded-lg bg-slate-100">
                <img
                  src={product.image}
                  alt={product.title}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
            )}

            <p className="mt-1 text-sm text-slate-600">{formatPrice(product.price_cents, product.currency)}</p>
            {categoryLabel && (
              <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {categoryLabel}
              </p>
            )}
            {product.badges.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {product.badges.map(badge => (
                  <span key={badge} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                    {badge}
                  </span>
                ))}
              </div>
            )}
            {product.description && (
              <p className="mt-3 text-sm text-slate-600">{product.description}</p>
            )}
            {product.rationale && product.rationale !== product.description && (
              <p className="mt-2 text-sm text-slate-500">{product.rationale}</p>
            )}
            <button
              onClick={() => addToCart(product)}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition hover:brightness-110"
            >
              Add to Cart
              {state.items.find(item => item.id === product.id) && (
                <span className="ml-2">({state.items.find(item => item.id === product.id)?.quantity})</span>
              )}
            </button>
          </article>
        );
      })}
    </div>
  );
}