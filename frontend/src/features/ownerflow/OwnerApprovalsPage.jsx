// Owner approvals — list on the left, full detail on the right (details / journey / remarks).
// Everything the Owner needs to decide is in the detail panel; Reject always asks for a remark.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import Layout from '../../components/Layout'
import { Empty, Loading, errText, fmtDateTime } from '../../components/ui'
import { JourneySteps } from './JourneyBar'

const rupees = (v) => (v === null || v === undefined || v === '') ? '—' : `₹ ${Number(v).toLocaleString('en-IN')}`
const TONE = { PENDING: ['#fff4d6', '#8a5a00'], APPROVED: ['#e3f5ea', '#17673a'], REJECTED: ['#fde7e7', '#a52a2a'] }
const Chip = ({ s }) => (<span style={{ background: TONE[s][0], color: TONE[s][1], borderRadius: 999, padding: '2px 10px', fontSize: 12, fontWeight: 600 }}>{s[0] + s.slice(1).toLowerCase()}</span>)
const ago = (t) => { const m = Math.max(0, Math.round((Date.now() - new Date(t + (String(t).endsWith('Z') || /[+-]\d\d:\d\d$/.test(t) ? '' : '+05:30')).getTime()) / 60000))
  return m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago` }
const KV = ({ rows }) => (<table style={{ width: '100%', borderCollapse: 'collapse' }}><tbody>{rows.map(([k, v]) => (
  <tr key={k} style={{ borderBottom: '1px solid #eef0f3' }}><td className="muted-note" style={{ padding: '9px 0', width: 190 }}>{k}</td><td style={{ fontWeight: 500 }}>{v ?? '—'}</td></tr>))}</tbody></table>)
const YN = ({ label, value, onChange }) => (
  <div><div className="muted-note">{label}</div><div style={{ display: 'flex', gap: 6 }}>{[[true, 'YES'], [false, 'NO']].map(([v, l]) => (
    <button type="button" key={l} onClick={() => onChange(v)} className={'btn btn-sm ' + (value === v ? 'btn-primary' : 'btn-outline')}>{l}</button>))}</div></div>)

function Detail({ item, onDone }) {
  const nav = useNavigate()
  const [tab, setTab] = useState('details')
  const [d, setD] = useState(null)
  const [j, setJ] = useState(null)
  const initial = item.stage === 'INITIAL'
  const [price, setPrice] = useState(item.discounted_price || item.on_road_price || '')
  const [cp, setCp] = useState(true)
  const [atw, setAtw] = useState(!!item.atw_quoted)
  const [remark, setRemark] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { setD(null); setJ(null); setTab('details'); setRejecting(false); setErr(''); setRemark(''); setPrice(item.discounted_price || item.on_road_price || ''); setAtw(!!item.atw_quoted)
    api.get(`/leads/${item.lead_id}/owner-flow`).then((r) => setD(r.data)).catch(() => setD(false))
    api.get(`/leads/${item.lead_id}/journey`).then((r) => setJ(r.data)).catch(() => setJ(false)) }, [item.lead_id, item.stage, item.round])
  async function send(approve) {
    setErr('')
    if (!approve && !remark.trim()) { setErr('Please write the reason for rejection in the box, then press "Confirm reject".'); return }
    if (approve && initial && !(Number(price) > 0)) { setErr('Enter the approved discounted price first.'); return }
    setBusy(true)
    const url = `/leads/${item.lead_id}/owner-flow/${initial ? 'initial' : 'final'}/decision`
    try {
      await api.post(url, initial ? { approve, discounted_price: approve ? Number(price) : null, customer_processing: approve ? cp : null, atw_allowed: approve ? atw : null, remark }
                                  : { approve, remark })
      onDone(approve ? 'Approved' : 'Rejected — the PBA has been notified')
    } catch (e) { setErr(errText(e)) } finally { setBusy(false) }
  }
  async function openPolicy() {
    try { const res = await api.get(`/leads/${item.lead_id}/insurance/policy.pdf`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data); window.open(url, '_blank', 'noopener'); setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { setErr('Could not open the policy.') } }
  const pending = item.status === 'PENDING'
  const P = d && d.payment
  const checks = d ? [['Payment ' + (P.kind === 'DOWN_PAYMENT' ? '(down payment)' : '(full)') + ' received', P.ok], ['All customer documents uploaded', d.documents.ok],
                      ['Insurance policy uploaded', !!d.insurance?.has_pdf]] : []
  return (
    <div className="card" style={{ padding: 0 }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #eef0f3' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}><b style={{ fontSize: 18 }}>{item.customer_name}</b><Chip s={item.status} />
              <span className="badge badge-gray">{initial ? 'Initial approval' : 'Final approval'}</span></div>
            <div className="muted-note">{item.enquiry_no} · {item.mobile}{item.city ? ' · ' + item.city : ''} · requested by {item.pba} · {ago(item.since)}
              {item.round > 1 ? ` · round ${item.round}` : ''}</div>
          </div>
          <button className="btn btn-sm btn-outline" onClick={() => nav(`/handoff/${item.lead_id}`)}>Open full file</button>
        </div>
        {pending && (
          <div style={{ marginTop: 14, background: '#f6f8fb', borderRadius: 10, padding: 14 }}>
            {initial && (<div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 12 }}>
              <div><div className="muted-note">Approved discounted price (₹)</div><input className="input" type="number" style={{ width: 180 }} value={price} onChange={(e) => setPrice(e.target.value)} /></div>
              <YN label="Customer processing" value={cp} onChange={setCp} /><YN label="ATW (10-yr warranty)" value={atw} onChange={setAtw} /></div>)}
            {!rejecting ? (<div style={{ display: 'flex', gap: 10 }}>
              <button className="btn btn-primary" disabled={busy} onClick={() => send(true)}>✓ {initial ? 'Approve' : 'Final approve'}</button>
              <button className="btn btn-outline" style={{ color: '#c0392b', borderColor: '#e3a5a0' }} disabled={busy} onClick={() => { setRejecting(true); setErr('') }}>✕ Reject</button></div>) : (
              <div><div style={{ color: '#b3261e', fontWeight: 600, fontSize: 13 }}>Reason for rejection (required)</div>
                <input className="input" autoFocus value={remark} onChange={(e) => { setRemark(e.target.value); setErr('') }} placeholder="e.g. Discount too high — maximum ₹ 5,000"
                  style={{ margin: '6px 0 8px', ...(err ? { borderColor: '#d64545', background: '#fff5f5' } : {}) }} />
                <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-sm" style={{ background: '#d64545', color: '#fff' }} disabled={busy} onClick={() => send(false)}>Confirm reject</button>
                  <button className="btn btn-sm btn-outline" onClick={() => { setRejecting(false); setErr('') }}>Cancel</button></div></div>)}
            {err && <div className="hint" style={{ marginTop: 8, background: 'var(--red-light)', color: '#7a2318' }}>{err}</div>}
          </div>)}
      </div>
      <div style={{ display: 'flex', gap: 22, padding: '0 20px', borderBottom: '1px solid #eef0f3' }}>
        {[['details', 'Details'], ['journey', 'Journey'], ['remarks', 'Remarks']].map(([k, l]) => (
          <div key={k} onClick={() => setTab(k)} style={{ padding: '12px 0', cursor: 'pointer', fontWeight: 600, color: tab === k ? '#2f6fed' : '#6b7480', borderBottom: tab === k ? '2px solid #2f6fed' : '2px solid transparent' }}>{l}</div>))}
      </div>
      <div style={{ padding: 20 }}>
        {d === null && <Loading />}
        {d && tab === 'details' && (<>
          <KV rows={[['Bike', `${d.model || ''} ${d.color || ''}`], ['Bike price (on-road)', rupees(d.bike_price)],
            ['Discounted price', rupees(d.discounted_price)], ['Payment', P.is_emi ? `EMI · down payment ${rupees(P.required)}${P.finance_bank ? ' · ' + P.finance_bank : ''}` : 'Cash'],
            ['Paid by customer', rupees(P.paid_by_customer)], ['Finance disbursed', rupees(P.finance_received)], ['Outstanding', rupees(P.outstanding)],
            ['ATW (10-yr warranty)', d.atw.quoted ? (d.atw.status ? d.atw.status.toLowerCase() : 'asked') : 'Not quoted'],
            ['Branch / PBA', `${d.branch || '—'} / ${d.pba || '—'}`], ['RTO', d.rto ? d.rto.status.toLowerCase() : 'Not yet']]} />
          {!initial && (<div style={{ background: '#e8f6ee', borderRadius: 10, padding: 14, marginTop: 16 }}>
            <div style={{ fontWeight: 700, color: '#17673a', marginBottom: 8 }}>Readiness checks</div>
            {checks.map(([l, ok]) => (<div key={l} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '3px 0' }}>
              <span style={{ width: 20, height: 20, borderRadius: 10, background: ok ? '#1f8a4c' : '#d64545', color: '#fff', textAlign: 'center', fontSize: 12, lineHeight: '20px' }}>{ok ? '✓' : '✕'}</span>{l}</div>))}
            {!d.documents.ok && <div className="muted-note">Missing: {d.documents.missing.join(', ')}</div>}
            {d.insurance?.has_pdf && <button className="btn btn-sm btn-outline" style={{ marginTop: 8 }} onClick={openPolicy}>View policy PDF</button>}
          </div>)}
        </>)}
        {tab === 'journey' && (j ? <JourneySteps j={j} vertical /> : <Loading />)}
        {d && tab === 'remarks' && (<KV rows={[
          ['Initial approval', d.initial ? `${d.initial.status.toLowerCase()}${d.initial.decided_by ? ' by ' + d.initial.decided_by + ' · ' + fmtDateTime(d.initial.decided_at) : ''}` : '—'],
          ['Initial remark', d.initial?.remark], ['Customer processing', d.initial?.customer_processing == null ? '—' : d.initial.customer_processing ? 'YES' : 'NO'],
          ['ATW decision', d.initial?.atw_allowed == null ? '—' : d.initial.atw_allowed ? 'YES' : 'NO'],
          ['Final approval', d.final ? `${d.final.status.toLowerCase()}${d.final.decided_by ? ' by ' + d.final.decided_by + ' · ' + fmtDateTime(d.final.decided_at) : ''}` : '—'],
          ['Final remark', d.final?.remark]]} />)}
      </div>
    </div>
  )
}

export default function OwnerApprovalsPage() {
  const nav = useNavigate()
  const [status, setStatus] = useState('PENDING')
  const [stage, setStage] = useState('ALL')
  const [page, setPage] = useState(1)
  const [d, setD] = useState(null)
  const [sel, setSel] = useState(null)
  const [flash, setFlash] = useState('')
  const load = useCallback(() => { api.get('/owner-flow/approvals', { params: { stage, status, page } }).then((r) => {
    setD(r.data); setSel((cur) => r.data.rows.find((x) => cur && x.lead_id === cur.lead_id && x.stage === cur.stage) || r.data.rows[0] || null) })
    .catch(() => setD({ rows: [], total: 0, page_size: 20, counts: {} })) }, [stage, status, page])
  useEffect(() => { setD(null); load() }, [load])
  const pages = d ? Math.max(1, Math.ceil(d.total / d.page_size)) : 1
  const Pill = ({ on, onClick, children }) => (<button className={'btn btn-sm ' + (on ? 'btn-primary' : 'btn-outline')} style={{ borderRadius: 999 }} onClick={onClick}>{children}</button>)
  return (
    <Layout title="Approvals" sub="Pick a customer on the left — decide on the right">
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <span className="badge badge-amber">My queue {d?.counts?.PENDING ?? '…'}</span>
        {[['PENDING', 'Pending'], ['APPROVED', 'Approved'], ['REJECTED', 'Rejected'], ['ALL', 'All']].map(([k, l]) => (
          <Pill key={k} on={status === k} onClick={() => { setStatus(k); setPage(1) }}>{l}</Pill>))}
        <span style={{ width: 12 }} />
        {[['ALL', 'All types'], ['INITIAL', 'Initial'], ['FINAL', 'Final']].map(([k, l]) => (<Pill key={k} on={stage === k} onClick={() => { setStage(k); setPage(1) }}>{l}</Pill>))}
        <button className="btn btn-sm btn-outline" onClick={() => nav('/owner/other')}>Other requests</button>
      </div>
      {flash && <div className="hint" style={{ marginBottom: 12 }}>{flash}</div>}
      {d === null && <Loading />}
      {d && d.rows.length === 0 && <Empty>Nothing here.</Empty>}
      {d && d.rows.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 380px) 1fr', gap: 16, alignItems: 'start' }}>
          <div>
            {d.rows.map((c) => { const on = sel && sel.lead_id === c.lead_id && sel.stage === c.stage
              return (<div key={c.lead_id + c.stage} onClick={() => setSel(c)} className="card"
                style={{ padding: 14, marginBottom: 8, cursor: 'pointer', border: on ? '2px solid #4f7df3' : undefined, background: on ? '#f4f7ff' : undefined }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><b>{c.customer_name}</b>
                  {c.status === 'PENDING' ? <span className={'badge ' + (Date.now() - new Date(c.since).getTime() > 864e5 ? 'badge-red' : 'badge-amber')}>{ago(c.since)}</span> : <Chip s={c.status} />}</div>
                <div className="muted-note">{c.enquiry_no} · {c.stage === 'INITIAL' ? 'Initial' : 'Final'} approval</div>
                <div className="muted-note">{c.model} · {rupees(c.discounted_price || c.on_road_price)} · {c.branch}</div>
              </div>) })}
            {pages > 1 && (<div style={{ display: 'flex', gap: 8, justifyContent: 'center', alignItems: 'center' }}>
              <button className="btn btn-sm btn-outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
              <span className="muted-note">{page}/{pages}</span>
              <button className="btn btn-sm btn-outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></div>)}
          </div>
          {sel && <Detail item={sel} onDone={(m) => { setFlash(m); load() }} />}
        </div>)}
    </Layout>
  )
}
