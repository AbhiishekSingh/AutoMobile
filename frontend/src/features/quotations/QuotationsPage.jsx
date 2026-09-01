import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const statusClass = (s) => ({
  DRAFT: 'badge-gray', SHARED: 'badge-sky', ACCEPTED: 'badge-green',
  EXPIRED: 'badge-amber', REJECTED: 'badge-red',
}[s] || 'badge-gray')

// Sends the quotation PDF straight to the customer's WhatsApp as an
// attachment via the backend (Meta WhatsApp Cloud API) — no local download,
// no wa.me link, no quotation URL in the message.
async function sendViaWhatsapp(quotationId, setStatus) {
  setStatus(quotationId, { type: 'sending', text: 'Sending…' })
  try {
    await api.post(`/quotations/${quotationId}/whatsapp-send`)
    setStatus(quotationId, { type: 'success', text: 'Sent ✓' })
  } catch (e) {
    const detail = e?.response?.data?.detail || 'Could not send via WhatsApp.'
    setStatus(quotationId, { type: 'error', text: detail })
  } finally {
    setTimeout(() => setStatus(quotationId, null), 4000)
  }
}

export default function QuotationsPage() {
  const nav = useNavigate()
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState('')
  const [waStatus, setWaStatus] = useState({})

  useEffect(() => {
    api.get('/quotations').then((r) => setRows(r.data)).catch(() => setErr('Could not load quotations.'))
  }, [])

  function setStatusFor(quotationId, status) {
    setWaStatus((prev) => ({ ...prev, [quotationId]: status }))
  }

  if (err) return <Layout title="Quotations"><div className="card"><div className="card-pad">{err}</div></div></Layout>
  if (!rows) return <Layout title="Quotations"><Loading /></Layout>

  return (
    <Layout title="QUOTATIONS" sub="All quotations generated across your leads">
      <div className="card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>Quotation No.</th><th>Customer</th><th>On Road Price</th><th>Status</th><th>Valid Until</th><th>Created</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((q) => {
                const status = waStatus[q.quotation_id]
                return (
                  <tr key={q.quotation_id} onClick={() => nav(`/quotations/${q.quotation_id}`)} style={{ cursor: 'pointer' }}>
                    <td className="cell-primary">{q.quotation_no}</td>
                    <td>{q.customer_name}</td>
                    <td>₹ {Number(q.on_road_price).toLocaleString()}</td>
                    <td><span className={'badge ' + statusClass(q.status)}>{q.status}</span></td>
                    <td className="cell-muted">{fmtDateTime(q.valid_until)}</td>
                    <td className="cell-muted">{fmtDateTime(q.created_at)}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <button className="btn btn-outline btn-sm" disabled={status?.type === 'sending'}
                                onClick={() => sendViaWhatsapp(q.quotation_id, setStatusFor)}>
                          {status?.type === 'sending' ? 'Sending…' : '💬 Send via WhatsApp'}
                        </button>
                        <button className="btn btn-outline btn-sm" onClick={() => nav(`/quotations/${q.quotation_id}`)}>
                          👁️ Preview
                        </button>
                      </div>
                      {status && status.type !== 'sending' && (
                        <div style={{
                          marginTop: 4, fontSize: 12,
                          color: status.type === 'success' ? '#2E9E6B' : '#D85B4A',
                        }}>{status.text}</div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {rows.length === 0 && <Empty>No quotations created yet.</Empty>}
        </div>
      </div>
    </Layout>
  )
}