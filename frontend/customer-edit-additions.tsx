// CUSTOMER MODAL - REPLACE THE EXISTING CustomerModal FUNCTION WITH THIS

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
        response = await api.updateCustomer(orgId, editing.id, data)
      } else {
        response = await api.createCustomer(orgId, data)
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
            <div className="form-warning" style={{ background: '#fff4e6', border: '1px solid #ff9800', padding: '12px', borderRadius: '6px', marginTop: '12px' }}>
              <strong style={{ color: '#e65100' }}>⚠️ Warning</strong>
              <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px', color: '#e65100' }}>
                {warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              <button type="button" className="secondary" style={{ marginTop: '8px', width: '100%' }} onClick={() => setWarnings([])}>
                Dismiss and continue anyway
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

// ADD THIS STATE VARIABLE IN THE App() FUNCTION (near other editing states):
//   const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)

// UPDATE THE CUSTOMERS TABLE ROW TO ADD EDIT BUTTON (replace the existing tr in customers table):
/*
<tr key={c.id}>
  <td className="strong">{c.name}</td>
  <td>{c.email || '—'}</td>
  <td>{c.phone || '—'}</td>
  <td>{open.length}</td>
  <td className="amount">{money(open.reduce((a, x) => a + x.balance_minor, 0))}</td>
  <td>{c.opt_out ? <span className="status overdue">Opted out</span> : <span className="status paid">Active</span>}</td>
  <td>
    <button 
      className="icon-btn" 
      onClick={() => { setEditingCustomer(c); setModal('customer') }}
      title="Edit customer"
    >
      <Pencil size={15} />
    </button>
  </td>
</tr>
*/

// UPDATE THE CustomerModal CALL IN THE MODAL RENDERING SECTION:
/*
{modal === 'customer' && org && (
  <CustomerModal
    orgId={org.id}
    editing={editingCustomer}
    onClose={() => { setModal(''); setEditingCustomer(null) }}
    onCreated={() => loadData(org)}
  />
)}
*/
