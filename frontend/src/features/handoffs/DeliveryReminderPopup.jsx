// Owner only: on first load after signing in, a pop-up lists approved deliveries due in the next 5 days.
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'
import { useAuth } from '../../lib/auth'

const KEY = 'sk-crm-delivery-popup-shown'

export default function DeliveryReminderPopup() {
  const { user } = useAuth()
  const nav = useNavigate()
  const [rows, setRows] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (user?.role !== 'OWNER') return
    let shown = false
    try { shown = sessionStorage.getItem(KEY) === String(user.user_id) } catch (_) {}
    if (shown) return
    api.get('/handoffs/delivery-reminders').then((r) => {
      if (r.data?.length) { setRows(r.data); setOpen(true) }
      try { sessionStorage.setItem(KEY, String(user.user_id)) } catch (_) {}
    }).catch(() => {})
  }, [user?.user_id, user?.role])

  if (!open) return null
  const when = (n) => (n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : `In ${n} days`)
  return (
    <div className="modal-overlay open" onClick={() => setOpen(false)}>
      <div className="modal-box" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h3 style={{ margin: 0 }}>Deliveries due in the next 5 days</h3>
          <button className="btn btn-outline btn-sm" onClick={() => setOpen(false)}>Close</button></div>
        <div style={{ padding: '8px 20px 16px' }}>
          <table className="data-table"><thead><tr><th>Customer</th><th>Enquiry</th><th>Delivery date</th><th>Due</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.lead_id} style={{ cursor: 'pointer' }} onClick={() => { setOpen(false); nav(`/handoff/${r.lead_id}`) }}>
                <td className="cell-primary">{r.customer_name}</td><td>{r.enquiry_no}</td><td>{r.delivery_date}</td>
                <td><span className={'badge ' + (r.days_left <= 1 ? 'badge-red' : 'badge-amber')}>{when(r.days_left)}</span></td>
              </tr>))}</tbody></table>
          <div className="muted-note" style={{ marginTop: 8 }}>Click a customer to open the file.</div>
        </div>
      </div>
    </div>
  )
}
