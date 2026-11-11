/**
 * API client — handles CSRF, org header, and error normalization.
 * All financial amounts from the API are integer Minor_Units (paise).
 */

export type Org = { id: string; name: string; role: string; currency: string }
export type User = { id: number; email: string; full_name: string; organizations: Org[] }
export type OrganizationDetail = Org & {
  state: string; legal_name: string; trading_name: string
  business_email: string; contact_phone: string; billing_address: string
}
export type Customer = {
  id: string; name: string; contact_name: string; email: string; phone: string
  billing_address: string; gstin: string; state: string; payment_terms_days: number
  active: boolean; opt_out: boolean; created_at: string
}
export type GSTRate = {
  id: string; name: string; rate_bps: number; active: boolean
  rate_percent: string; cgst_percent: string; sgst_percent: string; igst_percent: string
  preview: string; in_use: boolean; created_at: string
}
export type Product = {
  id: string; name: string; description: string; unit: string; sku: string
  hsn_sac: string; price_minor: number; default_gst_rate: string | null
  default_gst_rate_bps: number; default_gst_rate_name: string
  default_gst_rate_preview: string; active: boolean; created_at: string
}
export type InvoiceItem = {
  id: string; product: string | null; description: string; quantity: number
  unit_price_minor: number; discount_minor: number; line_total_minor: number
  sort_order: number
  gst_rate_bps: number; gst_rate_name: string; hsn_sac: string
  gst_tax_minor: number; gst_cgst_minor: number; gst_sgst_minor: number; gst_igst_minor: number
}
export type GstSummary = {
  has_gst: boolean; place_of_supply: string; warning: string
  rates: {
    rate_bps: number; rate_label: string; taxable_minor: number
    cgst_minor: number; sgst_minor: number; igst_minor: number
    tax_minor: number; line_count: number
  }[]
  totals: {
    taxable_minor: number; cgst_minor: number; sgst_minor: number
    igst_minor: number; tax_minor: number; grand_total_minor: number
  }
}
export type Invoice = {
  id: string; customer: string; customer_name: string
  invoice_number: string; invoice_date: string; due_date: string
  currency: string; subtotal_minor: number; discount_minor: number
  tax_minor: number; total_minor: number; status: string
  paid_minor: number; balance_minor: number; display_status: string
  items: InvoiceItem[]; gst_summary: GstSummary; gst_warning: string
  created_at: string
}
export type Payment = {
  id: string; customer: string; payment_date: string; amount_minor: number
  currency: string; method: string; reference: string; notes: string
  allocations: { id: string; invoice: string; invoice_number: string; amount_minor: number }[]
  unallocated_minor: number; created_at: string
}
// AUDIT LOG DISABLED — uncomment to re-enable
// export type AuditLog = {
//   id: number; action: string; entity_type: string; entity_id: string
//   summary: string; actor_name: string; created_at: string
// }
export type Notification = {
  id: string; event_type: string; entity_type: string; entity_id: string
  payload: Record<string, unknown>; read: boolean; created_at: string
}
export type DashboardData = {
  currency: string; as_of: string; outstanding_minor: number
  overdue_minor: number; due_today_minor: number; due_next_7_days_minor: number
  collected_this_month_minor: number; overdue_invoice_count: number
  customer_count: number
  top_overdue_customers: { customer_id: string; name: string; overdue_minor: number; invoice_count: number }[]
  recent_payments: { id: string; customer_name: string; payment_date: string; amount_minor: number; method: string }[]
}
export type AgingData = {
  as_of: string; currency: string; grand_total_minor: number
  bucket_totals: Record<string, number>
  buckets: Record<string, {
    id: string; invoice_number: string; customer: string
    due_date: string; days_overdue: number; balance_minor: number
  }[]>
}
// FORECAST DISABLED — uncomment to re-enable
// export type ForecastData = {
//   as_of: string; period_days: number; currency: string
//   insufficient_history: boolean
//   assumptions: Record<string, unknown>
//   scenarios: Record<string, { total_minor: number; lines: unknown[] }>
// }

// ── Helpers ────────────────────────────────────────────────────────────────

export const money = (minor: number, currency = 'INR') =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(minor / 100)

export const fmtDate = (value: string) =>
  new Date(value + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

function getCookie(name: string): string {
  return document.cookie.split('; ').find(x => x.startsWith(name + '='))?.split('=').slice(1).join('=') ?? ''
}

async function ensureCsrf() {
  await fetch('/api/v1/auth/csrf/', { credentials: 'include' })
}

function headers(orgId?: string): Record<string, string> {
  const h: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-CSRFToken': decodeURIComponent(getCookie('csrftoken')),
  }
  if (orgId) h['X-Organization-ID'] = orgId
  return h
}

// ── 401 global handler ──────────────────────────────────────────────────────
// App.tsx registers a callback here so that any 401 anywhere auto-clears auth.
type OnUnauthenticated = () => void
let _onUnauthenticated: OnUnauthenticated | null = null
export function setUnauthenticatedHandler(fn: OnUnauthenticated) {
  _onUnauthenticated = fn
}

