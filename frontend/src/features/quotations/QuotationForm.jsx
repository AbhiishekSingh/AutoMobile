import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../../lib/api'

const EMPTY_INCLUSION = { description: '', included: true }
const EMPTY_EMI = { tenure_months: '', down_payment: '', monthly_emi: '', roi_percent: '' }
const EMPTY_DOCUMENT = { document_name: '', required: true }

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
    discounted_price: '',      // internal only — never on the customer's quotation
    payment_type: 'CASH',
    down_payment: '',
    acc_helmet: true, acc_parking_cover: true, rsa_one_year: true,
    engine_warranty_years: 5,
  })

  const [inclusions, setInclusions] = useState([
    { description: 'Insurance Premium (1yr Own Damage + 5yr Third Party)', included: true },
    { description: 'RTO Road Tax & Registration', included: true },
    { description: 'Standard Tool Kit & First Aid Kit', included: true },
  ])

  const [emiOptions, setEmiOptions] = useState([
    { tenure_months: 12, down_payment: '', monthly_emi: '', roi_percent: '' },
    { tenure_months: 24, down_payment: '', monthly_emi: '', roi_percent: '' },
    { tenure_months: 36, down_payment: '', monthly_emi: '', roi_percent: '' },
    { tenure_months: 48, down_payment: '', monthly_emi: '', roi_percent: '' },
  ])

  const [documents, setDocuments] = useState([
    { document_name: 'PAN CARD', required: true },
    { document_name: 'AADHAR CARD (linked to mobile no.)', required: true },
    { document_name: 'ELECTRICITY BILL', required: true },
    { document_name: '6 Month Bank Statement', required: true },
    { document_name: 'Voter ID / Passport', required: true },
    { document_name: 'BH REG. COMPANY ID', required: true },
    { document_name: 'FORM 60', required: true },
    { document_name: 'GST / IT RETURN', required: true },
  ])

  const setF = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const setChk = (key) => (e) => setForm({ ...form, [key]: e.target.checked })
  const isEmi = form.payment_type === 'EMI'
  // amount the customer finances = offered price (else on-road price) minus the down payment
  const base = Number(form.discounted_price || form.on_road_price || 0)
  const financed = Math.max(0, base - Number(form.down_payment || 0))

  const updateInclusion = (idx, field, value) => {
    const next = [...inclusions]
    next[idx] = { ...next[idx], [field]: value }
    setInclusions(next)
  }
  const addInclusion = () => setInclusions([...inclusions, { ...EMPTY_INCLUSION }])
  const removeInclusion = (idx) => setInclusions(inclusions.filter((_, i) => i !== idx))

  const updateEmi = (idx, field, value) => {
    const next = [...emiOptions]
    next[idx] = { ...next[idx], [field]: value }
    setEmiOptions(next)
  }
  const addEmi = () => setEmiOptions([...emiOptions, { ...EMPTY_EMI }])
  const removeEmi = (idx) => setEmiOptions(emiOptions.filter((_, i) => i !== idx))

  const updateDocument = (idx, field, value) => {
    const next = [...documents]
    next[idx] = { ...next[idx], [field]: value }
    setDocuments(next)
  }
  const addDocument = () => setDocuments([...documents, { ...EMPTY_DOCUMENT, isCustom: true }])

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...form,
        model_id: form.model_id || null,
        on_road_price: Number(form.on_road_price),
        discounted_price: form.discounted_price === '' ? null : Number(form.discounted_price),
        down_payment: form.down_payment === '' ? null : Number(form.down_payment),
        engine_warranty_years: Number(form.engine_warranty_years),
      }
      const { data: quotation } = await api.post(`/leads/${lead.lead_id}/quotations`, payload)

      // sync inclusions if user edited the defaults
      await api.patch(`/quotations/${quotation.quotation_id}/inclusions`, {
        inclusions: inclusions.map((inc, i) => ({ ...inc, sort_order: i })),
      })

      // sync finance / EMI scheme options (cash needs none)
      if (isEmi) await api.patch(`/quotations/${quotation.quotation_id}/emi`, {
        emi_options: emiOptions
          .filter((e) => e.tenure_months !== '' && e.tenure_months !== null)
          .map((e) => ({
            tenure_months: Number(e.tenure_months),
            down_payment: e.down_payment === '' ? null : Number(e.down_payment),
            monthly_emi: e.monthly_emi === '' ? null : Number(e.monthly_emi),
            roi_percent: e.roi_percent === '' ? null : Number(e.roi_percent),
          })),
      })

      // sync documents required
      await api.patch(`/quotations/${quotation.quotation_id}/documents`, {
        documents: documents
          .filter((d) => d.document_name.trim() !== '')
          .map((d) => ({ document_name: d.document_name, required: d.required })),
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
            <div className="field"><label>Discount / Offered Price (₹) <span style={{ color: '#B45309', fontWeight: 400 }}>— internal, not shown to customer</span></label>
              <input className="input" type="number" min="0" value={form.discounted_price} onChange={setF('discounted_price')} /></div>
            <div className="field"><label>Payment</label>
              <select className="input" value={form.payment_type} onChange={setF('payment_type')}>
                <option value="CASH">Cash</option><option value="EMI">EMI / Finance</option>
              </select></div>
            <div className="field"><label>Down Payment (₹)</label>
              <input className="input" type="number" min="0" value={form.down_payment} onChange={setF('down_payment')} /></div>
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
            <label style={{ fontWeight: 600 }}>Accessories &amp; Warranty provided by us</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, marginTop: 8, alignItems: 'center', fontSize: 14 }}>
              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" checked={form.acc_helmet} onChange={setChk('acc_helmet')} /> Studio Helmet</label>
              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" checked={form.acc_parking_cover} onChange={setChk('acc_parking_cover')} /> Parking Cover</label>
              <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" checked={form.rsa_one_year} onChange={setChk('rsa_one_year')} /> RSA 1 Year</label>
              <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>Engine Warranty
                <select className="input" style={{ width: 'auto' }} value={form.engine_warranty_years} onChange={setF('engine_warranty_years')}>
                  <option value={5}>5 years</option><option value={10}>10 years</option>
                </select></label>
            </div>
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

          {isEmi && <div style={{ marginTop: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontWeight: 600 }}>Finance / EMI Scheme Options</label>
              <button type="button" className="btn btn-outline" onClick={addEmi}>+ Add Tenure</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 8, marginTop: 6, fontSize: 12, fontWeight: 600, color: '#666' }}>
              <div>Tenure (Months)</div><div>Down Payment (₹)</div><div>Monthly EMI (₹)</div><div>ROI %</div><div></div>
            </div>
            {emiOptions.map((e, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: 8, alignItems: 'center', marginTop: 6 }}>
                <input className="input" type="number" value={e.tenure_months}
                  onChange={(ev) => updateEmi(i, 'tenure_months', ev.target.value)} placeholder="e.g. 12" />
                <input className="input" type="number" value={e.down_payment}
                  onChange={(ev) => updateEmi(i, 'down_payment', ev.target.value)} placeholder="Optional" />
                <input className="input" type="number" value={e.monthly_emi}
                  onChange={(ev) => updateEmi(i, 'monthly_emi', ev.target.value)} placeholder="Optional" />
                <input className="input" type="number" step="0.01" value={e.roi_percent}
                  onChange={(ev) => updateEmi(i, 'roi_percent', ev.target.value)} placeholder="Optional" />
                <button type="button" className="btn btn-outline" onClick={() => removeEmi(i)}>✕</button>
              </div>
            ))}
            <div style={{ fontSize: 12, color: '#64748B', marginTop: 8 }}>
              Amount to be financed: <b>₹ {financed.toLocaleString('en-IN')}</b> (offered price, or on-road price, minus down payment).
              Type the ROI for each tenure; leave Monthly EMI empty and it is calculated automatically.
            </div>
          </div>}

          <div style={{ marginTop: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontWeight: 600 }}>Documents Required</label>
              <button type="button" className="btn btn-outline" onClick={addDocument}>+ Add Document</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', columnGap: 20 }}>
              {documents.map((d, i) => (
                <label key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: 14 }}>
                  <input type="checkbox" checked={d.required}
                    onChange={(e) => updateDocument(i, 'required', e.target.checked)} />
                  {d.isCustom ? (
                    <input className="input" style={{ flex: 1 }} value={d.document_name}
                      placeholder="Document name"
                      onChange={(e) => updateDocument(i, 'document_name', e.target.value)} />
                  ) : (
                    <span>{d.document_name}</span>
                  )}
                </label>
              ))}
            </div>
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