// FinPilot AI - Invoice Module Improved
import React, { useEffect, useState, useCallback, useRef } from 'react'
import { MarkdownAnswer } from './components/MarkdownAnswer'
import { useTheme } from './lib/theme'
import {
  Activity, ArrowUpRight, Bell, ChevronDown, ChevronUp, CircleHelp, Clock3,
  FileSpreadsheet, FileText, LayoutDashboard, Loader2, LogOut, Plus, Search,
  Send, Settings2, ShieldCheck, Users, Wallet, X, Bot, /*GitMerge,*/
  TrendingUp, Download, CheckCircle, AlertCircle, RefreshCw,
  Package, Pencil, Power, Percent, Tag, Sun, Moon,
} from 'lucide-react'

// -- Theme toggle button ----------------------------------------------------
function ThemeToggle() {
  const [theme, toggle] = useTheme()
  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  )
}
import {
  api, ApiError, money, fmtDate, fmtQty,
  setUnauthenticatedHandler, broadcastLogout, subscribeLogoutChannel,
  type User, type Org, type Invoice, type Customer,
  type Payment, type DashboardData, type AgingData, /*type ForecastData,*/ type Notification,
  type Product, type GSTRate, type OrganizationDetail,
  type ReminderSchedule, type ReminderStep, type ReminderJob,
  type ReminderTemplate, type ScheduleStepInput, type ArchiveImpact,
  type NotificationDetails,
} from './lib/api'

// -- Types ------------------------------------------------------------------

type Page = 'Overview' | 'Invoices' | 'Customers' | 'Payments' | 'Aging report' |
  'Reminders' | /*'Reconciliation' |*/ /*'Forecast' |*/ 'AI Assistant' |
  /*'Audit Log' |*/ 'Settings' | 'Notifications' | 'Products' | 'Customers owing' | 'Due in 7 days'

// -- GST preview helper (display-only; the server recalculates on save) ------
// Mirrors the backend: round-half-up to the nearest paise.
function gstAmount(taxableMinor: number, rateBps: number): number {
  if (!rateBps || rateBps <= 0 || taxableMinor <= 0) return 0
  return Math.round((taxableMinor * rateBps) / 10000)
}

// -- Marble chute SVG artwork (right panel decoration) ---------------------

function MarbleArtwork() {
  return (
    <svg viewBox="0 0 700 860" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style={{ width: '100%', height: '100%', display: 'block' }}>
      <defs>
        <linearGradient id="wallOuter" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#b4cbb8" />
          <stop offset="55%" stopColor="#9eb6a1" />
          <stop offset="100%" stopColor="#839c86" />
        </linearGradient>
        <linearGradient id="wallFace" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c8dac9" />
          <stop offset="100%" stopColor="#adc0ae" />
        </linearGradient>
        <linearGradient id="floorGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#c6dbc9" />
          <stop offset="50%" stopColor="#bed4c1" />
          <stop offset="100%" stopColor="#b2c9b6" />
        </linearGradient>
        <radialGradient id="marbleShading" cx="38%" cy="35%" r="55%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="30%" stopColor="#f2f7f3" />
          <stop offset="60%" stopColor="#d6e4d9" />
          <stop offset="85%" stopColor="#b9ccbd" />
          <stop offset="100%" stopColor="#9eb2a2" />
        </radialGradient>
        <radialGradient id="marbleHighlight" cx="30%" cy="28%" r="30%">
          <stop offset="0%" stopColor="rgba(255,255,255,0.9)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
        <filter id="dropShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="12" stdDeviation="18" floodColor="#486950" floodOpacity="0.22" />
        </filter>
      </defs>

      {/* -- Track: outer wall (left side curved channel) -- */}
      <g filter="url(#dropShadow)">
        {/* Back wall of the channel */}
        <path d="M 180 80 C 180 80 160 200 165 340 C 170 440 230 500 290 560 C 350 620 420 650 440 720 C 455 770 450 820 450 820 L 490 820 C 490 820 495 770 480 718 C 460 646 388 614 328 554 C 268 494 210 436 205 336 C 200 198 220 78 220 78 Z"
          fill="url(#wallOuter)" />
        {/* Channel floor */}
        <path d="M 220 78 C 220 78 200 198 205 336 C 210 436 268 494 328 554 C 388 614 460 646 480 718 C 495 770 490 820 490 820 L 530 820 C 530 820 528 770 512 716 C 492 642 418 608 358 548 C 298 488 242 428 238 332 C 233 194 253 76 253 76 Z"
          fill="url(#floorGrad)" />
        {/* Inner wall face */}
        <path d="M 253 76 C 253 76 233 194 238 332 C 242 428 298 488 358 548 C 418 608 492 642 512 716 C 528 770 530 820 530 820 L 560 820 C 560 820 558 768 542 714 C 522 638 448 603 388 542 C 328 482 273 420 269 328 C 264 190 284 74 284 74 Z"
          fill="url(#wallFace)" />
      </g>

      {/* -- Marble sphere -- */}
      <g filter="url(#dropShadow)">
        <circle cx="352" cy="410" r="52" fill="url(#marbleShading)" />
        <circle cx="352" cy="410" r="52" fill="url(#marbleHighlight)" />
        {/* Specular glint */}
        <ellipse cx="334" cy="393" rx="14" ry="9" fill="rgba(255,255,255,0.65)" transform="rotate(-20 334 393)" />
      </g>
    </svg>
  )
}

// -- Auth screen ------------------------------------------------------------