// ── Cross-tab logout via BroadcastChannel ───────────────────────────────────
// Emits 'logout' so other open tabs can clear their state.
const LOGOUT_CHANNEL = 'finpilot_auth'
export function broadcastLogout() {
  try {
    const ch = new BroadcastChannel(LOGOUT_CHANNEL)
    ch.postMessage({ type: 'logout' })
    ch.close()
  } catch {
    // BroadcastChannel not available (e.g. Firefox private mode) — fall back to localStorage
    try { localStorage.setItem('finpilot_logout', String(Date.now())) } catch { /* ignore */ }
  }
}
export function subscribeLogoutChannel(handler: () => void): () => void {
  let bc: BroadcastChannel | null = null
  let storageHandler: ((e: StorageEvent) => void) | null = null
  try {
    bc = new BroadcastChannel(LOGOUT_CHANNEL)
    bc.onmessage = (e) => { if (e.data?.type === 'logout') handler() }
  } catch {
    storageHandler = (e: StorageEvent) => {
      if (e.key === 'finpilot_logout') handler()
    }
    window.addEventListener('storage', storageHandler)
  }
  return () => {
    bc?.close()
    if (storageHandler) window.removeEventListener('storage', storageHandler)
  }
}

// Structured API error — preserves error_type and request_id from backend
export class ApiError extends Error {
  error_type: string
  request_id?: string
  status: number
  constructor(message: string, error_type: string, status: number, request_id?: string) {
    super(message)
    this.name = 'ApiError'
    this.error_type = error_type
    this.request_id = request_id
    this.status = status
  }
}

