// CRE-wise reports (Owner / GM / Admin; a CRE sees only their own row).
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import Tabs, { Tab } from '../../components/Tabs'
import { Empty, Loading, fmtDate, fmtDateTime } from '../../components/ui'

const today = new Date()
const iso = (d) => d.toISOString().slice(0, 10)
const KPI = [['total', 'Leads', 'all'], ['pending', 'Pending', 'pending'], ['due_today', 'Due today', 'due_today'], ['overdue', 'Overdue', 'overdue'],
  ['tr_scheduled', 'TR scheduled', 'tr_scheduled'], ['tr_completed', 'TR done', 'tr_completed'], ['showroom', 'Showroom', 'showroom'],
  ['booked', 'Bookings', 'booked'], ['lost', 'Lost leads', 'lost']]

function Bars({ items, color = '#2563eb', unit }) {
  const max = Math.max(1, ...items.map((i) => i.count))
  if (!items.length) return <div className="muted-note">No data.</div>
  return items.map((i) => (
    <div key={i.name || i.label || i.date} style={{ display: 'grid', gridTemplateColumns: 'minmax(110px,190px) 1fr 52px', gap: 12, alignItems: 'center', margin: '9px 0', fontSize: 13.5 }}>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={i.name || i.label || i.date}>{i.name || i.label || i.date}</span>
      <div style={{ background: '#eef1f6', borderRadius: 6, height: 12 }}><div style={{ width: `${(i.count / max) * 100}%`, minWidth: i.count ? 4 : 0, background: color, height: 12, borderRadius: 6 }} /></div>
      <b style={{ textAlign: 'right' }}>{i.count}{unit}</b>
    </div>))
}

const Panel = ({ title, hint, children }) => (
  <div style={{ background: '#fff', border: '1px solid #edf0f4', borderRadius: 14, padding: '16px 20px' }}>
    <div style={{ fontWeight: 700, fontSize: 14.5, color: '#1c2740' }}>{title}</div>
    {hint && <div className="muted-note" style={{ margin: '2px 0 6px' }}>{hint}</div>}
    <div style={{ marginTop: 6 }}>{children}</div>
  </div>)

function ReviewLog({ params }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/whatsapp/review-log', { params: { date_from: params.date_from, date_to: params.date_to, cre_id: params.cre_id, branch_id: params.branch_id } }).then((r) => setRows(r.data)).catch(() => setRows([])) }, [params.date_from, params.date_to, params.cre_id, params.branch_id])
  return (
    <div className="card" style={{ marginTop: 14 }}><div className="card-header"><h3>Google review link log</h3></div>
      <div className="table-wrap"><table className="data-table"><thead><tr><th>Sent</th><th>Customer</th><th>Lead</th><th>Mobile</th><th>Branch</th><th>Sent by (CRE)</th><th>Link</th><th>Status</th><th>Send #</th></tr></thead>
        <tbody>{(rows || []).map((r) => <tr key={r.id}><td>{fmtDateTime(r.sent_at)}</td><td>{r.customer}</td><td>{r.enquiry_no}</td><td>{r.mobile}</td><td>{r.branch || '—'}</td><td>{r.cre || 'Auto'}</td>
          <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.link || '—'}</td><td title={r.error || ''}>{r.status}</td><td>{r.send_no}{r.total_sends > 1 ? ` of ${r.total_sends}` : ''}{r.is_retry ? ' (retry)' : ''}</td></tr>)}</tbody></table>
        {rows === null && <Loading />}{rows && !rows.length && <Empty>No review links sent in this period.</Empty>}</div></div>)
}

