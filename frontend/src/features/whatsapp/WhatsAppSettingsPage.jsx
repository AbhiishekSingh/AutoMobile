// Owner / GM / Admin: the links used in WhatsApp messages (default + per showroom).
import { useEffect, useState } from 'react'
import Layout from '../../components/Layout'
import { Loading } from '../../components/ui'
import api from '../../lib/api'

export default function WhatsAppSettingsPage() {
  const [d, setD] = useState(null)
  const [vals, setVals] = useState({})
  const [msg, setMsg] = useState(null)
  const k = (b, key) => `${b ?? 'all'}|${key}`
  const load = () => api.get('/whatsapp/links').then((r) => {
    setD(r.data); const v = {}; r.data.values.forEach((x) => { v[k(x.branch_id, x.key)] = x.value || '' }); setVals(v)
  }).catch(() => setD(false))
  useEffect(() => { load() }, [])
  if (d === null) return <Layout title="WhatsApp settings"><Loading /></Layout>
  if (d === false) return <Layout title="WhatsApp settings"><div className="hint">Could not load.</div></Layout>

  async function save(branch, key) {
    setMsg(null)
    try { await api.put('/whatsapp/links', { branch_id: branch, key, value: vals[k(branch, key)] || '' }); setMsg({ ok: true, text: 'Saved.' }); load() }
    catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not save.' }) }
  }
  async function preset() {
    if (!window.confirm('Fill the Google review, Instagram and KTM app links for the showrooms from the dealership list? Links you already saved are kept.')) return
    setMsg(null)
    try {
      const r = (await api.post('/whatsapp/links/preset')).data
      setMsg({ ok: true, text: `${r.links_set} link(s) filled. Matched: ${r.matched.join('; ') || 'none'}.` +
        (r.branches_not_matched.length ? ` Not matched (set by hand): ${r.branches_not_matched.join(', ')}.` : '') +
        (r.list_entries_without_branch.length ? ` No branch found for: ${r.list_entries_without_branch.join(', ')}.` : '') })
      load()
    } catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not fill the links.' }) }
  }
  const rows = [{ id: null, name: 'All showrooms (default)' }, ...d.branches]
  return (
    <Layout title="WhatsApp settings" sub="Links sent in delivery and review messages">
      {!d.configured && <div className="hint" style={{ marginBottom: 10 }}>WhatsApp is not connected on the server yet (token and phone number ID missing).</div>}
      {msg && <div className="hint" style={{ marginBottom: 10, ...(msg.ok ? {} : { background: 'var(--red-light)', color: '#7a2318' }) }}>{msg.text}</div>}
      <div style={{ marginBottom: 10 }}><button className="btn btn-primary btn-sm" onClick={preset}>Fill showroom links from the dealership list</button></div>
      <div className="muted-note" style={{ marginBottom: 10 }}>A showroom's own link is used when set; otherwise the default applies.</div>
      {rows.map((b) => (
        <div className="card" key={b.id ?? 'all'} style={{ marginBottom: 12 }}>
          <div className="card-header"><h3>{b.name}</h3></div>
          <div className="card-pad">
            {d.keys.map((x) => (
              <div key={x.key} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                <label style={{ width: 160 }}>{x.label}</label>
                <input className="input" style={{ flex: 1, minWidth: 240 }} placeholder="https://" value={vals[k(b.id, x.key)] || ''}
                  onChange={(e) => setVals({ ...vals, [k(b.id, x.key)]: e.target.value })} />
                <button className="btn btn-outline btn-sm" onClick={() => save(b.id, x.key)}>Save</button>
              </div>))}
          </div>
        </div>))}
    </Layout>
  )
}
