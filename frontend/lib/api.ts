// Typed client for the FastAPI backend.
// All dashboard pages call the backend through these functions.

import type {
  CallRecord,
  CapturedOrder,
  ComplianceResult,
  Customer,
  HistoryItem,
  PlaceCallResult,
  Product,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- products ---
export async function listProducts(
  category?: string,
): Promise<{ count: number; products: Product[] }> {
  const params = new URLSearchParams({ limit: '200' });
  if (category) params.set('category', category);
  const q = `?${params.toString()}`;
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
    : '';
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

// --- calls (Phase 5) ---

// Thrown when the compliance gate refuses a call (HTTP 409). Carries the
// gate's decision so the UI can explain exactly why.
export class CallBlockedError extends Error {
  compliance: ComplianceResult;
  constructor(compliance: ComplianceResult) {
    super(compliance.message || 'Call blocked by compliance gate.');
    this.name = 'CallBlockedError';
    this.compliance = compliance;
  }
}

// Place an outbound call. Resolves with the placed-call result, or throws
// CallBlockedError (compliance) / Error (any other failure).
export async function placeCall(customerId: string): Promise<PlaceCallResult> {
  const res = await fetch(`${API_BASE}/calls`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer_id: customerId }),
  });

  if (res.status === 409) {
    // FastAPI nests our payload under `detail`.
    const body = await res.json().catch(() => null);
    const compliance = body?.detail?.compliance as ComplianceResult | undefined;
    if (compliance) throw new CallBlockedError(compliance);
    throw new Error('Call blocked by compliance gate.');
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail =
      typeof body?.detail === 'string' ? body.detail : `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return res.json() as Promise<PlaceCallResult>;
}

export async function listCalls(): Promise<{
  count: number;
  calls: CallRecord[];
}> {
  return get(`/calls`);
}

export async function getCall(vapiCallId: string): Promise<CallRecord> {
  return get(`/calls/${vapiCallId}`);
}

export function getCallTranscriptStreamUrl(vapiCallId: string): string {
  return `${API_BASE}/calls/${encodeURIComponent(vapiCallId)}/stream`;
}

export { API_BASE };
