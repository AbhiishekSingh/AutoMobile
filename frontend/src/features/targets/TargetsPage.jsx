// Monthly booking targets per PBA and bike model. Owner/GM/Admin edit; PBA/CRE view.
import { useEffect, useMemo, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading } from '../../components/ui'
import api from '../../lib/api'

const thisMonth = () => new Date(Date.now() + 330 * 60 * 1000).toISOString().slice(0, 7)
const shiftMonth = (m, n) => { const [y, mo] = m.split('-').map(Number); const d = new Date(Date.UTC(y, mo - 1 + n, 1)); return d.toISOString().slice(0, 7) }
const niceMonth = (m) => new Date(m + '-01T00:00:00Z').toLocaleDateString('en-IN', { month: 'long', year: 'numeric', timeZone: 'UTC' })
const tone = (pct, expected) => (pct === null ? '#9aa3b0' : pct >= expected ? '#1f8a4c' : pct >= expected * 0.7 ? '#e09a00' : '#d93025')

const CSS = `
.tg-seg{display:inline-flex;align-items:center;gap:6px}
.tg-hero{background:linear-gradient(135deg,#1d4fa8,#2f80ed);color:#fff;border-radius:16px;padding:18px 22px}
.tg-kpi{background:#fff;border:1px solid #edf0f4;border-radius:16px;padding:16px 18px}
.tg-kpi .l{color:#7c8696;font-size:12.5px;font-weight:600}.tg-kpi .v{font-size:26px;font-weight:800;margin-top:4px;color:#1c2740}
.tg-bar{height:9px;border-radius:5px;background:#eef0f4;overflow:hidden;position:relative}.tg-bar i{display:block;height:100%;border-radius:5px}
.tg-row{display:grid;grid-template-columns:minmax(150px,1.2fr) minmax(160px,2fr) 90px 90px auto;gap:14px;align-items:center;padding:13px 20px;border-top:1px solid #f1f3f6}
.tg-cells{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:10px;padding:6px 20px 18px;background:#fafbfd;border-top:1px solid #f1f3f6}
.tg-cell{background:#fff;border:1px solid #e5e9f0;border-radius:10px;padding:8px 10px}
.tg-cell .n{font-size:11.5px;font-weight:700;color:#6b7686;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tg-cell input{width:100%;border:1px solid #dfe3ea;border-radius:8px;padding:6px 8px;font:inherit;font-weight:700;margin:5px 0 2px}
.tg-chip{display:inline-block;border-radius:99px;padding:2px 10px;font-size:12px;font-weight:700;background:#eef3fc;color:#2459c4;margin:0 6px 6px 0}
.tg-save{position:sticky;bottom:0;z-index:5;background:#fff;border:1px solid #dfe3ea;border-radius:14px;padding:12px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;box-shadow:0 -6px 24px rgba(20,40,80,.08);margin-top:14px}
@media(max-width:900px){.tg-row{grid-template-columns:1fr 1fr;row-gap:8px}.tg-row .tg-barcol{grid-column:1/-1}}
`

