// ONE "Documents" section for the lead: customer KYC documents and RTO documents as two tabs inside a single card.
import { useState } from 'react'
import DocumentsSection from './DocumentsSection'
import RtoDocsCard from '../rto/RtoDocsCard'

export default function DocumentsHub({ leadId }) {
  const [tab, setTab] = useState('kyc')
  const [kycKey, setKycKey] = useState(0)     // bumped when RTO tab changes -> KYC tab reloads
  const [rtoKey, setRtoKey] = useState(0)     // bumped when KYC tab changes -> RTO tab reloads
  const T = ({ k, children }) => (
    <div onClick={() => setTab(k)} style={{ padding: '10px 0', marginRight: 22, cursor: 'pointer', fontWeight: 600,
      color: tab === k ? '#2f6fed' : '#6b7480', borderBottom: tab === k ? '2px solid #2f6fed' : '2px solid transparent' }}>{children}</div>)
  return (
    <div className="card">
      <div className="card-header"><h3>Documents</h3></div>
      <div style={{ display: 'flex', padding: '0 18px', borderBottom: '1px solid #eef0f3' }}>
        <T k="kyc">Customer KYC</T><T k="rto">RTO papers</T>
      </div>
      <div style={{ display: tab === 'kyc' ? 'block' : 'none' }}><DocumentsSection leadId={leadId} embedded refreshKey={kycKey} onChanged={() => setRtoKey((k) => k + 1)} /></div>
      <div style={{ display: tab === 'rto' ? 'block' : 'none' }}><RtoDocsCard leadId={leadId} embedded refreshKey={rtoKey} onChanged={() => setKycKey((k) => k + 1)} /></div>
    </div>)
}
