// Stock register for Owner / GM / Admin: totals, showroom-wise table, record movements, history, discrepancies.
import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'

const KIND = { VEHICLE: 'Vehicles', HELMET: 'Helmets', PARKING_COVER: 'Parking covers' }
const TYPE = { RECEIVE: 'Received at warehouse', ALLOCATE: 'Allocated to showroom', TRANSFER: 'Transferred',
  RECEIPT: 'Received at showroom', ISSUE: 'Issued', COUNT: 'Physical count' }
const err = (e, d) => e.response?.data?.detail || d
const num = (v) => (v === '' || v === null ? null : Number(v))

export default function StockPage() {
  const { user } = useAuth()
  const [d, setD] = useState(null)
  const [tab, setTab] = useState('register')
  const [msg, setMsg] = useState(null)
  const [hist, setHist] = useState([])
  const [hf, setHf] = useState({ item_id: '', branch_id: '', move_type: '', date_from: '', date_to: '' })
  const [mv, setMv] = useState({ move_type: 'RECEIVE', item_id: '', from_branch_id: '', to_branch_id: '', qty: '', counted_qty: '', reference: '', received_by: '', note: '' })
  const [ni, setNi] = useState({ kind: 'HELMET', name: '', variant: '', color: '' })
  const [busy, setBusy] = useState(false)

  const load = () => api.get('/stock/summary').then((r) => setD(r.data)).catch(() => setD(false))
  const loadHist = () => api.get('/stock/movements', { params: Object.fromEntries(Object.entries(hf).filter(([, v]) => v)) })
    .then((r) => setHist(r.data)).catch(() => setHist([]))
  useEffect(() => { load() }, [])
  useEffect(() => { if (tab === 'history' || tab === 'discrepancy') loadHist() }, [tab, hf.item_id, hf.branch_id, hf.move_type, hf.date_from, hf.date_to])

  if (d === null) return <Layout title="Stock"><Loading /></Layout>
  if (d === false) return <Layout title="Stock"><div className="hint">Could not load stock.</div></Layout>

  const isGm = user?.role === 'GM'
  const types = d.can_manage ? ['RECEIVE', 'ALLOCATE', 'TRANSFER', 'RECEIPT', 'ISSUE', 'COUNT'] : ['RECEIPT', 'ISSUE', 'COUNT']
  const t = mv.move_type
  const needFrom = ['TRANSFER', 'ISSUE'].includes(t)
  const needTo = ['ALLOCATE', 'TRANSFER', 'RECEIPT', 'COUNT'].includes(t)
  const branchesFor = (list) => isGm ? list.filter((b) => b.id === user.branch_id) : list
  const itemsOf = d.items

  async function submit() {
    setBusy(true); setMsg(null)
    try {
      await api.post('/stock/movements', { item_id: num(mv.item_id), move_type: t, from_branch_id: num(mv.from_branch_id),
        to_branch_id: num(mv.to_branch_id), qty: t === 'COUNT' ? null : num(mv.qty), counted_qty: t === 'COUNT' ? num(mv.counted_qty) : null,
        reference: mv.reference || null, received_by: mv.received_by || null, note: mv.note || null })
      setMsg({ ok: true, text: 'Saved.' }); setMv({ ...mv, qty: '', counted_qty: '', reference: '', received_by: '', note: '' }); load()
    } catch (e) { setMsg({ ok: false, text: err(e, 'Could not save.') }) } finally { setBusy(false) }
  }
  async function addItem() {
    setBusy(true); setMsg(null)
    try { await api.post('/stock/items', ni); setMsg({ ok: true, text: 'Item added.' }); setNi({ ...ni, name: '', variant: '', color: '' }); load() }
    catch (e) { setMsg({ ok: false, text: err(e, 'Could not add.') }) } finally { setBusy(false) }
  }
  const Tab = ({ id, children }) => (<button className={'btn btn-sm ' + (tab === id ? 'btn-primary' : 'btn-outline')} onClick={() => { setTab(id); setMsg(null) }}>{children}</button>)
  const note = msg && <div className="hint" style={{ margin: '10px 0', ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>
  const Field = ({ label, children }) => (<div className="field" style={{ marginBottom: 0 }}><label>{label}</label>{children}</div>)
  const sel = (v, f, opts, ph) => (<select className="input" value={v} onChange={(e) => f(e.target.value)}><option value="">{ph}</option>{opts.map(([val, lab]) => <option key={val} value={val}>{lab}</option>)}</select>)
  const brOpts = d.branches.map((b) => [b.id, b.name])
  const itOpts = itemsOf.map((i) => [i.id, `${KIND[i.kind].replace(/s$/, '')} – ${i.label}`])
  const move_rows = tab === 'discrepancy' ? hist.filter((h) => h.type === 'COUNT') : hist

  return (
    <Layout title="Stock" sub="Vehicles, helmets and parking covers by showroom">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 12, marginBottom: 16 }}>
        {Object.keys(KIND).map((k) => { const s = d.kinds[k]; return (
          <div className="card" key={k}><div className="card-pad">
            <div className="muted-note">Total {KIND[k].toLowerCase()}</div>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{s.available_total}</div>
            <div className="muted-note">Warehouse {s.warehouse} · Showrooms {s.allocated}</div>
            <div className="muted-note">Received {s.received} · Issued {s.issued}</div>
          </div></div>) })}
        {d.vehicle_flow && (<div className="card"><div className="card-pad">
          <div className="muted-note">Vehicle pipeline (customers)</div>
          <div style={{ marginTop: 6 }}>Booked, not invoiced: <b>{d.vehicle_flow.booked}</b></div>
          <div>Invoiced, not delivered: <b>{d.vehicle_flow.invoiced}</b></div>
          <div>Delivered: <b>{d.vehicle_flow.delivered}</b></div></div></div>)}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <Tab id="register">Stock register</Tab>
        {d.can_record && <Tab id="record">Record movement</Tab>}
        <Tab id="history">Movement history</Tab>
        <Tab id="discrepancy">Discrepancy report</Tab>
        {d.can_manage && <Tab id="items">Items</Tab>}
      </div>
      {note}

      {tab === 'register' && (<div className="card"><div className="card-pad table-wrap">
        {itemsOf.length === 0 ? <div className="muted-note">No stock items yet.{d.can_manage && ' Add items under "Items", then record a receipt.'}</div> : (
          <table className="data-table"><thead><tr><th>Type</th><th>Item</th><th style={{ textAlign: 'right' }}>Warehouse</th>
            {d.branches.map((b) => <th key={b.id} style={{ textAlign: 'right' }}>{b.name}</th>)}
            <th style={{ textAlign: 'right' }}>Total</th></tr></thead>
            <tbody>{itemsOf.map((i) => (<tr key={i.id}><td>{KIND[i.kind]}</td><td>{i.label}</td>
              <td style={{ textAlign: 'right' }}>{i.warehouse}</td>
              {d.branches.map((b) => <td key={b.id} style={{ textAlign: 'right' }}>{i.by_branch[b.id] ?? 0}</td>)}
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{i.total}</td></tr>))}</tbody></table>)}
        <h4 style={{ margin: '18px 0 6px' }}>Showroom-wise stock</h4>
        <table className="data-table"><thead><tr><th>Showroom</th><th style={{ textAlign: 'right' }}>Vehicles</th><th style={{ textAlign: 'right' }}>Helmets</th><th style={{ textAlign: 'right' }}>Parking covers</th></tr></thead>
          <tbody>{d.branches.map((b) => (<tr key={b.id}><td>{b.name}</td><td style={{ textAlign: 'right' }}>{b.VEHICLE}</td><td style={{ textAlign: 'right' }}>{b.HELMET}</td><td style={{ textAlign: 'right' }}>{b.PARKING_COVER}</td></tr>))}
            <tr style={{ fontWeight: 700 }}><td>Total at showrooms</td><td style={{ textAlign: 'right' }}>{d.kinds.VEHICLE.allocated}</td><td style={{ textAlign: 'right' }}>{d.kinds.HELMET.allocated}</td><td style={{ textAlign: 'right' }}>{d.kinds.PARKING_COVER.allocated}</td></tr></tbody></table>
      </div></div>)}

      {tab === 'record' && d.can_record && (<div className="card"><div className="card-pad">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 12 }}>
          <Field label="Action">{sel(t, (v) => setMv({ ...mv, move_type: v }), types.map((x) => [x, TYPE[x]]), '')}</Field>
          <Field label="Item">{sel(mv.item_id, (v) => setMv({ ...mv, item_id: v }), itOpts, 'Select item')}</Field>
          {needFrom && <Field label="From showroom">{sel(mv.from_branch_id, (v) => setMv({ ...mv, from_branch_id: v }), branchesFor(d.branches).map((b) => [b.id, b.name]), 'Select')}</Field>}
          {needTo && <Field label={t === 'COUNT' ? 'Showroom counted' : 'To showroom'}>{sel(mv.to_branch_id, (v) => setMv({ ...mv, to_branch_id: v }), branchesFor(d.branches).map((b) => [b.id, b.name]), 'Select')}</Field>}
          {t === 'COUNT'
            ? <Field label="Counted quantity"><input className="input" type="number" min="0" value={mv.counted_qty} onChange={(e) => setMv({ ...mv, counted_qty: e.target.value })} /></Field>
            : <Field label="Quantity"><input className="input" type="number" min="1" value={mv.qty} onChange={(e) => setMv({ ...mv, qty: e.target.value })} /></Field>}
          <Field label="Challan / reference"><input className="input" value={mv.reference} onChange={(e) => setMv({ ...mv, reference: e.target.value })} /></Field>
          {['ALLOCATE', 'TRANSFER', 'RECEIPT'].includes(t) && <Field label="Received by"><input className="input" value={mv.received_by} onChange={(e) => setMv({ ...mv, received_by: e.target.value })} /></Field>}
          <Field label={t === 'COUNT' ? 'Note (required)' : 'Note'}><input className="input" value={mv.note} onChange={(e) => setMv({ ...mv, note: e.target.value })} /></Field>
        </div>
        {t === 'COUNT' && <div className="muted-note" style={{ marginTop: 8 }}>The system compares your count with its figure and records the difference in the discrepancy report.</div>}
        <div style={{ marginTop: 12 }}><button className="btn btn-primary" disabled={busy || !mv.item_id} onClick={submit}>Save</button></div>
      </div></div>)}

      {(tab === 'history' || tab === 'discrepancy') && (<div className="card"><div className="card-pad">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          {sel(hf.item_id, (v) => setHf({ ...hf, item_id: v }), itOpts, 'All items')}
          {sel(hf.branch_id, (v) => setHf({ ...hf, branch_id: v }), brOpts, 'All showrooms')}
          {tab === 'history' && sel(hf.move_type, (v) => setHf({ ...hf, move_type: v }), Object.entries(TYPE), 'All actions')}
          <input className="input" style={{ maxWidth: 160 }} type="date" value={hf.date_from} onChange={(e) => setHf({ ...hf, date_from: e.target.value })} />
          <input className="input" style={{ maxWidth: 160 }} type="date" value={hf.date_to} onChange={(e) => setHf({ ...hf, date_to: e.target.value })} />
        </div>
        <div className="table-wrap">{move_rows.length === 0 ? <div className="muted-note">Nothing recorded.</div> : (
          <table className="data-table"><thead><tr><th>When</th><th>Action</th><th>Item</th><th style={{ textAlign: 'right' }}>{tab === 'discrepancy' ? 'Difference' : 'Qty'}</th>
            {tab === 'discrepancy' && <th style={{ textAlign: 'right' }}>Counted</th>}<th>From</th><th>To</th><th>By</th><th>Received by</th><th>Ref / note</th></tr></thead>
            <tbody>{move_rows.map((m) => (<tr key={m.id}><td>{fmtDateTime(m.at)}</td><td>{TYPE[m.type]}</td><td>{m.item}</td>
              <td style={{ textAlign: 'right', fontWeight: 600, color: m.type === 'COUNT' ? '#b42318' : undefined }}>{m.qty}</td>
              {tab === 'discrepancy' && <td style={{ textAlign: 'right' }}>{m.counted_qty}</td>}
              <td>{m.from || '—'}</td><td>{m.to || '—'}</td><td>{m.by || '—'}</td><td>{m.received_by || '—'}</td>
              <td>{[m.reference, m.note].filter(Boolean).join(' · ') || '—'}</td></tr>))}</tbody></table>)}</div>
      </div></div>)}

      {tab === 'items' && d.can_manage && (<div className="card"><div className="card-pad">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
          <Field label="Type">{sel(ni.kind, (v) => setNi({ ...ni, kind: v }), Object.entries(KIND).map(([k, v]) => [k, v.replace(/s$/, '')]), '')}</Field>
          <Field label={ni.kind === 'VEHICLE' ? 'Model' : ni.kind === 'HELMET' ? 'Helmet model / type' : 'Cover type'}><input className="input" value={ni.name} onChange={(e) => setNi({ ...ni, name: e.target.value })} /></Field>
          {ni.kind !== 'PARKING_COVER' && <Field label={ni.kind === 'VEHICLE' ? 'Variant' : 'Size'}><input className="input" value={ni.variant} onChange={(e) => setNi({ ...ni, variant: e.target.value })} /></Field>}
          {ni.kind !== 'PARKING_COVER' && <Field label="Color"><input className="input" value={ni.color} onChange={(e) => setNi({ ...ni, color: e.target.value })} /></Field>}
        </div>
        <div style={{ marginTop: 12 }}><button className="btn btn-primary" disabled={busy || !ni.name.trim()} onClick={addItem}>Add item</button></div>
      </div></div>)}
    </Layout>
  )
}
