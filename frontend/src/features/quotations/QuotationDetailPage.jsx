import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

export default function QuotationDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [quotation, setQuotation] = useState(null)
  const [err, setErr] = useState('')
  const [downloading, setDownloading] = useState(false)
  const [waStatus, setWaStatus] = useState(null)

  useEffect(() => {
    api.get(`/quotations/${id}`).then((r) => setQuotation(r.data)).catch(() => setErr('Quotation not found.'))
  }, [id])

  async function downloadPdf() {
    setDownloading(true)
    try {
      const res = await api.get(`/quotations/${id}/pdf`, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `${quotation.quotation_no}.pdf`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setErr('Could not download PDF.')
    } finally {
      setDownloading(false)
    }
  }

  // Sends the quotation PDF straight to the customer's WhatsApp as an
  // attachment via the backend (Meta WhatsApp Cloud API) — no local
  // download, no wa.me link, no quotation URL in the message.
  async function sendViaWhatsapp() {
    setWaStatus({ type: 'sending', text: 'Sending…' })
    try {
      await api.post(`/quotations/${id}/whatsapp-send`)
      setWaStatus({ type: 'success', text: 'Sent via WhatsApp ✓' })
    } catch (e) {
      const detail = e?.response?.data?.detail || 'Could not send via WhatsApp.'
      setWaStatus({ type: 'error', text: detail })
    }
  }

  if (err) return <Layout title="Quotation"><div className="card"><div className="card-pad">{err}</div></div></Layout>
  if (!quotation) return <Layout title="Quotation"><Loading /></Layout>


  return (
    <Layout title={`Quotation ${quotation.quotation_no}`}
      sub={`Status: ${quotation.status}`}
      back={{ label: 'Back to Lead', onClick: () => nav(`/leads/${quotation.lead_id}`) }}>

      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <h3>Quotation Details</h3>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              className="btn btn-success"
              disabled={waStatus?.type === 'sending'}
              onClick={sendViaWhatsapp}
              style={{
                backgroundColor: '#25D366',
                color: 'white',
                transition: 'background-color 0.3s ease',
                border: 'none',
              }}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#128C7E'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#25D366'}
            >
              {waStatus?.type === 'sending' ? 'Sending…' : '💬 Send via WhatsApp'}
            </button>
            <button className="btn btn-primary" onClick={downloadPdf} disabled={downloading}>
              {downloading ? 'Preparing PDF...' : '⬇ Download PDF'}
            </button>
          </div>
        </div>
        {waStatus && waStatus.type !== 'sending' && (
          <div className="card-pad" style={{
            paddingTop: 0, marginTop: -8,
            color: waStatus.type === 'success' ? '#2E9E6B' : '#D85B4A', fontSize: 13,
          }}>{waStatus.text}</div>
        )}
        <div className="field-grid card-pad">
          <div className="fg"><div className="fg-label">Customer Name</div><div className="fg-value">{quotation.customer_name}</div></div>
          <div className="fg"><div className="fg-label">Contact No.</div><div className="fg-value">{quotation.contact_no}</div></div>
          <div className="fg"><div className="fg-label">Email</div><div className="fg-value">{quotation.email || '—'}</div></div>
          <div className="fg"><div className="fg-label">Colour</div><div className="fg-value">{quotation.color || '—'}</div></div>
          <div className="fg"><div className="fg-label">On Road Price</div><div className="fg-value">₹ {Number(quotation.on_road_price).toLocaleString()}</div></div>
          <div className="fg"><div className="fg-label">HSPR Registration</div><div className="fg-value">{quotation.hspr_registration_type}</div></div>
          <div className="fg"><div className="fg-label">Sales Manager</div><div className="fg-value">{quotation.sales_manager_name || '—'}</div></div>
          <div className="fg"><div className="fg-label">Valid Until</div><div className="fg-value">{fmtDateTime(quotation.valid_until)}</div></div>
          <div className="fg"><div className="fg-label">Created</div><div className="fg-value">{fmtDateTime(quotation.created_at)}</div></div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Inclusions</h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Description</th><th>Status</th></tr></thead>
            <tbody>
              {quotation.inclusions.map((inc) => (
                <tr key={inc.id}>
                  <td>{inc.description}</td>
                  <td><span className={'badge ' + (inc.included ? 'badge-green' : 'badge-red')}>
                    {inc.included ? 'INCLUDED' : 'NOT INCLUDED'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Finance / EMI Options</h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Tenure</th><th>Down Payment</th><th>Monthly EMI</th><th>ROI %</th></tr></thead>
            <tbody>
              {quotation.emi_options.map((e) => (
                <tr key={e.id}>
                  <td>{e.tenure_months} Months</td>
                  <td>{e.down_payment ? `₹ ${Number(e.down_payment).toLocaleString()}` : '—'}</td>
                  <td>{e.monthly_emi ? `₹ ${Number(e.monthly_emi).toLocaleString()}` : '—'}</td>
                  <td>{e.roi_percent || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h3>Documents Required</h3></div>
        <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
          {quotation.documents.map((d) => (
            <div key={d.id}>☐ {d.document_name}</div>
          ))}
        </div>
      </div>
    </Layout>
  )
}