export default function CreReportsPage({ dashboard = false }) {
  const PAGE = dashboard ? 'CRE Dashboard' : 'CRE reports'
  const [f, setF] = useState({ date_from: iso(new Date(today.getFullYear(), today.getMonth(), 1)), date_to: iso(today), cre_id: '', branch_id: '', source: '', opportunity_status_id: '', disposition_id: '' })
  const [d, setD] = useState(null)
  const [drill, setDrill] = useState(null)
  const [more, setMore] = useState(false)
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v))
  const load = useCallback(() => api.get('/cre-reports', { params }).then((r) => setD(r.data)).catch(() => setD(false)), [JSON.stringify(params)])
  useEffect(() => { load() }, [load])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  async function open(kind, extra = {}, title) {
    const r = await api.get('/cre-reports/leads', { params: { ...params, ...extra, kind } })
    setDrill({ title: title || r.data.title, rows: r.data.rows })
  }
  async function exportXlsx() {
    const r = await api.get('/cre-reports/export', { params, responseType: 'blob' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = `cre-report-${f.date_from}-${f.date_to}.xlsx`; a.click()
  }
  if (d === null) return <Layout title={PAGE}><Loading /></Layout>
  if (d === false) return <Layout title={PAGE}><div className="hint">Could not load the report.</div></Layout>
  const T = d.total, o = d.options, rv = d.review
  return (
    <Layout title={PAGE} sub="Workload comes from each CRE's branches; calls, quotations and review links are what the CRE personally did">
      <style>{`
        .cr-tabs .data-table th,.cr-tabs .data-table td{white-space:nowrap;padding:11px 14px}
        .cr-tabs .table-wrap{overflow-x:auto}
        .cr-tabs .data-table th:first-child,.cr-tabs .data-table td:first-child{position:sticky;left:0;z-index:1;background:#fff;box-shadow:1px 0 0 #eef0f4}
        .cr-tabs .data-table th:first-child{background:#fafbfc}
        .cr-tabs .tabs-body .card-pad{padding:18px 22px}
      `}</style>
      <div className="card" style={{ marginBottom: 14 }}><div className="card-header" style={{ flexWrap: 'wrap', gap: 8 }}>
        <input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_from} onChange={set('date_from')} /><input className="input" type="date" style={{ maxWidth: 140 }} value={f.date_to} onChange={set('date_to')} />
        <select className="input" style={{ maxWidth: 160 }} value={f.cre_id} onChange={set('cre_id')}><option value="">All CREs</option>{o.cres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input" style={{ maxWidth: 150 }} value={f.branch_id} onChange={set('branch_id')}><option value="">All branches</option>{o.branches.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <button className="btn btn-outline btn-sm" onClick={() => setMore(!more)}>{more ? 'Fewer filters' : `More filters${f.source || f.opportunity_status_id || f.disposition_id ? ' ●' : ''}`}</button>
        {more && (<>
        <select className="input" style={{ maxWidth: 140 }} value={f.source} onChange={set('source')}><option value="">All sources</option><option value="CSV">LeadSquared</option><option value="WALKIN">Walk-in</option></select>
        <select className="input" style={{ maxWidth: 170 }} value={f.opportunity_status_id} onChange={set('opportunity_status_id')}><option value="">Any opportunity status</option>{o.opportunity.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        <select className="input" style={{ maxWidth: 160 }} value={f.disposition_id} onChange={set('disposition_id')}><option value="">Any disposition</option>{o.dispositions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
        </>)}
        <button className="btn btn-outline btn-sm" style={{ marginLeft: 'auto' }} onClick={exportXlsx}>Export Excel</button></div></div>

      <div className="card" style={{ marginBottom: 14, overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10,minmax(104px,1fr))' }}>
          {KPI.map(([k, l, kind], i) => (
            <div key={k} title="Click to see these leads" onClick={() => open(kind)} style={{ padding: '12px 14px', cursor: 'pointer', borderLeft: i ? '1px solid #eef0f4' : 0 }}>
              <div className="muted-note" style={{ fontSize: 11.5, fontWeight: 600, whiteSpace: 'nowrap' }}>{l}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: (k === 'overdue' && T[k]) ? '#b42318' : '#1c2740' }}>{T[k]}</div>
            </div>))}
          <div style={{ padding: '12px 14px', borderLeft: '1px solid #eef0f4', background: '#f6f9ff' }}>
            <div className="muted-note" style={{ fontSize: 11.5, fontWeight: 600 }}>Conversion</div>
            <div style={{ fontSize: 24, fontWeight: 800, color: '#2459c4' }}>{T.total ? Math.round((T.booked * 100) / T.total) : 0}%</div>
          </div>
        </div>
      </div>

      {drill && <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>{drill.title} ({drill.rows.length})</h3><button className="btn btn-outline btn-sm" onClick={() => setDrill(null)}>Close</button></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Enquiry</th><th>Customer</th><th>Mobile</th><th>Branch</th><th>PBA</th><th>Stage</th><th>Opportunity</th><th>Disposition</th><th>Next follow-up</th></tr></thead>
          <tbody>{drill.rows.map((r) => <tr key={r.lead_id}><td><Link to={`/leads/${r.lead_id}`}>{r.enquiry_no}</Link></td><td>{r.customer}</td><td>{r.mobile}</td><td>{r.branch}</td><td>{r.pba || '—'}</td><td>{r.stage}</td><td>{r.opportunity || '—'}</td><td>{r.disposition || '—'}</td><td>{r.next_followup_at ? fmtDateTime(r.next_followup_at) : '—'}</td></tr>)}</tbody></table>
          {!drill.rows.length && <Empty>Nothing here.</Empty>}</div></div>}

      <div className="cr-tabs">
      <Tabs tabs={[{ key: 'perf', label: 'CRE performance', count: d.rows.length }, { key: 'pipe', label: 'Pipeline' }, { key: 'fu', label: 'Follow-ups & test rides' }, { key: 'rev', label: 'Google reviews' }]}>
        <Tab k="perf">
      <div className="card" style={{ marginBottom: 14 }}><div className="card-header"><h3>CRE-wise performance</h3></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>CRE</th><th>Branches</th><th>Leads</th><th>Calls logged</th><th>Customers contacted</th><th>Pending</th><th>Overdue</th><th>Follow-up done %</th>
          <th>Quotations</th><th>TR sched.</th><th>TR done</th><th>Showroom</th><th>Bookings</th><th>Conv. %</th><th>Lost</th><th>Review links</th><th>Final reviews done</th><th>Final reviews pending</th></tr></thead>
          <tbody>{d.rows.map((r) => <tr key={r.cre_id}><td><b>{r.name}</b></td><td>{r.branches.join(', ') || '—'}</td><td>{r.total}</td><td>{r.calls}</td><td>{r.customers_contacted}</td>
            <td style={{ cursor: 'pointer' }} onClick={() => open('pending', { cre_id: r.cre_id }, `${r.name} — pending follow-ups`)}>{r.pending}</td>
            <td style={{ cursor: 'pointer', color: r.overdue ? '#b42318' : undefined }} onClick={() => open('overdue', { cre_id: r.cre_id }, `${r.name} — overdue follow-ups`)}>{r.overdue}</td>
            <td>{r.followup_completion_pct}%</td><td>{r.quotations_created}</td><td>{r.tr_scheduled}</td><td>{r.tr_completed}</td><td>{r.showroom}</td><td>{r.booked}</td><td>{r.conversion_pct}%</td><td>{r.lost}</td><td>{r.review_sent}</td><td>{r.final_done}</td><td>{r.final_pending}</td></tr>)}</tbody></table>
          {!d.rows.length && <Empty>No CREs match.</Empty>}</div></div>

        </Tab>
        <Tab k="pipe">
          <div style={{ padding: 20, display: 'grid', gap: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14.5, marginBottom: 10 }}>Lead conversion funnel</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: 10 }}>
                {d.funnel.map((i, n) => { const first = d.funnel[0]?.count || 0; return (
                  <div key={i.name || i.label} style={{ border: '1px solid #edf0f4', borderRadius: 12, padding: '10px 12px' }}>
                    <div className="muted-note" style={{ fontSize: 11.5, fontWeight: 600 }}>{i.name || i.label}</div>
                    <div style={{ fontSize: 22, fontWeight: 800 }}>{i.count}</div>
                    <div style={{ height: 5, borderRadius: 3, background: '#eef1f6', margin: '5px 0 4px' }}><div style={{ height: 5, borderRadius: 3, background: '#2563eb', width: `${first ? Math.min(100, i.count * 100 / first) : 0}%`, minWidth: i.count ? 3 : 0 }} /></div>
                    <div className="muted-note" style={{ fontSize: 11 }}>{n === 0 ? 'all leads' : `${first ? Math.round(i.count * 100 / first) : 0}% of leads`}</div>
                  </div>) })}
              </div>
              <div className="muted-note" style={{ marginTop: 8 }}>Qualified = contacted and showing interest (showroom / test-ride interest, a test ride, a quotation or a booking).</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(340px,1fr))', gap: 16 }}>
              <Panel title="Opportunity status"><Bars items={d.opportunity} color="#0ea5e9" /></Panel>
              <Panel title="Disposition"><Bars items={d.disposition} color="#8b5cf6" /></Panel>
            </div>
          </div>
        </Tab>
        <Tab k="fu">
          <div style={{ padding: 20, display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 16, alignItems: 'start' }}>
            <Panel title="Follow-up analytics">
              <Bars items={[{ name: 'Completed (calls connected)', count: d.rows.reduce((a, r) => a + r.calls_connected, 0) }, { name: 'Pending', count: T.pending }, { name: 'Overdue', count: T.overdue }]} color="#16a34a" />
            </Panel>
            <Panel title="Test rides">
              <Bars items={[{ name: 'Scheduled', count: T.tr_scheduled }, { name: 'Completed', count: T.tr_completed }, { name: 'Rescheduled', count: T.tr_rescheduled }]} color="#ef4444" />
            </Panel>
            <Panel title="Calls logged per day" hint="Last 14 days"><Bars items={d.trend.slice(-14)} color="#f59e0b" /></Panel>
          </div>
        </Tab>
        <Tab k="rev">
      <div className="card card-pad"><h3 style={{ marginTop: 0 }}>Google review links sent</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 8 }}><div><span className="muted-note">Total</span> <b>{rv.total}</b></div><div><span className="muted-note">Delivered / read</span> <b>{rv.delivered}</b></div><div><span className="muted-note">Failed</span> <b>{rv.failed}</b></div></div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 14 }}>
          <div><h4>CRE-wise</h4><Bars items={rv.by_cre} color="#14b8a6" /></div><div><h4>Branch-wise</h4><Bars items={rv.by_branch} color="#14b8a6" /></div><div><h4>Date-wise</h4><Bars items={rv.by_day.slice(-14)} color="#14b8a6" /></div></div></div>
      <ReviewLog params={params} />
        </Tab>
      </Tabs>
      </div>
    </Layout>
  )
}
