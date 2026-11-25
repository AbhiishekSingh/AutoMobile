// CRE: every test ride in the branches the CRE covers. Read-only worklist; a row opens the customer.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate, fmtTime } from '../../components/ui'

const TABS = [['today', 'Today'], ['upcoming', 'Upcoming'], ['overdue', 'Overdue'], ['completed', 'Completed'], ['cancelled', 'Cancelled'], ['all', 'All']]
const STATUS = {
  BOOKED: ['Booked', '#e6f0ff', '#2459c4'], RESCHEDULED: ['Rescheduled', '#fff1d6', '#8a5a00'],
  COMPLETED: ['Completed', '#e3f5ea', '#17673a'], CANCELLED: ['Cancelled', '#fde8e6', '#b3261e'],
}
const HELP = {
  today: 'Rides booked for today.', upcoming: 'Rides booked for the coming days.',
  overdue: 'The ride date has passed and it is still not marked Completed or Cancelled: call the PBA or customer.',
  completed: 'Rides that happened.', cancelled: 'Cancelled rides.', all: 'Every test ride.',
}

export default function CreTestRidesPage() {
  const nav = useNavigate()
  const [bucket, setBucket] = useState('today')
  const [q, setQ] = useState('')
  const [loc, setLoc] = useState('')
  const [data, setData] = useState(null)
  useEffect(() => {
    setData(null)
    const t = setTimeout(() => api.get('/test-rides', { params: { bucket, search: q || undefined, location: loc || undefined } })
      .then((r) => setData(r.data)).catch(() => setData({ counts: {}, rows: [] })), q ? 300 : 0)
    return () => clearTimeout(t)
  }, [bucket, q, loc])

  return (
    <Layout title="Test rides" sub="Test rides in your branches">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
        {TABS.map(([k, label]) => (
          <button key={k} type="button" className={'btn btn-sm ' + (bucket === k ? 'btn-primary' : 'btn-outline')} onClick={() => setBucket(k)}>
            {label}{data?.counts ? ` · ${data.counts[k] ?? 0}` : ''}</button>))}
        <select className="input" style={{ maxWidth: 170, marginLeft: 'auto' }} value={loc} onChange={(e) => setLoc(e.target.value)}>
          <option value="">All locations</option><option>Showroom</option><option>Home Test Ride</option><option>Office TD</option></select>
        <input className="input" style={{ maxWidth: 260, flex: '1 1 200px' }} placeholder="🔍 Customer, mobile or enquiry no." value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="muted-note" style={{ marginBottom: 10 }}>{HELP[bucket]}</div>
      {data === null && <Loading />}
      {data && data.rows.length === 0 && <Empty>No test rides here.</Empty>}
      {data && data.rows.length > 0 && (
        <div className="card">
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Customer</th><th>Bike</th><th>Date &amp; slot</th><th>Location</th><th>PBA</th><th>Branch</th><th>Status</th></tr></thead>
              <tbody>
                {data.rows.map((r) => {
                  const [sl, bg, fg] = STATUS[r.status] || [r.status, '#eef0f4', '#444']
                  return (
                    <tr key={r.id} style={{ cursor: 'pointer' }} onClick={() => nav(`/leads/${r.lead_id}`)}>
                      <td><div className="cell-primary">{r.customer_name}</div><div className="muted-note" style={{ fontSize: 12 }}>{r.mobile} · {r.enquiry_no}</div></td>
                      <td>{r.model_name || '—'}{r.color && <div className="muted-note" style={{ fontSize: 12 }}>{r.color}</div>}</td>
                      <td>{r.scheduled_at ? fmtDate(r.scheduled_at) : '—'}<div className="muted-note" style={{ fontSize: 12 }}>{r.slot || (r.scheduled_at ? fmtTime(r.scheduled_at) : '')}</div></td>
                      <td>{r.location || '—'}</td>
                      <td>{r.pba_name || <span className="muted-note">Unassigned</span>}</td>
                      <td>{r.branch || '—'}</td>
                      <td><span style={{ display: 'inline-block', padding: '3px 11px', borderRadius: 99, fontSize: 12, fontWeight: 700, background: bg, color: fg, whiteSpace: 'nowrap' }}>{sl}</span>
                        {r.opportunity_status && <div className="muted-note" style={{ fontSize: 11.5, marginTop: 3 }}>{r.opportunity_status}</div>}</td>
                    </tr>)
                })}
              </tbody>
            </table>
          </div>
        </div>)}
      {data?.truncated && <div className="muted-note" style={{ marginTop: 8 }}>Showing the first 500. Use search or a tab to narrow it down.</div>}
    </Layout>)
}
