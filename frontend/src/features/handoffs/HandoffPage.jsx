// The customer file the Owner / RTO / GM / Admin opens from the worklist or a notification.
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import Layout from '../../components/Layout'
import HandoffPanel from './HandoffPanel'
import PaymentSection from '../payments/PaymentSection'

export default function HandoffPage() {
  const { leadId } = useParams()
  const { user } = useAuth()
  const nav = useNavigate()
  const home = { OWNER: '/owner', RTO: '/rto', GM: '/gm', ADMIN: '/admin' }[user?.role] || '/'
  return (
    <Layout title="Customer file" sub={`Lead ${leadId}`} back={{ label: 'Back to list', onClick: () => nav(home) }}>
      <HandoffPanel leadId={leadId} />
      {user?.role !== 'RTO' && <PaymentSection leadId={leadId} opportunityStatus={null} />}
    </Layout>
  )
}
