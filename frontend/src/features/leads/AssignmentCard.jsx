// Who owns this customer: claim it from the branch's unassigned pool, or hand it to another PBA of the branch.
import { useEffect, useState } from 'react'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'

export default function AssignmentCard({ lead, onChanged }) {
  const { user } = useAuth()
  const [pbas, setPbas] = useState([])
  const [pick, setPick] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const role = user?.role
  const unassigned = lead.assigned_user_id == null
  const mine = lead.assigned_user_id === user?.user_id
  const canAssign = ['CRE', 'OWNER', 'GM', 'ADMIN'].includes(role) || (role === 'PBA' && (unassigned || mine))
  const canClaim = role === 'PBA' && unassigned && lead.branch_id === user?.branch_id

  useEffect(() => {
    if (canAssign && lead.branch_id) api.get(`/me/branches/${lead.branch_id}/pbas`).then((r) => setPbas(r.data)).catch(() => setPbas([]))
  }, [lead.branch_id, canAssign])

  if (!unassigned && !canAssign) return null
  if (!unassigned && !pbas.length) return null

  async function act(path, body, ok) {
    setBusy(true); setMsg(null)
    try { await api.post(`/leads/${lead.lead_id}/${path}`, body); setMsg({ ok: true, text: ok }); setPick(''); onChanged && onChanged() }
    catch (e) { setMsg({ ok: false, text: e.response?.data?.detail || 'Could not do that.' }) } finally { setBusy(false) }
  }
  return (
    <div className="hint" style={{ marginBottom: 14, ...(unassigned ? { background: '#fff4d6', color: '#7a5a00' } : {}) }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>
        {unassigned ? 'Not assigned to any PBA yet (branch pool)' : `Assigned to ${lead.salesperson_name || 'a PBA'}`}</div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {canClaim && <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => act('claim', null, 'This customer is now yours.')}>Claim this customer</button>}
        {canAssign && pbas.length > 0 && (<>
          <select className="input" style={{ maxWidth: 220 }} value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">{unassigned ? 'Assign to…' : 'Hand over to…'}</option>
            {pbas.filter((p) => p.user_id !== lead.assigned_user_id).map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name}</option>)}</select>
          <button className="btn btn-outline btn-sm" disabled={busy || !pick} onClick={() => act('assign', { user_id: Number(pick) }, 'Assigned.')}>{unassigned ? 'Assign' : 'Hand over'}</button>
        </>)}
      </div>
      {msg && <div style={{ marginTop: 6, color: msg.ok ? undefined : '#b42318' }}>{msg.text}</div>}
    </div>
  )
}
