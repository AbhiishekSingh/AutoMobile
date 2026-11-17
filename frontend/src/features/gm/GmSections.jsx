// GM-only part of the dashboard: bottlenecks, funnel, SLA, PBA / CRE / PBA-vs-CRE comparison, customer-wise status.
// Uses the date range and branch chosen at the top of the dashboard.
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import { Loading } from '../../components/ui'

const R = { textAlign: 'right' }
const SRC = [['', 'All sources'], ['WALKIN', 'Walkin'], ['CSV', 'LeadSquare']]
const nice = (s) => (s || '—').replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())
const Sel = ({ value, onChange, children, w = 170 }) => <select className="input" style={{ maxWidth: w }} value={value} onChange={(e) => onChange(e.target.value)}>{children}</select>
const pctCol = (p) => (p >= 75 ? '#12703f' : p >= 40 ? '#b54708' : '#b42318')

export default function GmSections({ start, end, branch }) {
  const [f, setF] = useState({ pba_id: '', cre_id: '', model_id: '', source: '' })
  const [c, setC] = useState({ booking_status: 'ACTIVE', insurance_status: '', rto_status: '', delivery_status: '' })
  const [d, setD] = useState(null)
  const [cust, setCust] = useState(null)
  const [busy, setBusy] = useState(false)
  const base = useMemo(() => ({ date_from: start, date_to: end, ...(branch ? { branch_id: branch } : {}),
    ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) }), [start, end, branch, f])

  useEffect(() => { setD(null); api.get('/gm/performance', { params: base }).then((r) => setD(r.data)).catch(() => setD(false)) }, [base])
  useEffect(() => {
    setCust(null)
    const p = { ...base, ...Object.fromEntries(Object.entries(c).filter(([, v]) => v)) }
    delete p.cre_id
    api.get('/gm/customers', { params: p }).then((r) => setCust(r.data.rows)).catch(() => setCust([]))
  }, [base, c])

  async function exportXlsx() {
    setBusy(true)
    try {
      const r = await api.get('/gm/export', { params: base, responseType: 'blob' })
      const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = `gm-report-${start}-${end}.xlsx`; a.click()
    } finally { setBusy(false) }
  }
  const setFv = (k) => (v) => setF({ ...f, [k]: v })
  const setCv = (k) => (v) => setC({ ...c, [k]: v })

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ background: '#0f2a5c', color: '#fff', padding: '8px 16px', borderRadius: '10px 10px 0 0', fontWeight: 700 }}>GM consolidated view — PBA, CRE and department bottlenecks</div>
      <div className="card no-print" style={{ borderRadius: '0 0 10px 10px', marginBottom: 14 }}><div className="card-pad" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Sel value={f.pba_id} onChange={setFv('pba_id')}><option value="">All PBAs</option>{d?.pba_options?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</Sel>
        <Sel value={f.cre_id} onChange={setFv('cre_id')}><option value="">All CREs</option>{d?.cre_options?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</Sel>
        <Sel value={f.model_id} onChange={setFv('model_id')}><option value="">All models</option>{d?.model_options?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</Sel>
        <Sel value={f.source} onChange={setFv('source')}>{SRC.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</Sel>
        <span style={{ flex: 1 }} />
        <button className="btn btn-outline btn-sm" disabled={busy} onClick={exportXlsx}>Export GM report (Excel)</button>
        <span className="muted-note">Leads enquired {start} to {end}. PBA, CRE and funnel numbers follow these filters.</span>
      </div></div>

      {d === null ? <Loading /> : d === false ? <div className="hint">Could not load the GM report.</div> : (<>
        <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>Pending activities &amp; department bottlenecks (right now)</h3></div>
          <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(190px,1fr))', gap: 10 }}>
            {d.bottlenecks.map((b) => (
              <div key={b.key} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: '10px 12px', background: b.count ? '#fff7ed' : '#f0fdf4' }}>
                <div className="muted-note">{b.dept}</div><div style={{ fontSize: 24, fontWeight: 700, color: b.count ? '#b54708' : '#12703f' }}>{b.count}</div>
                <div style={{ fontSize: 13 }}>{b.label}</div></div>))}
          </div></div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 14, marginBottom: 14 }}>
          <div className="card"><div className="card-header"><h3>Booking-to-delivery funnel</h3></div><div className="card-pad">
            {d.funnel.map((s, i) => { const m = d.funnel[0].count || 1
              return (<div key={s.label} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '5px 0', fontSize: 13 }}>
                <span style={{ width: 110 }}>{s.label}</span>
                <div style={{ flex: 1, background: '#eef2f7', borderRadius: 4 }}><div style={{ width: `${Math.max(2, s.count * 100 / m)}%`, background: i < 4 ? '#3b82f6' : '#16a34a', color: '#fff', borderRadius: 4, padding: '2px 8px', fontWeight: 700 }}>{s.count}</div></div></div>) })}
          </div></div>
          <div className="card"><div className="card-header"><h3>Follow-up SLA compliance (3-hour rule)</h3></div><div className="card-pad">
            <div style={{ fontSize: 36, fontWeight: 700, color: pctCol(d.sla.compliance_pct) }}>{d.sla.compliance_pct}%</div>
            <div className="muted-note">of leads were contacted within 3 hours</div>
            <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
              <span><b style={{ color: '#12703f' }}>{d.sla.green}</b> green</span><span><b style={{ color: '#b42318' }}>{d.sla.red}</b> red</span><span><b style={{ color: '#b54708' }}>{d.sla.waiting}</b> waiting</span></div>
          </div></div>
          <div className="card"><div className="card-header"><h3>PBA vs CRE</h3></div><div className="card-pad table-wrap">
            <table className="data-table"><thead><tr><th>Team</th><th style={R}>Leads</th><th style={R}>Contacted</th><th style={R}>Calls</th><th style={R}>Test rides</th><th style={R}>Quotations</th><th style={R}>Booked</th><th style={R}>Delivered</th><th style={R}>Conv. %</th></tr></thead>
              <tbody>{d.versus.map((v) => <tr key={v.team}><td className="cell-primary">{v.team}</td><td style={R}>{v.leads}</td><td style={R}>{v.contacted}</td><td style={R}>{v.calls}</td><td style={R}>{v.test_rides}</td><td style={R}>{v.quotations}</td><td style={R}>{v.booked}</td><td style={R}>{v.delivered}</td><td style={R}>{v.conversion_pct}%</td></tr>)}</tbody></table>
          </div></div>
        </div>

        <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>PBA-wise performance comparison</h3></div>
          <div className="card-pad table-wrap"><table className="data-table">
            <thead><tr><th>PBA</th><th>Branch</th><th style={R}>Leads</th><th style={R}>Contacted</th><th style={R}>SLA %</th><th style={R}>Calls</th><th style={R}>Overdue f/u</th><th style={R}>Test rides</th><th style={R}>Quotes</th><th style={R}>Booked</th><th style={R}>Invoiced</th><th style={R}>Delivered</th><th style={R}>Cancelled</th><th style={R}>Ins. pend.</th><th style={R}>RTO pend.</th><th style={R}>Conv. %</th></tr></thead>
            <tbody>{d.pba.map((r) => (<tr key={r.user_id ?? 'x'}><td className="cell-primary">{r.name}</td><td>{r.branch || '—'}</td><td style={R}>{r.leads}</td><td style={R}>{r.contacted}</td>
              <td style={{ ...R, fontWeight: 700, color: pctCol(r.sla_pct) }}>{r.sla_pct}%</td><td style={R}>{r.calls}</td><td style={R}>{r.overdue_followups}</td><td style={R}>{r.test_rides_done}/{r.test_rides}</td>
              <td style={R}>{r.quotations}</td><td style={R}>{r.booked}</td><td style={R}>{r.invoiced}</td><td style={R}>{r.delivered}</td><td style={R}>{r.cancelled}</td><td style={R}>{r.ins_pending}</td><td style={R}>{r.rto_pending}</td><td style={R}>{r.conversion_pct}%</td></tr>))}</tbody></table>
            {!d.pba.length && <div className="muted-note">No leads in this range.</div>}</div></div>

        <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>CRE-wise performance comparison</h3></div>
          <div className="card-pad table-wrap"><table className="data-table">
            <thead><tr><th>CRE</th><th>Branches</th><th style={R}>Total leads</th><th style={R}>Contacted</th><th style={R}>Calls</th><th style={R}>Follow-up pending</th><th style={R}>Overdue</th><th style={R}>Test ride done</th><th style={R}>Booked</th><th style={R}>Delivered</th><th style={R}>Lost</th><th style={R}>Conv. %</th></tr></thead>
            <tbody>{d.cre.map((r) => (<tr key={r.cre_id}><td className="cell-primary">{r.name}</td><td>{r.branches.join(', ')}</td><td style={R}>{r.total}</td><td style={R}>{r.contacted}</td><td style={R}>{r.calls}</td><td style={R}>{r.pending}</td><td style={R}>{r.overdue}</td><td style={R}>{r.tr_completed}/{r.tr_scheduled}</td><td style={R}>{r.booked}</td><td style={R}>{r.delivered}</td><td style={R}>{r.lost}</td><td style={R}>{r.conversion_pct}%</td></tr>))}</tbody></table>
            {!d.cre.length && <div className="muted-note">No CRE data.</div>}
            <div className="muted-note" style={{ marginTop: 8 }}>For dispositions, feedback, review log and drill-down open <Link to="/cre-reports">CRE reports</Link>.</div></div></div>
      </>)}

      <div className="card"><div className="card-header"><h3>Customer-wise booking status {Array.isArray(cust) && <span className="muted-note">({cust.length})</span>}</h3></div>
        <div className="card-pad">
          <div className="no-print" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
            <Sel value={c.booking_status} onChange={setCv('booking_status')}><option value="ACTIVE">Booked (active)</option><option value="CANCELLED">Cancelled</option></Sel>
            <Sel value={c.insurance_status} onChange={setCv('insurance_status')}><option value="">Insurance: any</option><option value="PENDING">Pending</option><option value="IN_PROGRESS">In progress</option><option value="COMPLETED">Completed</option></Sel>
            <Sel value={c.rto_status} onChange={setCv('rto_status')}><option value="">RTO: any</option><option value="PENDING">Pending</option><option value="IN_PROCESS">In process</option><option value="REGISTERED">Registered</option></Sel>
            <Sel value={c.delivery_status} onChange={setCv('delivery_status')}><option value="">Delivery: any</option><option value="PENDING">Pending delivery</option><option value="DELIVERED">Delivered</option></Sel>
          </div>
          {cust === null ? <Loading /> : (<div className="table-wrap"><table className="data-table">
            <thead><tr><th>Enquiry</th><th>Customer</th><th>Phone</th><th>Branch</th><th>PBA</th><th>Model</th><th>Stage</th><th>Payment</th><th style={R}>Outstanding</th><th>Insurance</th><th>RTO</th><th>Delivery</th><th></th></tr></thead>
            <tbody>{cust.map((r) => (<tr key={r.lead_id}><td className="cell-primary">{r.enquiry_no}</td><td>{r.customer}</td><td>{r.phone}</td><td>{r.branch || '—'}</td><td>{r.pba || '—'}</td><td>{r.model || '—'}</td>
              <td>{nice(r.stage)}</td><td>{nice(r.payment)}</td><td style={R}>{r.outstanding != null ? `Rs ${Number(r.outstanding).toLocaleString('en-IN')}` : '—'}</td><td>{nice(r.insurance)}</td><td>{nice(r.rto)}</td><td>{nice(r.delivery)}</td>
              <td><Link className="btn btn-outline btn-sm" to={`/handoff/${r.lead_id}`}>Open</Link></td></tr>))}</tbody></table>
            {!cust.length && <div className="muted-note">No customers match.</div>}</div>)}
        </div></div>
    </div>)
}
