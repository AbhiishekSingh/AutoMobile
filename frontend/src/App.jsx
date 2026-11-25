import PbaPipelinePage from './features/handoffs/PbaPipelinePage'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { AuthProvider, useAuth, ROLE_HOME } from './lib/auth'
import ProtectedRoute from './components/ProtectedRoute'
import { Loading } from './components/ui'
import { SALES_ROLES } from './lib/roles'
import LoginPage from './features/auth/LoginPage'
import RoleHome from './features/home/RoleHome'
import InsuranceDashboardPage from './features/insurance/InsuranceDashboardPage'
import CreReportsPage from './features/cre/CreReportsPage'
import CreTestRidesPage from './features/cre/CreTestRidesPage'
import FinalReviewsPage from './features/cre/FinalReviewsPage'
import AccountsPage from './features/accounts/AccountsPage'
import InsuranceCasePage from './features/insurance/InsuranceCasePage'
import WorkQueuePage from './features/handoffs/WorkQueuePage'
import OwnerApprovalsPage from './features/ownerflow/OwnerApprovalsPage'
import OwnerFlowBoardPage from './features/ownerflow/OwnerFlowBoardPage'
import HandoffPage from './features/handoffs/HandoffPage'
import BranchPickerPage from './features/branch/BranchPickerPage'
import StockPage from './features/stock/StockPage'
import OwnerDashboardPage from './features/owner/OwnerDashboardPage'
import OwnerKpiPage from './features/owner/OwnerKpiPage'
import TargetsPage from './features/targets/TargetsPage'
import SettingsPage from './features/settings/SettingsPage'
import WhatsAppSettingsPage from './features/whatsapp/WhatsAppSettingsPage'
import UsersPage from './features/admin/UsersPage'
import BranchesPage from './features/admin/BranchesPage'
import ImportPage from './features/admin/ImportPage'
import ActivityLogPage from './features/admin/ActivityLogPage'
import LeadsPage from './features/leads/LeadsPage'
import CustomerDetailPage from './features/leads/CustomerDetailPage'
import CustomersPage from './features/leads/CustomersPage'
import SyncLogPage from './features/admin/SyncLogPage'
import CreDashboardPage from './features/cre/CreDashboardPage'
import CreWorklistPage from './features/cre/CreWorklistPage'
import FollowupsPage from './features/leads/FollowupsPage'
import QuotationsPage from './features/quotations/QuotationsPage'
import QuotationDetailPage from './features/quotations/QuotationDetailPage'

// DashboardPage pulls in `recharts` (the largest dependency in the app), so
// it's lazy-loaded into its own chunk — it's the only route that needs it.
const DashboardPage = lazy(() => import('./features/dashboard/DashboardPage'))

// Send "/" to the right place based on auth + role
function Index() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={ROLE_HOME[user.role] || '/dashboard'} replace />
}

// /dashboard: CRE gets the CRE dashboard, PBA the usual one
function DashboardSwitch() {
  const { user } = useAuth()
  if (user?.role === 'CRE') return <CreDashboardPage />
  return <Suspense fallback={<Loading />}><DashboardPage /></Suspense>
}

