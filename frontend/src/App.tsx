// FinPilot AI - Invoice Module Improved
import { useEffect, useState, useCallback, useRef } from 'react'
import {
  Activity, ArrowUpRight, Bell, ChevronDown, CircleHelp, Clock3,
  FileSpreadsheet, FileText, LayoutDashboard, LogOut, Plus, Search,
  Settings2, ShieldCheck, Users, Wallet, X, Bot, /*GitMerge,*/
  TrendingUp, Download, CheckCircle, AlertCircle, RefreshCw,
  Package, Pencil, Power, Percent, Tag,
} from 'lucide-react'
import {
  api, ApiError, money, fmtDate,
  setUnauthenticatedHandler, broadcastLogout, subscribeLogoutChannel,
  type User, type Org, type Invoice, type Customer,
  type Payment, type DashboardData, type AgingData, /*type ForecastData,*/ type Notification,
  type Product, type GSTRate, type OrganizationDetail,
} from './lib/api'

// ── Types ──────────────────────────────────────────────────────────────────

type Page = 'Overview' | 'Invoices' | 'Customers' | 'Payments' | 'Aging report' |
  'Reminders' | /*'Reconciliation' |*/ /*'Forecast' |*/ 'AI Assistant' |
  /*'Audit Log' |*/ 'Settings' | 'Notifications' | 'Products'

// ── GST preview helper (display-only; the server recalculates on save) ──────
// Mirrors the backend: round-half-up to the nearest paise.
function gstAmount(taxableMinor: number, rateBps: number): number {
  if (!rateBps || rateBps <= 0 || taxableMinor <= 0) return 0
  return Math.round((taxableMinor * rateBps) / 10000)
}

// ── Auth screen ────────────────────────────────────────────────────────────

