// The customer file the Owner / RTO / GM / Admin opens from the worklist or a notification.
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import Layout from '../../components/Layout'
import HandoffPanel from './HandoffPanel'
import Tabs, { Tab } from '../../components/Tabs'
import JourneyBar from '../ownerflow/JourneyBar'
import OwnerFlowCard from '../ownerflow/OwnerFlowCard'
import RtoDocsCard from '../rto/RtoDocsCard'
import PaymentSection from '../payments/PaymentSection'

export default function HandoffPage() {
  const { leadId } = useParams()
  const { user } = useAuth()
  const nav = useNavigate()
  const home = { OWNER: '/owner', RTO: '/rto', GM: '/gm', ADMIN: '/admin' }[user?.role] || '/'
  return (
    <Layout title="Customer file" sub={`Lead ${leadId}`} back={{ label: 'Back to list', onClick: () => nav(home) }}>
      <JourneyBar leadId={leadId} cards />
      <Tabs tabs={[{ key: 'approvals', label: 'Approvals & Delivery' }, ...(user?.role !== 'RTO' ? [{ key: 'payment', label: 'Booking & Payment' }] : []), { key: 'documents', label: 'Documents' }]}>
        <Tab k="approvals">
          {user?.role !== 'RTO' && <OwnerFlowCard leadId={leadId} />}
          <HandoffPanel leadId={leadId} />
        </Tab>
        {user?.role !== 'RTO' && <Tab k="payment"><PaymentSection leadId={leadId} opportunityStatus={null} /></Tab>}
        <Tab k="documents"><RtoDocsCard leadId={leadId} /></Tab>
      </Tabs>
    </Layout>
  )
}
