import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

const statusClass = (s) => ({
  DRAFT: 'badge-gray', SHARED: 'badge-sky', ACCEPTED: 'badge-green',
  EXPIRED: 'badge-amber', REJECTED: 'badge-red',
}[s] || 'badge-gray')

// Build a wa.me link with a prefilled message for a quotation.
function whatsappLink(q) {
  const digits = String(q.contact_no || '').replace(/\D/g, '')
  const withCountry = digits.length === 10 ? `91${digits}` : digits
  const quotationUrl = `${window.location.origin}/quotations/${q.quotation_id}`
  const text = `Hi ${q.customer_name}, here is your quotation ${q.quotation_no} ` +
    `(On Road Price: ₹${Number(q.on_road_price).toLocaleString()}). View it here: ${quotationUrl}`
  return `https://wa.me/${withCountry}?text=${encodeURIComponent(text)}`
}

export default function QuotationsPage() {
  const nav = useNavigate()
  const [rows, setRows] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/quotations').then((r) => setRows(r.data)).catch(() => setErr('Could not load quotations.'))
  }, [])

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
              {rows.map((q) => (
                <tr key={q.quotation_id} onClick={() => nav(`/quotations/${q.quotation_id}`)} style={{ cursor: 'pointer' }}>
                  <td className="cell-primary">{q.quotation_no}</td>
                  <td>{q.customer_name}</td>
                  <td>₹ {Number(q.on_road_price).toLocaleString()}</td>
                  <td><span className={'badge ' + statusClass(q.status)}>{q.status}</span></td>
                  <td className="cell-muted">{fmtDateTime(q.valid_until)}</td>
                  <td className="cell-muted">{fmtDateTime(q.created_at)}</td>
                  <td onClick={(e) => e.stopPropagation()} style={{ display: 'flex', gap: 8 }}>
                    <a className="btn btn-outline btn-sm" href={whatsappLink(q)} target="_blank" rel="noopener noreferrer">
                      💬 Send via WhatsApp
                    </a>
                    <button className="btn btn-outline btn-sm" onClick={() => nav(`/quotations/${q.quotation_id}`)}>
                      👁️ Preview
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <Empty>No quotations created yet.</Empty>}
        </div>
      </div>
    </Layout>
  )
}