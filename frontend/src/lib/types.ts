export type Business = {
  id: number;
  name: string;
  gstin: string;
  pan: string;
  email: string;
  created_at: string;
};

export type InvoiceBatch = {
  id: number;
  source: "books" | "2a";
  original_filename: string;
  period: string;
  status: "processing" | "done" | "failed";
  error_message: string;
  row_count: number;
  uploaded_at: string;
};

export type UploadResponse = {
  batch_id: number;
  status: string;
  upload_token: string;
};

export type NeedsPasswordResponse = {
  needs_password: true;
  upload_token: string;
  filename: string;
};

export type ReconciliationRun = {
  id: number;
  period: string;
  status: "processing" | "done" | "failed";
  error_message: string;
  total_books_invoices: number;
  total_statement_invoices: number;
  matched_count: number;
  flagged_count: number;
  itc_at_risk_value: string;
  created_at: string;
  completed_at: string | null;
};

export type Invoice = {
  id: number;
  source: "books" | "2a";
  supplier_gstin: string;
  supplier_name: string;
  invoice_number: string;
  invoice_date: string | null;
  taxable_value: string;
  tax_amount: string;
  invoice_value: string;
};

export type DiscrepancyType =
  | "matched"
  | "missing_in_2a"
  | "missing_in_books"
  | "value_mismatch"
  | "duplicate"
  | "gstin_mismatch"
  | "date_mismatch";

export type Discrepancy = {
  id: number;
  discrepancy_type: DiscrepancyType;
  books_invoice: Invoice | null;
  statement_invoice: Invoice | null;
  detail: string;
  ai_explanation: string;
  value_at_risk: string;
  resolved: boolean;
  created_at: string;
};

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type Dashboard = {
  latest_run: ReconciliationRun | null;
  total_runs: number;
  total_purchase_invoices: number;
  total_statement_invoices: number;
  total_matched: number;
  total_flagged: number;
  total_itc_at_risk: number;
  discrepancies_by_type: Record<string, number>;
};

export const DISCREPANCY_LABELS: Record<DiscrepancyType, string> = {
  matched: "Matched",
  missing_in_2a: "Missing in GSTR-2A/2B",
  missing_in_books: "Missing in Purchase Register",
  value_mismatch: "Value Mismatch",
  duplicate: "Duplicate",
  gstin_mismatch: "GSTIN Mismatch",
  date_mismatch: "Date Mismatch",
};
