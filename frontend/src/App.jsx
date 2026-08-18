import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth, ROLE_HOME } from './lib/auth'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './features/auth/LoginPage'
import RoleHome from './features/home/RoleHome'
import UsersPage from './features/admin/UsersPage'
import ImportPage from './features/admin/ImportPage'
import DashboardPage from './features/dashboard/DashboardPage'
import LeadsPage from './features/leads/LeadsPage'
import CustomerDetailPage from './features/leads/CustomerDetailPage'
import CustomersPage from './features/leads/CustomersPage'
import FollowupsPage from './features/leads/FollowupsPage'

// Send "/" to the right place based on auth + role
function Index() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <Navigate to={ROLE_HOME[user.role] || '/dashboard'} replace />
}

// PBA-only wrapper to keep the route list tidy
const Pba = ({ children }) => <ProtectedRoute roles={['PBA']}>{children}</ProtectedRoute>

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/login" element={<LoginPage />} />

          {/* PBA module (Phase 2) */}
          <Route path="/dashboard" element={<Pba><DashboardPage /></Pba>} />
          <Route path="/leads" element={<Pba><LeadsPage /></Pba>} />
          <Route path="/leads/:id" element={<Pba><CustomerDetailPage /></Pba>} />
          <Route path="/customers" element={<Pba><CustomersPage /></Pba>} />
          <Route path="/followups" element={<Pba><FollowupsPage /></Pba>} />

          {/* other roles — placeholder homes for now */}
          <Route path="/owner" element={<ProtectedRoute roles={['OWNER']}><RoleHome title="Owner Dashboard" /></ProtectedRoute>} />
          <Route path="/gm" element={<ProtectedRoute roles={['GM']}><RoleHome title="GM Dashboard" /></ProtectedRoute>} />
          <Route path="/cre" element={<ProtectedRoute roles={['CRE']}><RoleHome title="CRE Dashboard" /></ProtectedRoute>} />
          <Route path="/rto" element={<ProtectedRoute roles={['RTO']}><RoleHome title="RTO Dashboard" /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute roles={['ADMIN']}><UsersPage /></ProtectedRoute>} />
          <Route path="/admin/import" element={<ProtectedRoute roles={['ADMIN']}><ImportPage /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}