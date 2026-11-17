// The customer journey as a stepper (green check = done, amber = now, red = rejected, grey = not yet).
// Same component for every department; <JourneySteps j=.../> is also used inside the Owner approval screen.
import { useEffect, useState } from 'react'
import api from '../../lib/api'

const SHORT = { followup: 'Follow-up', testride: 'Test ride', initial: 'Owner OK', paydocs: 'Pay & docs', final: 'Final OK' }
const COLOR = { DONE: '#1f8a4c', CURRENT: '#e09a00', REJECTED: '#d64545', WAITING: '#c9ced6' }

// Motorcycle (sport bike): big wheels, fairing + screen, tank, seat, tail, exhaust
export function BikeIcon({ size = 24, color = '#fff' }) {
  return (<svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke={color} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-label="motorcycle">
    <circle cx="7" cy="22.5" r="4.3" /><circle cx="25.5" cy="22.5" r="4.3" />
    <path d="M7 22.5l4.2-4.6h6.3l3.6-5.6" />
    <path d="M17.5 17.9l4.4 4.6" />
    <path d="M21.1 12.3l-3.4-2.6h-2.6" />
    <path d="M21.1 12.3l1.8-1.4 3.2.2-.8 3.3" />
    <path d="M23.3 12.9l2.2 9.6" />
    <path d="M10.6 14.6h6l.9 3.3" />
    <path d="M4.2 17.2l6.4-2.6" /></svg>)
}

export function JourneySteps({ j, vertical = false }) {
  const Dot = ({ s }) => (
    <div style={{ width: 34, height: 34, borderRadius: 17, background: s === 'WAITING' ? '#fff' : COLOR[s], border: `2px solid ${COLOR[s]}`,
                  color: s === 'WAITING' ? COLOR.WAITING : '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, flex: '0 0 34px' }}>
      {s === 'DONE' ? '✓' : s === 'REJECTED' ? '✕' : s === 'CURRENT' ? '●' : '○'}</div>)
  if (vertical) return (
    <div>{j.steps.map((s, i) => (
      <div key={s.key} style={{ display: 'flex', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}><Dot s={s.status} />
          {i < j.steps.length - 1 && <div style={{ width: 2, flex: 1, minHeight: 18, background: s.status === 'DONE' ? COLOR.DONE : '#e3e6ea' }} />}</div>
        <div style={{ paddingBottom: 14 }}><div style={{ fontWeight: 600 }}>{s.label} <span className="muted-note">· {s.dept}</span></div>
          <div className="muted-note">{s.detail}</div></div>
      </div>))}</div>)
  // arrow pipeline: one block per step, green = done, amber = now, red = rejected, grey = not yet
  const BG = { DONE: '#e3f5ea', CURRENT: '#fff1d6', REJECTED: '#fde4e4', WAITING: '#f0f2f6' }
  const FG = { DONE: '#17673a', CURRENT: '#8a5a00', REJECTED: '#b3261e', WAITING: '#8a93a0' }
  const MARK = { DONE: '✓ ', CURRENT: '● ', REJECTED: '✕ ', WAITING: '' }
  const clip = 'polygon(0 0, calc(100% - 14px) 0, 100% 50%, calc(100% - 14px) 100%, 0 100%, 14px 50%)'
  return (
    <div style={{ overflowX: 'auto', paddingBottom: 2 }}>
      <div style={{ display: 'flex', minWidth: j.steps.length * 96 }}>
        {j.steps.map((s, i) => (
          <div key={s.key} title={`${s.label} — ${s.dept}${s.detail ? ' — ' + s.detail : ''}`}
               style={{ flex: '1 1 0', minWidth: 0, background: BG[s.status], color: FG[s.status], fontWeight: 700, fontSize: 12.5,
                        padding: '13px 20px', marginLeft: i ? -8 : 0, clipPath: clip, whiteSpace: 'nowrap', textAlign: 'center',
                        overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {MARK[s.status]}{SHORT[s.key] || s.label}
          </div>))}
      </div>
    </div>)
}

const inr = (n) => (n == null ? '—' : '₹ ' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 }))
const niceStage = (x) => (x || '').toString().replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase())

function Tile({ label, value, sub, chip }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #edf0f4', borderRadius: 16, padding: '16px 20px', minWidth: 0 }}>
      <div style={{ fontSize: 12, color: '#8a93a0' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 800, marginTop: 4, color: '#1c2740', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
      {chip}
      {sub && <div style={{ fontSize: 12, color: '#8a93a0', marginTop: 8 }}>{sub}</div>}
    </div>)
}

// cards: show the Stage / Bike / On-road price / Paid so far tiles (customer file)
export default function JourneyBar({ leadId, refreshKey, cards = false }) {
  const [j, setJ] = useState(null)
  useEffect(() => { api.get(`/leads/${leadId}/journey`).then((r) => setJ(r.data)).catch(() => setJ(false)) }, [leadId, refreshKey])
  if (!j) return null
  const sm = j.summary || {}
  const nowChip = j.now
    ? <span style={{ display: 'inline-block', marginTop: 8, padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 700,
                     background: j.now.rejected ? '#fde4e4' : '#fff1d6', color: j.now.rejected ? '#b3261e' : '#8a5a00' }}>
        {j.now.rejected ? 'Rejected · ' : 'With '}{j.now.department}</span>
    : <span style={{ display: 'inline-block', marginTop: 8, padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 700, background: '#e3f5ea', color: '#17673a' }}>Complete</span>
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 24, fontWeight: 800, color: '#1c2740' }}>{j.customer_name}</div>
        <div className="muted-note" style={{ marginTop: 3 }}>{j.enquiry_no} · {j.source}{j.branch ? ' · ' + j.branch : ''}{!cards && j.model ? ' · ' + j.model : ''}
          {!cards && j.now && <> · <b style={{ color: j.now.rejected ? '#b3261e' : '#8a5a00' }}>{j.now.rejected ? 'Rejected at' : 'Now'}: {j.now.step} — with {j.now.department}</b></>}</div>
      </div>
      {cards && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 14, marginBottom: 14 }}>
          <Tile label="Stage" value={j.now ? j.now.step : niceStage(sm.stage) || 'Complete'} chip={nowChip} />
          <Tile label="Bike" value={j.model ? j.model + (j.color ? ' · ' + j.color : '') : '—'}
                sub={sm.other_models?.length ? '+ ' + sm.other_models.join(', ') + ' asked' : null} />
          {sm.on_road_price !== undefined && <Tile label="On-road price" value={inr(sm.on_road_price)} sub={sm.quotation_no || 'No quotation yet'} />}
          {sm.total_paid !== undefined && <Tile label="Paid so far" value={inr(sm.total_paid)} sub={sm.booking_no || 'Not booked yet'} />}
        </div>)}
      <div style={{ background: '#fff', border: '1px solid #edf0f4', borderRadius: 16, padding: '14px 18px' }}>
        <JourneySteps j={j} />
      </div>
    </div>
  )
}
