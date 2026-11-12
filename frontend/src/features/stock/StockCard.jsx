// Read-only stock at the showroom: vehicles, helmets and parking covers available.
import { useEffect, useState } from 'react'
import api from '../../lib/api'

const KINDS = [['VEHICLE', 'Vehicles available'], ['HELMET', 'Helmets'], ['PARKING_COVER', 'Parking covers']]

export default function StockCard({ params }) {
  const [d, setD] = useState(null)
  const key = JSON.stringify(params || {})
  useEffect(() => {
    setD(null)
    api.get('/stock/summary', { params }).then((r) => setD(r.data)).catch(() => setD(false))
  }, [key])
  if (d === false) return null
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-header"><h3>Stock at showroom</h3></div>
      <div className="card-pad">
        {!d ? <div className="muted-note">Loading…</div> : (<>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 12, marginBottom: 12 }}>
            {KINDS.map(([k, label]) => (
              <div key={k} style={{ border: '1px solid #eee', borderRadius: 10, padding: 12 }}>
                <div className="muted-note">{label}</div>
                <div style={{ fontSize: 26, fontWeight: 700 }}>{d.kinds[k].available_total}</div>
              </div>))}
          </div>
          {d.items.length === 0 ? <div className="muted-note">No stock has been entered yet.</div> : (
            <div className="table-wrap"><table className="data-table">
              <thead><tr><th>Item</th><th>Type</th><th style={{ textAlign: 'right' }}>Available</th></tr></thead>
              <tbody>{d.items.map((i) => (
                <tr key={i.id}><td>{i.label}</td><td>{i.kind.replace('_', ' ').toLowerCase()}</td>
                  <td style={{ textAlign: 'right', fontWeight: 600, color: i.total === 0 ? '#b42318' : undefined }}>{i.total}</td></tr>))}
              </tbody></table></div>)}
        </>)}
      </div>
    </div>
  )
}
