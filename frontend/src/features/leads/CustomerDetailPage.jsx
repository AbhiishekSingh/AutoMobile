import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Layout from '../../components/Layout'
import { Empty, Loading, fmtDate, fmtTime, fmtDateTime } from '../../components/ui'
import api from '../../lib/api'

// ---- badge colour helpers ----
function oppClass(name) {
  const n = (name || '').toUpperCase()
  if (n.includes('HOT') || n.includes('LOST')) return 'badge-red'
  if (n.includes('WARM')) return 'badge-amber'
  if (n.includes('BOOKING') || n.includes('DELIVERED') || n.includes('DELIVERY')) return 'badge-green'
  if (n.includes('COLD') || n.includes('FUTURE')) return 'badge-sky'
  if (n.includes('DEAD') || n.includes('CLOSED')) return 'badge-gray'
  return 'badge-gray'
}
function dispClass(name) {
  const n = (name || '').toUpperCase()
  if (n.includes('RINGING')) return 'badge-purple'
  if (n.includes('PLANNING') || n.includes('BOOKING')) return 'badge-green'
  if (n.includes('TEST RIDE')) return 'badge-sky'
  if (n.includes('INCORRECT') || n.includes('SWITCH OFF') || n.includes('CANCEL') || n.includes('ISSUE')) return 'badge-red'
  return 'badge-sky'
}
const Badge = ({ name, kind }) =>
  name ? <span className={'badge ' + (kind === 'disp' ? dispClass(name) : oppClass(name))}>{name}</span>
       : <span style={{ color: '#94A3B8' }}>—</span>

// Convert an IST-naive ISO string to a datetime-local input value (YYYY-MM-DDTHH:MM).
const toInput = (iso) => (iso ? String(iso).replace(' ', 'T').slice(0, 16) : '')

// Editable field cell: shows read value, or an input/select when `editing`.
function EField({ icon, label, editing, display, value, onChange, type = 'text', options, valueClass = '' }) {
  return (
    <div className="fg">
      <span className="fg-ico">{icon}</span>
      <div className="fg-body" style={{ flex: 1 }}>
        <div className="fg-label">{label}</div>
        {editing ? (
          options ? (
            <select className="input" value={value ?? ''} onChange={onChange}>
              <option value="">— select —</option>
              {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          ) : (
            <input className="input" type={type} value={value ?? ''} onChange={onChange} />
          )
        ) : (
          <div className={'fg-value ' + valueClass}>{display ?? '—'}</div>
        )}
      </div>
    </div>
  )
}

// Section header with edit / save / cancel controls.
function SecHead({ title, section, editing, onEdit, onSave, onCancel }) {
  const isEditing = editing === section
  return (
    <div className="sec-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: 0 }}>
      <h3 className="sec-title">{title}</h3>
      {isEditing ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-outline btn-sm" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary btn-sm" onClick={onSave}>Save</button>
        </div>
      ) : (
        <button className="btn btn-outline btn-sm" onClick={() => onEdit(section)} title="Edit this section"
                disabled={editing && editing !== section}>✏️ Edit</button>
      )}
    </div>
  )
}

const EMPTY_FU = { remark: '', contacted: true, disposition_id: '', opportunity_status_id: '', next_followup_at: '' }
const EMPTY_TR = { model_id: '', color: '', status: 'BOOKED', scheduled_at: '', slot: '', preferred_location: 'Showroom' }

const STAGES = ['OPEN', 'CLOSED', 'BOOKED', 'INVOICED']
const SECTION_FIELDS = {
  enquiry: ['enquiry_at', 'first_contact_at', 'dealer_code', 'salesperson_email', 'mode_id'],
  vehicle: ['full_name', 'phone', 'pincode', 'model_id', 'color', 'sku_code'],
  status: ['enquiry_stage', 'opportunity_status_id', 'disposition_id', 'lost_reason_id', 'next_followup_at', 'ageing_days'],
}
const NUMERIC = new Set(['mode_id', 'model_id', 'opportunity_status_id', 'disposition_id', 'lost_reason_id', 'ageing_days'])

