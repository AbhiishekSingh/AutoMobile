// Row of tabs; only the chosen tab's content is visible (others stay mounted but hidden, so forms and loaded data
// are kept). Usage: <Tabs tabs={[{ key, label, count }]}> <Tab k="key">...</Tab> </Tabs>
import { useState } from 'react'

const CSS = `
.modern .tabs-shell { background: #fff; border: 1px solid #edf0f4; border-radius: 16px; overflow: hidden; margin-bottom: 16px; }
.modern .tabs-body > div > .sec-card, .modern .tabs-body > div > .card, .modern .tabs-body > div > div > .sec-card, .modern .tabs-body > div > div > .card { border: 0; box-shadow: none; border-radius: 0; margin: 0; }
.modern .tabs-body > div > .sec-card + .sec-card, .modern .tabs-body > div > .sec-card + .card, .modern .tabs-body > div > .card + .sec-card, .modern .tabs-body > div > .card + .card { border-top: 1px solid #f1f3f6; }
.modern .sec-card, .modern .card { border: 1px solid #edf0f4; box-shadow: none; border-radius: 14px; margin-bottom: 14px; }
.modern .sec-head { padding: 16px 22px 0; }
.modern .sec-title, .modern .card-header h3 { font-size: 15px; font-weight: 700; text-transform: none; letter-spacing: 0; color: #1c2740; }
.modern .card-header { padding: 14px 22px; border-bottom: 1px solid #f1f3f6; }
.modern .field-grid { grid-template-columns: repeat(3, 1fr); gap: 16px 32px; padding: 14px 22px 20px; }
.modern .fg { gap: 0; }
.modern .fg-ico { display: none; }
.modern .fg-label { font-size: 12px; font-weight: 500; color: #8a93a0; margin-bottom: 2px; }
.modern .fg-value { font-size: 14.5px; font-weight: 600; color: #1c2740; }
.modern .btn-sm { border-radius: 8px; }
.modern .data-table th { font-size: 12px; font-weight: 600; color: #8a93a0; text-transform: none; letter-spacing: 0; background: #fafbfc; }
.modern .data-table td { padding-top: 11px; padding-bottom: 11px; }
@media (max-width: 900px) { .modern .field-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 560px) { .modern .field-grid { grid-template-columns: 1fr; } }
`

export function Tab({ children }) { return <>{children}</> }

export default function Tabs({ tabs, children, initial }) {
  const [cur, setCur] = useState(initial || tabs[0].key)
  const panels = Array.isArray(children) ? children : [children]
  return (
    <div className="modern">
      <style>{CSS}</style>
      <div className="tabs-shell">
      <div style={{ display: 'flex', gap: 28, overflowX: 'auto', background: '#fff', borderBottom: '1px solid #eceff3', padding: '0 22px' }}>
        {tabs.map((t) => {
          const on = cur === t.key
          return (
            <div key={t.key} onClick={() => setCur(t.key)} role="tab" aria-selected={on}
              style={{ padding: '15px 0 13px', cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: 600, fontSize: 14,
                       color: on ? '#2f80ed' : '#4a5361', borderBottom: on ? '3px solid #2f80ed' : '3px solid transparent' }}>
              {t.label}{t.count != null && <span style={{ marginLeft: 6, fontSize: 12, color: on ? '#2f80ed' : '#8a93a0' }}>({t.count})</span>}
            </div>)
        })}
      </div>
      <div className="tabs-body">
      {panels.filter(Boolean).map((p, i) => (<div key={p.props?.k ?? i} style={{ display: p.props?.k === cur ? 'block' : 'none' }}>{p}</div>))}
      </div>
      </div>
    </div>)
}
