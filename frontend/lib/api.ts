// Typed client for the FastAPI backend.
// All dashboard pages call the backend through these functions.

import type {
  CapturedOrder,
  Customer,
  HistoryItem,
  Product,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- products ---
export async function listProducts(
  category?: string,
): Promise<{ count: number; products: Product[] }> {
  const q = category ? `?category=${encodeURIComponent(category)}` : "";
  return get(`/products${q}`);
}

export async function listCategories(): Promise<{ categories: string[] }> {
  return get(`/products/categories`);
}

// --- customers ---
export async function listCustomers(): Promise<{
  count: number;
  customers: Customer[];
}> {
  return get(`/customers`);
}

export async function getCustomerHistory(
  customerId: string,
  subcategory?: string,
): Promise<{ customer_id: string; count: number; items: HistoryItem[] }> {
  const q = subcategory
    ? `?subcategory=${encodeURIComponent(subcategory)}`
    : "";
  return get(`/customers/${customerId}/history${q}`);
}

// --- orders ---
export async function listOrders(): Promise<{
  count: number;
  orders: CapturedOrder[];
}> {
  return get(`/orders`);
}

export async function getOrder(orderId: string): Promise<CapturedOrder> {
  return get(`/orders/${orderId}`);
}

export { API_BASE };
