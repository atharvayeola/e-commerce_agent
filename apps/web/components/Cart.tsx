"use client";

import { useCart } from "../lib/CartContext";

function formatPrice(priceCents: number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency
  }).format(priceCents / 100);
}

export default function Cart({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { state, removeFromCart, updateQuantity } = useCart();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="absolute inset-y-0 right-0 w-full max-w-md">
        <div className="flex h-full flex-col bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <h2 className="text-lg font-medium text-slate-900">Shopping Cart</h2>
            <button
              onClick={onClose}
              className="rounded-md p-2 text-slate-400 hover:text-slate-500"
            >
              <span className="sr-only">Close cart</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {state.items.length === 0 ? (
              <p className="text-center text-slate-500">Your cart is empty</p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {state.items.map(item => (
                  <li key={item.id} className="py-4">
                    <div className="flex items-center space-x-4">
                      {item.image && (
                        <img
                          src={item.image}
                          alt={item.title}
                          className="h-16 w-16 rounded-md object-cover"
                        />
                      )}
                      <div className="flex-1">
                        <h3 className="text-sm font-medium text-slate-900">{item.title}</h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {formatPrice(item.price_cents, item.currency)}
                        </p>
                        <div className="mt-2 flex items-center">
                          <label htmlFor={`quantity-${item.id}`} className="sr-only">
                            Quantity
                          </label>
                          <select
                            id={`quantity-${item.id}`}
                            value={item.quantity}
                            onChange={e => updateQuantity(item.id, Number(e.target.value))}
                            className="rounded-md border border-slate-300 py-1 pl-3 pr-8 text-sm"
                          >
                            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                              <option key={n} value={n}>
                                {n}
                              </option>
                            ))}
                          </select>
                          <button
                            onClick={() => removeFromCart(item.id)}
                            className="ml-4 text-sm font-medium text-primary hover:text-primary/80"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {state.items.length > 0 && (
            <div className="border-t border-slate-200 p-4">
              <div className="flex justify-between text-base font-medium text-slate-900">
                <p>Subtotal</p>
                <p>{formatPrice(state.total, "USD")}</p>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Shipping and taxes calculated at checkout.
              </p>
              <button className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition hover:brightness-110">
                Checkout
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}