export default function CustomerDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const [lead, setLead] = useState(null)
  const [lookups, setLookups] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')

  const [editing, setEditing] = useState(null)   // 'enquiry' | 'vehicle' | 'status' | null
  const [form, setForm] = useState({})

  const [fu, setFu] = useState(EMPTY_FU)
  const [tr, setTr] = useState(EMPTY_TR)

  function load() {
    setErr('')
    api.get(`/leads/${id}`).then((r) => setLead(r.data)).catch(() => setErr('Lead not found.'))
  }
  useEffect(() => { load(); api.get('/lookups').then((r) => setLookups(r.data)).catch(() => {}) }, [id])

  function startEdit(section) {
    if (!lead) return
    setForm({
      enquiry_at: toInput(lead.enquiry_date), first_contact_at: toInput(lead.first_contact_at),
      dealer_code: lead.dealer_code || '', salesperson_email: lead.salesperson_email || '',
      mode_id: lead.mode_id || '',
      full_name: lead.customer_name || '', phone: lead.mobile || '', pincode: lead.pincode || '',
      model_id: lead.model_id || '', color: lead.color || '', sku_code: lead.sku_code || '',
      enquiry_stage: lead.enquiry_stage || '', opportunity_status_id: lead.opportunity_status_id || '',
      disposition_id: lead.disposition_id || '', lost_reason_id: lead.lost_reason_id || '',
      next_followup_at: toInput(lead.next_followup_at), ageing_days: lead.ageing_days ?? '',
    })
    setEditing(section); setMsg('')
  }
  const setFld = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function saveSection() {
    const keys = SECTION_FIELDS[editing] || []
    const payload = {}
    for (const k of keys) {
      let v = form[k]
      if (NUMERIC.has(k)) v = v === '' || v == null ? null : Number(v)
      else v = v === '' ? null : v
      payload[k] = v
    }
    try {
      await api.patch(`/leads/${id}`, payload)
      setEditing(null); setMsg('Changes saved.'); load()
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Could not save changes.')
    }
  }

  // follow-up + test-ride (unchanged behaviour)
  const setFuF = (k) => (e) => setFu({ ...fu, [k]: e.target.value })
  const setTrF = (k) => (e) => setTr({ ...tr, [k]: e.target.value })
  async function addFollowup(e) {
    e.preventDefault(); setMsg('')
    try {
      await api.post(`/leads/${id}/followups`, {
        remark: fu.remark || null, contacted: fu.contacted === true || fu.contacted === 'true',
        disposition_id: fu.disposition_id ? Number(fu.disposition_id) : null,
        opportunity_status_id: fu.opportunity_status_id ? Number(fu.opportunity_status_id) : null,
        next_followup_at: fu.next_followup_at || null,
      })
      setFu(EMPTY_FU); setMsg('Follow-up added.'); load()
    } catch (e2) { setMsg(e2.response?.data?.detail || 'Could not add follow-up.') }
  }
  async function addTestRide(e) {
    e.preventDefault(); setMsg('')
    try {
      await api.post(`/leads/${id}/test-rides`, {
        model_id: tr.model_id ? Number(tr.model_id) : null, color: tr.color || null, status: tr.status,
        scheduled_at: tr.scheduled_at || null, slot: tr.slot || null, preferred_location: tr.preferred_location || null,
      })
      setTr(EMPTY_TR); setMsg('Test ride saved.'); load()
    } catch (e2) { setMsg(e2.response?.data?.detail || 'Could not save test ride.') }
  }

  if (err) return <Layout title="Customer Details"><div className="card"><div className="card-pad">{err}</div></div></Layout>
  if (!lead) return <Layout title="Customer Details"><Loading /></Layout>

  const ed = (s) => editing === s
  const latestTr = lead.test_rides[0]
  const anyCompleted = lead.test_rides.some((t) => t.completed)
  const lastFu = lead.followups[0]
  const contacted = !!lead.first_contact_at

  return (
    <Layout title="CUSTOMER DETAILS" sub="View & edit complete information of the customer"
            back={{ label: 'Back to Leads', onClick: () => nav('/leads') }}>

      {msg && <div className="hint" style={{ marginBottom: 14 }}>{msg}</div>}

      {/* ENQUIRY INFORMATION */}
      <div className="sec-card">
        <SecHead title="Enquiry Information" section="enquiry" editing={editing}
                 onEdit={startEdit} onSave={saveSection} onCancel={() => setEditing(null)} />
        <div className="field-grid">
          <EField icon="📄" label="Enquiry Number" editing={false} display={lead.enquiry_no} />
          <EField icon="📅" label="Enquiry Date & Time" editing={ed('enquiry')} type="datetime-local"
                  display={`${fmtDate(lead.enquiry_date)} · ${fmtTime(lead.enquiry_date)}`}
                  value={form.enquiry_at} onChange={setFld('enquiry_at')} />
          <EField icon="🕒" label="First Follow Up DateTime" editing={ed('enquiry')} type="datetime-local"
                  display={<>{fmtDateTime(lead.first_contact_at)}
                    {lead.within_3hrs === true && <span className="badge badge-green" style={{ marginLeft: 8 }}>3 HRS</span>}
                    {lead.within_3hrs === false && <span className="badge badge-red" style={{ marginLeft: 8 }}>&gt;3 HRS</span>}</>}
                  value={form.first_contact_at} onChange={setFld('first_contact_at')} />
          <EField icon="✉️" label="Salesperson Email" editing={ed('enquiry')} valueClass="link"
                  display={lead.salesperson_email} value={form.salesperson_email} onChange={setFld('salesperson_email')} />
          <EField icon="📄" label="Enquiry Dealer Code" editing={ed('enquiry')}
                  display={lead.dealer_code} value={form.dealer_code} onChange={setFld('dealer_code')} />
          <EField icon="📄" label="Enquiry Branch Code" editing={false} display={lead.dealer_code} />
          <EField icon="🔁" label="Followup Enquiry Mode" editing={ed('enquiry')} options={lookups?.enquiry_modes}
                  display={lead.followup_enquiry_mode} value={form.mode_id} onChange={setFld('mode_id')} />
          <EField icon="🏢" label="Enquiry Branch Name" editing={false} display={lead.branch_name} />
          <EField icon="👤" label="Salesperson Name" editing={false} display={lead.salesperson_name} />
        </div>
      </div>

      {/* CUSTOMER & VEHICLE INFORMATION */}
      <div className="sec-card">
        <SecHead title="Customer & Vehicle Information" section="vehicle" editing={editing}
                 onEdit={startEdit} onSave={saveSection} onCancel={() => setEditing(null)} />
        <div className="field-grid">
          <EField icon="🧑" label="Customer Name" editing={ed('vehicle')}
                  display={lead.customer_name} value={form.full_name} onChange={setFld('full_name')} />
          <EField icon="📱" label="Mobile" editing={ed('vehicle')}
                  display={lead.mobile} value={form.phone} onChange={setFld('phone')} />
          <EField icon="📍" label="PIN Code" editing={ed('vehicle')}
                  display={lead.pincode} value={form.pincode} onChange={setFld('pincode')} />
          <EField icon="🏍️" label="Model" editing={ed('vehicle')} options={lookups?.models}
                  display={lead.model_name} value={form.model_id} onChange={setFld('model_id')} />
          <EField icon="🎨" label="Color" editing={ed('vehicle')}
                  display={lead.color} value={form.color} onChange={setFld('color')} />
          <EField icon="🔖" label="SKU Code" editing={ed('vehicle')}
                  display={lead.sku_code} value={form.sku_code} onChange={setFld('sku_code')} />
        </div>
      </div>

      {/* LEAD STATUS & FOLLOW UP INFORMATION */}
      <div className="sec-card">
        <SecHead title="Lead Status & Follow Up Information" section="status" editing={editing}
                 onEdit={startEdit} onSave={saveSection} onCancel={() => setEditing(null)} />
        <div className="field-grid">
          <EField icon="🚩" label="Enquiry Stage" editing={ed('status')}
                  options={STAGES.map((s) => ({ id: s, name: s }))}
                  display={<Badge name={lead.enquiry_stage} />} value={form.enquiry_stage} onChange={setFld('enquiry_stage')} />
          <EField icon="✅" label="Opportunity Status" editing={ed('status')} options={lookups?.opportunity_statuses}
                  display={<Badge name={lead.opportunity_status} />} value={form.opportunity_status_id} onChange={setFld('opportunity_status_id')} />
          <EField icon="📞" label="Follow Up Dispositions" editing={ed('status')} options={lookups?.dispositions}
                  display={<Badge name={lead.disposition} kind="disp" />} value={form.disposition_id} onChange={setFld('disposition_id')} />
          <EField icon="⚠️" label="Lost Reason" editing={ed('status')} options={lookups?.lost_reasons} valueClass="red"
                  display={lead.lost_reason} value={form.lost_reason_id} onChange={setFld('lost_reason_id')} />
          <EField icon="📅" label="Last FollowUp Date Time" editing={false} display={fmtDateTime(lastFu?.created_at)} />
          <EField icon="✔️" label="Follow-Up Done" editing={false} valueClass={lead.followups.length ? 'green' : ''}
                  display={lead.followups.length ? 'YES' : 'NO'} />
          <EField icon="👥" label="Customer Contacted" editing={false} valueClass={contacted ? 'green' : ''}
                  display={contacted ? 'YES' : 'NO'} />
          <EField icon="📅" label="Next Follow Up DateTime" editing={ed('status')} type="datetime-local"
                  display={fmtDateTime(lead.next_followup_at)} value={form.next_followup_at} onChange={setFld('next_followup_at')} />
          <EField icon="🏍️" label="Test Ride Status" editing={false} display={latestTr?.status} />
          <EField icon="✅" label="Test Ride Completed" editing={false} display={anyCompleted ? 'YES' : '—'} />
          <EField icon="📅" label="Test Ride Booking Date" editing={false} display={fmtDateTime(latestTr?.scheduled_at)} />
          <EField icon="🕒" label="Test Ride Slot" editing={false} display={latestTr?.slot} />
          <EField icon="📍" label="Test Ride Location" editing={false} display={latestTr?.preferred_location} />
          <EField icon="⏳" label="Ageing Days" editing={ed('status')} type="number"
                  display={lead.ageing_days || 0} value={form.ageing_days} onChange={setFld('ageing_days')} />
        </div>
      </div>

      {/* FOLLOW UP HISTORY */}
      <div className="card">
        <div className="card-header"><h3>Follow Up History <span className="muted-note">({lead.followups.length})</span></h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Date &amp; Time</th><th>New Remark</th><th>Follow-up Disposition</th><th>Opportunity Sts</th><th>Next Follow-up Date</th><th>By</th></tr></thead>
            <tbody>
              {lead.followups.map((f) => (
                <tr key={f.id}>
                  <td className="cell-muted">{fmtDateTime(f.created_at)}</td>
                  <td>{f.remark || '—'}</td>
                  <td><Badge name={f.disposition} kind="disp" /></td>
                  <td><Badge name={f.opportunity_status} /></td>
                  <td>{fmtDateTime(f.next_followup_at)}</td>
                  <td>{f.by || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {lead.followups.length === 0 && <Empty>No follow-ups logged yet.</Empty>}
        </div>
      </div>

      {/* ADD NEW FOLLOW UP */}
      <div className="card">
        <div className="card-header"><h3>Add New Follow Up</h3></div>
        <form className="card-pad" onSubmit={addFollowup}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14 }}>
            <div className="field"><label>Contacted?</label>
              <select className="input" value={String(fu.contacted)} onChange={setFuF('contacted')}>
                <option value="true">Yes</option><option value="false">No</option>
              </select></div>
            <div className="field" style={{ gridColumn: 'span 2' }}><label>New Remark</label>
              <input className="input" value={fu.remark} onChange={setFuF('remark')} placeholder="Enter remark" /></div>
            <div className="field"><label>Follow-up Disposition</label>
              <select className="input" value={fu.disposition_id} onChange={setFuF('disposition_id')}>
                <option value="">Select Disposition</option>
                {lookups?.dispositions?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select></div>
            <div className="field"><label>Opportunity Sts</label>
              <select className="input" value={fu.opportunity_status_id} onChange={setFuF('opportunity_status_id')}>
                <option value="">Select Status</option>
                {lookups?.opportunity_statuses?.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select></div>
            <div className="field"><label>Next Follow-up Date</label>
              <input className="input" type="datetime-local" value={fu.next_followup_at} onChange={setFuF('next_followup_at')} /></div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
            <button type="button" className="btn btn-primary" disabled title="Quotation module — coming soon">+ Create Quotation</button>
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="button" className="btn btn-outline" onClick={() => setFu(EMPTY_FU)}>Cancel</button>
              <button className="btn btn-primary">Save Follow-up</button>
            </div>
          </div>
        </form>
      </div>

      {/* TEST RIDE HISTORY + SCHEDULE */}
      <div className="card">
        <div className="card-header"><h3>Test Ride History <span className="muted-note">({lead.test_rides.length})</span></h3></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Model</th><th>Colour</th><th>Status</th><th>Scheduled</th><th>Slot</th><th>Location</th><th>Completed</th></tr></thead>
            <tbody>
              {lead.test_rides.map((t) => (
                <tr key={t.id}>
                  <td className="cell-primary">{t.model_name || '—'}</td>
                  <td>{t.color || '—'}</td><td>{t.status}</td>
                  <td>{fmtDateTime(t.scheduled_at)}</td><td>{t.slot || '—'}</td>
                  <td>{t.preferred_location || '—'}</td><td>{t.completed ? '✅' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {lead.test_rides.length === 0 && <Empty>No test rides yet.</Empty>}
        </div>
        <form className="card-pad" onSubmit={addTestRide} style={{ borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
            <div className="field"><label>Model</label>
              <select className="input" value={tr.model_id} onChange={setTrF('model_id')}>
                <option value="">— select —</option>
                {lookups?.models?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select></div>
            <div className="field"><label>Colour</label><input className="input" value={tr.color} onChange={setTrF('color')} /></div>
            <div className="field"><label>Status</label>
              <select className="input" value={tr.status} onChange={setTrF('status')}>
                <option>BOOKED</option><option>COMPLETED</option><option>RESCHEDULED</option><option>CANCELLED</option>
              </select></div>
            <div className="field"><label>Scheduled at</label>
              <input className="input" type="datetime-local" value={tr.scheduled_at} onChange={setTrF('scheduled_at')} /></div>
            <div className="field"><label>Slot</label><input className="input" value={tr.slot} onChange={setTrF('slot')} placeholder="Morning / Evening" /></div>
            <div className="field"><label>Location</label>
              <select className="input" value={tr.preferred_location} onChange={setTrF('preferred_location')}>
                <option>Showroom</option><option>Home Test Ride</option><option>Office TD</option>
              </select></div>
          </div>
          <button className="btn btn-primary">Save test ride</button>
        </form>
      </div>
    </Layout>
  )
}