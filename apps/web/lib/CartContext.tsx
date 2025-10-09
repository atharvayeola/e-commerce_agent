"use client";

import { createContext, useContext, useReducer, ReactNode } from "react";
import { ProductCard } from "./types";

type CartItem = ProductCard & {
  quantity: number;
};

type CartState = {
  items: CartItem[];
  total: number;
};

type CartAction =
  | { type: "ADD_TO_CART"; product: ProductCard }
  | { type: "REMOVE_FROM_CART"; productId: string }
  | { type: "UPDATE_QUANTITY"; productId: string; quantity: number }
  | { type: "CLEAR_CART" };

function cartReducer(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case "ADD_TO_CART": {
      const existingItem = state.items.find(item => item.id === action.product.id);
      if (existingItem) {
        const updatedItems = state.items.map(item =>
          item.id === action.product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
        return {
          items: updatedItems,
          total: updatedItems.reduce((sum, item) => sum + (item.price_cents * item.quantity), 0)
        };
      }
      const newItem = { ...action.product, quantity: 1 };
      return {
        items: [...state.items, newItem],
        total: state.items.reduce((sum, item) => sum + (item.price_cents * item.quantity), 0) + action.product.price_cents
      };
    }
    case "REMOVE_FROM_CART": {
      const updatedItems = state.items.filter(item => item.id !== action.productId);
      return {
        items: updatedItems,
        total: updatedItems.reduce((sum, item) => sum + (item.price_cents * item.quantity), 0)
      };
    }
    case "UPDATE_QUANTITY": {
      const updatedItems = state.items.map(item =>
        item.id === action.productId
          ? { ...item, quantity: action.quantity }
          : item
      );
      return {
        items: updatedItems,
        total: updatedItems.reduce((sum, item) => sum + (item.price_cents * item.quantity), 0)
      };
    }
    case "CLEAR_CART":
      return { items: [], total: 0 };
    default:
      return state;
  }
}

const CartContext = createContext<{
  state: CartState;
  addToCart: (product: ProductCard) => void;
  removeFromCart: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearCart: () => void;
} | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(cartReducer, { items: [], total: 0 });

  const addToCart = (product: ProductCard) =>
    dispatch({ type: "ADD_TO_CART", product });

  const removeFromCart = (productId: string) =>
    dispatch({ type: "REMOVE_FROM_CART", productId });

  const updateQuantity = (productId: string, quantity: number) =>
    dispatch({ type: "UPDATE_QUANTITY", productId, quantity });

  const clearCart = () => dispatch({ type: "CLEAR_CART" });

  return (
    <CartContext.Provider value={{ state, addToCart, removeFromCart, updateQuantity, clearCart }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return context;
}