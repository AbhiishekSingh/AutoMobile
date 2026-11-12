// Monthly booking targets per PBA and bike model. Owner/GM/Admin edit; PBA/CRE view.
import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading } from '../../components/ui'
import api from '../../lib/api'

const thisMonth = () => new Date(Date.now() + 330 * 60 * 1000).toISOString().slice(0, 7)

export default function TargetsPage() {
  const [month, setMonth] = useState(thisMonth())
  const [d, setD] = useState(null)
  const [edit, setEdit] = useState({})      // "uid:mid" -> string
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => { setD(null); setEdit({}); api.get('/targets', { params: { month } }).then((r) => setD(r.data)).catch(() => setD(false)) }
  useEffect(() => { load() }, [month])

  if (d === null) return <Layout title="Targets"><Loading /></Layout>
  if (d === false) return <Layout title="Targets"><div className="hint">Could not load targets.</div></Layout>

  const past = month < thisMonth()
  const canEdit = d.can_edit && !past
  const key = (u, m) => `${u}:${m}`
  const val = (p, m) => edit[key(p.user_id, m)] ?? String(p.cells[m]?.target ?? 0)
  const dirty = Object.keys(edit).length > 0

  async function save() {
    setBusy(true); setMsg(null)
    try {
      const cells = Object.entries(edit).map(([k, v]) => { const [u, m] = k.split(':'); return { user_id: +u, model_id: +m, qty: Math.max(0, parseInt(v || '0', 10) || 0) } })
      await api.put('/targets', { month, cells })
      setMsg({ ok: true, text: 'Targets saved.' }); load()
    } catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not save.' }) } finally { setBusy(false) }
  }
  const totT = d.pbas.reduce((a, p) => a + p.target, 0), totA = d.pbas.reduce((a, p) => a + p.achieved, 0)

  return (
    <Layout title="Targets" sub="Booking target vs achievement, by PBA and model">
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="input" type="month" style={{ maxWidth: 180 }} value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
        <span className="muted-note">Achieved = bookings made in the month (cancelled bookings not counted).</span>
        {d.can_edit && past && <span className="muted-note">Past months can't be changed.</span>}
      </div>
      {msg && <div className="hint" style={{ margin: '0 0 10px', ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}
      <div className="card"><div className="card-pad table-wrap">
        {d.pbas.length === 0 ? <div className="muted-note">No PBAs to show.</div> : (
          <table className="data-table"><thead><tr><th>PBA</th>
            {d.models.map((m) => <th key={m.id} style={{ textAlign: 'center' }}>{m.name}</th>)}
            <th style={{ textAlign: 'right' }}>Target</th><th style={{ textAlign: 'right' }}>Achieved</th><th style={{ textAlign: 'right' }}>%</th></tr></thead>
            <tbody>{d.pbas.map((p) => (<tr key={p.user_id}><td>{p.name}</td>
              {d.models.map((m) => (<td key={m.id} style={{ textAlign: 'center' }}>
                {canEdit
                  ? <><input className="input" type="number" min="0" style={{ width: 64, display: 'inline-block', padding: '4px 6px' }} value={val(p, m.id)}
                      onChange={(e) => setEdit({ ...edit, [key(p.user_id, m.id)]: e.target.value })} /><div className="muted-note">got {p.cells[m.id].achieved}</div></>
                  : <>{p.cells[m.id].achieved} / {p.cells[m.id].target}</>}
              </td>))}
              <td style={{ textAlign: 'right' }}>{p.target}</td><td style={{ textAlign: 'right' }}>{p.achieved}</td>
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{p.pct === null ? '—' : `${p.pct}%`}</td></tr>))}
              <tr style={{ fontWeight: 700 }}><td>Total</td>{d.models.map((m) => <td key={m.id} />)}
                <td style={{ textAlign: 'right' }}>{totT}</td><td style={{ textAlign: 'right' }}>{totA}</td>
                <td style={{ textAlign: 'right' }}>{totT ? Math.round(totA * 100 / totT) + '%' : '—'}</td></tr></tbody></table>)}
        {canEdit && <div style={{ marginTop: 12 }}><button className="btn btn-primary" disabled={busy || !dirty} onClick={save}>Save targets</button></div>}
      </div></div>
    </Layout>
  )
}