function AuthScreen({ onAuth }: { onAuth: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    try {
      await api.csrf()
      if (mode === 'login') {
        await api.login(fd.get('email') as string, fd.get('password') as string)
      } else {
        await api.register(
          fd.get('name') as string, fd.get('email') as string,
          fd.get('password') as string, fd.get('org') as string
        )
      }
      const user = await api.me()
      onAuth(user)
    } catch (err: unknown) {
      setError((err as Error).message || 'Sign in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth">
      <div className="auth-brand">
        <div className="brand-icon"><Activity size={22} /></div>
        <span>FinPilot <b>AI</b></span>
      </div>
      <section className="auth-card">
        <div className="eyebrow">{mode === 'login' ? 'RECEIVABLES, UNDER CONTROL' : 'YOUR BUSINESS WORKSPACE'}</div>
        <h1>{mode === 'login' ? <>Cash flow clarity<br />starts here.</> : <>Start with a<br />clearer picture.</>}</h1>
        <p>{mode === 'login'
          ? 'Bring invoices, collections, and customer follow-ups into one calm workspace.'
          : 'Create your account and private organization in a few steps.'}</p>
        <form onSubmit={handle}>
          {mode === 'register' && <>
            <label>Your name<input name="name" placeholder="Full name" required /></label>
            <label>Business name<input name="org" placeholder="Your company" required /></label>
          </>}
          <label>Work email<input name="email" type="email" placeholder="you@company.com" required autoComplete="username" /></label>
          <label>Password<input name="password" type="password" placeholder={mode === 'login' ? 'Your password' : 'At least 8 characters'} required autoComplete={mode === 'login' ? 'current-password' : 'new-password'} /></label>
          {error && <div className="form-error">{error}</div>}
          <button className="primary full" disabled={busy}>
            {busy ? (mode === 'login' ? 'Signing in…' : 'Creating account…') : (mode === 'login' ? 'Sign in' : 'Create account')}
            <span>→</span>
          </button>
        </form>
        <button className="text-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'New to FinPilot? Create an account' : 'Already have an account? Sign in'}
        </button>
        <div className="secure-note"><ShieldCheck size={15} /> Secure, organization-scoped access</div>
      </section>
      <div className="auth-foot">Built for Indian businesses <span>·</span> INR native <span>·</span> Private by design</div>
    </main>
  )
}

// ── Create org screen ──────────────────────────────────────────────────────

function CreateOrgScreen({ user, onCreated, onLogout }: { user: User; onCreated: (org: Org) => void; onLogout: () => void }) {
  const [busy, setBusy] = useState(false)
  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setBusy(true)
    const fd = new FormData(e.currentTarget)
    try {
      const org = await api.createOrg(fd.get('name') as string)
      const me = await api.me()
      const found = me.organizations.find(o => o.id === org.id)
      if (found) onCreated(found)
    } catch (err) {
      alert((err as Error).message)
    } finally { setBusy(false) }
  }
  return (
    <main className="auth">
      <div className="auth-brand"><div className="brand-icon"><Activity size={22} /></div><span>FinPilot <b>AI</b></span></div>
      <section className="auth-card">
        <div className="eyebrow">GET STARTED</div>
        <h1>Create your<br />workspace.</h1>
        <p>Your organization's records stay isolated from every other business.</p>
        <form onSubmit={handle}>
          <label>Business name<input name="name" placeholder="e.g. Acme Industries" required /></label>
          <button className="primary full" disabled={busy}>{busy ? 'Creating…' : 'Create organization'}<span>→</span></button>
        </form>
        <button className="text-button" onClick={onLogout}>Sign out</button>
      </section>
    </main>
  )
}

// ── Metric card ────────────────────────────────────────────────────────────

function Metric({ icon, title, value, note, tone }: { icon: React.ReactNode; title: string; value: string | number; note: string; tone: string }) {
  return (
    <article className="metric">
      <div className="metric-top"><div className={`metric-icon ${tone}`}>{icon}</div></div>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </article>
  )
}

// ── Status badge ───────────────────────────────────────────────────────────

function StatusBadge({ s }: { s: string }) {
  const labels: Record<string, string> = {
    issued: 'Unpaid',
    partially_paid: 'Partially Paid',
    paid: 'Paid',
    overdue: 'Overdue',
    draft: 'Draft',
    void: 'Void',
  }
  return <span className={`status ${s}`}>{labels[s] ?? s.replace(/_/g, ' ')}</span>
}

// ── Invoice modal (line items + GST) ────────────────────────────────────────

type InvoiceLine = {
  product: string; description: string; quantity: string
  unit_price_minor: string; discount_minor: string
  gst_rate_bps: number; gst_rate_name: string; hsn_sac: string
}

// ── Invoice View Modal (Clean Modern Style - Green Theme) ─────────────────
function InvoiceViewModal({ invoice, customers, onClose, onEdit }: {
  invoice: Invoice; customers: Customer[]; onClose: () => void; onEdit: () => void
}) {
  const cust = customers.find(c => c.id === invoice.customer)
  const isIntra = invoice.gst_summary.place_of_supply === 'intra_state'
  
  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal invoice-view-modal-modern">
        {/* Header with Invoice Number */}
        <div className="invoice-modern-header">
          <div className="invoice-modern-header-left">
            <div className="invoice-modern-brand">FinPilot AI – Customer Invoice</div>
            <h1 className="invoice-modern-number">{invoice.invoice_number}</h1>
          </div>
          <div className="invoice-modern-header-right">
            <span className={`status ${invoice.display_status}`}>
              {invoice.display_status === 'issued' ? 'Posted' : 
               invoice.display_status === 'paid' ? 'Paid' :
               invoice.display_status === 'overdue' ? 'Overdue' :
               invoice.display_status === 'draft' ? 'Draft' : 'Issued'}
            </span>
            <button className="icon-btn" onClick={onClose}><X size={20} /></button>
          </div>
        </div>

        <div className="invoice-modern-body">
          {/* Top Info Grid */}
          <div className="invoice-modern-info-grid">
            <div className="invoice-modern-info-col">
              <div className="invoice-modern-label">CUSTOMER</div>
              <div className="invoice-modern-value-large">{cust?.name || '—'}</div>
              {cust?.billing_address && <div className="invoice-modern-address">{cust.billing_address}</div>}
            </div>
            
            <div className="invoice-modern-info-col">
              <div className="invoice-modern-label">INVOICE DATE</div>
              <div className="invoice-modern-value">{fmtDate(invoice.invoice_date)}</div>
              <div className="invoice-modern-meta">Due date: {fmtDate(invoice.due_date)}</div>
            </div>
          </div>

          {/* Invoice Lines Section */}
          <div className="invoice-modern-section">
            <h3 className="invoice-modern-section-title">Invoice Lines</h3>
            
            <table className="invoice-modern-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th style={{textAlign: 'right'}}>Qty</th>
                  <th style={{textAlign: 'right'}}>Price</th>
                  <th style={{textAlign: 'right'}}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {invoice.items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <div className="invoice-modern-product">{item.description}</div>
                      {item.hsn_sac && <div className="invoice-modern-product-meta">HSN/SAC: {item.hsn_sac}</div>}
                    </td>
                    <td style={{textAlign: 'right'}}>{item.quantity}</td>
                    <td style={{textAlign: 'right'}}>{money(item.unit_price_minor)}</td>
                    <td style={{textAlign: 'right'}} className="invoice-modern-amount">{money(item.line_total_minor + item.gst_tax_minor)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Totals Section */}
          <div className="invoice-modern-totals">
            <div className="invoice-modern-total-row">
              <span>Untaxed Amount</span>
              <span className="invoice-modern-total-value">{money(invoice.subtotal_minor)}</span>
            </div>
            {invoice.gst_summary.has_gst && (
              <div className="invoice-modern-total-row">
                <span>GST</span>
                <span className="invoice-modern-total-value">{money(invoice.tax_minor)}</span>
              </div>
            )}
            <div className="invoice-modern-total-row invoice-modern-grand-total">
              <span>Total</span>
              <span className="invoice-modern-total-amount">{money(invoice.total_minor)}</span>
            </div>
          </div>
        </div>

        {/* Footer with Actions */}
        <div className="modal-foot">
          <button type="button" className="secondary" onClick={onClose}>Close</button>
          <button type="button" className="primary" onClick={onEdit}>
            <Pencil size={15} />Edit invoice
          </button>
        </div>
      </section>
    </div>
  )
}

function InvoiceModal({ customers, products, gstRates, orgDetail, orgId, onClose, onCreated, editing }: {
  customers: Customer[]; products: Product[]; gstRates: GSTRate[]
  orgDetail: OrganizationDetail | null; orgId: string
  onClose: () => void; onCreated: () => void; editing: Invoice | null
}) {
  const isEdit = !!editing
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [customer, setCustomer] = useState(editing?.customer || '')
  const [number, setNumber] = useState(editing?.invoice_number || '')
  const [invDate, setInvDate] = useState(editing?.invoice_date || new Date().toISOString().slice(0, 10))
  const [dueDate, setDueDate] = useState(editing?.due_date || '')
  const [invDiscount, setInvDiscount] = useState(String(editing?.discount_minor ?? 0))
  const [lines, setLines] = useState<InvoiceLine[]>(
    (editing?.items?.length
      ? editing.items.map(it => ({
          product: it.product || '', description: it.description, quantity: String(it.quantity),
          unit_price_minor: String(it.unit_price_minor), discount_minor: String(it.discount_minor),
          gst_rate_bps: it.gst_rate_bps, gst_rate_name: it.gst_rate_name, hsn_sac: it.hsn_sac,
        }))
      : [{
          product: '', description: '', quantity: '1', unit_price_minor: '0',
          discount_minor: '0', gst_rate_bps: 0, gst_rate_name: 'No GST', hsn_sac: '',
        }])
  )

  const activeRates = gstRates.filter(r => r.active)

  const updateLine = (i: number, patch: Partial<InvoiceLine>) =>
    setLines(ls => ls.map((l, idx) => idx === i ? { ...l, ...patch } : l))

  const onProduct = (i: number, productId: string) => {
    if (!productId) { updateLine(i, { product: '' }); return }
    const p = products.find(x => x.id === productId)
    if (!p) return
    updateLine(i, {
      product: productId, description: p.name,
      unit_price_minor: String(p.price_minor), hsn_sac: p.hsn_sac,
      gst_rate_bps: p.default_gst_rate_bps || 0,
      gst_rate_name: p.default_gst_rate_bps ? (p.default_gst_rate_name || '') : 'No GST',
    })
  }

  const onGst = (i: number, rateId: string) => {
    if (!rateId) { updateLine(i, { gst_rate_bps: 0, gst_rate_name: 'No GST' }); return }
    const r = activeRates.find(x => x.id === rateId)
    if (r) updateLine(i, { gst_rate_bps: r.rate_bps, gst_rate_name: r.name })
  }

  const lineTotal = (l: InvoiceLine) => {
    const qty = parseFloat(l.quantity) || 0
    const unit = parseInt(l.unit_price_minor) || 0
    const disc = parseInt(l.discount_minor) || 0
    return Math.floor(qty * unit) - disc
  }

  const subtotal = lines.reduce((a, l) => a + Math.max(0, lineTotal(l)), 0)
  const tax = lines.reduce((a, l) => a + gstAmount(Math.max(0, lineTotal(l)), l.gst_rate_bps), 0)
  const invDisc = parseInt(invDiscount) || 0
  const total = subtotal - invDisc + tax

  // Place-of-supply preview
  const cust = customers.find(c => c.id === customer)
  const orgState = orgDetail?.state || ''
  const custState = cust?.state || ''
  const posWarning = (!orgState || !custState)
    ? 'Organization or customer state is missing; defaulting to intra-state (CGST + SGST).'
    : ''
  const isIntra = !posWarning ? orgState === custState : true

  const handle = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    if (!customer) { setErr('Choose a customer.'); setBusy(false); return }
    if (lines.length === 0) { setErr('Add at least one line.'); setBusy(false); return }
    for (const l of lines) {
      if ((parseFloat(l.quantity) || 0) <= 0 || (parseInt(l.unit_price_minor) || 0) <= 0) {
        setErr('Each line needs a positive quantity and unit price.'); setBusy(false); return
      }
    }
    const payload: Record<string, unknown> = {
      customer, invoice_number: number, invoice_date: invDate, due_date: dueDate,
      currency: 'INR', discount_minor: invDisc, status: editing?.status || 'issued',
      items: lines.map(l => {
        const item: Record<string, unknown> = {
          description: l.description || 'Item', quantity: parseFloat(l.quantity),
          unit_price_minor: parseInt(l.unit_price_minor),
          discount_minor: parseInt(l.discount_minor) || 0,
          gst_rate_bps: l.gst_rate_bps, gst_rate_name: l.gst_rate_name, hsn_sac: l.hsn_sac,
        }
        if (l.product) item.product = l.product
        return item
      }),
    }
    try {
      if (isEdit && editing) await api.updateInvoice(orgId, editing.id, payload)
      else await api.createInvoice(orgId, payload)
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal invoice-form-clean" style={{ width: 'min(1100px, 95%)', maxHeight: '90vh', overflow: 'auto' }}>
        {/* Header */}
        <div className="invoice-form-clean-header">
          <div>
            <div className="invoice-form-clean-title">Customer Invoice</div>
            <h2 className="invoice-form-clean-subtitle">{isEdit ? editing.invoice_number : 'Draft'}</h2>
          </div>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        <form onSubmit={handle}>
          <div className="invoice-form-clean-body">
            {/* Top Info Grid */}
            <div className="invoice-form-clean-grid">
              <div className="invoice-form-clean-col">
                <label className="invoice-form-clean-label">Customer *</label>
                <select className="invoice-form-clean-input" value={customer} onChange={e => setCustomer(e.target.value)} required>
                  <option value="">Choose a customer</option>
                  {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>

              <div className="invoice-form-clean-col">
                <label className="invoice-form-clean-label">Invoice Date *</label>
                <input className="invoice-form-clean-input" type="date" value={invDate} onChange={e => setInvDate(e.target.value)} required />
              </div>
            </div>

            <div className="invoice-form-clean-grid">
              <div className="invoice-form-clean-col">
                <label className="invoice-form-clean-label">Invoice Number *</label>
                <input className="invoice-form-clean-input" value={number} onChange={e => setNumber(e.target.value)} placeholder="INV-2026-001" required />
              </div>

              <div className="invoice-form-clean-col">
                <label className="invoice-form-clean-label">Due Date *</label>
                <input className="invoice-form-clean-input" type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} required />
              </div>
            </div>

            {/* Invoice Lines Table */}
            <div className="invoice-form-clean-section">
              <div className="invoice-form-clean-tabs">
                <button type="button" className="invoice-form-clean-tab active">Invoice Lines</button>
              </div>

              <div className="invoice-lines-table-wrap">
                <table className="invoice-lines-table-clean">
                  <thead>
                    <tr>
                      <th style={{width: '25%'}}>Product</th>
                      <th style={{width: '25%'}}>Description</th>
                      <th style={{width: '10%'}}>Quantity</th>
                      <th style={{width: '12%'}}>Price</th>
                      <th style={{width: '15%'}}>Taxes</th>
                      <th style={{width: '10%'}}>Subtotal</th>
                      <th style={{width: '3%'}}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {lines.map((l, i) => {
                      const lt = Math.max(0, lineTotal(l))
                      const gst = gstAmount(lt, l.gst_rate_bps)
                      return (
                        <tr key={i}>
                          <td>
                            <select 
                              className="invoice-table-select" 
                              value={l.product} 
                              onChange={e => onProduct(i, e.target.value)}
                            >
                              <option value="">Select product</option>
                              {products.filter(p => p.active).map(p => (
                                <option key={p.id} value={p.id}>{p.name}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input 
                              className="invoice-table-input" 
                              value={l.description} 
                              onChange={e => updateLine(i, { description: e.target.value })} 
                              placeholder="Description" 
                              required 
                            />
                          </td>
                          <td>
                            <input 
                              className="invoice-table-input" 
                              type="number" 
                              min="0.01" 
                              step="0.01" 
                              value={l.quantity} 
                              onChange={e => updateLine(i, { quantity: e.target.value })} 
                              required 
                            />
                          </td>
                          <td>
                            <input 
                              className="invoice-table-input" 
                              type="number" 
                              min="0.01" 
                              step="0.01" 
                              value={(parseInt(l.unit_price_minor) / 100).toFixed(2)} 
                              onChange={e => updateLine(i, { unit_price_minor: String(Math.round(parseFloat(e.target.value || '0') * 100)) })} 
                              required 
                            />
                          </td>
                          <td>
                            <select 
                              className="invoice-table-select" 
                              value={l.gst_rate_bps ? activeRates.find(r => r.rate_bps === l.gst_rate_bps)?.id || '' : ''} 
                              onChange={e => onGst(i, e.target.value)}
                            >
                              <option value="">No Tax</option>
                              {activeRates.map(r => (
                                <option key={r.id} value={r.id}>Tax {r.rate_percent}</option>
                              ))}
                            </select>
                          </td>
                          <td className="invoice-table-subtotal">
                            {money(lt + gst)}
                          </td>
                          <td>
                            {lines.length > 1 && (
                              <button 
                                type="button" 
                                className="invoice-table-delete" 
                                onClick={() => setLines(ls => ls.filter((_, idx) => idx !== i))}
                                title="Remove line"
                              >
                                <X size={16} />
                              </button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <button 
                type="button" 
                className="invoice-add-line-btn" 
                onClick={() => setLines(ls => [...ls, { 
                  product: '', description: '', quantity: '1', unit_price_minor: '0',
                  discount_minor: '0', gst_rate_bps: 0, gst_rate_name: 'No GST', hsn_sac: '' 
                }])}
              >
                <Plus size={15} /> Add a line
              </button>
            </div>

            {/* Totals Summary */}
            <div className="invoice-form-clean-totals">
              <div className="invoice-total-line">
                <span>Untaxed Amount</span>
                <strong>{money(subtotal)}</strong>
              </div>
              <div className="invoice-total-line">
                <span>Taxes</span>
                <strong>{money(tax)}</strong>
              </div>
              {invDisc > 0 && (
                <div className="invoice-total-line">
                  <span>Discount</span>
                  <strong>-{money(invDisc)}</strong>
                </div>
              )}
              <div className="invoice-total-line invoice-total-grand">
                <span>Total</span>
                <strong>{money(total)}</strong>
              </div>
            </div>
          </div>

          {err && <div className="form-error" style={{padding: '0 32px'}}>{err}</div>}

          {/* Footer Actions */}
          <div className="invoice-form-clean-footer">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Saving…' : isEdit ? 'Save' : 'Create'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ── Customer modal ─────────────────────────────────────────────────────────

function CustomerModal({ orgId, onClose, onCreated }: { orgId: string; onClose: () => void; onCreated: () => void }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setBusy(true); setErr('')
    const fd = new FormData(e.currentTarget)
    try {
      await api.createCustomer(orgId, { name: fd.get('name') as string, email: fd.get('email') as string, phone: fd.get('phone') as string })
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal">
        <div className="modal-head">
          <div><div className="eyebrow">WORKSPACE</div><h2>Add a customer</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Customer name<input name="name" placeholder="Business or individual name" required /></label>
          <label>Email<input name="email" type="email" placeholder="accounts@customer.in" /></label>
          <label>Phone<input name="phone" placeholder="+91 98765 43210" /></label>
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}><Plus size={15} />{busy ? 'Adding…' : 'Add customer'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ── Payment modal ──────────────────────────────────────────────────────────

function PaymentModal({ customers, invoices, orgId, onClose, onCreated }: {
  customers: Customer[]; invoices: Invoice[]; orgId: string; onClose: () => void; onCreated: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [selectedCust, setSelectedCust] = useState('')
  const custInvoices = invoices.filter(i => i.customer === selectedCust && i.balance_minor > 0)

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setBusy(true); setErr('')
    const fd = new FormData(e.currentTarget)
    const amount = parseFloat(fd.get('amount') as string)
    const invoiceId = fd.get('invoice') as string
    const allocations = invoiceId ? [{ invoice: invoiceId, amount_minor: Math.round(amount * 100) }] : []
    try {
      await api.createPayment(orgId, {
        customer: fd.get('customer'),
        payment_date: fd.get('date'),
        amount_minor: Math.round(amount * 100),
        currency: 'INR',
        method: fd.get('method') || 'bank_transfer',
        reference: fd.get('reference') || '',
        allocations_input: allocations,
      })
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal">
        <div className="modal-head">
          <div><div className="eyebrow">PAYMENTS</div><h2>Record a payment</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Customer
            <select name="customer" required onChange={e => setSelectedCust(e.target.value)}>
              <option value="">Choose a customer</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          {custInvoices.length > 0 && (
            <label>Allocate to invoice (optional)
              <select name="invoice">
                <option value="">No allocation</option>
                {custInvoices.map(i => (
                  <option key={i.id} value={i.id}>{i.invoice_number} — {money(i.balance_minor)} outstanding</option>
                ))}
              </select>
            </label>
          )}
          <div className="form-row">
            <label>Payment date<input name="date" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></label>
            <label>Amount (₹)<input name="amount" type="number" min="0.01" step="0.01" required placeholder="0.00" /></label>
          </div>
          <div className="form-row">
            <label>Method
              <select name="method">
                <option value="bank_transfer">Bank Transfer</option>
                <option value="upi">UPI</option>
                <option value="cheque">Cheque</option>
                <option value="cash">Cash</option>
              </select>
            </label>
            <label>Reference (optional)<input name="reference" placeholder="UTR / cheque no." /></label>
          </div>
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}><Plus size={15} />{busy ? 'Recording…' : 'Record payment'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ── GST rate modal (with live preview) ─────────────────────────────────────

function GstRateModal({ orgId, onClose, onCreated, editing }: {
  orgId: string; onClose: () => void; onCreated: () => void; editing: GSTRate | null
}) {
  const [name, setName] = useState(editing?.name || '')
  const [percent, setPercent] = useState(editing ? String(editing.rate_bps / 100) : '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const pct = parseFloat(percent) || 0
  const half = pct / 2
  const preview = pct > 0 ? `CGST ${half}% + SGST ${half}% | IGST ${pct}%` : 'No GST'

  const handle = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    if (!name.trim()) { setErr('Name is required.'); setBusy(false); return }
    const rate_bps = Math.round(pct * 100)
    if (rate_bps < 0) { setErr('Rate cannot be negative.'); setBusy(false); return }
    try {
      if (editing) await api.updateGstRate(orgId, editing.id, { name: name.trim(), rate_bps })
      else await api.createGstRate(orgId, { name: name.trim(), rate_bps })
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal" style={{ width: 'min(460px, 100%)' }}>
        <div className="modal-head">
          <div><div className="eyebrow">GST RATES</div><h2>{editing ? 'Edit GST rate' : 'New GST rate'}</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Name<input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. 18% GST" required /></label>
          <label>Total rate (%)<input type="number" min="0" step="0.25" value={percent} onChange={e => setPercent(e.target.value)} placeholder="e.g. 18" required /></label>
          <div className="gst-preview"><div className="gst-preview-head"><Percent size={14} /> Live preview</div>
            <div className="gst-row" style={{ border: 0, padding: 0 }}><b>{preview}</b></div>
          </div>
          <p style={{ fontSize: 11, color: '#87928b', margin: 0 }}>CGST and SGST are always equal halves. IGST is the full rate.</p>
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}>{editing ? 'Save' : 'Create rate'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ── Product modal ──────────────────────────────────────────────────────────

function ProductModal({ orgId, gstRates, onClose, onCreated, editing }: {
  orgId: string; gstRates: GSTRate[]; onClose: () => void; onCreated: () => void; editing: Product | null
}) {
  const [name, setName] = useState(editing?.name || '')
  const [price, setPrice] = useState(editing ? String(editing.price_minor / 100) : '')
  const [unit, setUnit] = useState(editing?.unit || 'Nos')
  const [sku, setSku] = useState(editing?.sku || '')
  const [hsn, setHsn] = useState(editing?.hsn_sac || '')
  const [desc, setDesc] = useState(editing?.description || '')
  const [gstRateId, setGstRateId] = useState(editing?.default_gst_rate || '')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const handle = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    if (!name.trim()) { setErr('Name is required.'); setBusy(false); return }
    const price_minor = Math.round((parseFloat(price) || 0) * 100)
    if (price_minor <= 0) { setErr('Price must be positive.'); setBusy(false); return }
    try {
      const data: Partial<Product> = {
        name: name.trim(), price_minor, unit, sku: sku.trim(), hsn_sac: hsn.trim(),
        description: desc, default_gst_rate: gstRateId || null,
      }
      if (editing) await api.updateProduct(orgId, editing.id, data)
      else await api.createProduct(orgId, data)
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  const activeRates = gstRates.filter(r => r.active)

  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal" style={{ width: 'min(520px, 100%)' }}>
        <div className="modal-head">
          <div><div className="eyebrow">PRODUCTS</div><h2>{editing ? 'Edit product' : 'Add a product'}</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Product name<input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Accounting software license" required /></label>
          <div className="form-row">
            <label>Price (₹)<input type="number" min="0.01" step="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" required /></label>
            <label>Unit<input value={unit} onChange={e => setUnit(e.target.value)} placeholder="Nos" /></label>
          </div>
          <div className="form-row">
            <label>SKU (optional)<input value={sku} onChange={e => setSku(e.target.value)} placeholder="Optional" /></label>
            <label>HSN/SAC (optional)<input value={hsn} onChange={e => setHsn(e.target.value)} placeholder="e.g. 998313" /></label>
          </div>
          <label>Default GST rate (optional)
            <select value={gstRateId} onChange={e => setGstRateId(e.target.value)}>
              <option value="">No GST</option>
              {activeRates.map(r => <option key={r.id} value={r.id}>{r.name} ({r.rate_percent})</option>)}
            </select>
          </label>
          <label>Description (optional)<textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} style={{ border: '1px solid #e3e8e5', borderRadius: 7, padding: '8px 10px', outline: 0, resize: 'vertical', fontFamily: 'inherit' }} /></label>
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}>{editing ? 'Save' : 'Add product'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

// ── Products page (tabs: Products / GST Rates) ──────────────────────────────

function ProductsPage({ orgId, products, gstRates, onReload, onOpenProductModal, onOpenRateModal }: {
  orgId: string; products: Product[]; gstRates: GSTRate[]; onReload: () => void
  onOpenProductModal: (p: Product | null) => void; onOpenRateModal: (r: GSTRate | null) => void
}) {
  const [tab, setTab] = useState<'products' | 'rates'>('products')
  const [query, setQuery] = useState('')
  const [busyId, setBusyId] = useState('')

  const toggleProduct = async (p: Product) => {
    setBusyId(p.id)
    try {
      if (p.active) await api.deactivateProduct(orgId, p.id)
      else await api.activateProduct(orgId, p.id)
      onReload()
    } catch { /* ignore */ } finally { setBusyId('') }
  }
  const toggleRate = async (r: GSTRate) => {
    setBusyId(r.id)
    try {
      if (r.active) await api.deactivateGstRate(orgId, r.id)
      else await api.activateGstRate(orgId, r.id)
      onReload()
    } catch { /* ignore */ } finally { setBusyId('') }
  }

  const filteredProducts = products.filter(p =>
    `${p.name} ${p.sku} ${p.hsn_sac}`.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="panel">
      <div className="panel-head" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div><h2>Products & GST</h2><p>Manage your catalogue and tax rates</p></div>
          {tab === 'products'
            ? <button className="primary" onClick={() => onOpenProductModal(null)}><Plus size={16} /> Add product</button>
            : <button className="primary" onClick={() => onOpenRateModal(null)}><Plus size={16} /> Add GST rate</button>}
        </div>
        <div className="tabs">
          <button className={`tab ${tab === 'products' ? 'active' : ''}`} onClick={() => setTab('products')}><Package size={14} /> Products</button>
          <button className={`tab ${tab === 'rates' ? 'active' : ''}`} onClick={() => setTab('rates')}><Percent size={14} /> GST Rates</button>
        </div>
      </div>

      {tab === 'products' && (
        <div className="table-wrap">
          <div style={{ padding: '12px 20px' }}>
            <div className="search"><Search size={15} /><input placeholder="Search products…" value={query} onChange={e => setQuery(e.target.value)} /></div>
          </div>
          <table>
            <thead><tr><th>PRODUCT</th><th>SKU</th><th>HSN/SAC</th><th>PRICE</th><th>DEFAULT GST</th><th>STATUS</th><th></th></tr></thead>
            <tbody>
              {filteredProducts.map(p => (
                <tr key={p.id}>
                  <td className="strong">{p.name}<div style={{ fontWeight: 400, color: '#9ba29d', fontSize: 10 }}>{p.unit} · {p.description?.slice(0, 40)}</div></td>
                  <td>{p.sku || '—'}</td>
                  <td>{p.hsn_sac || '—'}</td>
                  <td className="amount">{money(p.price_minor)}</td>
                  <td>{p.default_gst_rate_bps ? `${p.default_gst_rate_name} (${p.default_gst_rate_bps / 100}%)` : 'No GST'}</td>
                  <td>{p.active ? <span className="status paid">Active</span> : <span className="status draft">Inactive</span>}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="icon-btn" title="Edit" onClick={() => onOpenProductModal(p)}><Pencil size={14} /></button>
                    <button className="icon-btn" title={p.active ? 'Deactivate' : 'Activate'} disabled={busyId === p.id} onClick={() => toggleProduct(p)}><Power size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filteredProducts.length === 0 && <div className="empty">{query ? 'No products match your search.' : 'No products yet. Add your first product to get started.'}</div>}
        </div>
      )}

      {tab === 'rates' && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>RATE</th><th>TOTAL</th><th>PREVIEW</th><th>USED ON INVOICES</th><th>STATUS</th><th></th></tr></thead>
            <tbody>
              {gstRates.map(r => (
                <tr key={r.id}>
                  <td className="strong">{r.name}</td>
                  <td className="amount">{r.rate_percent}</td>
                  <td style={{ fontSize: 10 }}>{r.preview}</td>
                  <td>{r.in_use ? <span className="status issued">Yes</span> : '—'}</td>
                  <td>{r.active ? <span className="status paid">Active</span> : <span className="status draft">Inactive</span>}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="icon-btn" title="Edit" onClick={() => onOpenRateModal(r)}><Pencil size={14} /></button>
                    <button className="icon-btn" title={r.active ? 'Deactivate' : 'Activate'} disabled={busyId === r.id} onClick={() => toggleRate(r)}><Power size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {gstRates.length === 0 && <div className="empty">No GST rates yet. Add your first rate.</div>}
          {gstRates.some(r => r.in_use && !r.active) && (
            <div className="notice" style={{ margin: 12 }}>Some rates are deactivated but still referenced by past invoices — they are preserved as snapshots.</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [org, setOrg] = useState<Org | null>(null)
  const [page, setPage] = useState<Page>('Overview')
  const [modal, setModal] = useState<'' | 'invoice' | 'customer' | 'payment' | 'product' | 'gstrate' | 'edit-invoice' | 'view-invoice'>('')
  const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null)
  const [viewingInvoice, setViewingInvoice] = useState<Invoice | null>(null)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [editingRate, setEditingRate] = useState<GSTRate | null>(null)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  // Logout state
  const [logoutConfirm, setLogoutConfirm] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const logoutCancelRef = useRef<HTMLButtonElement>(null)

  // Data state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [aging, setAging] = useState<AgingData | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [gstRates, setGstRates] = useState<GSTRate[]>([])
  const [orgDetail, setOrgDetail] = useState<OrganizationDetail | null>(null)
  // FORECAST DISABLED — uncomment to re-enable
  // const [forecast, setForecast] = useState<ForecastData | null>(null)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  // AI assistant
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [aiError, setAiError] = useState<{ type: string; message: string; requestId?: string } | null>(null)
  const [asking, setAsking] = useState(false)
  const [sessionId] = useState(() =>
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  )

  const loadData = useCallback(async (activeOrg: Org) => {
    try {
      const [d, inv, cust, p, a, pr, gr] = await Promise.all([
        api.dashboard(activeOrg.id),
        api.invoices(activeOrg.id),
        api.customers(activeOrg.id),
        api.payments(activeOrg.id),
        api.aging(activeOrg.id),
        api.products(activeOrg.id),
        api.gstRates(activeOrg.id),
      ])
      setDashboard(d)
      setInvoices(inv.results || [])
      setCustomers(cust.results || [])
      setPayments(p.results || [])
      setAging(a)
      setProducts(pr.results || [])
      setGstRates(gr.results || [])
      // Fetch org detail (state) for GST place-of-supply display.
      api.organization(activeOrg.id).then(setOrgDetail).catch(() => {})
    } catch {
      setNotice('Unable to reach the API. Start the backend and refresh.')
    }
  }, [])

  const loadNotifications = useCallback(async (activeOrg: Org) => {
    try {
      const n = await api.notifications(activeOrg.id)
      setNotifications(n.notifications || [])
      setUnreadCount(n.unread_count || 0)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    api.csrf().then(() =>
      api.me().then(u => {
        setUser(u)
        if (u.organizations?.length) {
          const o = u.organizations[0]
          setOrg(o)
          loadData(o)
          loadNotifications(o)
        }
      }).catch(() => { })
    ).finally(() => setLoading(false))
  }, [loadData, loadNotifications])

  useEffect(() => {
    if (org) { loadData(org); loadNotifications(org) }
  }, [org?.id])

  const clearAuth = useCallback(() => {
    setUser(null)
    setOrg(null)
    setDashboard(null)
    setInvoices([])
    setCustomers([])
    setPayments([])
    setAging(null)
    // FORECAST DISABLED — uncomment to re-enable
    // setForecast(null)
    setNotifications([])
    setUnreadCount(0)
    setLogoutConfirm(false)
    setLoggingOut(false)
  }, [])

  const logout = useCallback(async () => {
    setLoggingOut(true)
    try {
      await api.logout(org?.id)
    } catch {
      // Proceed even if backend call fails — clear client state regardless
    }
    broadcastLogout()
    clearAuth()
    setNotice('Logged out successfully.')
  }, [org?.id, clearAuth])

  // 401 global handler: any protected request that returns 401 auto-clears auth
  useEffect(() => {
    setUnauthenticatedHandler(() => {
      clearAuth()
      setNotice('Your session expired. Please sign in again.')
    })
  }, [clearAuth])

  // Cross-tab logout: if another tab logs out, clear this tab too
  useEffect(() => {
    const unsub = subscribeLogoutChannel(() => {
      clearAuth()
      // No toast here — only the initiating tab shows "Logged out successfully"
    })
    return unsub
  }, [clearAuth])

  // Auto-dismiss notice after 4 seconds
  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(''), 4000)
    return () => clearTimeout(t)
  }, [notice])

  const askAI = async (e: React.FormEvent) => {
    e.preventDefault(); if (!question.trim() || !org) return
    setAsking(true); setAnswer(''); setAiError(null)
    try {
      const r = await api.ask(org.id, question, sessionId)
      setAnswer(r.answer)
    } catch (err: unknown) {
      const apiErr = err instanceof ApiError ? err : null
      const errorType = apiErr?.error_type ?? 'unknown_error'
      let userMessage: string

      if (errorType === 'llm_quota_exceeded') {
        userMessage = 'Your AI API quota is exhausted. Open the .env file, replace the API key with a fresh one, and restart the backend.'
      } else if (errorType === 'llm_unavailable') {
        userMessage = apiErr?.message || 'The AI service is unavailable. Check that your API key is valid in the .env file and restart the backend.'
      } else if (errorType === 'llm_api_error') {
        userMessage = 'The AI service encountered an error. Please try again in a moment.'
      } else if (errorType === 'validation_error') {
        userMessage = apiErr?.message || 'Invalid question. Please rephrase and try again.'
      } else {
        userMessage = apiErr?.message || 'Unable to get an answer. Please try again.'
      }

      setAiError({ type: errorType, message: userMessage, requestId: apiErr?.request_id })
      console.error('[AI Assistant Error]', { errorType, message: apiErr?.message, requestId: apiErr?.request_id })
    } finally { setAsking(false) }
  }

  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', color: '#729e85' }}><Activity size={28} /></div>
  if (!user) return <AuthScreen onAuth={u => { setUser(u); if (u.organizations?.length) { setOrg(u.organizations[0]); loadData(u.organizations[0]) } }} />
  if (!org) return <CreateOrgScreen user={user} onCreated={o => { setOrg(o); loadData(o) }} onLogout={logout} />

  const filtered = invoices.filter(i =>
    `${i.invoice_number} ${i.customer_name}`.toLowerCase().includes(query.toLowerCase())
  )

  const nav: { name: Page; icon: React.ElementType; soon?: boolean }[] = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Invoices', icon: FileText },
    { name: 'Customers', icon: Users },
    { name: 'Products', icon: Package },
    { name: 'Payments', icon: Wallet },
    { name: 'Aging report', icon: Clock3 },
    { name: 'Reminders', icon: Bell, soon: true },
    // RECONCILIATION DISABLED — uncomment to re-enable
    // { name: 'Reconciliation', icon: GitMerge, soon: true },
    // FORECAST DISABLED — uncomment to re-enable
    // { name: 'Forecast', icon: TrendingUp },
    { name: 'AI Assistant', icon: Bot },
  ]

  const invoiceTable = (
    <div className="table-wrap">
      <table>
        <thead><tr><th>CUSTOMER</th><th>INVOICE</th><th>DATE</th><th>DUE</th><th>TOTAL</th><th>BALANCE</th><th>STATUS</th><th></th></tr></thead>
        <tbody>
          {filtered.map(i => (
            <tr key={i.id} onClick={() => { setViewingInvoice(i); setModal('view-invoice') }} style={{cursor: 'pointer'}}>
              <td className="strong">{i.customer_name}</td>
              <td className="invoice-number-cell">{i.invoice_number}</td>
              <td>{fmtDate(i.invoice_date)}</td>
              <td>{fmtDate(i.due_date)}</td>
              <td className="amount">{money(i.total_minor)}</td>
              <td className="amount">{money(i.balance_minor)}</td>
              <td><StatusBadge s={i.display_status} /></td>
              <td><button className="icon-btn" title="Edit" onClick={(e) => { e.stopPropagation(); setEditingInvoice(i); setModal('edit-invoice') }}><Pencil size={14} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {filtered.length === 0 && <div className="empty">No invoices yet. Create your first invoice to get started.</div>}
    </div>
  )

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon"><Activity size={19} /></div><span>FinPilot <b>AI</b></span></div>
        <button className="org-switch">
          <div className="org-avatar">{org.name.slice(0, 1).toUpperCase()}</div>
          <span><strong>{org.name}</strong><small>{org.role} account</small></span>
          <ChevronDown size={15} />
        </button>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {nav.map(n => (
            <button key={n.name} className={`nav-item ${page === n.name ? 'active' : ''}`} onClick={() => setPage(n.name)}>
              <n.icon size={17} />{n.name}
              {n.soon && <span className="soon">SOON</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" onClick={() => setPage('Notifications')}>
            <Bell size={17} />Notifications
            {unreadCount > 0 && <span className="soon">{unreadCount}</span>}
          </button>
          {/* AUDIT LOG DISABLED — uncomment to re-enable */}
          {/* <button className="nav-item" onClick={() => setPage('Audit Log')}><ShieldCheck size={17} />Audit Log</button> */}
          <button className="nav-item" onClick={() => setPage('Settings')}><Settings2 size={17} />Settings</button>
          <div className="profile">
            <div className="avatar">{user.full_name?.slice(0, 1) || user.email.slice(0, 1)}</div>
            <span><strong>{user.full_name || user.email}</strong><small>{user.email}</small></span>
          </div>
          <button
            onClick={() => setLogoutConfirm(true)}
            title="Sign out"
            className="logout-row-btn"
            disabled={loggingOut}
            aria-label="Sign out"
          >
            <LogOut size={15} /><span>{loggingOut ? 'Signing out…' : 'Sign out'}</span>
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main">
        <header className="topbar">
          <div className="crumb">Workspace <span>/</span> <b>{page}</b></div>
          <div className="top-actions">
            <div className="period"><span className="live-dot" />Live data</div>
            <button className="icon-btn" onClick={() => setPage('Notifications')} title="Notifications">
              <Bell size={18} />{unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}
            </button>
            <button className="icon-btn" title="Help"><CircleHelp size={18} /></button>
            {/* Mobile logout — hidden on desktop via CSS class */}
            <button
              className="icon-btn logout-btn-mobile"
              title="Sign out"
              aria-label="Sign out"
              disabled={loggingOut}
              onClick={() => setLogoutConfirm(true)}
            >
              <LogOut size={18} />
            </button>
            <div className="avatar mini">{user.full_name?.slice(0, 1) || 'U'}</div>
          </div>
        </header>

        <section className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).toUpperCase()}</div>
              <h1>{page === 'Overview' ? `Good ${new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'}, ${user.full_name?.split(' ')[0] || 'there'}` : page}</h1>
              <p>{page === 'Overview' ? "Here's your receivables position today." : `Your ${page.toLowerCase()} at a glance.`}</p>
            </div>
            {page === 'Overview' && (
              <div className="heading-actions">
                <button className="secondary" onClick={() => setModal('customer')}><Plus size={16} /> Customer</button>
                <button className="primary" onClick={() => setModal('invoice')}><Plus size={16} /> New invoice</button>
              </div>
            )}
          </div>

          {notice && <div className="notice" onClick={() => setNotice('')}>{notice}<X size={15} /></div>}

          {/* ── Overview ── */}
          {page === 'Overview' && <>
            <div className="metrics">
              <Metric icon={<Wallet />} title="Total receivables" value={money(dashboard?.outstanding_minor || 0)} note="Across all issued invoices" tone="blue" />
              <Metric icon={<ArrowUpRight />} title="Overdue" value={money(dashboard?.overdue_minor || 0)} note={`${dashboard?.overdue_invoice_count || 0} invoices need attention`} tone="rose" />
              <Metric icon={<Clock3 />} title="Due in 7 days" value={money(dashboard?.due_next_7_days_minor || 0)} note="Upcoming cash flow" tone="amber" />
              <Metric icon={<Users />} title="Customers owing" value={dashboard?.customer_count || 0} note="With outstanding balance" tone="green" />
            </div>

            <div className="panel">
              <div className="panel-head">
                <div><h2>Outstanding invoices</h2><p>Keep an eye on what's coming in</p></div>
                <div className="toolbar">
                  <button className="link-btn" onClick={() => setPage('Invoices')}>View all <span>→</span></button>
                </div>
              </div>
              {invoiceTable}
            </div>

            <div className="lower-grid">
              <div className="panel aging-panel">
                <div className="panel-head">
                  <div><h2>Receivables aging</h2><p>Outstanding by days past due</p></div>
                  <button className="link-btn" onClick={() => setPage('Aging report')}>Full report →</button>
                </div>
                <div className="aging-list">
                  {[
                    ['Not yet due', 'not_yet_due', 'blue'],
                    ['1–30 days', 'days_1_30', 'green'],
                    ['31–60 days', 'days_31_60', 'amber'],
                    ['61–90 days', 'days_61_90', 'orange'],
                    ['Over 90 days', 'over_90', 'rose'],
                  ].map(([title, key, tone]) => (
                    <div className="aging-row" key={key}>
                      <span className={`aging-dot ${tone}`} />
                      <span className="aging-title">{title}</span>
                      <span className="aging-count">{aging?.buckets?.[key]?.length || 0}</span>
                      <strong>{money((aging?.buckets?.[key] || []).reduce((a, x) => a + x.balance_minor, 0))}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="tip-card">
                <div className="tip-icon"><Bot size={18} /></div>
                <div className="eyebrow">AI FINANCE ASSISTANT</div>
                <h3>Ask about your<br />financial Transactions.</h3>
                <p>Get instant answers about outstanding balances, overdue customers, and cash flow forecasts.</p>
                <button onClick={() => setPage('AI Assistant')}>Open AI assistant <span>→</span></button>
              </div>
            </div>
          </>}

          {/* ── Invoices ── */}
          {page === 'Invoices' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>All invoices</h2><p>{filtered.length} invoices in your workspace</p></div>
                <div className="toolbar">
                  <div className="search"><Search size={15} /><input placeholder="Search invoices…" value={query} onChange={e => setQuery(e.target.value)} /></div>
                  <a href={`/api/v1/exports/invoices/?`} className="secondary" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 7, padding: '9px 13px', border: '1px solid #e4e9e6', fontSize: 12, fontWeight: 600, color: '#52615a', background: '#fff' }} onClick={e => { e.preventDefault(); fetch(`/api/v1/exports/invoices/`, { credentials: 'include', headers: { 'X-Organization-ID': org.id } }).then(r => r.blob()).then(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'invoices.csv'; a.click() }) }}>
                    <Download size={15} /> Export
                  </a>
                  <button className="primary" onClick={() => setModal('invoice')}><Plus size={16} /> New invoice</button>
                </div>
              </div>
              {invoiceTable}
            </div>
          )}

          {/* ── Customers ── */}
          {page === 'Customers' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>Customers</h2><p>{customers.length} customers</p></div>
                <div className="toolbar">
                  <div className="search"><Search size={15} /><input placeholder="Search…" value={query} onChange={e => setQuery(e.target.value)} /></div>
                  <button className="primary" onClick={() => setModal('customer')}><Plus size={16} /> Add customer</button>
                </div>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>CUSTOMER</th><th>EMAIL</th><th>PHONE</th><th>OPEN INVOICES</th><th>OUTSTANDING</th><th>OPT-OUT</th></tr></thead>
                  <tbody>
                    {customers.filter(c => c.name.toLowerCase().includes(query.toLowerCase())).map(c => {
                      const open = invoices.filter(i => i.customer === c.id && i.balance_minor > 0)
                      return (
                        <tr key={c.id}>
                          <td className="strong">{c.name}</td>
                          <td>{c.email || '—'}</td>
                          <td>{c.phone || '—'}</td>
                          <td>{open.length}</td>
                          <td className="amount">{money(open.reduce((a, x) => a + x.balance_minor, 0))}</td>
                          <td>{c.opt_out ? <span className="status overdue">Opted out</span> : <span className="status paid">Active</span>}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {customers.length === 0 && <div className="empty">No customers yet. Add your first customer to get started.</div>}
              </div>
            </div>
          )}

          {/* ── Payments ── */}
          {page === 'Payments' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>Payments received</h2><p>{payments.length} payment records</p></div>
                <button className="primary" onClick={() => setModal('payment')}><Plus size={16} /> Record payment</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>DATE</th><th>CUSTOMER</th><th>AMOUNT</th><th>METHOD</th><th>REFERENCE</th><th>ALLOCATED TO</th><th>UNALLOCATED</th></tr></thead>
                  <tbody>
                    {payments.map(p => (
                      <tr key={p.id}>
                        <td>{fmtDate(p.payment_date)}</td>
                        <td className="strong">{customers.find(c => c.id === p.customer)?.name || '—'}</td>
                        <td className="amount">{money(p.amount_minor)}</td>
                        <td>{p.method.replace(/_/g, ' ')}</td>
                        <td>{p.reference || '—'}</td>
                        <td>{p.allocations.map(a => a.invoice_number).join(', ') || '—'}</td>
                        <td className={p.unallocated_minor > 0 ? 'amount' : ''}>{p.unallocated_minor > 0 ? money(p.unallocated_minor) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {payments.length === 0 && <div className="empty">No payments recorded yet.</div>}
              </div>
            </div>
          )}

          {/* ── Aging report ── */}
          {page === 'Aging report' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>Invoice aging report</h2><p>As of {aging?.as_of || 'today'} · Total outstanding: {money(aging?.grand_total_minor || 0)}</p></div>
                <button className="secondary" onClick={() => org && api.aging(org.id).then(setAging)}><RefreshCw size={15} /> Refresh</button>
              </div>
              {(['not_yet_due', 'days_1_30', 'days_31_60', 'days_61_90', 'over_90'] as const).map(key => {
                const rows = aging?.buckets?.[key] || []
                const labels: Record<string, string> = {
                  not_yet_due: 'Not yet due', days_1_30: '1–30 days overdue',
                  days_31_60: '31–60 days overdue', days_61_90: '61–90 days overdue', over_90: 'Over 90 days overdue',
                }
                return (
                  <div className="aging-section" key={key}>
                    <h3>{labels[key]} — {money(rows.reduce((a, r) => a + r.balance_minor, 0))} <span style={{ fontWeight: 400, color: '#9ba29d' }}>({rows.length} invoices)</span></h3>
                    {rows.length ? rows.map(r => (
                      <div className="aging-invoice" key={r.id}>
                        <b>{r.invoice_number}</b>
                        <span>{r.customer}</span>
                        <span>Due {fmtDate(r.due_date)}</span>
                        <strong>{money(r.balance_minor)}</strong>
                      </div>
                    )) : <div className="sub-empty">No invoices in this bucket.</div>}
                  </div>
                )
              })}
            </div>
          )}

          {/* ── Forecast ── DISABLED — uncomment to re-enable */}
          {/* {page === 'Forecast' && (
            <ForecastPage orgId={org.id} />
          )} */}

          {/* ── AI Assistant ── */}
          {page === 'AI Assistant' && (
            <div className="panel ai-panel">
              <div className="panel-head">
                <div><h2>AI Finance Assistant</h2><p>Ask questions about your FinancialRecord — answers are based on your live data.</p></div>
              </div>
              <div className="ai-body">
                <div className="ai-disclaimer">
                  <AlertCircle size={14} />
                  <span>Read-only assistant. All data is retrieved from your organization's records. Forecasts are projections, not guaranteed receipts.</span>
                </div>
                <form className="ai-form" onSubmit={askAI}>
                  <input
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    placeholder="e.g. How much is overdue? Which customers owe the most?"
                    className="ai-input"
                  />
                  <button className="primary" disabled={asking || !question.trim()}>
                    {asking ? <><RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} /> Thinking…</> : <><Bot size={15} /> Ask</>}
                  </button>
                </form>

                {/* Error banner — shown instead of the answer box */}
                {aiError && (
                  <div className={`ai-error-banner ${aiError.type === 'llm_quota_exceeded' ? 'ai-error-quota' : 'ai-error-generic'}`}>
                    <div className="ai-error-header">
                      <AlertCircle size={15} />
                      <span>{aiError.type === 'llm_quota_exceeded' ? 'API Quota Exhausted' : 'Assistant Unavailable'}</span>
                      <button className="ai-error-dismiss" onClick={() => setAiError(null)} aria-label="Dismiss"><X size={13} /></button>
                    </div>
                    <p>{aiError.message}</p>
                    {aiError.requestId && (
                      <span className="ai-error-id">Request ID: {aiError.requestId}</span>
                    )}
                  </div>
                )}

                {/* Answer box — only shown on success */}
                {answer && !aiError && (
                  <div className="ai-answer">
                    <div className="ai-answer-label"><CheckCircle size={14} /> Answer</div>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
                  </div>
                )}

                {!answer && !aiError && !asking && (
                  <div className="ai-suggestions">
                    <p>Try asking:</p>
                    <div className="ai-chips">
                      {[
                        'How much is overdue?',
                        'Which 5 customers owe the most?',
                        'Which invoices are due next week?',
                        'What is the 30-day cash inflow forecast?',
                        'Which customers have paid late historically?',
                      ].map(q => (
                        <button key={q} className="ai-chip" onClick={() => setQuestion(q)}>{q}</button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Notifications ── */}
          {page === 'Notifications' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>Notifications</h2><p>{unreadCount} unread</p></div>
                <button className="secondary" onClick={async () => { await api.markAllRead(org.id); loadNotifications(org) }}>Mark all read</button>
              </div>
              <div style={{ padding: '0 4px' }}>
                {notifications.length === 0 && <div className="empty">You're all caught up.</div>}
                {notifications.map(n => (
                  <div key={n.id} className={`notif-row ${n.read ? 'read' : 'unread'}`}>
                    <Bell size={15} />
                    <div>
                      <div className="notif-type">{n.event_type.replace(/_/g, ' ')}</div>
                      <div className="notif-time">{new Date(n.created_at).toLocaleString('en-IN')}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Audit log ── DISABLED — uncomment to re-enable */}
          {/* {page === 'Audit Log' && <AuditLogPage orgId={org.id} />} */}

          {/* ── Settings ── */}
          {page === 'Settings' && (
            <div className="panel">
              <div className="panel-head"><div><h2>Organization settings</h2><p>Manage your workspace</p></div></div>
              <div style={{ padding: '20px 24px' }}>
                <p><strong>Organization:</strong> {org.name}</p>
                <p><strong>Your role:</strong> {org.role}</p>
                <p><strong>Currency:</strong> {org.currency}</p>
                <p style={{ color: '#8fa294', fontSize: 12, marginTop: 16 }}>
                  Full settings configuration including billing address, GSTIN, payment terms, and reminder preferences will be available in the next release.
                </p>
              </div>
            </div>
          )}

          {/* ── Products ── */}
          {page === 'Products' && org && (
            <ProductsPage
              orgId={org.id} products={products} gstRates={gstRates}
              onReload={() => loadData(org)}
              onOpenProductModal={p => { setEditingProduct(p); setModal('product') }}
              onOpenRateModal={r => { setEditingRate(r); setModal('gstrate') }}
            />
          )}

          {/* ── Reminders / Reconciliation (coming soon) ── */}
          {/* RECONCILIATION DISABLED — uncomment `|| page === 'Reconciliation'` to re-enable */}
          {(page === 'Reminders' /* || page === 'Reconciliation' */) && (
            <div className="coming">
              <div className="coming-icon"><Activity size={24} /></div>
              <div className="eyebrow">ON THE ROADMAP</div>
              <h2>{page} is being prepared</h2>
              <p>The backend models, policies, and APIs for {page.toLowerCase()} are fully implemented. The review screens are coming next.</p>
              <button className="secondary" onClick={() => setPage('Overview')}>Back to overview</button>
            </div>
          )}

          <footer>
            FinPilot AI <span>·</span> INR reporting <span>·</span> Data as of {dashboard?.as_of || 'today'}
            <span className="footer-right">Questions? <a href="mailto:support@finpilot.ai">Talk to our team</a></span>
          </footer>
        </section>
      </main>

      {/* Modals */}
      {modal === 'view-invoice' && viewingInvoice && org && (
        <InvoiceViewModal
          invoice={viewingInvoice}
          customers={customers}
          onClose={() => { setModal(''); setViewingInvoice(null) }}
          onEdit={() => { setEditingInvoice(viewingInvoice); setModal('edit-invoice'); setViewingInvoice(null) }}
        />
      )}
      {(modal === 'invoice' || modal === 'edit-invoice') && org && (
        <InvoiceModal
          customers={customers} products={products} gstRates={gstRates}
          orgDetail={orgDetail} orgId={org.id}
          editing={modal === 'edit-invoice' ? editingInvoice : null}
          onClose={() => { setModal(''); setEditingInvoice(null) }}
          onCreated={() => loadData(org)}
        />
      )}
      {modal === 'customer' && org && (
        <CustomerModal orgId={org.id} onClose={() => setModal('')} onCreated={() => loadData(org)} />
      )}
      {modal === 'payment' && org && (
        <PaymentModal customers={customers} invoices={invoices} orgId={org.id} onClose={() => setModal('')} onCreated={() => loadData(org)} />
      )}
      {modal === 'product' && org && (
        <ProductModal
          orgId={org.id} gstRates={gstRates} editing={editingProduct}
          onClose={() => { setModal(''); setEditingProduct(null) }}
          onCreated={() => loadData(org)}
        />
      )}
      {modal === 'gstrate' && org && (
        <GstRateModal
          orgId={org.id} editing={editingRate}
          onClose={() => { setModal(''); setEditingRate(null) }}
          onCreated={() => loadData(org)}
        />
      )}

      {/* ── Logout confirm dialog ─────────────────────────────────────── */}
      {logoutConfirm && (
        <div
          className="backdrop"
          role="dialog"
          aria-modal="true"
          aria-labelledby="logout-dialog-title"
          onMouseDown={e => { if (e.target === e.currentTarget && !loggingOut) setLogoutConfirm(false) }}
        >
          <section className="modal" style={{ maxWidth: 380 }}>
            <div className="modal-head">
              <div><div className="eyebrow">ACCOUNT</div><h2 id="logout-dialog-title">Sign out?</h2></div>
              <button
                className="icon-btn"
                onClick={() => setLogoutConfirm(false)}
                disabled={loggingOut}
                aria-label="Cancel"
              ><X size={18} /></button>
            </div>
            <p style={{ fontSize: 13, color: '#526059', margin: '4px 0 20px', lineHeight: 1.6 }}>
              You'll be returned to the sign-in screen. Any unsaved work will be lost.
            </p>
            <div className="modal-foot">
              <button
                ref={logoutCancelRef}
                type="button"
                className="secondary"
                onClick={() => setLogoutConfirm(false)}
                disabled={loggingOut}
                autoFocus
              >Cancel</button>
              <button
                className="primary"
                onClick={logout}
                disabled={loggingOut}
                aria-busy={loggingOut}
                data-testid="confirm-logout-btn"
              >
                <LogOut size={15} />{loggingOut ? 'Signing out…' : 'Sign out'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}

// ── Forecast page component ── DISABLED — uncomment to re-enable ─────────────
/*
function ForecastPage({ orgId }: { orgId: string }) {
  const [period, setPeriod] = useState<7 | 30 | 60>(30)
  const [timing, setTiming] = useState('due_date')
  const [data, setData] = useState<ForecastData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.forecast(orgId, period, timing).then(setData).finally(() => setLoading(false))
  }, [orgId, period, timing])

  return (
    <div className="panel">
      <div className="panel-head">
        <div><h2>Cash inflow forecast</h2><p>Expected receivables — not a full cash balance. Excludes expenses, payroll, and other outflows.</p></div>
        <div className="toolbar">
          <select value={period} onChange={e => setPeriod(Number(e.target.value) as 7 | 30 | 60)} style={{ height: 34, borderRadius: 7, border: '1px solid #e3e8e5', padding: '0 9px', fontSize: 12 }}>
            <option value={7}>7 days</option>
            <option value={30}>30 days</option>
            <option value={60}>60 days</option>
          </select>
          <select value={timing} onChange={e => setTiming(e.target.value)} style={{ height: 34, borderRadius: 7, border: '1px solid #e3e8e5', padding: '0 9px', fontSize: 12 }}>
            <option value="due_date">By due date</option>
            <option value="historical_delay">Historical delay</option>
          </select>
        </div>
      </div>
      {loading && <div className="empty"><RefreshCw size={18} style={{ animation: 'spin 1s linear infinite' }} /> Loading forecast…</div>}
      {data && !loading && (
        <div style={{ padding: '0 24px 20px' }}>
          {data.insufficient_history && (
            <div className="notice">Insufficient payment history for historical delay calculation. Using rule-based assumptions.</div>
          )}
          <div className="metrics" style={{ marginTop: 16 }}>
            {(['conservative', 'base', 'optimistic'] as const).map((s, i) => (
              <Metric
                key={s}
                icon={<TrendingUp />}
                title={s.charAt(0).toUpperCase() + s.slice(1)}
                value={money(data.scenarios[s]?.total_minor || 0)}
                note={`${data.scenarios[s]?.lines?.filter((l: unknown) => (l as { included: boolean }).included).length || 0} invoices contributing`}
                tone={['rose', 'blue', 'green'][i]}
              />
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#9aa39e', marginTop: 12, borderTop: '1px solid #f0f2f1', paddingTop: 12 }}>
            <strong>Assumptions:</strong>{' '}
            Timing: {String(data.assumptions.timing_assumption)}{' '}·{' '}
            Conservative offset: +{String(data.assumptions.conservative_offset_days)} days{' '}·{' '}
            Base offset: {String(data.assumptions.base_offset_days)} days{' '}·{' '}
            Optimistic offset: {String(data.assumptions.optimistic_offset_days)} days
          </div>
        </div>
      )}
    </div>
  )
}
*/

// ── Audit log page ── DISABLED — uncomment to re-enable ─────────────────────
/*
function AuditLogPage({ orgId }: { orgId: string }) {
  const [logs, setLogs] = useState<import('./lib/api').AuditLog[]>([])
  useEffect(() => {
    api.auditLogs(orgId).then(setLogs).catch(() => { })
  }, [orgId])
  return (
    <div className="panel">
      <div className="panel-head"><div><h2>Audit log</h2><p>Recent security-sensitive and financial actions</p></div></div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>TIMESTAMP</th><th>ACTION</th><th>ENTITY</th><th>DESCRIPTION</th><th>ACTOR</th></tr></thead>
          <tbody>
            {logs.map(l => (
              <tr key={l.id}>
                <td style={{ fontSize: 10 }}>{new Date(l.created_at).toLocaleString('en-IN')}</td>
                <td className="strong">{l.action}</td>
                <td>{l.entity_type}</td>
                <td>{l.summary}</td>
                <td>{l.actor_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {logs.length === 0 && <div className="empty">No audit entries yet.</div>}
      </div>
    </div>
  )
}
*/
