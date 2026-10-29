import { useEffect, useState, useCallback } from 'react'
import {
  Activity, ArrowUpRight, Bell, ChevronDown, CircleHelp, Clock3,
  FileSpreadsheet, FileText, LayoutDashboard, LogOut, Plus, Search,
  Settings2, ShieldCheck, Users, Wallet, X, Bot, GitMerge,
  TrendingUp, Download, CheckCircle, AlertCircle, RefreshCw,
} from 'lucide-react'
import {
  api, money, fmtDate,
  type User, type Org, type Invoice, type Customer,
  type Payment, type DashboardData, type AgingData, type ForecastData, type Notification,
} from './lib/api'

// ── Types ──────────────────────────────────────────────────────────────────

type Page = 'Overview' | 'Invoices' | 'Customers' | 'Payments' | 'Aging report' |
  'Reminders' | 'Reconciliation' | 'Forecast' | 'AI Assistant' |
  'Audit Log' | 'Settings' | 'Notifications'

// ── Auth screen ────────────────────────────────────────────────────────────

function AuthScreen({ onAuth }: { onAuth: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setBusy(true); setError('')
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
  return <span className={`status ${s}`}>{s.replace(/_/g, ' ')}</span>
}

// ── Invoice modal ──────────────────────────────────────────────────────────

function InvoiceModal({ customers, orgId, onClose, onCreated }: {
  customers: Customer[]; orgId: string; onClose: () => void; onCreated: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setBusy(true); setErr('')
    const fd = new FormData(e.currentTarget)
    const amount = parseFloat(fd.get('amount') as string)
    try {
      await api.createInvoice(orgId, {
        customer: fd.get('customer'),
        invoice_number: fd.get('number'),
        invoice_date: fd.get('date'),
        due_date: fd.get('due'),
        currency: 'INR',
        subtotal_minor: Math.round(amount * 100),
        discount_minor: 0,
        tax_minor: 0,
        status: 'issued',
      })
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal">
        <div className="modal-head">
          <div><div className="eyebrow">WORKSPACE</div><h2>Create an invoice</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Customer<select name="customer" required><option value="">Choose a customer</option>{customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
          <label>Invoice number<input name="number" placeholder="INV-2026-001" required /></label>
          <div className="form-row">
            <label>Invoice date<input name="date" type="date" required defaultValue={new Date().toISOString().slice(0, 10)} /></label>
            <label>Due date<input name="due" type="date" required /></label>
          </div>
          <label>Total amount (₹)<input name="amount" type="number" min="1" step="0.01" placeholder="0.00" required /></label>
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}><Plus size={15} />{busy ? 'Creating…' : 'Create invoice'}</button>
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

// ── Main App ───────────────────────────────────────────────────────────────

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [org, setOrg] = useState<Org | null>(null)
  const [page, setPage] = useState<Page>('Overview')
  const [modal, setModal] = useState<'' | 'invoice' | 'customer' | 'payment'>('')
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  // Data state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [aging, setAging] = useState<AgingData | null>(null)
  const [forecast, setForecast] = useState<ForecastData | null>(null)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  // AI assistant
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [asking, setAsking] = useState(false)
  const [sessionId] = useState(() => crypto.randomUUID())

  const loadData = useCallback(async (activeOrg: Org) => {
    try {
      const [d, inv, cust, p, a] = await Promise.all([
        api.dashboard(activeOrg.id),
        api.invoices(activeOrg.id),
        api.customers(activeOrg.id),
        api.payments(activeOrg.id),
        api.aging(activeOrg.id),
      ])
      setDashboard(d)
      setInvoices(inv.results || [])
      setCustomers(cust.results || [])
      setPayments(p.results || [])
      setAging(a)
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

  const logout = async () => {
    await api.logout(org?.id)
    setUser(null); setOrg(null)
  }

  const askAI = async (e: React.FormEvent) => {
    e.preventDefault(); if (!question.trim() || !org) return
    setAsking(true); setAnswer('')
    try {
      const r = await api.ask(org.id, question, sessionId)
      setAnswer(r.answer)
    } catch (err) {
      setAnswer('Unable to get an answer. Please try again.')
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
    { name: 'Payments', icon: Wallet },
    { name: 'Aging report', icon: Clock3 },
    { name: 'Reminders', icon: Bell, soon: true },
    { name: 'Reconciliation', icon: GitMerge, soon: true },
    { name: 'Forecast', icon: TrendingUp },
    { name: 'AI Assistant', icon: Bot },
  ]

  const invoiceTable = (
    <div className="table-wrap">
      <table>
        <thead><tr><th>INVOICE</th><th>CUSTOMER</th><th>ISSUED</th><th>DUE DATE</th><th>AMOUNT DUE</th><th>STATUS</th></tr></thead>
        <tbody>
          {filtered.map(i => (
            <tr key={i.id}>
              <td className="strong">{i.invoice_number}</td>
              <td>{i.customer_name}</td>
              <td>{fmtDate(i.invoice_date)}</td>
              <td>{fmtDate(i.due_date)}</td>
              <td className="amount">{money(i.balance_minor)}</td>
              <td><StatusBadge s={i.display_status} /></td>
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
          <button className="nav-item" onClick={() => setPage('Audit Log')}><ShieldCheck size={17} />Audit Log</button>
          <button className="nav-item" onClick={() => setPage('Settings')}><Settings2 size={17} />Settings</button>
          <div className="profile">
            <div className="avatar">{user.full_name?.slice(0, 1) || user.email.slice(0, 1)}</div>
            <span><strong>{user.full_name || user.email}</strong><small>{user.email}</small></span>
            <button onClick={logout} title="Sign out"><LogOut size={16} /></button>
          </div>
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
            <div className="heading-actions">
              <button className="secondary" onClick={() => setModal('customer')}><Plus size={16} /> Customer</button>
              <button className="primary" onClick={() => setModal('invoice')}><Plus size={16} /> New invoice</button>
            </div>
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
                <h3>Ask about your<br />receivables.</h3>
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

          {/* ── Forecast ── */}
          {page === 'Forecast' && (
            <ForecastPage orgId={org.id} />
          )}

          {/* ── AI Assistant ── */}
          {page === 'AI Assistant' && (
            <div className="panel ai-panel">
              <div className="panel-head">
                <div><h2>AI Finance Assistant</h2><p>Ask questions about your receivables — answers are based on your live data.</p></div>
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
                {answer && (
                  <div className="ai-answer">
                    <div className="ai-answer-label"><CheckCircle size={14} /> Answer</div>
                    <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
                  </div>
                )}
                {!answer && !asking && (
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

          {/* ── Audit log ── */}
          {page === 'Audit Log' && <AuditLogPage orgId={org.id} />}

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

          {/* ── Reminders / Reconciliation (coming soon) ── */}
          {(page === 'Reminders' || page === 'Reconciliation') && (
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
      {modal === 'invoice' && (
        <InvoiceModal customers={customers} orgId={org.id} onClose={() => setModal('')} onCreated={() => loadData(org)} />
      )}
      {modal === 'customer' && (
        <CustomerModal orgId={org.id} onClose={() => setModal('')} onCreated={() => loadData(org)} />
      )}
      {modal === 'payment' && (
        <PaymentModal customers={customers} invoices={invoices} orgId={org.id} onClose={() => setModal('')} onCreated={() => loadData(org)} />
      )}
    </div>
  )
}

// ── Forecast page component ────────────────────────────────────────────────

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

// ── Audit log page ─────────────────────────────────────────────────────────

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
