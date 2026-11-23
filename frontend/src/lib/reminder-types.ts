/**
 * Type definitions and API calls for the Reminder (Dunning) module.
 * Import these alongside the main api.ts types.
 */

export type ReminderTemplate = {
  id: string
  name: string
  channel: string
  subject: string
  body: string
  active: boolean
  pending_revision: boolean
  created_at: string
  updated_at: string
}

export type ReminderPolicy = {
  id: string
  name: string
  applicable_statuses: string[]
  trigger_offset_days: number
  channel: string
  template: string
  template_name: string
  send_hour: number
  send_minute: number
  quiet_hours_start: number | null
  quiet_hours_end: number | null
  max_attempts: number
  min_days_between_reminders: number
  approval_mode: string
  excluded_customer_ids: string[]
  enabled: boolean
  created_at: string
}

export type ReminderJob = {
  id: string
  policy: string
  policy_name: string
  invoice: string
  invoice_number: string
  customer: string
  customer_name: string
  customer_email: string
  scheduled_date: string
  status: string
  balance_at_scheduling_minor: number
  balance_minor: number | null
  rendered_preview: { subject: string; body_preview: string } | null
  approved_by: number | null
  approved_at: string | null
  rejected_at: string | null
  dispatched_at: string | null
  block_reason: string
  retry_count: number
  created_at: string
}

export type MessageLog = {
  id: string
  reminder_job: string | null
  invoice: string | null
  invoice_number: string
  customer: string | null
  customer_name: string
  channel: string
  provider: string
  provider_message_id: string
  recipient: string
  subject: string
  body_preview: string
  status: string
  error_code: string
  error_detail: string
  retry_count: number
  queued_at: string
  sent_at: string | null
  delivered_at: string | null
}

export type ReminderStats = {
  pending_approval: number
  sent_last_30_days: number
  failed_last_30_days: number
  total_dispatched: number
  upcoming_scheduled: number
  plan_limits: {
    allowed: boolean
    remaining: number
    limit: number
    used?: number
    error?: string
  }
}

export type DefaultTemplate = {
  tone: string
  channel: string
  subject: string
  body: string
}

// Helper to make API calls with org context
// Reuse the request function from api.ts by importing it
import { ApiError } from './api'

function getCookie(name: string): string {
  return document.cookie.split('; ').find(x => x.startsWith(name + '='))?.split('=').slice(1).join('=') ?? ''
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
  method: string,
  path: string,
  body?: unknown,
  orgId?: string
): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: headers(orgId),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Network error' }))
    let message = err.error || err.detail || ''
    if (!message && err.non_field_errors) {
      message = Array.isArray(err.non_field_errors) ? err.non_field_errors.join(' ') : String(err.non_field_errors)
    }
    if (!message) {
      const skip = new Set(['error', 'detail', 'error_type', 'request_id', 'non_field_errors'])
      const msgs = Object.entries(err)
        .filter(([k]) => !skip.has(k))
        .map(([, v]) => (Array.isArray(v) ? v.join(' ') : String(v)))
      if (msgs.length) message = msgs.join(' ')
    }
    if (!message) message = 'An unexpected error occurred.'
    throw new ApiError(message, err.error_type || 'api_error', res.status, err.request_id)
  }
  return res.json()
}

// Reminder API endpoints
export const reminderApi = {
  // Templates
  templates: (orgId: string) =>
    request<{ results: ReminderTemplate[]; count: number }>(
      'GET',
      '/api/v1/reminders/templates/?page_size=200',
      undefined,
      orgId
    ),
  createTemplate: (orgId: string, data: Partial<ReminderTemplate>) =>
    request<ReminderTemplate>('POST', '/api/v1/reminders/templates/', data, orgId),
  updateTemplate: (orgId: string, id: string, data: Partial<ReminderTemplate>) =>
    request<ReminderTemplate>('PATCH', `/api/v1/reminders/templates/${id}/`, data, orgId),
  
  // Policies
  policies: (orgId: string) =>
    request<{ results: ReminderPolicy[]; count: number }>(
      'GET',
      '/api/v1/reminders/policies/?page_size=200',
      undefined,
      orgId
    ),
  createPolicy: (orgId: string, data: Partial<ReminderPolicy>) =>
    request<ReminderPolicy>('POST', '/api/v1/reminders/policies/', data, orgId),
  updatePolicy: (orgId: string, id: string, data: Partial<ReminderPolicy>) =>
    request<ReminderPolicy>('PATCH', `/api/v1/reminders/policies/${id}/`, data, orgId),
  activateAutoMode: (orgId: string, id: string) =>
    request<{ detail: string }>('POST', `/api/v1/reminders/policies/${id}/activate-auto/`, { confirm: true }, orgId),
  deactivateAutoMode: (orgId: string, id: string) =>
    request<{ detail: string }>('POST', `/api/v1/reminders/policies/${id}/deactivate-auto/`, {}, orgId),
  
  // Jobs (approval queue)
  jobs: (orgId: string, status?: string) =>
    request<{ results: ReminderJob[]; count: number }>(
      'GET',
      `/api/v1/reminders/jobs/?page_size=200${status ? `&status=${status}` : ''}`,
      undefined,
      orgId
    ),
  approveJob: (orgId: string, id: string) =>
    request<{ detail: string }>('POST', `/api/v1/reminders/jobs/${id}/approve/`, {}, orgId),
  rejectJob: (orgId: string, id: string) =>
    request<{ detail: string }>('POST', `/api/v1/reminders/jobs/${id}/reject/`, {}, orgId),
  bulkApprove: (orgId: string, jobIds: string[]) =>
    request<{ detail: string }>('POST', '/api/v1/reminders/jobs/bulk_approve/', { job_ids: jobIds }, orgId),
  
  // Message history
  messages: (orgId: string) =>
    request<{ results: MessageLog[]; count: number }>(
      'GET',
      '/api/v1/reminders/messages/?page_size=200',
      undefined,
      orgId
    ),
  
  // Stats
  stats: (orgId: string) =>
    request<ReminderStats>('GET', '/api/v1/reminders/stats/', undefined, orgId),
  
  // Invoice history
  invoiceHistory: (orgId: string, invoiceId: string) =>
    request<{ invoice_number: string; jobs: ReminderJob[]; messages: MessageLog[] }>(
      'GET',
      `/api/v1/reminders/invoice/${invoiceId}/history/`,
      undefined,
      orgId
    ),
  
  // Default templates
  defaultTemplates: (orgId: string) =>
    request<DefaultTemplate[]>('GET', '/api/v1/reminders/default-templates/', undefined, orgId),
}