export default function TargetsPage() {
  const [month, setMonth] = useState(thisMonth())
  const [d, setD] = useState(null)
  const [edit, setEdit] = useState({})      // "uid:mid" -> string
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(null)    // PBA row whose model targets are open
  const [branch, setBranch] = useState('')
  const [branches, setBranches] = useState([])

  const load = () => { setD(null); setEdit({}); setOpen(null); api.get('/targets', { params: { month } }).then((r) => setD(r.data)).catch(() => setD(false)) }
  useEffect(() => { load() }, [month])
  useEffect(() => { api.get('/me/branches').then((r) => setBranches(r.data)).catch(() => setBranches([])) }, [])

  const rows = useMemo(() => (d ? d.pbas.filter((p) => !branch || String(p.branch_id) === branch) : []), [d, branch])

  if (d === null) return <Layout title="Targets"><Loading /></Layout>
  if (d === false) return <Layout title="Targets"><div className="hint">Could not load targets.</div></Layout>

  const past = month < thisMonth()
  const current = month === thisMonth()
  const canEdit = d.can_edit && !past
  const key = (u, m) => `${u}:${m}`
  const val = (p, m) => edit[key(p.user_id, m)] ?? String(p.cells[m]?.target ?? 0)
  const num = (p, m) => Math.max(0, parseInt(val(p, m) || '0', 10) || 0)
  const pTarget = (p) => d.models.reduce((a, m) => a + num(p, m.id), 0)   // includes unsaved edits
  const dirty = Object.keys(edit).length
  const bName = (id) => branches.find((b) => b.branch_id === id)?.name?.replace(/^S\.?K\.? ?KTM /i, '') || ''

  const totT = rows.reduce((a, p) => a + pTarget(p), 0), totA = rows.reduce((a, p) => a + p.achieved, 0)
  const pct = totT ? Math.round(totA * 100 / totT) : null
  const [yy, mm] = month.split('-').map(Number)
  const daysIn = new Date(yy, mm, 0).getDate()
  const dayNow = current ? Math.min(daysIn, new Date(Date.now() + 330 * 60 * 1000).getUTCDate()) : daysIn
  const expected = past ? 100 : Math.round(dayNow * 100 / daysIn)
  const left = Math.max(0, daysIn - dayNow)
  const perDay = left && totT > totA ? ((totT - totA) / left).toFixed(1) : null
  const byModel = d.models.map((m) => ({ ...m, t: rows.reduce((a, p) => a + num(p, m.id), 0), a: rows.reduce((a, p) => a + (p.cells[m.id]?.achieved || 0), 0) }))

  async function save() {
    setBusy(true); setMsg(null)
    try {
      const cells = Object.entries(edit).map(([k, v]) => { const [u, m] = k.split(':'); return { user_id: +u, model_id: +m, qty: Math.max(0, parseInt(v || '0', 10) || 0) } })
      await api.put('/targets', { month, cells })
      await load(); setMsg({ ok: true, text: `Targets saved for ${niceMonth(month)}.` })
    } catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not save.' }) } finally { setBusy(false) }
  }
  async function copyLast() {
    setMsg(null)
    try {
      const r = await api.get('/targets', { params: { month: shiftMonth(month, -1) } })
      const next = {}
      r.data.pbas.forEach((p) => d.models.forEach((m) => { const t = p.cells[m.id]?.target || 0; if (t !== (d.pbas.find((x) => x.user_id === p.user_id)?.cells[m.id]?.target || 0)) next[key(p.user_id, m.id)] = String(t) }))
      if (!Object.keys(next).length) { setMsg({ ok: false, text: `Nothing to copy: ${niceMonth(shiftMonth(month, -1))} has the same targets or none.` }); return }
      setEdit({ ...edit, ...next }); setMsg({ ok: true, text: `Copied from ${niceMonth(shiftMonth(month, -1))}. Check the numbers, then press Save.` })
    } catch (e) { setMsg({ ok: false, text: 'Could not read last month.' }) }
  }

  return (
    <Layout title="Targets" sub="Booking target vs achievement, by PBA and model">
      <style>{CSS}</style>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <div className="tg-seg">
          <button className="btn btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, -1))}>◀</button>
          <b style={{ minWidth: 130, textAlign: 'center', fontSize: 15 }}>{niceMonth(month)}</b>
          <button className="btn btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, 1))}>▶</button>
          {!current && <button className="btn btn-outline btn-sm" onClick={() => setMonth(thisMonth())}>This month</button>}
        </div>
        {d.can_edit && branches.length > 1 && (
          <select className="input" style={{ maxWidth: 220 }} value={branch} onChange={(e) => setBranch(e.target.value)}>
            <option value="">All branches</option>{branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{b.name}</option>)}</select>)}
        <span style={{ flex: 1 }} />
        {canEdit && <button className="btn btn-outline btn-sm" onClick={copyLast}>Copy last month's targets</button>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 14, marginBottom: 14 }}>
        <div className="tg-hero">
          <div style={{ opacity: .85, fontWeight: 600, fontSize: 13 }}>Achieved this month</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6 }}><span style={{ fontSize: 44, fontWeight: 800, lineHeight: 1 }}>{totA}</span><span style={{ opacity: .85 }}>of {totT} target</span></div>
          <div style={{ background: 'rgba(255,255,255,.25)', height: 9, borderRadius: 5, marginTop: 12 }}><div style={{ width: `${Math.min(100, pct || 0)}%`, height: '100%', background: '#fff', borderRadius: 5 }} /></div>
          <div style={{ opacity: .9, marginTop: 8, fontSize: 13 }}>{pct === null ? 'No targets set yet' : `${pct}% achieved`}</div>
        </div>
        <div className="tg-kpi"><div className="l">Achievement</div><div className="v" style={{ color: tone(pct, expected) }}>{pct === null ? '—' : `${pct}%`}</div>
          <div className="muted-note">{past ? 'Month closed' : `Expected by today: ${expected}%`}</div></div>
        <div className="tg-kpi"><div className="l">{past ? 'Month' : 'Days left'}</div><div className="v">{past ? 'Closed' : left}</div>
          <div className="muted-note">{perDay ? `Needs ${perDay} bookings a day` : current ? (totT && totA >= totT ? 'Target reached 🎉' : 'Set targets to see the daily pace') : ' '}</div></div>
        <div className="tg-kpi"><div className="l">Still to book</div><div className="v">{Math.max(0, totT - totA)}</div><div className="muted-note">{rows.length} PBA{rows.length === 1 ? '' : 's'}{branch ? ' in this branch' : ''}</div></div>
      </div>
      <div className="muted-note" style={{ marginBottom: 14 }}>Achieved = bookings made in the month (cancelled bookings not counted). {d.can_edit && past && "Past months can't be changed."}</div>

      <div className="card" style={{ marginBottom: 14, overflow: 'hidden' }}>
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between' }}><h3>By PBA</h3>{canEdit && <span className="muted-note">Click “Set targets” to enter numbers per model</span>}</div>
        {rows.length === 0 && <div className="card-pad muted-note">No PBAs to show.</div>}
        {rows.map((p) => {
          const t = pTarget(p), pp = t ? Math.round(p.achieved * 100 / t) : null, isOpen = open === p.user_id
          const changed = d.models.some((m) => key(p.user_id, m.id) in edit)
          return (
            <div key={p.user_id}>
              <div className="tg-row">
                <div><b>{p.name}</b>{changed && <span style={{ color: '#b45309', fontWeight: 700, fontSize: 12 }}> ● edited</span>}<div className="muted-note">{bName(p.branch_id)}</div></div>
                <div className="tg-barcol"><div className="tg-bar"><i style={{ width: `${Math.min(100, pp || 0)}%`, background: tone(pp, expected) }} /></div>
                  <div className="muted-note" style={{ marginTop: 4 }}>{p.achieved} booked of {t}</div></div>
                <div style={{ textAlign: 'right' }}><div className="muted-note">Target</div><b>{t}</b></div>
                <div style={{ textAlign: 'right' }}><div className="muted-note">Achieved</div><b style={{ color: tone(pp, expected) }}>{pp === null ? '—' : `${pp}%`}</b></div>
                <div style={{ textAlign: 'right' }}>{(canEdit || t > 0) && <button className="btn btn-outline btn-sm" onClick={() => setOpen(isOpen ? null : p.user_id)}>{isOpen ? 'Close' : canEdit ? 'Set targets' : 'By model'}</button>}</div>
              </div>
              {isOpen && (canEdit
                ? <div className="tg-cells">{d.models.map((m) => (
                    <label key={m.id} className="tg-cell"><div className="n" title={m.name}>{m.name}</div>
                      <input type="number" min="0" inputMode="numeric" value={val(p, m.id)} onFocus={(e) => e.target.select()} onChange={(e) => setEdit({ ...edit, [key(p.user_id, m.id)]: e.target.value })} />
                      <div className="muted-note">booked {p.cells[m.id]?.achieved || 0}</div></label>))}</div>
                : <div className="tg-cells" style={{ display: 'block' }}>{d.models.filter((m) => (p.cells[m.id]?.target || 0) > 0 || (p.cells[m.id]?.achieved || 0) > 0)
                    .map((m) => <span key={m.id} className="tg-chip">{m.name}: {p.cells[m.id].achieved} / {p.cells[m.id].target}</span>)}</div>)}
            </div>)
        })}
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="card-header"><h3>By model</h3></div>
        <div className="card-pad" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: '12px 28px' }}>
          {byModel.filter((m) => m.t > 0 || m.a > 0).length === 0 && <div className="muted-note">No targets or bookings for any model yet.</div>}
          {byModel.filter((m) => m.t > 0 || m.a > 0).map((m) => { const pm = m.t ? Math.round(m.a * 100 / m.t) : null; return (
            <div key={m.id}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5 }}><b>{m.name}</b><span className="muted-note"><b style={{ color: '#1c2740' }}>{m.a}</b> / {m.t}{pm !== null && ` · ${pm}%`}</span></div>
              <div className="tg-bar" style={{ marginTop: 5 }}><i style={{ width: `${Math.min(100, pm || 0)}%`, background: tone(pm, expected) }} /></div></div>) })}
        </div>
      </div>

      {(dirty > 0 || msg) && (
        <div className="tg-save">
          {dirty > 0 && <><b>{dirty} change{dirty === 1 ? '' : 's'} not saved</b>
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={save}>Save targets</button>
            <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => { setEdit({}); setMsg(null) }}>Discard</button></>}
          {msg && <span style={{ fontWeight: 600, color: msg.ok ? '#0f6b3a' : '#7a2318' }}>{msg.ok ? '✓ ' : '✕ '}{msg.text}</span>}
        </div>)}
    </Layout>
  )
}
