// Types mirroring the FastAPI backend's data shapes.

export interface Product {
  _id: string;
  name: string;
  brand: string;
  category: string;
  subcategory: string;
  aliases: string[];
  size: string;
  unit: string;
  price: number;
  in_stock: boolean;
  popularity_score: number;
}

export interface Customer {
  _id: string;
  name: string;
  phone: string;
  do_not_call: boolean;
  preferred_language: string;
}

export interface OrderItem {
  product_id: string;
  name: string;
  quantity: number;
  brand_source: 'history' | 'mentioned' | 'recommended';
}

export interface CapturedOrder {
  _id: string;
  customer_id: string;
  customer_name: string;
  call_id: string;
  created_at: string | null;
  status: string;
  items: OrderItem[];
  item_count: number;
  transcript_url: string | null;
}

export interface HistoryItem {
  product_id: string;
  name: string;
  category: string;
  subcategory: string;
  quantity: number;
  ordered_at: string;
}

// --- Phase 5: outbound calls ---

// The compliance gate's decision, mirrored from the backend.
export interface ComplianceResult {
  allowed: boolean;
  reason: string | null; // "do_not_call" | "outside_calling_hours" | "no_consent"
  message: string;
  checked_at: string;
  timezone: string;
}

// Result of POST /calls when a call is successfully placed.
export interface PlaceCallResult {
  ok: true;
  call_id: string;
  status: string;
  dry_run: boolean;
  compliance: ComplianceResult;
  call_record_id: string;
}

export interface TranscriptLine {
  role: 'assistant' | 'customer';
  text: string;
  ts: number;
}

// A persisted call record (audit trail).
export interface CallRecord {
  _id: string;
  customer_id: string;
  customer_name: string;
  phone: string;
  created_at: string | null;
  status: string;
  vapi_call_id: string | null;
  dry_run: boolean;
  compliance: ComplianceResult;
  transcript?: TranscriptLine[];
  transcript_count?: number;
  transcript_fetch_error?: string;
  recording_url?: string;
}
