import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'

const EMPTY_INCLUSION = { description: '', included: true }

export default function QuotationForm({ lead, lookups, onClose, onCreated }) {
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    customer_name: lead.customer_name || '',
    contact_no: lead.mobile || '',
    email: '',
    model_id: lead.model_id || '',
    color: lead.color || '',
    on_road_price: '',
    hspr_registration_type: 'REGULAR',
    sales_manager_name: '',
    finance_bank_name: '',
    finance_financer_name: '',
  })

  const [inclusions, setInclusions] = useState([
    { description: 'Insurance Premium (1yr Own Damage + 5yr Third Party)', included: true },
    { description: 'RTO Road Tax & Registration', included: true },
    { description: 'ISI Certified Helmet', included: true },
    { description: 'RSA (Road Side Assistance)', included: true },
    { description: 'Standard Tool Kit & First Aid Kit', included: true },
    { description: 'Parking Cover', included: true },
    { description: '10yrs Engine Warranty (KTM 5yr + 5yr Extended Warranty)', included: true },
  ])

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const updateInclusion = (idx, field, value) => {
    const next = [...inclusions]
    next[idx] = { ...next[idx], [field]: value }
    setInclusions(next)
  }
  const addInclusion = () => setInclusions([...inclusions, { ...EMPTY_INCLUSION }])
  const removeInclusion = (idx) => setInclusions(inclusions.filter((_, i) => i !== idx))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...form,
        model_id: form.model_id || null,
        on_road_price: Number(form.on_road_price),
      }
      const { data: quotation } = await api.post(`/leads/${lead.lead_id}/quotations`, payload)

      // sync inclusions if user edited the defaults
      await api.patch(`/quotations/${quotation.quotation_id}/inclusions`, {
        inclusions: inclusions.map((inc, i) => ({ ...inc, sort_order: i })),
      })

      onCreated?.(quotation.quotation_id)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create quotation')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ maxWidth: 720 }}>
        <div className="card-header">
          <h3>Create Quotation</h3>
          <button className="btn btn-outline" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit} className="card-pad">
          {error && <div className="alert alert-error">{error}</div>}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
            <div className="field"><label>Customer Name</label>
              <input className="input" value={form.customer_name} onChange={setF('customer_name')} required /></div>
            <div className="field"><label>Contact No.</label>
              <input className="input" value={form.contact_no} onChange={setF('contact_no')} required /></div>
            <div className="field"><label>Email</label>
              <input className="input" type="email" value={form.email} onChange={setF('email')} /></div>
            <div className="field"><label>Vehicle Model</label>
              <select className="input" value={form.model_id} onChange={setF('model_id')}>
                <option value="">Select Model</option>
                {lookups?.models?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select></div>
            <div className="field"><label>Colour</label>
              <input className="input" value={form.color} onChange={setF('color')} /></div>
            <div className="field"><label>On Road Price (₹)</label>
              <input className="input" type="number" value={form.on_road_price} onChange={setF('on_road_price')} required /></div>
            <div className="field"><label>HSPR Registration Type</label>
              <select className="input" value={form.hspr_registration_type} onChange={setF('hspr_registration_type')}>
                <option value="REGULAR">Regular No.</option>
                <option value="CHOICE">Choice No.</option>
                <option value="BH_PASSING">BH Passing No.</option>
              </select></div>
            <div className="field"><label>Sales Manager Name</label>
              <input className="input" value={form.sales_manager_name} onChange={setF('sales_manager_name')} /></div>
            <div className="field"><label>Finance Bank Name</label>
              <input className="input" value={form.finance_bank_name} onChange={setF('finance_bank_name')} /></div>
            <div className="field"><label>Financer Name</label>
              <input className="input" value={form.finance_financer_name} onChange={setF('finance_financer_name')} /></div>
          </div>

          <div style={{ marginTop: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontWeight: 600 }}>Inclusions</label>
              <button type="button" className="btn btn-outline" onClick={addInclusion}>+ Add Item</button>
            </div>
            {inclusions.map((inc, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <input className="input" style={{ flex: 1 }} value={inc.description}
                  onChange={(e) => updateInclusion(i, 'description', e.target.value)} />
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                  <input type="checkbox" checked={inc.included}
                    onChange={(e) => updateInclusion(i, 'included', e.target.checked)} />
                  Included
                </label>
                <button type="button" className="btn btn-outline" onClick={() => removeInclusion(i)}>✕</button>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
            <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={saving}>
              {saving ? 'Creating...' : 'Create Quotation'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}