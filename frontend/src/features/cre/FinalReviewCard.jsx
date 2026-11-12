// CRE final review of a delivered customer. Completing it closes the customer.
import { useCallback, useEffect, useState } from 'react'
import api from '../../lib/api'
import { fmtDateTime } from '../../components/ui'

const today = () => new Date().toISOString().slice(0, 10)

export default function FinalReviewCard({ leadId, onChanged }) {
  const [d, setD] = useState(null)
  const [f, setF] = useState({ review_date: today(), customer_feedback: '', product_satisfaction: '', customer_experience: '', cre_remarks: '', status: '' })
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => api.get(`/leads/${leadId}/final-review`).then((r) => {
    setD(r.data)
    if (r.data.review) setF({ ...r.data.review, review_date: r.data.review.review_date || today() })
  }).catch(() => setD(false)), [leadId])
  useEffect(() => { load() }, [load])
  if (!d || !d.show) return null
  const r = d.review
  const closed = d.stage === 'CLOSED'
  const lab = (list, v) => list.find((x) => x.value === v)?.label || '—'
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function submit() {
    if (f.status === 'COMPLETED' && !window.confirm('Completing the final review will CLOSE this customer. Continue?')) return
    setBusy(true); setMsg(null)
    try {
      const res = await api.post(`/leads/${leadId}/final-review`, { ...f, product_satisfaction: Number(f.product_satisfaction) || null, customer_experience: Number(f.customer_experience) || null })
      setMsg({ ok: true, text: res.data.closed ? 'Final review saved. The customer is now CLOSED.' : 'Saved. The customer stays open until the review is completed.' })
      await load(); onChanged && onChanged()
    } catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not save.' }) } finally { setBusy(false) }
  }
  return (
    <div className="card" style={{ padding: 14, marginBottom: 14, borderLeft: closed ? '4px solid #16a34a' : '4px solid #d97706' }}>
      <h3 style={{ marginTop: 0 }}>Final review {closed ? '· Closed' : '· Due — call the customer'}</h3>
      {msg && <div className="hint" style={{ marginBottom: 8, ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}
      {closed && r ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 8 }}>
          <div><div className="muted-note">Review date</div>{r.review_date}</div><div><div className="muted-note">Closed</div>{fmtDateTime(r.closed_at)}</div>
          <div><div className="muted-note">Reviewed by (CRE)</div>{r.reviewed_by}</div>
          <div><div className="muted-note">Product satisfaction</div>{lab(d.ratings, r.product_satisfaction)}</div><div><div className="muted-note">Customer experience</div>{lab(d.ratings, r.customer_experience)}</div>
          <div style={{ gridColumn: '1/-1' }}><div className="muted-note">Customer feedback</div>{r.customer_feedback}</div><div style={{ gridColumn: '1/-1' }}><div className="muted-note">CRE final remarks</div>{r.cre_remarks}</div>
        </div>
      ) : (<>
        {r && <div className="muted-note" style={{ marginBottom: 8 }}>Last saved: {lab(d.statuses, r.status)} · {r.attempts} attempt(s) · {r.reviewed_by}</div>}
        {!d.can_review && <div className="muted-note">Waiting for the CRE to complete the final review.</div>}
        {d.can_review && (<>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 10 }}>
            <div className="field"><label>Final review date *</label><input className="input" type="date" max={today()} value={f.review_date} onChange={set('review_date')} /></div>
            <div className="field"><label>Product satisfaction *</label><select className="input" value={f.product_satisfaction} onChange={set('product_satisfaction')}><option value="">Select</option>{d.ratings.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}</select></div>
            <div className="field"><label>Customer experience *</label><select className="input" value={f.customer_experience} onChange={set('customer_experience')}><option value="">Select</option>{d.ratings.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}</select></div>
            <div className="field"><label>Final review status *</label><select className="input" value={f.status} onChange={set('status')}><option value="">Select</option>{d.statuses.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}</select></div>
          </div>
          <div className="field"><label>Customer feedback *</label><textarea className="input" rows={2} value={f.customer_feedback} onChange={set('customer_feedback')} /></div>
          <div className="field"><label>CRE final remarks *</label><textarea className="input" rows={2} value={f.cre_remarks} onChange={set('cre_remarks')} /></div>
          <button className="btn btn-primary btn-sm" disabled={busy || !f.status} onClick={submit}>{f.status === 'COMPLETED' ? 'Submit & close customer' : 'Save'}</button>
        </>)}
      </>)}
    </div>
  )
}
