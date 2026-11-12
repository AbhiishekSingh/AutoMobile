// Booking & Payment — section on the Customer Details page.
//
// Appears once the lead's Opportunity Status is BOOKING DONE (or as soon as a
// booking exists). The PBA records every payment received (cash, UPI, cheque,
// card, bank transfer, finance); the screen shows the running total paid, the
// outstanding amount and the payment status. All figures and rules come from
// the server (app/modules/payments/service.py) — the checks here only save a
// wasted click; the server checks again.
//
// The FIRST saved payment creates the booking and moves the lead to BOOKED,
// so the page is told (onChanged) to reload the lead and its stage history.
import { useEffect, useRef, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { Empty, Loading, fmtDate, fmtDateTime } from '../../components/ui'

const rupees = (v) => (v === null || v === undefined || v === '')
  ? '—' : `₹ ${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
const todayIST = () => new Date(Date.now() + 330 * 60 * 1000).toISOString().slice(0, 10)

const STATUS = {
  PENDING:        { cls: 'badge-gray',  label: 'Pending' },
  PARTIALLY_PAID: { cls: 'badge-amber', label: 'Partially Paid' },
  PAID:           { cls: 'badge-green', label: 'Paid' },
}
const EMPTY_FORM = () => ({ amount: '', payment_date: todayIST(), mode: 'CASH', reference: '',
                            finance_bank_name: '', remark: '' })

const Tile = ({ label, value, accent }) => (
  <div className="kpi-card" style={{ flex: '1 1 150px' }}>
    <div className="kpi-label">{label}</div>
    <div className="kpi-value" style={{ fontSize: 20, color: accent }}>{value}</div>
  </div>
)

export default function PaymentSection({ leadId, opportunityStatus, onChanged }) {
  const { user } = useAuth()
  const canRecord = user?.role === 'PBA'
  const photoRef = useRef(null)
  const attachRef = useRef(null)

  const [sum, setSum] = useState(null)
  const [maxMb, setMaxMb] = useState(5)
  const [form, setForm] = useState(EMPTY_FORM())
  const [file, setFile] = useState(null)
  const [fin, setFin] = useState({ finance_bank_name: '', emi_tenure_months: '', roi_percent: '' })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)             // { type: 'ok' | 'error', text }
  const [attachFor, setAttachFor] = useState(null) // payment id waiting for a photo
  const [langs, setLangs] = useState({ en: true, mr: false })   // receipt languages the server can make
  const [rcptLang, setRcptLang] = useState({})                  // payment_id -> 'en' | 'mr'

  function load() {
    api.get(`/leads/${leadId}/booking`).then((r) => {
      setSum(r.data)
      setFin({ finance_bank_name: r.data.finance.finance_bank_name || '',
               emi_tenure_months: r.data.finance.emi_tenure_months ?? '',
               roi_percent: r.data.finance.roi_percent ?? '' })
    }).catch(() => setSum(false))
  }
  // reload when the lead's Opportunity Status changes (it decides whether a payment can start)
  useEffect(() => { load() }, [leadId, opportunityStatus])
  useEffect(() => {
    api.get('/payments/receipt-languages').then((r) => setLangs(r.data)).catch(() => {})
    api.get('/documents/settings').then((r) => setMaxMb(r.data.max_mb || 5)).catch(() => {})
  }, [])

  const isBookingDone = /BOOKING\s*DONE/i.test(opportunityStatus || '')
  if (sum === null) return null                             // loading: show nothing yet
  if (sum === false || (!sum.booking_no && !isBookingDone)) return null   // not at booking stage

  const mode = sum.modes.find((m) => m.value === form.mode)
  const setF = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const st = STATUS[sum.payment_status] || STATUS.PENDING

  function pickPhoto(e) {
    const f = e.target.files?.[0] || null
    if (f && f.size > maxMb * 1024 * 1024) {
      setMsg({ type: 'error', text: `${f.name} is too large. The limit is ${maxMb} MB.` })
      e.target.value = ''; setFile(null); return
    }
    setMsg(null); setFile(f)
  }

  async function savePayment(e) {
    e.preventDefault(); setMsg(null)
    const amount = Number(form.amount)
    if (!(amount > 0)) { setMsg({ type: 'error', text: 'Enter the amount received.' }); return }
    if (sum.outstanding !== null && amount > Number(sum.outstanding)) {
      setMsg({ type: 'error', text: `This is more than the outstanding amount (${rupees(sum.outstanding)}).` }); return
    }
    if (mode?.needs_reference && !form.reference.trim()) {
      setMsg({ type: 'error', text: 'Enter the UTR / transaction / cheque number.' }); return
    }
    if (form.mode === 'FINANCE' && !(form.finance_bank_name.trim() || sum.finance.finance_bank_name)) {
      setMsg({ type: 'error', text: 'Enter the finance bank name.' }); return
    }
    setBusy(true)
    try {
      const { data } = await api.post(`/leads/${leadId}/payments`, {
        amount, mode: form.mode, payment_date: form.payment_date || null,
        reference: form.reference.trim() || null,
        finance_bank_name: form.finance_bank_name.trim() || null,
        remark: form.remark.trim() || null,
      })
      let text = 'Payment saved.'
      let type = 'ok'
      if (file) {
        try {
          const fd = new FormData(); fd.append('file', file)
          await api.post(`/payments/${data.new_payment_id}/photo`, fd,
                         { headers: { 'Content-Type': 'multipart/form-data' } })
        } catch (err) {
          type = 'error'
          text = 'Payment saved, but the photo could not be uploaded: ' +
                 (err.response?.data?.detail || 'please attach it again from the list below.')
        }
      }
      setForm(EMPTY_FORM()); setFile(null)
      if (photoRef.current) photoRef.current.value = ''
      setMsg({ type, text })
      load()
      onChanged && onChanged()          // reload the lead (stage may now be BOOKED)
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Could not save the payment.' })
    } finally {
      setBusy(false)
    }
  }

  async function attachPhoto(e) {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f || !attachFor) return
    if (f.size > maxMb * 1024 * 1024) { setMsg({ type: 'error', text: `File too large (limit ${maxMb} MB).` }); return }
    try {
      const fd = new FormData(); fd.append('file', f)
      await api.post(`/payments/${attachFor}/photo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMsg({ type: 'ok', text: 'Photo attached.' }); load()
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Could not attach the photo.' })
    } finally { setAttachFor(null) }
  }

  async function viewPhoto(p) {
    try {
      const res = await api.get(`/payments/${p.payment_id}/photo`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { setMsg({ type: 'error', text: 'Could not open this photo.' }) }
  }

  async function downloadReceipt(p) {
    const lang = rcptLang[p.payment_id] || 'en'
    try {
      const res = await api.get(`/payments/${p.payment_id}/receipt.pdf`, { params: { lang }, responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `${p.receipt_no}-${lang}.pdf`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch (err) {
      let text = 'Could not create the receipt.'
      try { text = JSON.parse(await err.response.data.text()).detail || text } catch { /* keep default */ }
      setMsg({ type: 'error', text })
    }
  }

  // link the customer opens (no login) to review the receipt and press I AGREE
  async function copyAgreeLink(p) {
    try {
      const { data } = await api.post(`/payments/${p.payment_id}/agree-link`)
      let copied = false
      try { await navigator.clipboard.writeText(data.url); copied = true } catch { /* show the link instead */ }
      setMsg({ type: 'ok', text: (copied ? 'Link copied — send it to the customer: ' : 'Customer link: ') + data.url })
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Could not create the customer link.' })
    }
  }

  async function saveFinance(e) {
    e.preventDefault(); setMsg(null)
    try {
      const { data } = await api.patch(`/leads/${leadId}/booking/finance`, {
        finance_bank_name: fin.finance_bank_name.trim() || null,
        emi_tenure_months: fin.emi_tenure_months === '' ? null : Number(fin.emi_tenure_months),
        roi_percent: fin.roi_percent === '' ? null : Number(fin.roi_percent),
      })
      setSum(data); setMsg({ type: 'ok', text: 'Finance details saved.' })
    } catch (err) {
      setMsg({ type: 'error', text: err.response?.data?.detail || 'Could not save the finance details.' })
    }
  }

  const note = (m) => m && (
    <div className="hint" style={{ marginTop: 10, ...(m.type === 'error' ? { background: 'var(--red-light)', color: '#7a2318' } : {}) }}>
      {m.text}
    </div>
  )

  return (
    <div className="card">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3>Booking &amp; Payment {sum.booking_no && <span className="muted-note">· {sum.booking_no}</span>}</h3>
        <span className={'badge ' + st.cls}>{st.label}</span>
      </div>

      {/* totals — worked out by the server from the quotation and the payments */}
      <div className="card-pad" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', paddingBottom: 0 }}>
        <Tile label="Total vehicle cost" value={rupees(sum.total_vehicle_cost)} />
        <Tile label="Total paid" value={rupees(sum.total_paid)} accent="var(--green)" />
        <Tile label="Outstanding" value={rupees(sum.outstanding)} accent={Number(sum.outstanding) > 0 ? 'var(--red)' : 'var(--green)'} />
      </div>
      {sum.quotation_no && (
        <div className="card-pad muted-note" style={{ paddingTop: 8, paddingBottom: 0 }}>
          Total cost is the on-road price on quotation {sum.quotation_no}.
        </div>
      )}

      {/* add a payment (PBA) */}
      {canRecord && (sum.can_add_payment ? (
        <form className="card-pad" onSubmit={savePayment}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, alignItems: 'end' }}>
            <div className="field" style={{ marginBottom: 0 }}><label>Amount received (₹) *</label>
              <input className="input" type="number" min="1" step="0.01" value={form.amount} onChange={setF('amount')} placeholder={sum.booking_no ? '' : 'Booking amount'} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Payment date</label>
              <input className="input" type="date" max={todayIST()} value={form.payment_date} onChange={setF('payment_date')} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Payment mode *</label>
              <select className="input" value={form.mode} onChange={setF('mode')}>
                {sum.modes.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select></div>
            {mode?.needs_reference && (
              <div className="field" style={{ marginBottom: 0 }}><label>{form.mode === 'CHEQUE' ? 'Cheque no. *' : 'UTR / transaction no. *'}</label>
                <input className="input" value={form.reference} onChange={setF('reference')} maxLength={60} /></div>
            )}
            {form.mode === 'FINANCE' && (
              <div className="field" style={{ marginBottom: 0 }}><label>Finance bank name *</label>
                <input className="input" value={form.finance_bank_name || sum.finance.finance_bank_name || ''} onChange={setF('finance_bank_name')} maxLength={80} /></div>
            )}
            <div className="field" style={{ marginBottom: 0 }}><label>Transaction photo</label>
              <input ref={photoRef} className="input" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={pickPhoto} /></div>
            <div className="field" style={{ marginBottom: 0, gridColumn: 'span 2' }}><label>Remark</label>
              <input className="input" value={form.remark} onChange={setF('remark')} maxLength={200} /></div>
            <div><button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : (sum.booking_no ? 'Add Payment' : 'Save Booking Amount')}</button></div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 8 }}>
            {sum.booking_no ? 'Each payment gets its own receipt number.'
              : 'The first payment creates the booking and moves this lead to Booked.'}
            {' '}Cash needs no reference. Photo: PDF, JPG or PNG up to {maxMb} MB (optional).
          </div>
          {note(msg)}
        </form>
      ) : (
        <div className="card-pad">
          <div className="hint">{sum.blocked_reason}</div>
          {note(msg)}
        </div>
      ))}
      {!canRecord && msg && <div className="card-pad">{note(msg)}</div>}

      {/* finance / EMI plan — once a booking exists */}
      {sum.booking_no && (
        <form className="card-pad" onSubmit={saveFinance} style={{ paddingTop: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Finance / EMI plan <span className="muted-note">(only if the customer takes a loan)</span></div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12, alignItems: 'end' }}>
            <div className="field" style={{ marginBottom: 0 }}><label>Bank</label>
              <input className="input" value={fin.finance_bank_name} disabled={!canRecord} maxLength={80}
                     onChange={(e) => setFin({ ...fin, finance_bank_name: e.target.value })} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>Tenure (months)</label>
              <input className="input" type="number" min="1" value={fin.emi_tenure_months} disabled={!canRecord}
                     onChange={(e) => setFin({ ...fin, emi_tenure_months: e.target.value })} /></div>
            <div className="field" style={{ marginBottom: 0 }}><label>ROI (% p.a.)</label>
              <input className="input" type="number" min="0" max="100" step="0.01" value={fin.roi_percent} disabled={!canRecord}
                     onChange={(e) => setFin({ ...fin, roi_percent: e.target.value })} /></div>
            {canRecord && <div><button className="btn btn-outline">Save finance details</button></div>}
          </div>
        </form>
      )}

      {/* payment history */}
      <input ref={attachRef} type="file" accept=".pdf,.jpg,.jpeg,.png" style={{ display: 'none' }} onChange={attachPhoto} />
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Receipt No</th><th>Date</th><th>Mode</th><th>Reference / Bank</th><th>Amount</th><th>Recorded by</th><th>Photo</th><th>Receipt</th><th>Customer I AGREE</th></tr></thead>
          <tbody>
            {sum.payments.map((p) => (
              <tr key={p.payment_id}>
                <td className="cell-primary">{p.receipt_no}{p.remark ? <div className="muted-note">{p.remark}</div> : null}</td>
                <td className="cell-muted">{fmtDate(p.payment_date)}</td>
                <td>{p.mode_label}</td>
                <td>{[p.reference, p.finance_bank_name].filter(Boolean).join(' · ') || '—'}</td>
                <td><b>{rupees(p.amount)}</b></td>
                <td>{p.recorded_by || '—'}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {p.has_photo
                    ? <button type="button" className="btn btn-outline btn-sm" onClick={() => viewPhoto(p)}>View</button>
                    : (canRecord
                        ? <button type="button" className="btn btn-outline btn-sm"
                                  onClick={() => { setAttachFor(p.payment_id); attachRef.current?.click() }}>Attach</button>
                        : '—')}
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <select className="input" style={{ width: 'auto', display: 'inline-block', padding: '2px 6px' }}
                          value={rcptLang[p.payment_id] || 'en'}
                          onChange={(e) => setRcptLang({ ...rcptLang, [p.payment_id]: e.target.value })}>
                    <option value="en">English</option>
                    <option value="mr" disabled={!langs.mr}>मराठी{langs.mr ? '' : ' (not set up)'}</option>
                  </select>{' '}
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => downloadReceipt(p)}>Download PDF</button>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {p.agreed_at
                    ? <span className="badge badge-green" title="Customer acknowledged this receipt">Agreed {fmtDateTime(p.agreed_at)}</span>
                    : <><span className="badge badge-gray">Not yet</span>{' '}
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => copyAgreeLink(p)}>Copy link</button></>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sum.payments.length === 0 && <Empty>No payments recorded yet.</Empty>}
      </div>
    </div>
  )
}