async function request<T>(  // <T> = empty box = placeholder for the response type (we don't know yet)
                            // Sending data to Django takes time, so we must wait for its response.
  method: string, path: string, body?: unknown, orgId?: string
): Promise<T> {                    //This means the function will return a Promise containing the response data of type T.👇
  const res = await fetch(path, {   //In simple words: this function sends a request and eventually gives us the backend response.
    method,
    credentials: 'include',  //include — relevant cookies are included.
    headers: headers(orgId),
    body: body !== undefined ? JSON.stringify(body) : undefined,   //Because JavaScript objects need to be converted into JSON text before being sent in a normal HTTP request body.
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    // Prefer structured backend error shape {error, error_type, request_id}
    // Fall back to DRF {detail} shape, then DRF validation errors, then raw JSON
    let message = err.error || err.detail || ''
    // DRF serializer validation: {"non_field_errors": ["msg"]}
    if (!message && err.non_field_errors) {
      message = Array.isArray(err.non_field_errors) ? err.non_field_errors.join(' ') : String(err.non_field_errors)
    }
    // DRF field-level validation: {"field_name": ["msg"], ...}
    if (!message) {
      const skip = new Set(['error', 'detail', 'error_type', 'request_id', 'non_field_errors'])
      const msgs = Object.entries(err)
        .filter(([k]) => !skip.has(k))
        .map(([, v]) => Array.isArray(v) ? v.join(' ') : String(v))
      if (msgs.length) message = msgs.join(' ')
    }
    if (!message) message = 'An unexpected error occurred.'
    const error_type = err.error_type || 'unknown_error'
    const request_id = err.request_id
    const apiErr = new ApiError(message, error_type, res.status, request_id)
    // Auto-clear auth on any 401
    if (res.status === 401) {
      _onUnauthenticated?.()
    }
    throw apiErr
  }
  const text = await res.text()
  return text ? JSON.parse(text) : ({} as T)
}

// ── Auth ───────────────────────────────────────────────────────────────────

export const api = {
  csrf: () => ensureCsrf(),
  login: (email: string, password: string) =>
    request<{ detail: string }>('POST', '/api/v1/auth/login/', { username: email, password }),
  register: (full_name: string, email: string, password: string, organization_name: string) =>
    request<{ detail: string }>('POST', '/api/v1/auth/register/', { full_name, email, password, organization_name }),
  logout: (orgId?: string) => request<void>('POST', '/api/v1/auth/logout/', undefined, orgId),
  me: () => request<User>('GET', '/api/v1/auth/me/'),

  // Org
  createOrg: (name: string) =>
    request<{ id: string; name: string }>('POST', '/api/v1/organizations/', { name, default_currency: 'INR', country: 'IN', timezone: 'Asia/Kolkata' }),

  // Dashboard
  dashboard: (orgId: string) => request<DashboardData>('GET', `/api/v1/dashboard/`, undefined, orgId),
  aging: (orgId: string, asOf?: string) =>
    request<AgingData>('GET', `/api/v1/reports/aging/${asOf ? '?as_of=' + asOf : ''}`, undefined, orgId),

  // Customers
  customers: (orgId: string) =>
    request<{ results: Customer[]; count: number }>('GET', '/api/v1/customers/?page_size=200', undefined, orgId),
  createCustomer: (orgId: string, data: Partial<Customer>) =>
    request<Customer>('POST', '/api/v1/customers/', data, orgId),
  updateCustomer: (orgId: string, id: string, data: Partial<Customer>) =>
    request<Customer>('PATCH', `/api/v1/customers/${id}/`, data, orgId),
  customerOptOut: (orgId: string, id: string) =>
    request<void>('POST', `/api/v1/customers/${id}/opt-out/`, {}, orgId),

  // Invoices
  invoices: (orgId: string) =>
    request<{ results: Invoice[]; count: number }>('GET', '/api/v1/invoices/?page_size=200', undefined, orgId),
  createInvoice: (orgId: string, data: Record<string, unknown>) =>
    request<Invoice>('POST', '/api/v1/invoices/', data, orgId),
  updateInvoice: (orgId: string, id: string, data: Record<string, unknown>) =>
    request<Invoice>('PUT', `/api/v1/invoices/${id}/`, data, orgId),
  voidInvoice: (orgId: string, id: string) =>
    request<Invoice>('POST', `/api/v1/invoices/${id}/void/`, {}, orgId),

  // Payments
  payments: (orgId: string) =>
    request<{ results: Payment[]; count: number }>('GET', '/api/v1/payments/?page_size=200', undefined, orgId),
  createPayment: (orgId: string, data: Record<string, unknown>) =>
    request<Payment>('POST', '/api/v1/payments/', data, orgId),

  // Organization detail (incl. state for GST place-of-supply)
  organization: (orgId: string) =>
    request<OrganizationDetail>('GET', `/api/v1/organizations/${orgId}/`, undefined, orgId),

  // GST rates
  gstRates: (orgId: string) =>
    request<{ results: GSTRate[]; count: number }>('GET', '/api/v1/gst-rates/?page_size=200', undefined, orgId),
  createGstRate: (orgId: string, data: Partial<GSTRate>) =>
    request<GSTRate>('POST', '/api/v1/gst-rates/', data, orgId),
  updateGstRate: (orgId: string, id: string, data: Partial<GSTRate>) =>
    request<GSTRate>('PATCH', `/api/v1/gst-rates/${id}/`, data, orgId),
  deactivateGstRate: (orgId: string, id: string) =>
    request<GSTRate>('POST', `/api/v1/gst-rates/${id}/deactivate/`, {}, orgId),
  activateGstRate: (orgId: string, id: string) =>
    request<GSTRate>('POST', `/api/v1/gst-rates/${id}/activate/`, {}, orgId),

  // Products
  products: (orgId: string, search?: string) =>
    request<{ results: Product[]; count: number }>('GET', `/api/v1/products/?page_size=200${search ? `&search=${encodeURIComponent(search)}` : ''}`, undefined, orgId),
  createProduct: (orgId: string, data: Partial<Product>) =>
    request<Product>('POST', '/api/v1/products/', data, orgId),
  updateProduct: (orgId: string, id: string, data: Partial<Product>) =>
    request<Product>('PATCH', `/api/v1/products/${id}/`, data, orgId),
  deactivateProduct: (orgId: string, id: string) =>
    request<Product>('POST', `/api/v1/products/${id}/deactivate/`, {}, orgId),
  activateProduct: (orgId: string, id: string) =>
    request<Product>('POST', `/api/v1/products/${id}/activate/`, {}, orgId),

  // FORECAST DISABLED — uncomment to re-enable
  // forecast: (orgId: string, period: 7 | 30 | 60, timing = 'due_date') =>
  //   request<ForecastData>('GET', `/api/v1/forecasts/?period=${period}&timing=${timing}`, undefined, orgId),

  // AI Assistant 
  ask: (orgId: string, question: string, session_id?: string) =>  // The part inside < > is TypeScript's generic type.
  //                                                            //It tells TypeScript what kind of response we expect:
  request<{ answer: string; basis: Record<string, unknown> }>(
      'POST', '/api/v1/assistant/', { question, session_id }, orgId
    ),

  // AUDIT LOG DISABLED — uncomment to re-enable
  // auditLogs: (orgId: string) =>
  //   request<AuditLog[]>('GET', '/api/v1/audit-logs/', undefined, orgId),

  // Notifications
  notifications: (orgId: string) =>
    request<{ unread_count: number; notifications: Notification[] }>('GET', '/api/v1/notifications/', undefined, orgId),
  markAllRead: (orgId: string) =>
    request<void>('POST', '/api/v1/notifications/mark-all-read/', {}, orgId),

  // Exports
  exportInvoices: (orgId: string) =>
    `/api/v1/exports/invoices/?org=${orgId}`,  // Direct navigation
  exportCustomers: (orgId: string) =>
    `/api/v1/exports/customers/?org=${orgId}`,
  exportPayments: (orgId: string) =>
    `/api/v1/exports/payments/?org=${orgId}`,
}
