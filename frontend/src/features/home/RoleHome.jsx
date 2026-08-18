import Layout from '../../components/Layout'
import { useAuth } from '../../lib/auth'

// Placeholder home for each role. Phase 1 = login works & routes here.
// The full modules (PBA dashboard, CRE, RTO, etc.) get built in later phases.
export default function RoleHome({ title }) {
  const { user } = useAuth()
  return (
    <Layout title={title} sub={`Signed in as ${user?.full_name} · ${user?.login_id}`}>
      <div className="card">
        <div className="card-pad">
          <h3 style={{ marginTop: 0 }}>✅ You are logged in as {user?.role}</h3>
          <p style={{ color: 'var(--muted)' }}>
            Authentication is working end-to-end (JWT access + refresh, role-based routing).
            This is the landing page for the <strong>{user?.role}</strong> role — the full module
            will be built in the next phase.
          </p>
        </div>
      </div>
    </Layout>
  )
}