// Sales screens (PBA + CRE share them) — keeps the route list tidy
const Sales = ({ children }) => <ProtectedRoute roles={SALES_ROLES}>{children}</ProtectedRoute>

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Sales module — PBA and CRE (CRE sees its 1-2 branches, with a branch filter) */}
          <Route path="/dashboard" element={<Sales><DashboardSwitch /></Sales>} />
          <Route path="/cre/walkin" element={<ProtectedRoute roles={['CRE', 'OWNER', 'GM', 'ADMIN']}><CreWorklistPage source="WALKIN" /></ProtectedRoute>} />
          <Route path="/cre/leadsquare" element={<ProtectedRoute roles={['CRE', 'OWNER', 'GM', 'ADMIN']}><CreWorklistPage source="CSV" /></ProtectedRoute>} />
          <Route path="/leads" element={<Sales><LeadsPage /></Sales>} />
          <Route path="/leads/:id" element={<Sales><CustomerDetailPage /></Sales>} />
          <Route path="/customers" element={<Sales><CustomersPage /></Sales>} />
          <Route path="/followups" element={<Sales><FollowupsPage /></Sales>} />
          <Route path="/quotations" element={<Sales><QuotationsPage /></Sales>} />
          <Route path="/quotations/:id" element={<Sales><QuotationDetailPage /></Sales>} />

          {/* other roles — placeholder homes for now */}
          <Route path="/owner/kpi" element={<ProtectedRoute roles={['OWNER', 'ADMIN', 'GM']}><OwnerKpiPage /></ProtectedRoute>} />
          <Route path="/owner/dashboard" element={<ProtectedRoute roles={['OWNER', 'ADMIN']}><OwnerDashboardPage /></ProtectedRoute>} />
          <Route path="/workflow" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN', 'PBA', 'CRE']}><OwnerFlowBoardPage /></ProtectedRoute>} />
          <Route path="/owner" element={<ProtectedRoute roles={['OWNER']}><OwnerApprovalsPage /></ProtectedRoute>} />
          <Route path="/owner/other" element={<ProtectedRoute roles={['OWNER']}><WorkQueuePage title="Owner — Other requests (ATW / special)" /></ProtectedRoute>} />
          <Route path="/gm" element={<ProtectedRoute roles={['GM']}><OwnerDashboardPage gm /></ProtectedRoute>} />
          <Route path="/cre-reports" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN', 'CRE']}><CreReportsPage /></ProtectedRoute>} />
          <Route path="/cre/test-rides" element={<ProtectedRoute roles={['CRE', 'OWNER', 'GM', 'ADMIN']}><CreTestRidesPage /></ProtectedRoute>} />
          <Route path="/final-reviews" element={<ProtectedRoute roles={['CRE', 'OWNER', 'GM', 'ADMIN']}><FinalReviewsPage /></ProtectedRoute>} />
          <Route path="/accounts" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN']}><AccountsPage /></ProtectedRoute>} />
          <Route path="/insurance" element={<ProtectedRoute roles={['INSURANCE', 'ADMIN', 'OWNER', 'GM', 'CRE']}><InsuranceDashboardPage /></ProtectedRoute>} />
          <Route path="/insurance/:leadId" element={<ProtectedRoute roles={['INSURANCE', 'ADMIN', 'OWNER', 'GM', 'CRE']}><InsuranceCasePage /></ProtectedRoute>} />
          <Route path="/invoices" element={<ProtectedRoute roles={['PBA']}><PbaPipelinePage mode="invoice" /></ProtectedRoute>} />
          <Route path="/rto-status" element={<ProtectedRoute roles={['PBA']}><PbaPipelinePage mode="rto" /></ProtectedRoute>} />
          <Route path="/rto" element={<ProtectedRoute roles={['RTO']}><WorkQueuePage title="RTO — Registrations" /></ProtectedRoute>} />
          <Route path="/handoff/:leadId" element={<ProtectedRoute roles={['OWNER', 'RTO', 'GM', 'ADMIN']}><HandoffPage /></ProtectedRoute>} />
          <Route path="/targets" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN', 'PBA', 'CRE']}><TargetsPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/whatsapp-settings" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN']}><WhatsAppSettingsPage /></ProtectedRoute>} />
          <Route path="/stock" element={<ProtectedRoute roles={['OWNER', 'GM', 'ADMIN']}><StockPage /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute roles={['ADMIN']}><UsersPage /></ProtectedRoute>} />
          <Route path="/admin/branches" element={<ProtectedRoute roles={['ADMIN']}><BranchesPage /></ProtectedRoute>} />
          <Route path="/branch" element={<ProtectedRoute roles={['BRANCH', 'PBA']}><BranchPickerPage /></ProtectedRoute>} />
          <Route path="/admin/import" element={<ProtectedRoute roles={['ADMIN']}><ImportPage /></ProtectedRoute>} />
          <Route path="/admin/sync-log" element={<ProtectedRoute roles={['ADMIN']}><SyncLogPage /></ProtectedRoute>} />
          <Route path="/admin/activity-log" element={<ProtectedRoute roles={['ADMIN']}><ActivityLogPage /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