function AuthScreen({ onAuth }: { onAuth: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register' | 'forgot'>('login')
  const [error, setError] = useState('')
  const [googleError, setGoogleError] = useState('')
  const [forgotSent, setForgotSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [googleBusy, setGoogleBusy] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  // Check for Google OAuth errors in URL on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const googleErr = params.get('google_error')
    if (googleErr) {
      setGoogleError(decodeURIComponent(googleErr))
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [])

  const switchMode = (m: 'login' | 'register' | 'forgot') => {
    setMode(m)
    setError('')
    setGoogleError('')
    setForgotSent(false)
    setShowPassword(false)
    setShowConfirm(false)
  }

  const handleGoogleSignIn = async () => {
    setGoogleError('')
    setGoogleBusy(true)
    try {
      await api.csrf()
      const response = await api.googleAuthUrl()
      // Redirect to Google OAuth
      window.location.href = response.auth_url
    } catch (err: unknown) {
      setGoogleBusy(false)
      setGoogleError((err as Error).message || 'Failed to start Google sign-in')
    }
  }

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')
    const fd = new FormData(e.currentTarget)

    // Client-side validation for register
    if (mode === 'register') {
      const name = (fd.get('name') as string).trim()
      const email = (fd.get('email') as string).trim()
      const pwd = fd.get('password') as string
      const confirm = fd.get('confirm') as string
      const org = (fd.get('org') as string).trim()
      if (name.length < 2) { setError('Full name must be at least 2 characters.'); return }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError('Please enter a valid business email address.'); return }
      if (pwd.length < 8) { setError('Password must be at least 8 characters.'); return }
      if (pwd !== confirm) { setError('Password and Confirm Password do not match.'); return }
      if (org.length < 2) { setError('Business name must be at least 2 characters.'); return }
    }

    // Forgot password — UI only, no backend endpoint
    if (mode === 'forgot') {
      setBusy(true)
      await new Promise(r => setTimeout(r, 800)) // brief simulated delay
      setBusy(false)
      setForgotSent(true)
      return
    }

    setBusy(true)
    try {
      await api.csrf()
      if (mode === 'login') {
        await api.login(fd.get('email') as string, fd.get('password') as string)
      } else {
        await api.register(
          fd.get('name') as string,
          fd.get('email') as string,
          fd.get('password') as string,
          fd.get('org') as string,
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

  const headings = {
    login:    { eyebrow: 'RECEIVABLES, UNDER CONTROL', h1: 'Welcome Back', sub: 'Sign in to access your FinPilot AI workspace.' },
    register: { eyebrow: 'YOUR BUSINESS WORKSPACE',   h1: 'Create Account', sub: 'Register your business profile to get started.' },
    forgot:   { eyebrow: 'ACCOUNT RECOVERY',          h1: 'Reset Password', sub: 'Enter your registered email address.' },
  }
  const { eyebrow, h1, sub } = headings[mode]

  return (
    <main className="auth-shell">
      {/* -- Browser-chrome wrapper card -- */}
      <div className="auth-window">
        {/* Window title bar */}
        <div className="auth-titlebar">
          <span className="auth-titlebar-dot" style={{ background: '#ff5f57' }} />
          <span className="auth-titlebar-dot" style={{ background: '#febc2e' }} />
          <span className="auth-titlebar-dot" style={{ background: '#28c840' }} />
          <span className="auth-titlebar-label">FinPilot AI</span>
          <span className="auth-titlebar-spacer" />
          <ThemeToggle />
        </div>

        <div className="auth-columns">
          {/* -- LEFT: form column -- */}
          <div className="auth-left">
            {/* Brand */}
            <div className="auth-brand-row">
              <div className="auth-brand-icon"><Activity size={18} /></div>
              <span className="auth-brand-name">FinPilot <b>AI</b></span>
            </div>

            {/* Mode tabs (not shown on forgot screen) */}
            {mode !== 'forgot' && (
              <div className="auth-tabs">
                <button
                  type="button"
                  className={`auth-tab${mode === 'login' ? ' auth-tab-active' : ''}`}
                  onClick={() => switchMode('login')}
                >Login</button>
                <button
                  type="button"
                  className={`auth-tab${mode === 'register' ? ' auth-tab-active' : ''}`}
                  onClick={() => switchMode('register')}
                >Sign Up</button>
              </div>
            )}

            {/* Headings */}
            <div className="auth-eyebrow">{eyebrow}</div>
            <h1 className="auth-h1">{h1}</h1>
            <p className="auth-sub">{sub}</p>

            {/* Error banner */}
            {error && (
              <div className="auth-error-banner">
                <strong>{mode === 'login' ? 'Authentication failed' : mode === 'register' ? 'Registration failed' : 'Error'}</strong>
                <span>{error}</span>
              </div>
            )}

            {/* Forgot-password success banner */}
            {forgotSent && (
              <div className="auth-success-banner">
                <strong>Check your inbox</strong>
                <span>If an account exists for that email, you'll receive reset instructions shortly. (Email delivery is not yet active in this build.)</span>
              </div>
            )}

            {/* Form */}
            {!forgotSent && (
              <form onSubmit={handle} className="auth-form">
                {mode === 'register' && (
                  <>
                    <div className="auth-field">
                      <label htmlFor="fp-name">Full Name</label>
                      <input id="fp-name" name="name" type="text" placeholder="e.g. Ankit Sharma" required autoComplete="name" />
                    </div>
                    <div className="auth-field">
                      <label htmlFor="fp-org">Business Name</label>
                      <input id="fp-org" name="org" type="text" placeholder="Your company" required />
                    </div>
                  </>
                )}

                <div className="auth-field">
                  <label htmlFor="fp-email">{mode === 'login' ? 'Registered Email' : 'Business Email'}</label>
                  <input id="fp-email" name="email" type="email" placeholder="you@company.com" required autoComplete="username" />
                </div>

                {mode !== 'forgot' && (
                  <div className="auth-field">
                    <div className="auth-field-row">
                      <label htmlFor="fp-password">Password</label>
                      {mode === 'login' && (
                        <button type="button" className="auth-forgot-link" onClick={() => switchMode('forgot')}>
                          Forgot Password?
                        </button>
                      )}
                    </div>
                    <div className="auth-password-wrap">
                      <input
                        id="fp-password"
                        name="password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder={mode === 'login' ? '••••••••' : 'Minimum 8 characters'}
                        required
                        autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                      />
                      <button
                        type="button"
                        className="auth-eye-btn"
                        onClick={() => setShowPassword(v => !v)}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                            <line x1="1" y1="1" x2="23" y2="23" />
                          </svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {mode === 'register' && (
                  <div className="auth-field">
                    <label htmlFor="fp-confirm">Confirm Password</label>
                    <div className="auth-password-wrap">
                      <input
                        id="fp-confirm"
                        name="confirm"
                        type={showConfirm ? 'text' : 'password'}
                        placeholder="Re-enter your password"
                        required
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        className="auth-eye-btn"
                        onClick={() => setShowConfirm(v => !v)}
                        aria-label={showConfirm ? 'Hide password' : 'Show password'}
                      >
                        {showConfirm ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                            <line x1="1" y1="1" x2="23" y2="23" />
                          </svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )}

                {mode === 'login' && (
                  <label className="auth-remember">
                    <input type="checkbox" defaultChecked />
                    <span>Remember Me</span>
                  </label>
                )}

                <button className="auth-submit-btn" disabled={busy}>
                  {busy
                    ? (mode === 'login' ? 'Authenticating...' : mode === 'register' ? 'Creating Account...' : 'Sending...')
                    : (mode === 'login' ? 'Login' : mode === 'register' ? 'Create Account & Continue ?' : 'Send Reset Instructions')}
                </button>
              </form>
            )}

            {/* Google OAuth Button */}
            {mode !== 'forgot' && (
              <>
                <div className="auth-divider">or</div>
                
                {googleError && (
                  <div className="auth-google-error">
                    <strong>Google Sign-In Error</strong>
                    <span>{googleError}</span>
                  </div>
                )}
                
                <button 
                  type="button" 
                  className="auth-google-btn" 
                  onClick={handleGoogleSignIn}
                  disabled={googleBusy}
                >
                  <svg className="google-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  {googleBusy ? 'Redirecting to Google...' : 'Continue with Google'}
                </button>
              </>
            )}

            {/* Bottom toggle link */}
            {mode === 'forgot' ? (
              <button type="button" className="auth-bottom-link" onClick={() => switchMode('login')}>
                ? Back to Login
              </button>
            ) : (
              <p className="auth-bottom-link">
                {mode === 'login'
                  ? <>Don't have an account? <button type="button" onClick={() => switchMode('register')}>Sign up</button></>
                  : <>Already have an account? <button type="button" onClick={() => switchMode('login')}>Login</button></>
                }
              </p>
            )}

            <div className="auth-left-foot">© FinPilot AI 2026</div>
          </div>

          {/* -- RIGHT: artwork column -- */}
          <div className="auth-right">
            <MarbleArtwork />
          </div>
        </div>
      </div>
    </main>
  )
}

// -- Create org screen ------------------------------------------------------

// Indian GST State Codes - matches backend products/gst.py
const INDIAN_STATES = [
  { code: '01', name: 'Jammu & Kashmir' },
  { code: '02', name: 'Himachal Pradesh' },
  { code: '03', name: 'Punjab' },
  { code: '04', name: 'Chandigarh' },
  { code: '05', name: 'Uttarakhand' },
  { code: '06', name: 'Haryana' },
  { code: '07', name: 'Delhi' },
  { code: '08', name: 'Rajasthan' },
  { code: '09', name: 'Uttar Pradesh' },
  { code: '10', name: 'Bihar' },
  { code: '11', name: 'Sikkim' },
  { code: '12', name: 'Arunachal Pradesh' },
  { code: '13', name: 'Nagaland' },
  { code: '14', name: 'Manipur' },
  { code: '15', name: 'Mizoram' },
  { code: '16', name: 'Tripura' },
  { code: '17', name: 'Meghalaya' },
  { code: '18', name: 'Assam' },
  { code: '19', name: 'West Bengal' },
  { code: '20', name: 'Jharkhand' },
  { code: '21', name: 'Odisha' },
  { code: '22', name: 'Chhattisgarh' },
  { code: '23', name: 'Madhya Pradesh' },
  { code: '24', name: 'Gujarat' },
  { code: '26', name: 'Dadra & Nagar Haveli and Daman & Diu' },
  { code: '27', name: 'Maharashtra' },
  { code: '29', name: 'Karnataka' },
  { code: '30', name: 'Goa' },
  { code: '31', name: 'Lakshadweep' },
  { code: '32', name: 'Kerala' },
  { code: '33', name: 'Tamil Nadu' },
  { code: '34', name: 'Puducherry' },
  { code: '35', name: 'Andaman & Nicobar Islands' },
  { code: '36', name: 'Telangana' },
  { code: '37', name: 'Andhra Pradesh' },
  { code: '38', name: 'Ladakh' },
]

function CreateOrgScreen({ user, onCreated, onLogout }: { user: User; onCreated: (org: Org) => void; onLogout: () => void }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [showSuccess, setShowSuccess] = useState(false)
  const [createdOrg, setCreatedOrg] = useState<Org | null>(null)

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const orgName = (fd.get('name') as string).trim()
    if (orgName.length < 2) { setErr('Organization name must be at least 2 characters.'); return }
    setBusy(true); setErr('')
    try {
      const org = await api.createOrg({
        name: orgName,
        business_email: (fd.get('business_email') as string) || '',
        contact_phone: (fd.get('phone') as string) || '',
        state: (fd.get('state') as string) || '',
        city: (fd.get('city') as string) || '',
        legal_name: orgName,
        structure: (fd.get('structure') as string) || '',
        industry: (fd.get('industry') as string) || '',
        org_size: (fd.get('org_size') as string) || '',
      })
      const me = await api.me()
      const found = me.organizations.find(o => o.id === org.id)
      if (found) {
        setCreatedOrg(found)
        setShowSuccess(true)
      }
    } catch (error) {
      setErr((error as Error).message)
    } finally { setBusy(false) }
  }

  return (
    <main className="org-setup-shell">
      <div className="auth-floating-toggle"><ThemeToggle /></div>
      <div className="org-setup-window">
        {/* -- LEFT aside: brand + feature cards -- */}
        <aside className="org-aside">
          {/* Logo */}
          <div className="org-aside-logo">
            <div className="org-aside-logo-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                <line x1="1" y1="10" x2="23" y2="10" />
              </svg>
            </div>
            <div>
              <div className="org-aside-brand">FinPilot <span>AI</span></div>
              <div className="org-aside-tagline">AUTONOMOUS CASHFLOW ENGINE</div>
            </div>
          </div>
          <div className="org-aside-badge">
            <span className="org-badge-dot" />
            Built for Indian MSME Working Capital
          </div>

          <h1 className="org-aside-h1">Set up your<br />organization</h1>
          <p className="org-aside-desc">Create your high-trust business workspace to reconcile ledgers, orchestrate smart payment nudges, and secure predictable liquidity.</p>

          {/* Feature cards */}
          <div className="org-feature-cards">
            <div className="org-feature-card">
              <div className="org-feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 0 1 4-4h14" />
                  <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 0 1-4 4H3" />
                </svg>
              </div>
              <div>
                <div className="org-feature-title">Track outstanding invoices</div>
                <div className="org-feature-body">Continuous zero-latency sync across TallyPrime, Zoho Books, Busy, and GSTN e-Invoice portals.</div>
              </div>
            </div>
            <div className="org-feature-card">
              <div className="org-feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
              </div>
              <div>
                <div className="org-feature-title">Simplify payment follow-ups</div>
                <div className="org-feature-body">Context-aware WhatsApp &amp; email follow-ups embed dynamic Bharat BillPay &amp; instant UPI autopay links.</div>
              </div>
            </div>
            <div className="org-feature-card">
              <div className="org-feature-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
                </svg>
              </div>
              <div>
                <div className="org-feature-title">Understand your cash flow</div>
                <div className="org-feature-body">Predictive collection algorithms quantify DSO variances and forecast 90-day cash positions.</div>
              </div>
            </div>
          </div>

          {/* Compliance footer */}
          <div className="org-compliance">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#27845F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>COMPLIANCE &amp; SECURITY STANDARDS</span>
            <p>256-bit bank-grade encryption · RBI Fair Practices Framework · ISO 27001 &amp; SOC2 Type II Certified</p>
          </div>
        </aside>

        {/* -- RIGHT section: form -- */}
        <section className="org-form-panel">
          {/* 3-step progress bar */}
          <div className="org-progress">
            <div className="org-progress-label">
              <span className="org-step-done">STEP 2 OF 3</span>
              <span className="org-step-next">Organization Setup · Next: Dashboard</span>
            </div>
            <div className="org-progress-bars">
              <div className="org-progress-bar org-progress-done" />
              <div className="org-progress-bar org-progress-active" />
              <div className="org-progress-bar org-progress-upcoming" />
            </div>
            <div className="org-progress-steps">
              <span className="org-step org-step-done-txt">? Sign In (Done)</span>
              <span className="org-step org-step-active-txt">Org Setup (Active)</span>
              <span className="org-step org-step-upcoming-txt">Step 3: Dashboard</span>
            </div>
          </div>

          <h2 className="org-form-h2">Organization details</h2>
          <p className="org-form-sub">Tell us a little about your business entity to configure your auto-reconciliation ledgers.</p>

          {err && (
            <div className="org-error-banner">
              <strong>Setup failed</strong>
              <span>{err}</span>
            </div>
          )}

          <form onSubmit={handle} className="org-form">
            {/* Row 1 */}
            <div className="org-form-row">
              <div className="org-field">
                <label htmlFor="of-name">Organization Name <span className="org-required">*</span></label>
                <input id="of-name" name="name" type="text" placeholder="e.g. Acme Tech Solutions Pvt Ltd" required />
              </div>
              <div className="org-field">
                <label htmlFor="of-email">Business Email <span className="org-required">*</span></label>
                <input id="of-email" name="business_email" type="email" placeholder="billing@company.com" defaultValue={user.email} required />
              </div>
            </div>

            {/* Row 2 */}
            <div className="org-form-row">
              <div className="org-field">
                <label htmlFor="of-phone">Phone Number <span className="org-required">*</span></label>
                <input id="of-phone" name="phone" type="tel" placeholder="e.g. +91 98234 11290" required />
              </div>
              <div className="org-field">
                <label htmlFor="of-structure">Business Structure <span className="org-required">*</span></label>
                <select id="of-structure" name="structure" required defaultValue="Private Limited Company">
                  <option>Private Limited Company</option>
                  <option>Sole Proprietorship</option>
                  <option>Partnership</option>
                  <option>LLP</option>
                  <option>Public Limited Company</option>
                  <option>Other</option>
                </select>
              </div>
            </div>

            {/* Row 3 */}
            <div className="org-form-row">
              <div className="org-field">
                <label htmlFor="of-industry">Industry Vertical <span className="org-required">*</span></label>
                <select id="of-industry" name="industry" required defaultValue="Manufacturing & Engineering">
                  <option>Manufacturing &amp; Engineering</option>
                  <option>Retail</option>
                  <option>Wholesale / Distribution</option>
                  <option>IT &amp; Software Services</option>
                  <option>Professional Services</option>
                  <option>Healthcare &amp; Pharma</option>
                  <option>Education</option>
                  <option>Other</option>
                </select>
              </div>
              <div className="org-field">
                <label htmlFor="of-size">Organization Size <span className="org-required">*</span></label>
                <select id="of-size" name="org_size" required defaultValue="11 - 50 employees">
                  <option>1 - 10 employees</option>
                  <option>11 - 50 employees</option>
                  <option>51 - 200 employees</option>
                  <option>201+ employees</option>
                </select>
              </div>
            </div>

            {/* Row 4: location */}
            <div className="org-form-row org-form-row-3">
              <div className="org-field">
                <label htmlFor="of-country">Country <span className="org-required">*</span></label>
                <input id="of-country" name="country" type="text" value="India" readOnly className="org-input-locked" />
              </div>
              <div className="org-field">
                <label htmlFor="of-state">State <span className="org-required">*</span></label>
                <select id="of-state" name="state" required defaultValue="">
                  <option value="" disabled>Select state</option>
                  {INDIAN_STATES.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}
                </select>
              </div>
              <div className="org-field">
                <label htmlFor="of-city">City <span className="org-required">*</span></label>
                <input id="of-city" name="city" type="text" placeholder="e.g. Pune" required />
              </div>
            </div>

            {/* Security note */}
            <div className="org-security-box">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#27845F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span>Your business data is stored under AES-256 encryption. Only verified organization owners and appointed finance controllers can view ledger records.</span>
            </div>

            <div className="org-form-actions">
              <button type="submit" className="org-submit-btn" disabled={busy}>
                {busy ? 'Creating Workspace...' : 'Create Organization ?'}
              </button>
              <button type="button" className="org-signout-btn" onClick={onLogout}>Sign out</button>
            </div>
          </form>

          {/* Success overlay */}
          {showSuccess && (
            <div className="org-success-overlay">
              <div className="org-success-content">
                <div className="org-success-icon">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#27845F" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <h2>Organization Configured!</h2>
                <p>Your workspace has been initialized with statutory MSME limits and ledger reconciliation rules.</p>
                <button
                  className="org-submit-btn"
                  onClick={() => { if (createdOrg) onCreated(createdOrg) }}
                >
                  Launch Dashboard ?
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

// -- Metric card ------------------------------------------------------------

function Metric({ icon, title, value, note, tone, onClick }: { icon: React.ReactNode; title: string; value: string | number; note: string; tone: string; onClick?: () => void }) {
  const inner = <>
    <div className="metric-top"><div className={`metric-icon ${tone}`}>{icon}</div></div>
    <div className="metric-title">{title}</div>
    <div className="metric-value">{value}</div>
    <div className="metric-note">{note}</div>
  </>
  if (onClick) return <button className="metric metric-clickable" onClick={onClick} type="button">{inner}</button>
  return <article className="metric">{inner}</article>
}

// -- Status badge -----------------------------------------------------------

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

// -- Invoice modal (line items + GST) ----------------------------------------

type InvoiceLine = {
  product: string; description: string; quantity: string
  unit_price_minor: string; discount_minor: string
  gst_rate_bps: number; gst_rate_name: string; hsn_sac: string
}

// -- Invoice View Modal (Clean Modern Style - Green Theme) -----------------
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
              <div className="invoice-modern-meta">Reminders: {invoice.no_reminders ? 'Disabled' : (invoice.reminder_schedule_name && invoice.reminder_schedule_name !== 'Default schedule' ? invoice.reminder_schedule_name : 'Default schedule')}</div>
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
                    <td style={{textAlign: 'right'}}>{fmtQty(item.quantity)}</td>
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
  const [reminderSchedule, setReminderSchedule] = useState<string>(editing?.reminder_schedule || '')
  const [noReminders, setNoReminders] = useState(editing?.no_reminders ?? false)
  const [schedules, setSchedules] = useState<ReminderSchedule[]>([])
  const [number, setNumber] = useState(editing?.invoice_number || '')
  const [invDate, setInvDate] = useState(editing?.invoice_date || new Date().toISOString().slice(0, 10))
  const [dueDate, setDueDate] = useState(editing?.due_date || '')
  const [invDiscount, setInvDiscount] = useState(String(editing?.discount_minor ?? 0))
  const [lines, setLines] = useState<InvoiceLine[]>(
    (editing?.items?.length
      ? editing.items.map(it => ({
          product: it.product || '', description: it.description, quantity: fmtQty(it.quantity),
          unit_price_minor: String(it.unit_price_minor), discount_minor: String(it.discount_minor),
          gst_rate_bps: it.gst_rate_bps, gst_rate_name: it.gst_rate_name, hsn_sac: it.hsn_sac,
        }))
      : [{
          product: '', description: '', quantity: '1', unit_price_minor: '0',
          discount_minor: '0', gst_rate_bps: 0, gst_rate_name: 'No GST', hsn_sac: '',
        }])
  )

  const activeRates = gstRates.filter(r => r.active)

  // Load active schedules for the dropdown
  useEffect(() => {
    api.getActiveSchedules(orgId)
      .then(r => setSchedules(r.results.filter(s => s.enabled && !s.archived)))
      .catch(() => {})
  }, [orgId])

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
      reminder_schedule: noReminders ? null : (reminderSchedule || null),
      no_reminders: noReminders,
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

            {/* Reminder Schedule */}
            <div className="invoice-form-clean-grid" style={{ gridTemplateColumns: '1fr' }}>
              <div className="invoice-form-clean-col">
                <label className="invoice-form-clean-label">Reminder schedule</label>
                <select
                  className="invoice-form-clean-input"
                  value={noReminders ? '__none__' : (reminderSchedule || '__default__')}
                  onChange={e => {
                    if (e.target.value === '__none__') {
                      setNoReminders(true)
                      setReminderSchedule('')
                    } else if (e.target.value === '__default__') {
                      setNoReminders(false)
                      setReminderSchedule('')
                    } else {
                      setNoReminders(false)
                      setReminderSchedule(e.target.value)
                    }
                  }}
                >
                  <option value="__default__">
                    Use default schedule{schedules.find(s => s.is_default) ? ` (${schedules.find(s => s.is_default)!.name})` : ''}
                  </option>
                  <option value="__none__">No reminders</option>
                  {schedules.filter(s => !s.is_default).map(s => (
                    <option key={s.id} value={s.id}>{s.name}{s.step_count ? ` · ${s.step_count} step${s.step_count !== 1 ? 's' : ''}` : ''}</option>
                  ))}
                </select>
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

// -- Customer modal ---------------------------------------------------------

function CustomerModal({ orgId, onClose, onCreated, editing }: { orgId: string; onClose: () => void; onCreated: () => void; editing: Customer | null }) {
  const isEdit = !!editing
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [warnings, setWarnings] = useState<string[]>([])
  const [name, setName] = useState(editing?.name || '')
  const [contactName, setContactName] = useState(editing?.contact_name || '')
  const [email, setEmail] = useState(editing?.email || '')
  const [phone, setPhone] = useState(editing?.phone || '')
  const [billingAddress, setBillingAddress] = useState(editing?.billing_address || '')
  const [gstin, setGstin] = useState(editing?.gstin || '')
  const [state, setState] = useState(editing?.state || '')
  const [paymentTerms, setPaymentTerms] = useState(String(editing?.payment_terms_days || 30))
  const [notes, setNotes] = useState(editing?.notes || '')
  const [active, setActive] = useState(editing?.active ?? true)

  const handle = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setBusy(true); setErr(''); setWarnings([])
    try {
      const data: Partial<Customer> = {
        name: name.trim(),
        contact_name: contactName.trim(),
        email: email.trim(),
        phone: phone.trim(),
        billing_address: billingAddress.trim(),
        gstin: gstin.trim().toUpperCase(),
        state,
        payment_terms_days: parseInt(paymentTerms) || 30,
        notes: notes.trim(),
        active,
      }
      let response: Customer & { warnings?: string[] }
      if (isEdit && editing) {
        response = await api.updateCustomer(orgId, editing.id, data) as Customer & { warnings?: string[] }
      } else {
        response = await api.createCustomer(orgId, data) as Customer & { warnings?: string[] }
      }
      if (response.warnings && response.warnings.length > 0) {
        setWarnings(response.warnings)
        setBusy(false)
        return
      }
      onCreated(); onClose()
    } catch (e: unknown) { setErr((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <section className="modal" style={{ width: 'min(700px, 95%)' }}>
        <div className="modal-head">
          <div><div className="eyebrow">CUSTOMERS</div><h2>{isEdit ? 'Edit customer' : 'Add a customer'}</h2></div>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handle}>
          <label>Customer name *<input value={name} onChange={e => setName(e.target.value)} placeholder="Business or individual name" required /></label>
          <label>Contact person<input value={contactName} onChange={e => setContactName(e.target.value)} placeholder="e.g. Rajesh Kumar" /></label>
          <div className="form-row">
            <label>Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="accounts@customer.in" /></label>
            <label>Phone<input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+91 98765 43210" /></label>
          </div>
          <label>Billing address<textarea rows={3} value={billingAddress} onChange={e => setBillingAddress(e.target.value)} placeholder="Street address, city, state, PIN" /></label>
          <div className="form-row">
            <label>GSTIN<input value={gstin} onChange={e => setGstin(e.target.value)} placeholder="22AAAAA0000A1Z5" maxLength={15} /></label>
            <label>State
              <select value={state} onChange={e => setState(e.target.value)}>
                <option value="">Select state</option>
                {INDIAN_STATES.map(s => <option key={s.code} value={s.code}>{s.name}</option>)}
              </select>
            </label>
          </div>
          <label>Payment terms (days)<input type="number" min="0" value={paymentTerms} onChange={e => setPaymentTerms(e.target.value)} placeholder="30" /></label>
          <label>Notes<textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Internal notes about this customer" /></label>
          {isEdit && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input type="checkbox" checked={active} onChange={e => setActive(e.target.checked)} />
              <span>Active (uncheck to deactivate)</span>
            </label>
          )}
          {warnings.length > 0 && (
            <div style={{ background: '#fff4e6', border: '1px solid #ff9800', padding: '12px', borderRadius: '6px', marginTop: '12px' }}>
              <strong style={{ color: '#e65100' }}>⚠️ Warning</strong>
              <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px', color: '#e65100' }}>
                {warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              <button type="button" className="secondary" style={{ marginTop: '8px', width: '100%' }} onClick={() => setWarnings([])}>
                Dismiss and continue
              </button>
            </div>
          )}
          {err && <div className="form-error">{err}</div>}
          <div className="modal-foot">
            <button type="button" className="secondary" onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy}>{isEdit ? (busy ? 'Saving…' : 'Save changes') : (busy ? 'Adding…' : 'Add customer')}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

// -- Payment modal ----------------------------------------------------------

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
            <label>Amount (?)<input name="amount" type="number" min="0.01" step="0.01" required placeholder="0.00" /></label>
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

// -- GST rate modal (with live preview) -------------------------------------

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

// -- Product modal ----------------------------------------------------------

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
            <label>Price (?)<input type="number" min="0.01" step="0.01" value={price} onChange={e => setPrice(e.target.value)} placeholder="0.00" required /></label>
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

// -- Products page (tabs: Products / GST Rates) ------------------------------

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

// -- Main App ---------------------------------------------------------------



// -- Reminders Page Component --

// ========== REMINDERS PAGE COMPONENT ==========

// Renders an iframe that grows to fit its own content, so it never shows an
// internal scrollbar. The surrounding container (e.g. a modal body) becomes
// the single scroll region. Works with `srcDoc` content, which is same-origin,
// so we can read the document's scrollHeight and observe layout changes.
function AutoHeightIframe({
  srcDoc,
  title,
  background = 'white',
}: {
  srcDoc: string
  title: string
  background?: string
}) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const roRef = useRef<ResizeObserver | null>(null)

  const measure = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe) return
    try {
      const doc = iframe.contentDocument
      if (!doc) return
      const h = Math.max(
        doc.body?.scrollHeight ?? 0,
        doc.documentElement?.scrollHeight ?? 0,
      )
      // Avoid feedback loops / layout thrash: only update on a real change.
      const current = parseInt(iframe.style.height, 10)
      if (h > 0 && h !== current) iframe.style.height = `${h}px`
    } catch {
      // contentDocument unavailable (cross-origin / not loaded yet) — skip.
    }
  }, [])

  useEffect(() => {
    const iframe = iframeRef.current
    if (!iframe) return

    const attach = () => {
      measure()
      const doc = iframe.contentDocument
      if (!doc) return
      try {
        roRef.current?.disconnect()
        const ro = new ResizeObserver(() => measure())
        if (doc.documentElement) ro.observe(doc.documentElement)
        if (doc.body) ro.observe(doc.body)
        roRef.current = ro
        // Re-measure when images finish loading (late layout shifts).
        doc.querySelectorAll('img').forEach((img) => {
          if (!img.complete) img.addEventListener('load', measure, { once: true })
        })
      } catch {
        /* ignore */
      }
    }

    iframe.addEventListener('load', attach)
    // Cover the case where load already fired (e.g. cached/empty content).
    attach()

    return () => {
      iframe.removeEventListener('load', attach)
      roRef.current?.disconnect()
      roRef.current = null
    }
  }, [srcDoc, measure])

  return (
    <iframe
      ref={iframeRef}
      srcDoc={srcDoc}
      title={title}
      scrolling="no"
      style={{ width: '100%', border: 'none', background, display: 'block' }}
    />
  )
}

// ========== SCHEDULE FORM MODAL ==========
type StepDraft = {
  id: string
  basis: 'issue' | 'due'
  kind: 'on' | 'before' | 'after'
  days: number
  template: string
  templateName: string
}

function timingLabel(s: StepDraft): string {
  if (s.basis === 'issue') {
    return s.days === 0 ? 'On invoice issue date' : `${s.days} day${s.days !== 1 ? 's' : ''} after invoice issue`
  }
  if (s.kind === 'on') return 'On the due date'
  if (s.kind === 'before') return `${s.days} day${s.days !== 1 ? 's' : ''} before due date`
  return `${s.days} day${s.days !== 1 ? 's' : ''} after due date`
}

function newStep(): StepDraft {
  return { id: Math.random().toString(36).slice(2), basis: 'due', kind: 'on', days: 0, template: '', templateName: '' }
}

function ScheduleFormModal({
  org,
  schedule,
  onSaved,
  onClose,
}: {
  org: { id: string }
  schedule: (ReminderSchedule & { steps: ReminderStep[] }) | null
  onSaved: (s: ReminderSchedule) => void
  onClose: () => void
}) {
  const [name, setName] = useState(schedule?.name ?? '')
  const [steps, setSteps] = useState<StepDraft[]>(() => {
    if (schedule && schedule.steps && schedule.steps.length > 0) {
      return schedule.steps.map(st => {
        const basis: 'issue' | 'due' = st.offset_from_issue !== null ? 'issue' : 'due'
        const raw = basis === 'issue' ? (st.offset_from_issue ?? 0) : (st.offset_from_due ?? 0)
        let kind: 'on' | 'before' | 'after' = 'on'
        let days = 0
        if (basis === 'due') {
          if (raw === 0) { kind = 'on'; days = 0 }
          else if (raw < 0) { kind = 'before'; days = Math.abs(raw) }
          else { kind = 'after'; days = raw }
        } else {
          days = raw
        }
        return { id: Math.random().toString(36).slice(2), basis, kind, days, template: st.template, templateName: st.template_name }
      })
    }
    return [newStep()]
  })
  const [templates, setTemplates] = useState<ReminderTemplate[]>([])
  const [saving, setSaving] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState('')
  const isEdit = !!schedule

  useEffect(() => {
    api.reminderTemplates(org.id)
      .then(r => setTemplates(r.results.filter(t => t.active && t.channel === 'email')))
      .catch(() => {})
  }, [org.id])

  const setStep = (id: string, patch: Partial<StepDraft>) =>
    setSteps(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s))

  const addStep = () => {
    if (steps.length >= 10) return
    setSteps(prev => [...prev, newStep()])
  }

  const removeStep = (id: string) => setSteps(prev => prev.filter(s => s.id !== id))

  const moveUp = (idx: number) => {
    if (idx === 0) return
    setSteps(prev => { const a = [...prev]; [a[idx - 1], a[idx]] = [a[idx], a[idx - 1]]; return a })
  }

  const moveDown = (idx: number) => {
    if (idx === steps.length - 1) return
    setSteps(prev => { const a = [...prev]; [a[idx], a[idx + 1]] = [a[idx + 1], a[idx]]; return a })
  }

  const validate = (): boolean => {
    const errs: Record<string, string> = {}
    if (!name.trim()) errs['name'] = 'Schedule name is required.'
    if (steps.length === 0) errs['steps'] = 'Add at least one step.'
    const seen = new Set<string>()
    steps.forEach((s, i) => {
      if (!s.template) errs[`step_${i}_template`] = 'Choose a template.'
      if (s.basis === 'due' && s.kind !== 'on' && s.days <= 0) errs[`step_${i}_days`] = 'Enter a number greater than 0.'
      if (s.basis === 'issue' && s.days < 0) errs[`step_${i}_days`] = 'Days cannot be negative.'
      if (s.days > 365) errs[`step_${i}_days`] = 'Maximum is 365 days.'
      const key = s.basis === 'issue' ? `issue:${s.days}` : `due:${s.kind === 'before' ? -s.days : s.kind === 'on' ? 0 : s.days}`
      if (seen.has(key)) errs[`step_${i}_timing`] = 'Another step already uses this timing.'
      seen.add(key)
    })
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async () => {
    if (!validate()) return
    setSaving(true)
    setSubmitError('')
    const payload = {
      name: name.trim(),
      steps: steps.map(s => ({
        basis: s.basis,
        kind: s.kind,
        days: s.days,
        template: s.template,
      } as ScheduleStepInput)),
    }
    try {
      let saved: ReminderSchedule
      if (isEdit && schedule) {
        saved = await api.updateScheduleWithSteps(org.id, schedule.id, payload)
      } else {
        saved = await api.createScheduleWithSteps(org.id, payload)
      }
      onSaved(saved)
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Could not save. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const iStyle: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box', padding: '8px 12px',
    border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '14px',
    fontFamily: 'inherit', outline: 'none',
  }
  const eStyle: React.CSSProperties = { fontSize: '12px', color: '#dc2626', marginTop: '4px' }
  const lStyle: React.CSSProperties = { fontSize: '13px', fontWeight: 600, color: '#374151', display: 'block', marginBottom: '6px' }

  return (
    <div
      role="presentation"
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '16px' }}
      onClick={e => { if (e.target === e.currentTarget && !saving) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="sfm-title"
        style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', boxShadow: '0 20px 60px rgba(0,0,0,0.18)', width: '100%', maxWidth: '680px', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
          <h2 id="sfm-title" style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
            {isEdit ? 'Edit Schedule' : 'New Reminder Schedule'}
          </h2>
          <button onClick={onClose} disabled={saving} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#6b7280', padding: '4px' }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1, padding: '24px' }}>
          <div style={{ marginBottom: '24px' }}>
            <label htmlFor="sfm-name" style={lStyle}>Schedule name</label>
            <input
              id="sfm-name"
              value={name}
              onChange={e => { setName(e.target.value); setFieldErrors(p => ({ ...p, name: '' })) }}
              placeholder="e.g. Standard Payment Reminders"
              style={{ ...iStyle, borderColor: fieldErrors.name ? '#dc2626' : '#d1d5db' }}
            />
            {fieldErrors.name && <div style={eStyle}>{fieldErrors.name}</div>}
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ ...lStyle, margin: 0 }}>Steps ({steps.length}/10)</span>
              <button
                onClick={addStep}
                disabled={steps.length >= 10}
                style={{ padding: '6px 14px', background: steps.length >= 10 ? '#f3f4f6' : '#3b82f6', color: steps.length >= 10 ? '#9ca3af' : 'white', border: 'none', borderRadius: '6px', cursor: steps.length >= 10 ? 'not-allowed' : 'pointer', fontSize: '13px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Plus size={14} /> Add step
              </button>
            </div>
            {fieldErrors.steps && <div style={{ ...eStyle, marginBottom: '8px' }}>{fieldErrors.steps}</div>}

            {steps.map((step, idx) => (
              <div key={step.id} style={{ background: '#f9fafb', border: `1px solid ${fieldErrors[`step_${idx}_timing`] ? '#fca5a5' : '#e5e7eb'}`, borderRadius: '8px', padding: '16px', marginBottom: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>Step {idx + 1}</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button onClick={() => moveUp(idx)} disabled={idx === 0} title="Move up" style={{ background: 'none', border: '1px solid #e5e7eb', borderRadius: '4px', cursor: idx === 0 ? 'default' : 'pointer', padding: '4px 6px', color: idx === 0 ? '#d1d5db' : '#6b7280' }}><ChevronUp size={14} /></button>
                    <button onClick={() => moveDown(idx)} disabled={idx === steps.length - 1} title="Move down" style={{ background: 'none', border: '1px solid #e5e7eb', borderRadius: '4px', cursor: idx === steps.length - 1 ? 'default' : 'pointer', padding: '4px 6px', color: idx === steps.length - 1 ? '#d1d5db' : '#6b7280' }}><ChevronDown size={14} /></button>
                    <button onClick={() => removeStep(step.id)} disabled={steps.length === 1} title="Remove step" style={{ background: 'none', border: '1px solid #e5e7eb', borderRadius: '4px', cursor: steps.length === 1 ? 'default' : 'pointer', padding: '4px 6px', color: steps.length === 1 ? '#d1d5db' : '#dc2626' }}><X size={14} /></button>
                  </div>
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <label style={lStyle}>When to send</label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    <select
                      value={step.basis}
                      onChange={e => {
                        const b = e.target.value as 'issue' | 'due'
                        setStep(step.id, { basis: b, kind: 'on', days: 0 })
                        setFieldErrors(p => ({ ...p, [`step_${idx}_timing`]: '', [`step_${idx}_days`]: '' }))
                      }}
                      style={iStyle}
                    >
                      <option value="due">Relative to due date</option>
                      <option value="issue">Relative to invoice issue date</option>
                    </select>

                    {step.basis === 'due' ? (
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <select
                          value={step.kind}
                          onChange={e => {
                            const k = e.target.value as 'on' | 'before' | 'after'
                            setStep(step.id, { kind: k, days: k === 'on' ? 0 : step.days || 1 })
                            setFieldErrors(p => ({ ...p, [`step_${idx}_days`]: '' }))
                          }}
                          style={{ ...iStyle, flex: '0 0 auto', width: 'auto' }}
                        >
                          <option value="on">On the due date</option>
                          <option value="before">Before due date</option>
                          <option value="after">After due date</option>
                        </select>
                        {step.kind !== 'on' && (
                          <input
                            type="number"
                            min={1}
                            max={365}
                            value={step.days}
                            onChange={e => {
                              setStep(step.id, { days: Math.max(1, parseInt(e.target.value) || 1) })
                              setFieldErrors(p => ({ ...p, [`step_${idx}_days`]: '' }))
                            }}
                            style={{ ...iStyle, width: '80px', flexShrink: 0, borderColor: fieldErrors[`step_${idx}_days`] ? '#dc2626' : '#d1d5db' }}
                          />
                        )}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <input
                          type="number"
                          min={0}
                          max={365}
                          value={step.days}
                          onChange={e => {
                            setStep(step.id, { days: Math.max(0, parseInt(e.target.value) || 0) })
                            setFieldErrors(p => ({ ...p, [`step_${idx}_days`]: '' }))
                          }}
                          style={{ ...iStyle, width: '80px', borderColor: fieldErrors[`step_${idx}_days`] ? '#dc2626' : '#d1d5db' }}
                        />
                        <span style={{ fontSize: '13px', color: '#6b7280', whiteSpace: 'nowrap' }}>days after issue</span>
                      </div>
                    )}
                  </div>
                  {fieldErrors[`step_${idx}_days`] && <div style={eStyle}>{fieldErrors[`step_${idx}_days`]}</div>}
                  {fieldErrors[`step_${idx}_timing`] && <div style={eStyle}>{fieldErrors[`step_${idx}_timing`]}</div>}
                  <div style={{ marginTop: '6px', fontSize: '12px', color: '#3b82f6', fontWeight: 500 }}>
                    {timingLabel(step)}
                  </div>
                </div>

                <div style={{ marginBottom: '12px' }}>
                  <label style={lStyle}>Channel</label>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <div style={{ padding: '7px 14px', background: '#eff6ff', border: '2px solid #3b82f6', borderRadius: '6px', fontSize: '13px', fontWeight: 600, color: '#1d4ed8' }}>
                      Email
                    </div>
                    <div title="Coming soon" style={{ padding: '7px 14px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '6px', fontSize: '13px', color: '#9ca3af', cursor: 'not-allowed' }}>
                      WhatsApp <span style={{ fontSize: '11px', background: '#f3f4f6', borderRadius: '4px', padding: '1px 5px' }}>coming soon</span>
                    </div>
                  </div>
                </div>

                <div>
                  <label style={lStyle}>Message template</label>
                  <select
                    value={step.template}
                    onChange={e => {
                      const t = templates.find(x => x.id === e.target.value)
                      setStep(step.id, { template: e.target.value, templateName: t?.name ?? '' })
                      setFieldErrors(p => ({ ...p, [`step_${idx}_template`]: '' }))
                    }}
                    style={{ ...iStyle, borderColor: fieldErrors[`step_${idx}_template`] ? '#dc2626' : '#d1d5db' }}
                  >
                    <option value="">— choose a template —</option>
                    {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                  {fieldErrors[`step_${idx}_template`] && <div style={eStyle}>{fieldErrors[`step_${idx}_template`]}</div>}
                  {templates.length === 0 && (
                    <div style={{ marginTop: '6px', fontSize: '12px', color: '#f59e0b' }}>
                      No active email templates found. Create one in the Reminders templates section first.
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: '16px 24px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0, gap: '12px' }}>
          <div style={{ flex: 1 }}>
            {submitError && <div style={{ fontSize: '13px', color: '#dc2626' }}>{submitError}</div>}
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={onClose} disabled={saving} style={{ padding: '9px 20px', background: 'white', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#374151' }}>
              Cancel
            </button>
            <button onClick={handleSubmit} disabled={saving} style={{ padding: '9px 20px', background: saving ? '#93c5fd' : '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: saving ? 'not-allowed' : 'pointer', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              {saving && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
              {saving ? 'Saving...' : isEdit ? 'Save changes' : 'Create schedule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}



// ── Notification display helpers ──────────────────────────────────────────

function notifTitle(n: Notification): string {
  switch (n.event_type) {
    case 'reminder_approval': return 'Reminder Awaiting Approval'
    case 'reminder_failed':   return 'Reminder Delivery Failed'
    case 'import_complete':   return 'Import Completed'
    case 'import_failed':     return 'Import Failed'
    case 'reconciliation_review': return 'Reconciliation Needs Review'
    case 'forecast_failed':   return 'Forecast Failed'
    case 'subscription_changed': return 'Subscription Changed'
    case 'security_event':    return 'Security Event'
    case 'membership_changed': return 'Team Membership Changed'
    case 'payment_gateway':   return 'Payment Gateway Event'
    default: return n.event_type.replace(/_/g, ' ')
  }
}

function buildDetailLine(n: Notification, d: NotificationDetails): string {
  if (d.error === 'details_unavailable') return 'Details no longer available'
  switch (n.event_type) {
    case 'reminder_approval': {
      if (!d.customer_name && !d.invoice_number) return ''
      const name = d.customer_name || 'Customer'
      const inv  = d.invoice_number ? `Invoice ${d.invoice_number}` : ''
      const amt  = d.outstanding_minor != null ? `, ${money(d.outstanding_minor)} due` : ''
      const over = d.days_overdue && d.days_overdue > 0
        ? `, ${d.days_overdue} day${d.days_overdue !== 1 ? 's' : ''} overdue`
        : (d.due_date ? `, due ${fmtDate(d.due_date)}` : '')
      const step = d.step_label ? ` · ${d.step_label}` : ''
      return `${name}${inv ? ' · ' + inv : ''}${amt}${over}${step}`
    }
    case 'reminder_failed': {
      const name = d.customer_name || ''
      const inv  = d.invoice_number ? `Invoice ${d.invoice_number}` : ''
      const reason = d.block_reason ? ` — ${d.block_reason}` : ''
      return [name, inv].filter(Boolean).join(' · ') + reason
    }
    case 'import_complete': {
      const file = d.file_name || 'File'
      const type = d.batch_type === 'bank_statement' ? 'bank statement' : 'invoices'
      const rows = d.rows_created != null ? ` · ${d.rows_created} created` : ''
      const rej  = d.rows_rejected && d.rows_rejected > 0 ? `, ${d.rows_rejected} rejected` : ''
      return `${file} (${type})${rows}${rej}`
    }
    case 'import_failed': {
      const file = d.file_name || 'Import failed'
      const rej  = d.rows_rejected && d.rows_rejected > 0 ? ` · ${d.rows_rejected} rows failed` : ''
      return `${file}${rej}`
    }
    case 'reconciliation_review': {
      const u = d.unmatched_count ?? 0
      const s = d.suggested_count ?? 0
      if (u === 0 && s === 0) return 'Transactions need review'
      const parts: string[] = []
      if (u > 0) parts.push(`${u} unmatched`)
      if (s > 0) parts.push(`${s} with suggestions`)
      return parts.join(', ') + ' — open Reconciliation to review'
    }
    default:
      return ''
  }
}

function notifTarget(n: Notification): 'reminders' | 'reconciliation' | 'import' | null {
  switch (n.event_type) {
    case 'reminder_approval':
    case 'reminder_failed':
      return 'reminders'
    case 'reconciliation_review':
      return 'reconciliation'
    case 'import_complete':
    case 'import_failed':
      return 'import'
    default:
      return null
  }
}
// ── NotificationsPage helpers ─────────────────────────────────────────────

function relativeTime(isoStr: string): string {
  const diff = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  if (hrs < 48) return 'yesterday'
  return new Date(isoStr).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })
}

function notifIconColor(eventType: string, read: boolean): 'amber' | 'red' | 'green' | 'blue' | 'slate' {
  if (read) return 'slate'
  switch (eventType) {
    case 'reminder_approval': return 'amber'
    case 'reminder_failed': return 'red'
    case 'import_complete': return 'green'
    case 'import_failed': return 'red'
    case 'reconciliation_review': return 'blue'
    default: return 'slate'
  }
}

function NotifIcon({ eventType }: { eventType: string }) {
  switch (eventType) {
    case 'reminder_failed': return <AlertCircle size={18} />
    case 'import_complete': return <CheckCircle size={18} />
    case 'import_failed': return <AlertCircle size={18} />
    case 'reconciliation_review': return <RefreshCw size={18} />
    default: return <Bell size={18} />
  }
}

function notifStatusPill(n: Notification): { label: string; cls: string } | null {
  const d = n.details || {}
  if (n.event_type === 'reminder_approval') {
    return n.read
      ? { label: 'Read', cls: 'notif-pill-slate' }
      : { label: 'Action needed', cls: 'notif-pill-amber' }
  }
  if (n.event_type === 'reminder_failed') return { label: 'Failed', cls: 'notif-pill-red' }
  if (n.event_type === 'reconciliation_review') return { label: 'Needs review', cls: 'notif-pill-blue' }
  if (d.days_overdue && d.days_overdue > 0) return { label: `${d.days_overdue}d overdue`, cls: 'notif-pill-red' }
  return null
}

function groupNotifsByDate(notifs: Notification[]): { label: string; items: Notification[] }[] {
  const now = new Date()
  const todayStr = now.toLocaleDateString()
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const yesterdayStr = yesterday.toLocaleDateString()
  const weekAgo = new Date(now)
  weekAgo.setDate(weekAgo.getDate() - 7)

  const buckets: Record<string, Notification[]> = {}
  for (const n of notifs) {
    const d = new Date(n.created_at)
    const dStr = d.toLocaleDateString()
    let label: string
    if (dStr === todayStr) label = 'TODAY'
    else if (dStr === yesterdayStr) label = 'YESTERDAY'
    else if (d >= weekAgo) label = 'EARLIER THIS WEEK'
    else label = 'EARLIER'
    if (!buckets[label]) buckets[label] = []
    buckets[label].push(n)
  }

  const order = ['TODAY', 'YESTERDAY', 'EARLIER THIS WEEK', 'EARLIER']
  return order.filter(l => buckets[l]).map(l => ({ label: l, items: buckets[l] }))
}

// ── NotificationsPage component ───────────────────────────────────────────

function NotificationsPage({
  notifications,
  unreadCount,
  org: _org,
  onNotifClick,
  onMarkAllRead,
  onApproveJob,
}: {
  notifications: Notification[]
  unreadCount: number
  org: Org
  onNotifClick: (n: Notification) => Promise<void>
  onMarkAllRead: () => Promise<void>
  onApproveJob: (jobId: string) => void
}) {
  const [tab, setTab] = useState<'all' | 'unread' | 'approvals' | 'overdue'>('all')
  const [search, setSearch] = useState('')
  const [selectedNotif, setSelectedNotif] = useState<Notification | null>(null)
  const [notifLoading] = useState(false)

  const hasApprovalUnread = notifications.some(n => n.event_type === 'reminder_approval' && !n.read)

  const tabCounts = {
    all: notifications.length,
    unread: notifications.filter(n => !n.read).length,
    approvals: notifications.filter(n => n.event_type === 'reminder_approval').length,
    overdue: notifications.filter(n =>
      n.event_type === 'reminder_failed' || (n.details?.days_overdue != null && n.details.days_overdue > 0)
    ).length,
  }

  const filtered = notifications
    .filter(n => {
      if (tab === 'unread') return !n.read
      if (tab === 'approvals') return n.event_type === 'reminder_approval'
      if (tab === 'overdue') return n.event_type === 'reminder_failed' || (n.details?.days_overdue != null && n.details.days_overdue > 0)
      return true
    })
    .filter(n => {
      if (!search.trim()) return true
      const q = search.toLowerCase()
      const name = (n.details?.customer_name || '').toLowerCase()
      const inv = (n.details?.invoice_number || '').toLowerCase()
      return name.includes(q) || inv.includes(q)
    })
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const groups = groupNotifsByDate(filtered)

  const todayLabel = new Date().toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  }).toUpperCase()

  const handleRowClick = async (n: Notification) => {
    setSelectedNotif(n)
    await onNotifClick(n)
  }

  // Inspector panel
  const insp = selectedNotif
  const inspD = insp?.details || {}

  return (
    <div className="notif-page">
      {/* Header */}
      <div className="notif-page-header">
        <div>
          <div style={{ fontSize: 12, color: '#A8B5C6', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 2 }}>
            {todayLabel}
          </div>
          <h1 className="notif-page-title">Notifications</h1>
          <p className="notif-page-subtitle">
            Review pending reminder approvals, overdue alerts, and incoming payments.
          </p>
        </div>
        <div className="notif-page-actions">
          <button
            className="secondary"
            style={{ background: 'rgba(21, 27, 43, 0.6)', border: '1px solid #2A3448' }}
            onClick={onMarkAllRead}
          >
            Mark all read
          </button>
          {hasApprovalUnread && (
            <button
              className="notif-approve-cta"
              onClick={() => onApproveJob('')}
            >
              Approve all pending
            </button>
          )}
        </div>
      </div>

      {/* Tabs + search toolbar */}
      <div className="notif-toolbar notif-tabs-row" style={{ marginBottom: 16, background: 'rgba(21,27,43,0.72)', border: '1px solid #2A3448', borderRadius: '10px 10px 0 0' }}>
        {(['all', 'unread', 'approvals', 'overdue'] as const).map(t => (
          <button
            key={t}
            className={`notif-tab${tab === t ? ' active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
            <span className={`notif-tab-count${t === 'unread' && tabCounts.unread > 0 ? ' unread-pill' : ''}`}>
              {tabCounts[t]}
            </span>
          </button>
        ))}
        <div className="notif-search-wrap">
          <Search size={13} className="notif-search-icon" />
          <input
            className="notif-search"
            placeholder="Search customer or invoice..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Layout: feed + inspector */}
      <div className="notif-layout">
        {/* Feed */}
        <div className="notif-feed">
          <div className="notif-feed-inner">
            {notifLoading && (
              <>
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="notif-skeleton-row">
                    <div className="notif-skeleton-icon" style={{ animation: 'pulse 1.5s infinite' }} />
                    <div className="notif-skeleton-body">
                      <div className="notif-skeleton-line" style={{ width: '60%', animation: 'pulse 1.5s infinite' }} />
                      <div className="notif-skeleton-line" style={{ width: '80%', animation: 'pulse 1.5s infinite' }} />
                    </div>
                  </div>
                ))}
              </>
            )}

            {!notifLoading && filtered.length === 0 && (
              <div className="notif-empty">
                <div className="notif-empty-icon"><Bell size={26} /></div>
                <p className="notif-empty-title">You're all caught up</p>
                <p className="notif-empty-sub">No notifications to show.</p>
              </div>
            )}

            {!notifLoading && groups.map(group => (
              <div key={group.label}>
                <div className="notif-group-header">
                  <span>{group.label}</span>
                  <span>{group.items.length}</span>
                </div>
                {group.items.map(n => {
                  const d = n.details || {}
                  const iconColor = notifIconColor(n.event_type, n.read)
                  const pill = notifStatusPill(n)
                  const isSelected = selectedNotif?.id === n.id
                  const relTime = relativeTime(n.created_at)
                  const exactTime = new Date(n.created_at).toLocaleString('en-IN')
                  const hasTarget = !!notifTarget(n)
                  const isApprovalUnread = n.event_type === 'reminder_approval' && !n.read
                  return (
                    <div
                      key={n.id}
                      className={`notif-row-new${!n.read ? ' is-unread' : ' is-read'}${isSelected ? ' is-selected' : ''}`}
                      onClick={() => handleRowClick(n)}
                    >
                      {/* Icon tile */}
                      <div className={`notif-icon-tile ${iconColor}`}>
                        <NotifIcon eventType={n.event_type} />
                        {!n.read && <span className="notif-unread-dot" />}
                      </div>

                      {/* Body */}
                      <div className="notif-row-body">
                        <div className="notif-row-line1">
                          <span className="notif-row-title">{notifTitle(n)}</span>
                          {pill && (
                            <span className={`notif-status-pill ${pill.cls}`}>{pill.label}</span>
                          )}
                        </div>
                        <div className="notif-row-line2">
                          {d.customer_name && <span>{d.customer_name}</span>}
                          {d.customer_name && (d.invoice_number || d.due_date || d.step_label) && (
                            <span style={{ color: '#4A5568' }}>·</span>
                          )}
                          {d.invoice_number && (
                            <span className="notif-inv-chip">{d.invoice_number}</span>
                          )}
                          {d.due_date && (
                            <span>Due {fmtDate(d.due_date)}</span>
                          )}
                          {d.step_label && (
                            <span style={{ color: '#6B7A8D' }}>{d.step_label}</span>
                          )}
                        </div>
                      </div>

                      {/* Right column */}
                      <div className="notif-row-right">
                        {d.outstanding_minor != null && (
                          <span className="notif-amount">{money(d.outstanding_minor)}</span>
                        )}
                        <span className="notif-reltime" title={exactTime}>{relTime}</span>
                        {isApprovalUnread ? (
                          <button
                            className="notif-quick-btn"
                            onClick={e => { e.stopPropagation(); onApproveJob(n.entity_id) }}
                          >
                            Approve
                          </button>
                        ) : hasTarget ? (
                          <span className="notif-quick-chevron" style={{ fontSize: 14 }}>›</span>
                        ) : null}
                      </div>
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>

        {/* Inspector pane (desktop only via CSS) */}
        <div className="notif-inspector">
          {!insp ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#6B7A8D', fontSize: 13 }}>
              Select a notification to see details
            </div>
          ) : (
            <>
              <div className="notif-inspector-eyebrow">Selected Notification</div>
              <div className="notif-inspector-title" style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                {notifTitle(insp)}
                {notifStatusPill(insp) && (
                  <span className={`notif-status-pill ${notifStatusPill(insp)!.cls}`}>
                    {notifStatusPill(insp)!.label}
                  </span>
                )}
              </div>

              {/* Metrics grid */}
              <div className="notif-inspector-metrics">
                <div>
                  <div className="notif-inspector-metric-label">Customer</div>
                  <div className="notif-inspector-metric-value">{inspD.customer_name || '—'}</div>
                </div>
                <div>
                  <div className="notif-inspector-metric-label">Invoice</div>
                  <div className={`notif-inspector-metric-value${inspD.invoice_number ? ' mono' : ''}`}>
                    {inspD.invoice_number || '—'}
                  </div>
                </div>
                <div>
                  <div className="notif-inspector-metric-label">Amount Due</div>
                  <div className={`notif-inspector-metric-value${inspD.outstanding_minor != null ? ' amount' : ''}`}>
                    {inspD.outstanding_minor != null ? money(inspD.outstanding_minor) : '—'}
                  </div>
                </div>
                <div>
                  <div className="notif-inspector-metric-label">Due Date</div>
                  <div className="notif-inspector-metric-value">
                    {inspD.due_date ? fmtDate(inspD.due_date) : '—'}
                  </div>
                </div>
              </div>

              {/* Step label */}
              {inspD.step_label && (
                <div style={{ background: 'rgba(42,52,72,0.4)', border: '1px solid #2A3448', borderRadius: 8, padding: '8px 12px', fontSize: 12, color: '#A8B5C6', marginBottom: 14 }}>
                  <span style={{ color: '#6B7A8D', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Step · </span>
                  {inspD.step_label}
                </div>
              )}

              {/* Actions */}
              <div className="notif-inspector-actions">
                {insp.event_type === 'reminder_approval' && (
                  <button
                    className="btn-approve"
                    onClick={() => onApproveJob(insp.entity_id)}
                  >
                    Approve &amp; Send
                  </button>
                )}
                <div className="btn-secondary-row">
                  {inspD.invoice_number && (
                    <button className="secondary" style={{ fontSize: 12 }}>View Invoice</button>
                  )}
                  {!insp.read && (
                    <button
                      className="secondary"
                      style={{ fontSize: 12 }}
                      onClick={() => onNotifClick(insp)}
                    >
                      Mark Read
                    </button>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function RemindersPage({
  org,
  deepLinkJobId,
  onDeepLinkConsumed,
}: {
  org: Org
  deepLinkJobId?: string
  onDeepLinkConsumed?: () => void
}) {
  const [view, setView] = useState<'pending' | 'sent' | 'failed' | 'schedules'>('pending')
  const [schedules, setSchedules] = useState<ReminderSchedule[]>([])
  const [steps, setSteps] = useState<ReminderStep[]>([])
  const [jobs, setJobs] = useState<ReminderJob[]>([])
  const [selectedSchedule, setSelectedSchedule] = useState<ReminderSchedule | null>(null)
  const [previewJob, setPreviewJob] = useState<ReminderJob | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Modal states
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [showStepModal, setShowStepModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ReminderSchedule | null>(null)
  const [editingStep, setEditingStep] = useState<ReminderStep | null>(null)
  const [archiveConfirm, setArchiveConfirm] = useState<{ schedule: ReminderSchedule; impact: ArchiveImpact } | null>(null)
  const [toggleConfirm, setToggleConfirm] = useState<ReminderSchedule | null>(null)

  // Approval form state
  const [customIntro, setCustomIntro] = useState('')
  const [customClosing, setCustomClosing] = useState('')
  // Controls the left-pane collapse on mobile (< 900 px)
  const [detailsOpen, setDetailsOpen] = useState(true)

  // Load data
  const loadSchedules = useCallback(async () => {
    try {
      const data = await api.reminderSchedules(org.id)
      setSchedules(data.results)
    } catch (err) {
      console.error('Failed to load schedules:', err)
    }
  }, [org.id])

  const loadSteps = useCallback(async (scheduleId?: string) => {
    try {
      const data = await api.reminderSteps(org.id, scheduleId)
      setSteps(data.results)
    } catch (err) {
      console.error('Failed to load steps:', err)
    }
  }, [org.id])

  const loadJobs = useCallback(async (status?: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await api.reminderJobs(org.id, { status, include_preview: false })
      setJobs(data.results)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load reminders')
    } finally {
      setLoading(false)
    }
  }, [org.id])


  // Check if user can manage schedules (owner or manager)
  const canManage = org.role === 'owner' || org.role === 'manager'

  // Toggle schedule active/inactive
  const handleToggle = async (schedule: ReminderSchedule) => {
    if (!canManage) {
      setError('Only Business Owner or Finance Manager can toggle schedules.')
      return
    }
    if (schedule.enabled && schedule.is_default) {
      setError('This is the default schedule. Set another schedule as default before deactivating it.')
      return
    }
    if (schedule.enabled) {
      if (!confirm('Deactivate "' + schedule.name + '"? New reminders will not be created from this schedule while it\'s inactive. Pending approvals and already-sent reminders are not affected.')) return
    }
    setLoading(true); setError('')
    try {
      const updated = await api.toggleSchedule(org.id, schedule.id)
      setSchedules(prev => prev.map(s => s.id === updated.id ? updated : s))
      setSuccess('Schedule "' + updated.name + '" ' + (updated.enabled ? 'activated' : 'deactivated') + '.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to toggle schedule')
    } finally { setLoading(false) }
  }

  // Show archive confirmation dialog
  const handleShowArchiveConfirm = async (schedule: ReminderSchedule) => {
    if (!canManage) { setError('Only Business Owner or Finance Manager can delete schedules.'); return }
    if (schedule.is_default) { setError('This is the default schedule. Set another schedule as default before deleting it.'); return }
    setLoading(true)
    try {
      const impact = await api.archiveImpact(org.id, schedule.id)
      setArchiveConfirm({ schedule, impact })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load schedule impact')
    } finally { setLoading(false) }
  }

  // Archive schedule
  const handleArchive = async () => {
    if (!archiveConfirm) return
    const { schedule } = archiveConfirm
    setLoading(true); setError('')
    try {
      const result = await api.archiveSchedule(org.id, schedule.id)
      setSchedules(prev => prev.filter(s => s.id !== schedule.id))
      setArchiveConfirm(null)
      setSuccess(result.detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to archive schedule')
    } finally { setLoading(false) }
  }

  // Set schedule as default
  const handleSetDefault = async (schedule: ReminderSchedule) => {
    if (!canManage) { setError('Only Business Owner or Finance Manager can change the default schedule.'); return }
    if (schedule.is_default) return
    setLoading(true); setError('')
    try {
      const updated = await api.setDefaultSchedule(org.id, schedule.id)
      setSchedules(prev => prev.map(s => s.id === updated.id ? { ...s, is_default: true } : { ...s, is_default: false }))
      setSuccess('"' + updated.name + '" set as the default reminder schedule.')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to set default schedule')
    } finally { setLoading(false) }
  }

  // Initial load
  useEffect(() => {
    loadSchedules()
    if (view === 'pending') loadJobs('proposed')
    else if (view === 'sent') loadJobs('dispatched')
    else if (view === 'failed') loadJobs('failed')
  }, [view, loadSchedules, loadJobs])

  // Deep-link: when navigated here from a notification, auto-open that job's modal
  useEffect(() => {
    if (!deepLinkJobId) return
    setView('pending')
    onDeepLinkConsumed?.()
    ;(async () => {
      setLoading(true)
      try {
        const fullJob = await api.getReminderJobWithPreview(org.id, deepLinkJobId)
        setPreviewJob(fullJob)
        setCustomIntro(fullJob.approved_custom_intro || '')
        setCustomClosing(fullJob.approved_custom_closing || '')
        setShowPreviewModal(true)
        loadJobs('proposed')
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not load reminder details')
        loadJobs('proposed')
      } finally {
        setLoading(false)
      }
    })()
  }, [deepLinkJobId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Seed default setup
  const handleSeedDefaults = async () => {
    if (!confirm('Create default 4-step reminder schedule? This will create:\n- Invoice Issue Notification\n- 7 days before due reminder\n- 3 days after due reminder\n- 15 days after due final notice')) return
    setLoading(true)
    setError('')
    setSuccess('')
    try {
      const result = await api.seedDefaultReminders(org.id)
      setSuccess(`${result.message} (${result.steps_created} steps created)`)
      await loadSchedules()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to seed defaults')
    } finally {
      setLoading(false)
    }
  }

  // Preview reminder
  const handlePreview = async (job: ReminderJob) => {
    setLoading(true)
    try {
      const fullJob = await api.getReminderJobWithPreview(org.id, job.id)
      setPreviewJob(fullJob)
      setCustomIntro(fullJob.approved_custom_intro || '')
      setCustomClosing(fullJob.approved_custom_closing || '')
      setShowPreviewModal(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load preview')
    } finally {
      setLoading(false)
    }
  }

  // Approve reminder
  const handleApprove = async () => {
    if (!previewJob) return
    setLoading(true)
    setError('')
    try {
      const res = await api.approveReminderJob(org.id, previewJob.id, {
        custom_intro: customIntro,
        custom_closing: customClosing,
      })
      setSuccess(res.detail || 'Reminder approved and queued for sending')
      setShowPreviewModal(false)
      setPreviewJob(null)
      await loadJobs(view === 'pending' ? 'proposed' : view === 'sent' ? 'dispatched' : 'failed')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to approve reminder')
    } finally {
      setLoading(false)
    }
  }

  // Reject reminder
  const handleReject = async (jobId: string) => {
    if (!confirm('Reject this reminder? It will not be sent.')) return
    setLoading(true)
    setError('')
    try {
      await api.rejectReminderJob(org.id, jobId)
      setSuccess('Reminder rejected')
      await loadJobs('proposed')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to reject reminder')
    } finally {
      setLoading(false)
    }
  }

  // Count by status
  const pendingCount = jobs.filter(j => j.status === 'proposed').length
  const sentTodayCount = jobs.filter(j => j.status === 'dispatched' && j.dispatched_at?.startsWith(new Date().toISOString().split('T')[0])).length
  const failedCount = jobs.filter(j => j.status === 'failed').length
  type ScheduleForEdit = ReminderSchedule & { steps: ReminderStep[] }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="reminders-page-title" style={{ margin: 0, fontSize: '28px', fontWeight: 700, letterSpacing: '-0.5px' }}>Payment Reminders</h1>
        <div style={{ display: 'flex', gap: '12px' }}>
          {schedules.length === 0 && (
            <button onClick={handleSeedDefaults} disabled={loading} className="reminders-cta-btn" style={{
              padding: '10px 20px', background: 'linear-gradient(to right, #14B8A6, #03B5D3)', color: '#003731', border: 'none',
              borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 600, fontSize: '14px',
              boxShadow: '0 0 20px rgba(20,184,166,0.3)', opacity: loading ? 0.6 : 1
            }}>
              Set Up Reminders
            </button>
          )}
          <button onClick={() => { setEditingSchedule(null); setShowScheduleModal(true) }} className="reminders-cta-btn" style={{
            padding: '10px 20px', background: 'linear-gradient(to right, #14B8A6, #03B5D3)', color: '#003731', border: 'none',
            borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '14px',
            boxShadow: '0 0 20px rgba(20,184,166,0.3)', display: 'inline-flex', alignItems: 'center'
          }}>
            <Plus size={16} style={{ marginRight: '6px' }} />
            New Schedule
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="reminders-alert-error" style={{ padding: '12px 16px', background: 'rgba(76,29,36,0.7)', border: '1px solid rgba(251,113,133,0.35)', borderRadius: '10px', marginBottom: '16px', color: '#FFE4E6', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
          <span>{error}</span>
          <button onClick={() => setError('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#FB7185', marginLeft: '12px', flexShrink: 0 }}>
            <X size={16} />
          </button>
        </div>
      )}
      {success && (
        <div className="reminders-alert-success" style={{ padding: '12px 16px', background: 'rgba(15,61,46,0.7)', border: '1px solid rgba(52,211,153,0.35)', borderRadius: '10px', marginBottom: '16px', color: '#D1FAE5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
          <span>{success}</span>
          <button onClick={() => setSuccess('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#34D399', marginLeft: '12px', flexShrink: 0 }}>
            <X size={16} />
          </button>
        </div>
      )}

      {/* View Tabs */}
      <div className="reminders-tab-bar" style={{ display: 'flex', gap: '0', marginBottom: '24px', borderBottom: '1px solid rgba(42,52,72,0.6)' }}>
        <button onClick={() => setView('pending')} className={`reminders-tab${view === 'pending' ? ' reminders-tab-active' : ''}`} style={{
          padding: '11px 22px', background: 'transparent', border: 'none',
          borderBottom: view === 'pending' ? '2px solid #4FDBC8' : '2px solid transparent',
          cursor: 'pointer', fontWeight: view === 'pending' ? 600 : 500, fontSize: '13px',
          color: view === 'pending' ? '#4FDBC8' : '#6B7A8D', transition: 'color 0.15s, border-color 0.15s'
        }}>
          Pending Approvals {pendingCount > 0 && <span style={{ marginLeft: '6px', padding: '2px 8px', background: 'rgba(76,29,36,0.7)', borderRadius: '999px', fontSize: '11px', color: '#FB7185', fontWeight: 700 }}>{pendingCount}</span>}
        </button>
        <button onClick={() => setView('sent')} className={`reminders-tab${view === 'sent' ? ' reminders-tab-active' : ''}`} style={{
          padding: '11px 22px', background: 'transparent', border: 'none',
          borderBottom: view === 'sent' ? '2px solid #4FDBC8' : '2px solid transparent',
          cursor: 'pointer', fontWeight: view === 'sent' ? 600 : 500, fontSize: '13px',
          color: view === 'sent' ? '#4FDBC8' : '#6B7A8D', transition: 'color 0.15s, border-color 0.15s'
        }}>
          Sent History
        </button>
        <button onClick={() => setView('failed')} className={`reminders-tab${view === 'failed' ? ' reminders-tab-active' : ''}`} style={{
          padding: '11px 22px', background: 'transparent', border: 'none',
          borderBottom: view === 'failed' ? '2px solid #4FDBC8' : '2px solid transparent',
          cursor: 'pointer', fontWeight: view === 'failed' ? 600 : 500, fontSize: '13px',
          color: view === 'failed' ? '#4FDBC8' : '#6B7A8D', transition: 'color 0.15s, border-color 0.15s'
        }}>
          Failed {failedCount > 0 && <span style={{ marginLeft: '6px', padding: '2px 8px', background: 'rgba(76,29,36,0.7)', borderRadius: '999px', fontSize: '11px', color: '#FB7185', fontWeight: 700 }}>{failedCount}</span>}
        </button>
        <button onClick={() => setView('schedules')} className={`reminders-tab${view === 'schedules' ? ' reminders-tab-active' : ''}`} style={{
          padding: '11px 22px', background: 'transparent', border: 'none',
          borderBottom: view === 'schedules' ? '2px solid #4FDBC8' : '2px solid transparent',
          cursor: 'pointer', fontWeight: view === 'schedules' ? 600 : 500, fontSize: '13px',
          color: view === 'schedules' ? '#4FDBC8' : '#6B7A8D', transition: 'color 0.15s, border-color 0.15s'
        }}>
          Schedules {schedules.length > 0 && <span style={{ marginLeft: '6px', padding: '2px 8px', background: 'rgba(79,219,200,0.12)', borderRadius: '999px', fontSize: '11px', color: '#4FDBC8', fontWeight: 700 }}>{schedules.length}</span>}
        </button>
      </div>

      {/* Content */}
      {loading && <div style={{ textAlign: 'center', padding: '40px', color: '#6B7A8D', fontSize: '14px' }}>Loading...</div>}

      {!loading && view === 'pending' && (
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: '#EEF0FF', letterSpacing: '-0.2px' }}>Awaiting Your Approval</h2>
          {jobs.length === 0 ? (
            <div className="glass-iridescent" style={{ textAlign: 'center', padding: '48px 24px', color: '#6B7A8D', overflow: 'hidden' }}>
              <Bell size={40} style={{ opacity: 0.3, marginBottom: '14px', color: '#4FDBC8' }} />
              <div style={{ fontSize: '14px' }}>No pending reminders to approve</div>
            </div>
          ) : (
            <div className="glass-iridescent" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '11px 14px', textAlign: 'left', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Invoice</th>
                    <th style={{ padding: '11px 14px', textAlign: 'left', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Customer</th>
                    <th style={{ padding: '11px 14px', textAlign: 'right', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Outstanding</th>
                    <th style={{ padding: '11px 14px', textAlign: 'left', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Due Date</th>
                    <th style={{ padding: '11px 14px', textAlign: 'left', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Step</th>
                    <th style={{ padding: '11px 14px', textAlign: 'left', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Scheduled</th>
                    <th style={{ padding: '11px 14px', textAlign: 'right', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} className="reminders-table-row" style={{ borderBottom: '1px solid rgba(42,52,72,0.5)' }}>
                      <td style={{ padding: '13px 14px', fontFamily: "'Red Hat Mono', monospace", fontSize: '12px', color: '#A8B5C6' }}>{job.invoice_number}</td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#EEF0FF', fontWeight: 500 }}>{job.customer_name}</td>
                      <td style={{ padding: '13px 14px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', fontSize: '13px', color: job.snapshot_days_overdue > 0 ? '#FB7185' : '#34D399' }}>
                        {money(job.current_outstanding_minor || job.snapshot_outstanding_minor)}
                      </td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#A8B5C6' }}>
                        <span className={job.snapshot_days_overdue > 0 ? 'overdue-date' : ''}>{fmtDate(job.snapshot_due_date)}</span>
                        {job.snapshot_days_overdue > 0 && (
                          <span style={{ marginLeft: '8px', fontSize: '11px', color: '#FB7185', background: 'rgba(76,29,36,0.5)', padding: '1px 6px', borderRadius: '999px' }}>
                            {job.snapshot_days_overdue}d overdue
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '13px 14px' }}>
                        <span style={{
                          padding: '3px 9px', borderRadius: '999px', fontSize: '11px', fontWeight: 600,
                          background: job.step_tone === 'issue' ? '#1E3A5F' : job.step_tone === 'friendly' ? '#0F3D2E' : job.step_tone === 'gentle' ? '#452A0F' : '#4C1D24',
                          color: job.step_tone === 'issue' ? '#93C5FD' : job.step_tone === 'friendly' ? '#86EFAC' : job.step_tone === 'gentle' ? '#FDE68A' : '#FCA5A5',
                          letterSpacing: '0.02em'
                        }}>
                          Step {job.step_number}
                        </span>
                      </td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#6B7A8D' }}>{fmtDate(job.scheduled_date)}</td>
                      <td style={{ padding: '13px 14px', textAlign: 'right' }}>
                        <button onClick={() => handlePreview(job)} style={{
                          padding: '6px 12px', background: 'linear-gradient(to right, #14B8A6, #03B5D3)', color: '#003731',
                          border: 'none', borderRadius: '6px', cursor: 'pointer', marginRight: '8px', fontSize: '12px',
                          fontWeight: 600, boxShadow: '0 0 10px rgba(20,184,166,0.25)'
                        }}>
                          Preview & Approve
                        </button>
                        <button onClick={() => handleReject(job.id)} style={{
                          padding: '6px 12px', background: 'rgba(76,29,36,0.7)', color: '#FFE4E6',
                          border: '1px solid rgba(251,113,133,0.3)', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 600
                        }}>
                          Reject
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && view === 'sent' && (
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Sent Reminders</h2>
          {jobs.length === 0 ? (
            <div className="glass-iridescent" style={{ textAlign: 'center', padding: '48px 24px', color: '#6B7A8D', overflow: 'hidden', fontSize: '14px' }}>No sent reminders yet</div>
          ) : (
            <div className="glass-iridescent" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Sent At</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Invoice</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Customer</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'right' }}>Amount Sent For</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Step</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} className="reminders-table-row" style={{ borderBottom: '1px solid rgba(42,52,72,0.5)' }}>
                      <td style={{ padding: '13px 14px', fontSize: '12px', color: '#6B7A8D', fontVariantNumeric: 'tabular-nums' }}>{job.dispatched_at ? new Date(job.dispatched_at).toLocaleString('en-IN') : '—'}</td>
                      <td style={{ padding: '13px 14px', fontFamily: "'Red Hat Mono', monospace", fontSize: '12px', color: '#A8B5C6' }}>{job.invoice_number}</td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#EEF0FF', fontWeight: 500 }}>{job.customer_name}</td>
                      <td style={{ padding: '13px 14px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', fontSize: '13px', color: '#4FDBC8' }}>{money(job.sent_outstanding_minor || job.snapshot_outstanding_minor)}</td>
                      <td style={{ padding: '13px 14px' }}>
                        <span style={{ padding: '3px 9px', borderRadius: '999px', fontSize: '11px', fontWeight: 600, background: '#0F3D2E', color: '#86EFAC' }}>
                          Step {job.step_number}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && view === 'failed' && (
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: '#FB7185', letterSpacing: '-0.2px' }}>Failed Deliveries</h2>
          {jobs.length === 0 ? (
            <div className="glass-iridescent" style={{ textAlign: 'center', padding: '48px 24px', color: '#6B7A8D', overflow: 'hidden' }}>
              <CheckCircle size={40} style={{ color: '#34D399', marginBottom: '14px' }} />
              <div style={{ fontSize: '14px' }}>No failed deliveries</div>
            </div>
          ) : (
            <div className="glass-iridescent" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Invoice</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Customer</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Error</th>
                    <th style={{ padding: '11px 14px', fontWeight: 600, fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#6B7A8D', background: 'rgba(25,31,47,0.6)', borderBottom: '1px solid rgba(42,52,72,0.5)', textAlign: 'left' }}>Retry Count</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map(job => (
                    <tr key={job.id} className="reminders-table-row" style={{ borderBottom: '1px solid rgba(42,52,72,0.5)' }}>
                      <td style={{ padding: '13px 14px', fontFamily: "'Red Hat Mono', monospace", fontSize: '12px', color: '#A8B5C6' }}>{job.invoice_number}</td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#EEF0FF', fontWeight: 500 }}>{job.customer_name}</td>
                      <td style={{ padding: '13px 14px', color: '#FB7185', fontSize: '12px' }}>{job.block_reason || 'Unknown error'}</td>
                      <td style={{ padding: '13px 14px', fontSize: '13px', color: '#A8B5C6' }}>{job.retry_count || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!loading && view === 'schedules' && (
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px', color: '#EEF0FF', letterSpacing: '-0.2px' }}>Reminder Schedules</h2>
          {schedules.length === 0 ? (
            <div className="glass-iridescent" style={{ textAlign: 'center', padding: '48px 24px', overflow: 'hidden' }}>
              <div style={{ marginBottom: '16px', color: '#6B7A8D', fontSize: '14px' }}>No schedules configured yet</div>
              <button onClick={handleSeedDefaults} style={{
                padding: '10px 20px', background: 'linear-gradient(to right, #14B8A6, #03B5D3)', color: '#003731', border: 'none',
                borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '14px', boxShadow: '0 0 16px rgba(20,184,166,0.3)'
              }}>
                Create Default 4-Step Schedule
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {schedules.map(schedule => (
                <div key={schedule.id} className="glass-iridescent" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#EEF0FF' }}>{schedule.name}</h3>
                        {schedule.is_default && (
                          <span style={{
                            padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: 600,
                            background: 'rgba(79,219,200,0.12)', color: '#4FDBC8', textTransform: 'uppercase', letterSpacing: '0.05em', border: '1px solid rgba(79,219,200,0.3)'
                          }}>
                            Default
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '13px', color: '#6B7A8D', marginTop: '4px' }}>
                        {schedule.step_count} steps · Business hours: {schedule.send_hour_start}:00–{schedule.send_hour_end}:00
                      </div>
                    </div>
                    <div style={{
                      padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: 600,
                      background: schedule.enabled ? '#0F3D2E' : '#4C1D24',
                      color: schedule.enabled ? '#86EFAC' : '#FCA5A5',
                      border: schedule.enabled ? '1px solid rgba(52,211,153,0.3)' : '1px solid rgba(251,113,133,0.3)'
                    }}>
                      {schedule.enabled ? 'Active' : 'Inactive'}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button onClick={() => { setSelectedSchedule(schedule); loadSteps(schedule.id) }} style={{
                      padding: '8px 16px', background: '#f3f4f6', border: 'none',
                      borderRadius: '6px', cursor: 'pointer', fontWeight: 500, fontSize: '14px'
                    }}>
                      View Steps â†’
                    </button>
                    <button onClick={() => { setEditingSchedule(schedule); setShowScheduleModal(true) }} style={{
                      padding: '8px 16px', background: 'rgba(25,31,47,0.8)', border: '1px solid #2A3448',
                      borderRadius: '8px', cursor: 'pointer', fontWeight: 500, fontSize: '13px', color: '#A8B5C6',
                      display: canManage ? 'inline-flex' : 'none'
                    }}>
                      Edit
                    </button>
                    {canManage && (
                      <button onClick={() => handleToggle(schedule)} title={schedule.enabled ? 'Deactivate' : 'Activate'} style={{
                        padding: '8px 16px', background: schedule.enabled ? 'rgba(69,42,15,0.5)' : 'rgba(15,61,46,0.5)',
                        border: schedule.enabled ? '1px solid rgba(251,191,36,0.3)' : '1px solid rgba(52,211,153,0.3)',
                        borderRadius: '8px', cursor: 'pointer', fontWeight: 500, fontSize: '13px',
                        color: schedule.enabled ? '#FBBF24' : '#34D399'
                      }}>
                        {schedule.enabled ? 'Deactivate' : 'Activate'}
                      </button>
                    )}
                    {canManage && !schedule.is_default && (
                      <button onClick={() => handleSetDefault(schedule)} style={{
                        padding: '8px 16px', background: 'rgba(79,219,200,0.08)', border: '1px solid rgba(79,219,200,0.3)',
                        borderRadius: '8px', cursor: 'pointer', fontWeight: 500, fontSize: '13px', color: '#4FDBC8'
                      }}>
                        Set as default
                      </button>
                    )}
                    {canManage && (
                      <button onClick={() => handleShowArchiveConfirm(schedule)} title="Delete (archive) this schedule" style={{
                        padding: '8px 16px', background: 'rgba(76,29,36,0.5)', border: '1px solid rgba(251,113,133,0.3)',
                        borderRadius: '8px', cursor: 'pointer', fontWeight: 500, fontSize: '13px', color: '#FB7185'
                      }}>
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Schedule Steps Panel */}
          {selectedSchedule && (
            <div className="glass-iridescent" style={{ marginTop: '24px', padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: '#EEF0FF' }}>Steps for: {selectedSchedule.name}</h3>
                <button onClick={() => setSelectedSchedule(null)} style={{
                  background: 'rgba(25,31,47,0.8)', border: '1px solid #2A3448', borderRadius: '8px', cursor: 'pointer', color: '#6B7A8D', padding: '4px 8px', display: 'flex', alignItems: 'center'
                }}>
                  <X size={16} />
                </button>
              </div>
              {steps.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '20px', color: '#6B7A8D', fontSize: '13px' }}>No steps configured</div>
              ) : (
                <div style={{ display: 'grid', gap: '10px' }}>
                  {steps.map(step => (
                    <div key={step.id} style={{ background: 'rgba(25,31,47,0.6)', border: '1px solid rgba(42,52,72,0.6)', borderRadius: '10px', padding: '14px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                        <div>
                          <div style={{ fontWeight: 600, marginBottom: '4px', color: '#EEF0FF', fontSize: '13px' }}>
                            Step {step.step_number}: {step.tone_display}
                          </div>
                          <div style={{ fontSize: '12px', color: '#6B7A8D' }}>
                            Trigger: {step.offset_from_due !== null
                              ? `${step.offset_from_due} days ${step.offset_from_due < 0 ? 'before' : 'after'} due date`
                              : `${step.offset_from_issue} days from invoice issue`}
                          </div>
                          <div style={{ fontSize: '13px', color: '#6b7280', marginTop: '4px' }}>
                            Approval: {step.approval_mode_display}
                            {step.is_final_notice && <span style={{ marginLeft: '8px', color: '#dc2626', fontWeight: 500 }}>(Final Notice)</span>}
                          </div>
                        </div>
                        <div style={{
                          padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 500,
                          background: step.enabled ? '#d1fae5' : '#fee2e2',
                          color: step.enabled ? '#065f46' : '#991b1b'
                        }}>
                          {step.enabled ? 'Enabled' : 'Disabled'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {showScheduleModal && (
        <ScheduleFormModal
          org={org}
          schedule={editingSchedule as ScheduleForEdit | null}
          onSaved={saved => {
            setSchedules(prev => {
              const idx2 = prev.findIndex(s => s.id === saved.id)
              if (idx2 >= 0) { const next = [...prev]; next[idx2] = saved; return next }
              return [saved, ...prev]
            })
            setShowScheduleModal(false)
            setEditingSchedule(null)
            setSuccess(editingSchedule ? `Schedule "${saved.name}" updated.` : `Schedule "${saved.name}" created.`)
            setView('schedules')
          }}
          onClose={() => { setShowScheduleModal(false); setEditingSchedule(null) }}
        />
      )}
      {/* Email Preview Modal — two-pane redesign */}
      {/* Archive Confirmation Dialog */}
      {archiveConfirm && (
        <div
          role="presentation"
          style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1100, padding: '16px' }}
          onClick={e => { if (e.target === e.currentTarget && !loading) setArchiveConfirm(null) }}
        >
          <div
            role="dialog"
            aria-modal="true"
            style={{ background: 'white', borderRadius: '12px', border: '1px solid #e5e7eb', boxShadow: '0 20px 60px rgba(0,0,0,0.18)', width: '100%', maxWidth: '480px', padding: '24px' }}
          >
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: '#dc2626', marginBottom: '16px' }}>
              Delete Schedule "{archiveConfirm.schedule.name}"?
            </h2>
            <p style={{ margin: 0, fontSize: '14px', color: '#374151', lineHeight: 1.6, marginBottom: '12px' }}>
              This schedule will be archived and removed from the list. All existing reminder history will be preserved.
            </p>
            {archiveConfirm.impact.invoices_affected > 0 && (
              <p style={{ margin: 0, fontSize: '14px', color: '#d97706', fontWeight: 500, marginBottom: '12px' }}>
                <strong>{archiveConfirm.impact.invoices_affected} invoice{archiveConfirm.impact.invoices_affected !== 1 ? 's' : ''}</strong> {archiveConfirm.impact.invoices_affected === 1 ? 'is' : 'are'} linked to this schedule. Future reminders for these invoices will fall back to the default schedule.
              </p>
            )}
            {archiveConfirm.impact.live_jobs > 0 && (
              <p style={{ margin: 0, fontSize: '14px', color: '#374151', marginBottom: '12px' }}>
                <strong>{archiveConfirm.impact.live_jobs} pending reminder{archiveConfirm.impact.live_jobs !== 1 ? 's' : ''}</strong> from this schedule will remain visible and can still be approved.
              </p>
            )}
            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button onClick={() => setArchiveConfirm(null)} disabled={loading} style={{ flex: 1, padding: '10px 20px', background: 'white', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#374151' }}>
                Cancel
              </button>
              <button onClick={handleArchive} disabled={loading} style={{ flex: 1, padding: '10px 20px', background: '#dc2626', color: 'white', border: 'none', borderRadius: '6px', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '14px', fontWeight: 600 }}>
                {loading ? 'Deleting...' : 'Delete Schedule'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showPreviewModal && previewJob && (() => {
        const closeModal = () => { setShowPreviewModal(false); setPreviewJob(null) }
        const overdueDays = previewJob.snapshot_days_overdue
        const isOverdue = overdueDays > 0
        const outstandingColor = isOverdue ? '#dc2626' : '#059669'
        const subject = previewJob.email_preview_subject || `Payment Reminder: Invoice ${previewJob.invoice_number}`
        return (
          /* Backdrop */
          <div
            role="presentation"
            style={{
              position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
              background: 'rgba(15,23,42,0.55)', display: 'flex',
              justifyContent: 'center', alignItems: 'center',
              zIndex: 1000, padding: '12px'
            }}
            onClick={e => { if (e.target === e.currentTarget) closeModal() }}
          >
            {/* Modal shell */}
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="rap-title"
              style={{
                background: 'white', borderRadius: '16px',
                border: '1px solid #e5e7eb',
                boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
                width: '100%', maxWidth: '1100px',
                height: '85vh', maxHeight: '85vh',
                display: 'flex', flexDirection: 'column',
                overflow: 'hidden'
              }}
            >
              {/* Fixed Header */}
              <header style={{
                flexShrink: 0, padding: '16px 24px',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', gap: '16px',
                background: 'white'
              }}>
                <h2 id="rap-title" style={{
                  margin: 0, fontSize: '17px', fontWeight: 700,
                  color: '#0f172a', letterSpacing: '-0.01em',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                }}>
                  Preview &amp; Approve Reminder: {previewJob.invoice_number}
                </h2>
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={loading}
                  aria-label="Close modal"
                  style={{
                    flexShrink: 0, width: '32px', height: '32px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'none', border: 'none', borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    color: '#64748b', opacity: loading ? 0.5 : 1
                  }}
                >
                  <X size={20} aria-hidden="true" />
                </button>
              </header>

              {/* Two-column body */}
              <div style={{
                flex: 1, minHeight: 0, display: 'grid', overflow: 'hidden',
                gridTemplateColumns: 'clamp(260px, 35%, 380px) 1fr'
              }}>
                {/* Left Pane */}
                <aside style={{
                  background: '#f8f9fb',
                  borderRight: '1px solid #e5e7eb',
                  display: 'flex', flexDirection: 'column',
                  overflowY: 'auto', overflowX: 'hidden',
                  padding: '20px', gap: '14px'
                }}>
                  {/* Already-processed banner */}
                  {previewJob.status !== 'proposed' && (
                    <div style={{
                      padding: '10px 14px', background: '#fef3c7',
                      border: '1px solid #f59e0b', borderRadius: '8px',
                      fontSize: '13px', color: '#92400e'
                    }}>
                      This reminder is no longer pending — it was <strong>{previewJob.status_display || previewJob.status}</strong>.
                      {previewJob.status === 'dispatched' && previewJob.dispatched_at && (
                        <span> Sent on {new Date(previewJob.dispatched_at).toLocaleString('en-IN')}.</span>
                      )}
                    </div>
                  )}

                  {/* Summary card */}
                  <div style={{
                    background: 'white', border: '1px solid #e5e7eb',
                    borderRadius: '10px', padding: '16px',
                    display: 'flex', flexDirection: 'column', gap: '12px'
                  }}>
                    {/* Customer */}
                    <div style={{ paddingBottom: '12px', borderBottom: '1px solid #f1f5f9' }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                        Customer
                      </div>
                      <div style={{ fontSize: '14px', fontWeight: 600, color: '#0f172a', marginBottom: '2px' }}>
                        {previewJob.customer_name || '\u2014'}
                      </div>
                      <div style={{ fontSize: '12px', color: '#64748b', wordBreak: 'break-all' }}>
                        {previewJob.customer_email || '\u2014'}
                      </div>
                    </div>
                    {/* Outstanding */}
                    <div style={{
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'space-between', gap: '8px',
                      paddingBottom: '12px', borderBottom: '1px solid #f1f5f9'
                    }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Outstanding
                      </div>
                      <div style={{ fontSize: '15px', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: outstandingColor }}>
                        {money(previewJob.current_outstanding_minor || previewJob.snapshot_outstanding_minor)}
                      </div>
                    </div>
                    {/* Due Date + overdue pill */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Due Date
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: '#0f172a' }}>
                          {fmtDate(previewJob.snapshot_due_date) || '\u2014'}
                        </span>
                        {isOverdue && (
                          <span style={{
                            display: 'inline-flex', alignItems: 'center',
                            padding: '2px 8px', borderRadius: '999px',
                            background: '#fef2f2', color: '#dc2626',
                            fontSize: '11px', fontWeight: 600
                          }}>
                            {overdueDays} {overdueDays === 1 ? 'day' : 'days'} overdue
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Custom Introduction */}
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a' }}>
                      Custom Introduction{' '}
                      <span style={{ fontWeight: 400, color: '#64748b' }}>(optional)</span>
                    </span>
                    <textarea
                      rows={3}
                      value={customIntro}
                      onChange={e => setCustomIntro(e.target.value)}
                      disabled={loading}
                      placeholder="Add a personal message at the beginning of the email..."
                      style={{
                        width: '100%', boxSizing: 'border-box',
                        padding: '8px 12px', border: '1px solid #d1d5db',
                        borderRadius: '8px', fontSize: '13px',
                        color: '#0f172a', background: 'white',
                        resize: 'vertical', minHeight: '72px',
                        outline: 'none', fontFamily: 'inherit',
                        opacity: loading ? 0.6 : 1,
                        cursor: loading ? 'not-allowed' : 'text'
                      }}
                    />
                  </label>

                  {/* Custom Closing */}
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a' }}>
                      Custom Closing{' '}
                      <span style={{ fontWeight: 400, color: '#64748b' }}>(optional)</span>
                    </span>
                    <textarea
                      rows={3}
                      value={customClosing}
                      onChange={e => setCustomClosing(e.target.value)}
                      disabled={loading}
                      placeholder="Add a personal message at the end of the email..."
                      style={{
                        width: '100%', boxSizing: 'border-box',
                        padding: '8px 12px', border: '1px solid #d1d5db',
                        borderRadius: '8px', fontSize: '13px',
                        color: '#0f172a', background: 'white',
                        resize: 'vertical', minHeight: '72px',
                        outline: 'none', fontFamily: 'inherit',
                        opacity: loading ? 0.6 : 1,
                        cursor: loading ? 'not-allowed' : 'text'
                      }}
                    />
                  </label>

                  {/* Email Subject (read-only) */}
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: '#0f172a' }}>Email Subject</span>
                    <input
                      type="text"
                      readOnly
                      value={subject}
                      style={{
                        width: '100%', boxSizing: 'border-box',
                        padding: '8px 12px', border: '1px solid #e5e7eb',
                        borderRadius: '8px', fontSize: '13px',
                        color: '#0f172a', background: '#f3f4f6',
                        cursor: 'default', outline: 'none', fontFamily: 'inherit'
                      }}
                    />
                  </label>
                </aside>

                {/* Right Pane — sole scroll region */}
                <section style={{
                  display: 'flex', flexDirection: 'column',
                  background: '#f3f4f6', minHeight: 0, overflow: 'hidden'
                }}>
                  {/* Preview label bar */}
                  <div style={{
                    flexShrink: 0, padding: '10px 24px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#475569' }}>Email Preview</span>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '5px',
                        padding: '2px 8px', borderRadius: '999px',
                        background: '#eff6ff', color: '#2563eb',
                        fontSize: '11px', fontWeight: 600
                      }}>
                        <span style={{
                          width: '6px', height: '6px', borderRadius: '50%',
                          background: '#10b981', display: 'inline-block', flexShrink: 0
                        }} aria-hidden="true" />
                        Live
                      </span>
                    </div>
                    {previewJob.invoice_number && (
                      <span style={{ fontSize: '12px', color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>
                        {previewJob.invoice_number}
                      </span>
                    )}
                  </div>

                  {/* Scrollable email frame */}
                  <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '24px' }}>
                    <div style={{
                      maxWidth: '640px', margin: '0 auto',
                      background: 'white', borderRadius: '12px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                      overflow: 'hidden'
                    }}>
                      {previewJob.email_preview_html ? (
                        <AutoHeightIframe
                          srcDoc={previewJob.email_preview_html}
                          title="Email Preview"
                        />
                      ) : (
                        <div style={{ textAlign: 'center', padding: '48px 24px', color: '#94a3b8', fontSize: '14px' }}>
                          Email preview not available
                        </div>
                      )}
                    </div>
                  </div>
                </section>
              </div>

              {/* Fixed Footer */}
              <footer style={{
                flexShrink: 0, padding: '14px 24px',
                borderTop: '1px solid #e5e7eb', background: 'white',
                display: 'flex', justifyContent: 'flex-end', gap: '10px'
              }}>
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={loading}
                  style={{
                    padding: '9px 20px', background: '#f3f4f6',
                    border: '1px solid #e5e7eb', borderRadius: '8px',
                    fontSize: '14px', fontWeight: 600, color: '#0f172a',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    opacity: loading ? 0.5 : 1,
                    transition: 'background 0.15s, box-shadow 0.15s, transform 0.1s'
                  }}
                  onMouseEnter={e => { if (!loading) { const b = e.currentTarget as HTMLButtonElement; b.style.background = '#e5e7eb'; b.style.boxShadow = '0 1px 4px rgba(0,0,0,0.10)' } }}
                  onMouseLeave={e => { const b = e.currentTarget as HTMLButtonElement; b.style.background = '#f3f4f6'; b.style.boxShadow = 'none'; b.style.transform = 'scale(1)' }}
                  onMouseDown={e => { if (!loading) (e.currentTarget as HTMLButtonElement).style.transform = 'scale(0.97)' }}
                  onMouseUp={e => { (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)' }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleApprove}
                  disabled={loading || previewJob.status !== 'proposed'}
                  style={{
                    padding: '9px 20px',
                    background: previewJob.status !== 'proposed' ? '#e5e7eb' : '#18ac7a',
                    border: 'none', borderRadius: '8px',
                    fontSize: '14px', fontWeight: 600,
                    color: previewJob.status !== 'proposed' ? '#6b7280' : '#000000',
                    cursor: (loading || previewJob.status !== 'proposed') ? 'not-allowed' : 'pointer',
                    opacity: loading ? 0.6 : 1,
                    display: 'inline-flex', alignItems: 'center', gap: '8px',
                    transition: 'background 0.15s, box-shadow 0.15s, transform 0.1s'
                  }}
                  onMouseEnter={e => { if (!loading && previewJob.status === 'proposed') { const b = e.currentTarget as HTMLButtonElement; b.style.background = '#00FF00'; b.style.boxShadow = '0 2px 8px rgba(0,255,0,0.35)' } }}
                  onMouseLeave={e => { const b = e.currentTarget as HTMLButtonElement; b.style.background = previewJob.status !== 'proposed' ? '#e5e7eb' : '#10b981'; b.style.boxShadow = 'none'; b.style.transform = 'scale(1)' }}
                  onMouseDown={e => { if (!loading && previewJob.status === 'proposed') { const b = e.currentTarget as HTMLButtonElement; b.style.background = '#0d9668'; b.style.transform = 'scale(0.97)' } }}
                  onMouseUp={e => { const b = e.currentTarget as HTMLButtonElement; b.style.background = previewJob.status !== 'proposed' ? '#e5e7eb' : '#0ea571'; b.style.transform = 'scale(1)' }}
                >
                  {loading
                    ? <Loader2 size={15} aria-hidden="true" style={{ animation: 'spin 1s linear infinite' }} />
                    : <Send size={15} aria-hidden="true" />
                  }
                  <span>{loading ? 'Sending...' : previewJob.status !== 'proposed' ? 'Already Processed' : 'Approve & Send'}</span>
                </button>
              </footer>
            </div>
          </div>
        )
      })()}
    </div>
  )
}

export default function App() {
  console.log('?? [TEST] FinPilot App is running! If you see this, console is working.');
  const [user, setUser] = useState<User | null>(null)
  const [org, setOrg] = useState<Org | null>(null)
  const [page, setPage] = useState<Page>('Overview')
  const [modal, setModal] = useState<'' | 'invoice' | 'customer' | 'payment' | 'product' | 'gstrate' | 'edit-invoice' | 'view-invoice'>('')
  const [editingInvoice, setEditingInvoice] = useState<Invoice | null>(null)
  const [viewingInvoice, setViewingInvoice] = useState<Invoice | null>(null)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [editingRate, setEditingRate] = useState<GSTRate | null>(null)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [showAllOutstanding, setShowAllOutstanding] = useState(false)

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

  // Notification deep-link: carries a reminder job ID when navigating
  // from a notification click so RemindersPage can auto-open that job's modal.
  const [notifDeepLink, setNotifDeepLink] = useState<{ reminderJobId?: string } | null>(null)

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
    // Handle Google OAuth redirect - force re-authentication
    const params = new URLSearchParams(window.location.search)
    const isGoogleReturn = params.has('code') && params.has('state')
    if (isGoogleReturn) {
      console.log('[Auth] Detected Google OAuth return, cleaning URL...')
      window.history.replaceState({}, '', window.location.pathname)
    }
    if (params.get('google_login') === 'success') {
      window.history.replaceState({}, '', window.location.pathname)
    }

    api.csrf().then(() =>
      api.me().then(u => {
        console.log('[Auth] User data received:', u)
        console.log('[Auth] Organizations:', u.organizations)
        console.log('[Auth] Org count:', u.organizations?.length || 0)
        setUser(u)
        if (u.organizations?.length) {
          const o = u.organizations[0]
          console.log('[Auth] Setting org:', o)
          setOrg(o)
          loadData(o)
          loadNotifications(o)
        } else {
          console.log('[Auth] No organizations found, user will see CreateOrgScreen')
        }
      }).catch((err) => {
        console.log('[Auth] api.me() failed:', err)
      })
    ).finally(() => setLoading(false))
  }, [loadData, loadNotifications])

  const handleNotifClick = useCallback(async (n: Notification) => {
    if (!org) return
    if (!n.read) {
      try {
        await api.markRead(org.id, n.id)
        setNotifications(prev => prev.map(x => x.id === n.id ? { ...x, read: true } : x))
        setUnreadCount(prev => Math.max(0, prev - 1))
      } catch { /* ignore */ }
    }
    const target = notifTarget(n)
    if (target === 'reminders') {
      const jobId = n.entity_type === 'reminder_job' ? n.entity_id : undefined
      setNotifDeepLink(jobId ? { reminderJobId: jobId } : {})
      setPage('Reminders')
    } else if (target === 'reconciliation') {
      setPage('Reminders') // placeholder until Reconciliation page exists
    }
    // import_complete / import_failed: just marks as read, no page to open yet
  }, [org, setPage])

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
    `${i.invoice_number} ${i.customer_name}`.toLowerCase().includes(query.toLowerCase()) &&
    (!statusFilter || i.display_status === statusFilter)
  )

  const nav: { name: Page; icon: React.ElementType; soon?: boolean }[] = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Invoices', icon: FileText },
    { name: 'Customers', icon: Users },
    { name: 'Products', icon: Package },
    { name: 'Payments', icon: Wallet },
    { name: 'Aging report', icon: Clock3 },
    { name: 'Reminders', icon: Bell },
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
            <button key={n.name} className={`nav-item ${page === n.name ? 'active' : ''}`} onClick={() => { setPage(n.name); setQuery(''); setStatusFilter('') }}>
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
            <ThemeToggle />
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

          {/* -- Overview -- */}
          {page === 'Overview' && <>
            <div className="metrics">
              <Metric icon={<Wallet />} title="Total receivables" value={money(dashboard?.outstanding_minor || 0)} note="Across all issued invoices" tone="blue" />
              <Metric icon={<ArrowUpRight />} title="Overdue" value={money(dashboard?.overdue_minor || 0)} note={`${dashboard?.overdue_invoice_count || 0} invoices need attention`} tone="rose" onClick={() => { setStatusFilter('overdue'); setQuery(''); setPage('Invoices') }} />
              <Metric icon={<Clock3 />} title="Due in 7 days" value={money(dashboard?.due_next_7_days_minor || 0)} note="Upcoming cash flow" tone="amber" onClick={() => { setQuery(''); setStatusFilter(''); setPage('Due in 7 days') }} />
              <Metric icon={<Users />} title="Customers owing" value={dashboard?.customer_count || 0} note="With outstanding balance" tone="green" onClick={() => { setQuery(''); setStatusFilter(''); setPage('Customers owing') }} />
            </div>

            <div className="panel">
              <div className="panel-head">
                <div><h2>Outstanding invoices</h2><p>Keep an eye on what's coming in</p></div>
                <div className="toolbar">
                  <button className="link-btn" onClick={() => setPage('Invoices')}>View all <span>?</span></button>
                </div>
              </div>
              {invoiceTable}
            </div>

            <div className="lower-grid">
              <div className="panel aging-panel">
                <div className="panel-head">
                  <div><h2>Receivables aging</h2><p>Outstanding by days past due</p></div>
                  <button className="link-btn" onClick={() => setPage('Aging report')}>Full report ?</button>
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
                <button onClick={() => setPage('AI Assistant')}>Open AI assistant <span>?</span></button>
              </div>
            </div>
          </>}

          {/* -- Due in 7 days -- */}
          {page === 'Due in 7 days' && (() => {
            const today = new Date(); today.setHours(0,0,0,0)
            const in7 = new Date(today); in7.setDate(today.getDate() + 7)
            const dueRows = invoices.filter(inv => {
              if (inv.balance_minor <= 0) return false
              const d = new Date(inv.due_date + 'T00:00:00')
              return d >= today && d <= in7
            }).sort((a, b) => new Date(a.due_date + 'T00:00:00').getTime() - new Date(b.due_date + 'T00:00:00').getTime())
            return (
              <div className="panel">
                <div className="panel-head">
                  <div>
                    <h2>Due in 7 days</h2>
                    <p>{dueRows.length} invoice{dueRows.length !== 1 ? 's' : ''} due between today and {in7.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</p>
                  </div>
                  <button className="link-btn" onClick={() => setPage('Overview')}>? Back to Overview</button>
                </div>
                {dueRows.length === 0
                  ? <div className="empty">No invoices due in the next 7 days.</div>
                  : <>
                      <div className="table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>CUSTOMER</th>
                              <th>INVOICE #</th>
                              <th>INVOICE DATE</th>
                              <th>DUE DATE</th>
                              <th>TOTAL</th>
                              <th>PAID</th>
                              <th>OUTSTANDING</th>
                              <th>STATUS</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dueRows.map(inv => (
                              <tr key={inv.id}
                                style={{ cursor: 'pointer' }}
                                onClick={() => { setViewingInvoice(inv); setModal('view-invoice') }}
                              >
                                <td className="strong">{inv.customer_name}</td>
                                <td className="invoice-number-cell">{inv.invoice_number}</td>
                                <td>{fmtDate(inv.invoice_date)}</td>
                                <td>{fmtDate(inv.due_date)}</td>
                                <td className="amount">{money(inv.total_minor)}</td>
                                <td className="amount">{money(inv.paid_minor)}</td>
                                <td className="amount">{money(inv.balance_minor)}</td>
                                <td><StatusBadge s={inv.display_status} /></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                }
              </div>
            )
          })()}
          {/* -- Customers owing -- */}
          {page === 'Customers owing' && (() => {
            // Build per-customer summary from already-loaded invoices
            const owingRows = customers.map(c => {
              const custInvoices = invoices.filter(i => i.customer === c.id && i.balance_minor > 0)
              return { customer: c, invoices: custInvoices, total: custInvoices.reduce((a, i) => a + i.balance_minor, 0) }
            }).filter(r => r.invoices.length > 0).sort((a, b) => b.total - a.total)
            return (
              <div className="panel">
                <div className="panel-head">
                  <div>
                    <h2>Customers owing</h2>
                    <p>{owingRows.length} customers with outstanding balance</p>
                  </div>
                  <button className="link-btn" onClick={() => setPage('Overview')}>? Back to Overview</button>
                </div>
                {owingRows.length === 0
                  ? <div className="empty">No outstanding balances. All invoices are settled.</div>
                  : owingRows.map(({ customer: c, invoices: cinv, total }) => (
                      <div key={c.id} className="owing-customer-block">
                        <div className="owing-customer-head">
                          <div className="owing-customer-name">
                            <div className="owing-avatar">{c.name.slice(0,1).toUpperCase()}</div>
                            <div>
                              <strong>{c.name}</strong>
                              {c.email && <span className="owing-meta">{c.email}</span>}
                            </div>
                          </div>
                          <div className="owing-customer-total">
                            <span className="owing-label">Total outstanding</span>
                            <strong className="owing-amount">{money(total)}</strong>
                          </div>
                        </div>
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>INVOICE #</th>
                                <th>INVOICE DATE</th>
                                <th>DUE DATE</th>
                                <th>TOTAL</th>
                                <th>PAID</th>
                                <th>OUTSTANDING</th>
                                <th>OVERDUE</th>
                                <th>STATUS</th>
                              </tr>
                            </thead>
                            <tbody>
                              {cinv.map(inv => {
                                const isOverdue = inv.display_status === 'overdue'
                                const overdueAmt = isOverdue ? inv.balance_minor : 0
                                return (
                                  <tr key={inv.id}
                                    style={{ cursor: 'pointer' }}
                                    onClick={() => { setViewingInvoice(inv); setModal('view-invoice') }}
                                  >
                                    <td className="strong">{inv.invoice_number}</td>
                                    <td>{fmtDate(inv.invoice_date)}</td>
                                    <td>{fmtDate(inv.due_date)}</td>
                                    <td className="amount">{money(inv.total_minor)}</td>
                                    <td className="amount">{money(inv.paid_minor)}</td>
                                    <td className="amount">{money(inv.balance_minor)}</td>
                                    <td className={isOverdue ? 'amount' : ''}>{isOverdue ? money(overdueAmt) : '—'}</td>
                                    <td><StatusBadge s={inv.display_status} /></td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ))
                }
              </div>
            )
          })()}
          {/* -- Invoices -- */}
          {page === 'Invoices' && (
            <div className="panel">
              <div className="panel-head">
                <div><h2>All invoices</h2><p>{filtered.length} invoices in your workspace</p></div>
                <div className="toolbar">
                  <div className="search"><Search size={15} /><input placeholder="Search invoices…" value={query} onChange={e => setQuery(e.target.value)} /></div>
                  <select className="status-filter-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}><option value="">All statuses</option><option value="overdue">Overdue</option><option value="issued">Unpaid</option><option value="partially_paid">Partially Paid</option><option value="paid">Paid</option><option value="draft">Draft</option></select>
                  <a href={`/api/v1/exports/invoices/?`} className="secondary" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 7, padding: '9px 13px', border: '1px solid #e4e9e6', fontSize: 12, fontWeight: 600, color: '#52615a', background: '#fff' }} onClick={e => { e.preventDefault(); fetch(`/api/v1/exports/invoices/`, { credentials: 'include', headers: { 'X-Organization-ID': org.id } }).then(r => r.blob()).then(b => { const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'invoices.csv'; a.click() }) }}>
                    <Download size={15} /> Export
                  </a>
                  <button className="primary" onClick={() => setModal('invoice')}><Plus size={16} /> New invoice</button>
                </div>
              </div>
              {invoiceTable}
            </div>
          )}

          {/* -- Customers -- */}
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
                  <thead><tr><th>CUSTOMER</th><th>EMAIL</th><th>PHONE</th><th>OPEN INVOICES</th><th>OUTSTANDING</th><th>OPT-OUT</th><th></th></tr></thead>
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
                          <td><button className="icon-btn" onClick={() => { setEditingCustomer(c); setModal('customer') }} title="Edit customer"><Pencil size={15} /></button></td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
                {customers.length === 0 && <div className="empty">No customers yet. Add your first customer to get started.</div>}
              </div>
            </div>
          )}

          {/* -- Payments -- */}
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

          {/* -- Aging report -- */}
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

          {/* -- Forecast -- DISABLED — uncomment to re-enable */}
          {/* {page === 'Forecast' && (
            <ForecastPage orgId={org.id} />
          )} */}

          {/* -- AI Assistant -- */}
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
                    <MarkdownAnswer text={answer} />
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

          {/* -- Notifications -- */}
          {page === 'Notifications' && org && (
            <NotificationsPage
              notifications={notifications}
              unreadCount={unreadCount}
              org={org}
              onNotifClick={handleNotifClick}
              onMarkAllRead={async () => {
                await api.markAllRead(org.id)
                loadNotifications(org)
              }}
              onApproveJob={(jobId) => {
                if (jobId) setNotifDeepLink({ reminderJobId: jobId })
                else setNotifDeepLink({})
                setPage('Reminders')
              }}
            />
          )}

          {/* -- Audit log -- DISABLED — uncomment to re-enable */}
          {/* {page === 'Audit Log' && <AuditLogPage orgId={org.id} />} */}

          {/* -- Settings -- */}
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

          {/* -- Products -- */}
          {page === 'Products' && org && (
            <ProductsPage
              orgId={org.id} products={products} gstRates={gstRates}
              onReload={() => loadData(org)}
              onOpenProductModal={p => { setEditingProduct(p); setModal('product') }}
              onOpenRateModal={r => { setEditingRate(r); setModal('gstrate') }}
            />
          )}

          {/* -- Reminders / Reconciliation (coming soon) -- */}
          {/* RECONCILIATION DISABLED — uncomment `|| page === 'Reconciliation'` to re-enable */}
          {(page === 'Reminders' && org) && (
            <RemindersPage
              org={org}
              deepLinkJobId={notifDeepLink?.reminderJobId}
              onDeepLinkConsumed={() => setNotifDeepLink(null)}
            />
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
        <CustomerModal orgId={org.id} editing={editingCustomer} onClose={() => { setModal(''); setEditingCustomer(null) }} onCreated={() => loadData(org)} />
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

      {/* -- Logout confirm dialog --------------------------------------- */}
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

// -- Forecast page component -- DISABLED — uncomment to re-enable -------------
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

// -- Audit log page -- DISABLED — uncomment to re-enable ---------------------
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
