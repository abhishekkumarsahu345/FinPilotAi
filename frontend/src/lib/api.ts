/**
 * API client — handles CSRF, org header, and error normalization.
 * All financial amounts from the API are integer Minor_Units (paise).
 */

export type Org = { id: string; name: string; role: string; currency: string }
export type User = { id: number; email: string; full_name: string; organizations: Org[] }
export type Customer = {
  id: string; name: string; contact_name: string; email: string; phone: string
  billing_address: string; gstin: string; payment_terms_days: number
  active: boolean; opt_out: boolean; created_at: string
}
export type InvoiceItem = {
  id: string; description: string; quantity: number
  unit_price_minor: number; discount_minor: number; line_total_minor: number
}
export type Invoice = {
  id: string; customer: string; customer_name: string
  invoice_number: string; invoice_date: string; due_date: string
  currency: string; subtotal_minor: number; discount_minor: number
  tax_minor: number; total_minor: number; status: string
  paid_minor: number; balance_minor: number; display_status: string
  items: InvoiceItem[]; created_at: string
}
export type Payment = {
  id: string; customer: string; payment_date: string; amount_minor: number
  currency: string; method: string; reference: string; notes: string
  allocations: { id: string; invoice: string; invoice_number: string; amount_minor: number }[]
  unallocated_minor: number; created_at: string
}
export type AuditLog = {
  id: number; action: string; entity_type: string; entity_id: string
  summary: string; actor_name: string; created_at: string
}
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
export type ForecastData = {
  as_of: string; period_days: number; currency: string
  insufficient_history: boolean
  assumptions: Record<string, unknown>
  scenarios: Record<string, { total_minor: number; lines: unknown[] }>
}

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

async function request<T>(
  method: string, path: string, body?: unknown, orgId?: string
): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: headers(orgId),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    throw new Error(err.detail || JSON.stringify(err))
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
  voidInvoice: (orgId: string, id: string) =>
    request<Invoice>('POST', `/api/v1/invoices/${id}/void/`, {}, orgId),

  // Payments
  payments: (orgId: string) =>
    request<{ results: Payment[]; count: number }>('GET', '/api/v1/payments/?page_size=200', undefined, orgId),
  createPayment: (orgId: string, data: Record<string, unknown>) =>
    request<Payment>('POST', '/api/v1/payments/', data, orgId),

  // Forecast
  forecast: (orgId: string, period: 7 | 30 | 60, timing = 'due_date') =>
    request<ForecastData>('GET', `/api/v1/forecasts/?period=${period}&timing=${timing}`, undefined, orgId),

  // AI Assistant
  ask: (orgId: string, question: string, session_id?: string) =>
    request<{ answer: string; basis: Record<string, unknown> }>(
      'POST', '/api/v1/assistant/', { question, session_id }, orgId
    ),

  // Audit logs
  auditLogs: (orgId: string) =>
    request<AuditLog[]>('GET', '/api/v1/audit-logs/', undefined, orgId),

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
