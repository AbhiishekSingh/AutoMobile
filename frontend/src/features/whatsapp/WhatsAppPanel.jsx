// WhatsApp section of the lead page: send buttons + the send log (status, failure reason, retry).
import { useEffect, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { fmtDateTime } from '../../components/ui'

const BADGE = { SENT: 'badge-amber', DELIVERED: 'badge-green', READ: 'badge-green', FAILED: 'badge-red', PENDING: 'badge-gray' }
const LABEL = { SENT: 'Sent', DELIVERED: 'Delivered', READ: 'Read', FAILED: 'Failed' }

export default function WhatsAppPanel({ leadId }) {
  const { user } = useAuth()
  const role = user?.role
  const [d, setD] = useState(null)
  const [pays, setPays] = useState([])
  const [payId, setPayId] = useState('')
  const [lang, setLang] = useState('en')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => api.get(`/leads/${leadId}/whatsapp`).then((r) => setD(r.data)).catch(() => setD(false))
  useEffect(() => {
    load()
    api.get(`/leads/${leadId}/booking`).then((r) => {
      const p = r.data?.payments || []
      setPays(p); if (p.length) setPayId(String(p[p.length - 1].payment_id))
    }).catch(() => {})
  }, [leadId])

  async function go(path, body, okText) {
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(path, body)
      setMsg(r.data.status === 'FAILED' ? { ok: false, text: `Not sent: ${r.data.error}` } : { ok: true, text: okText })
      load()
    } catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not send.' }) } finally { setBusy(false) }
  }
  if (d === null || d === false) return null
  const can = (...r) => r.includes(role)
  const B = ({ children, ...p }) => <button className="btn btn-outline btn-sm" disabled={busy} {...p}>{children}</button>

  return (
    <div className="card">
      <div className="card-header"><h3>WhatsApp</h3></div>
      <div className="card-pad">
        {!d.configured && <div className="hint" style={{ marginBottom: 10 }}>WhatsApp is not connected on the server yet, so messages will be logged as failed until it is.</div>}
        {msg && <div className="hint" style={{ margin: '0 0 10px', ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          {pays.length > 0 && (<>
            <select className="input" style={{ maxWidth: 190 }} value={payId} onChange={(e) => setPayId(e.target.value)}>
              {pays.map((p) => <option key={p.payment_id} value={p.payment_id}>{p.receipt_no}</option>)}</select>
            <select className="input" style={{ maxWidth: 110 }} value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="en">English</option><option value="mr">Marathi</option></select>
            <B onClick={() => window.confirm('Send this receipt to the customer on WhatsApp?') && go(`/leads/${leadId}/whatsapp/receipt`, { payment_id: Number(payId), lang }, 'Receipt sent.')}>Send receipt</B>
          </>)}
          <B onClick={() => window.confirm('Send the insurance policy PDF to the customer on WhatsApp?') && go(`/leads/${leadId}/whatsapp/insurance`, null, 'Insurance policy sent.')}>Send insurance PDF</B>
          {can('PBA', 'OWNER', 'GM', 'ADMIN') && <B onClick={() => window.confirm('Send the delivery receipt to the customer? The Instagram, KTM app and Google review links follow automatically.') && go(`/leads/${leadId}/whatsapp/delivery`, null, 'Delivery receipt sent. Engagement links follow.')}>Send delivery receipt</B>}
          {can('PBA', 'OWNER', 'GM', 'ADMIN') && <B onClick={() => window.confirm('Resend the engagement links (KTM app, Instagram, Google review)?') && go(`/leads/${leadId}/whatsapp/engagement`, null, 'Engagement links sent.')}>Resend engagement links</B>}
          <B onClick={() => window.confirm('Send the Google review link to the customer?') && go(`/leads/${leadId}/whatsapp/review`, null, 'Review link sent.')}>Send Google review link</B>
          <B onClick={() => window.confirm('Send the welcome message to the customer?') && go(`/leads/${leadId}/whatsapp/welcome`, null, 'Welcome message sent.')}>Send welcome</B>
        </div>
        <div className="table-wrap" style={{ marginTop: 14 }}>
          {d.messages.length === 0 ? <div className="muted-note">No WhatsApp messages sent for this customer yet.</div> : (
            <table className="data-table"><thead><tr><th>When</th><th>Message</th><th>To</th><th>Status</th><th>By</th><th /></tr></thead>
              <tbody>{d.messages.map((m) => (<tr key={m.id}>
                <td>{fmtDateTime(m.at)}</td><td>{m.label}{m.recipient === 'PBA' ? ' (PBA)' : ''}</td><td>{m.to}</td>
                <td><span className={'badge ' + (BADGE[m.status] || 'badge-gray')}>{LABEL[m.status] || m.status}</span>
                  {m.error && <div className="muted-note" style={{ color: '#b42318' }}>{m.error}</div>}
                  {m.delivered_at && m.status !== 'READ' && <div className="muted-note">Delivered {fmtDateTime(m.delivered_at)}</div>}
                  {m.read_at && <div className="muted-note">Read {fmtDateTime(m.read_at)}</div>}</td>
                <td>{m.auto ? 'Automatic' : (m.by || '—')}</td>
                <td>{m.status === 'FAILED' && !m.retried && <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => go(`/whatsapp/${m.id}/retry`, null, 'Retried.')}>Retry</button>}</td>
              </tr>))}</tbody></table>)}
        </div>
      </div>
    </div>
  )
}
