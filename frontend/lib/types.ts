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
  brand_source: "history" | "mentioned" | "recommended";
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
