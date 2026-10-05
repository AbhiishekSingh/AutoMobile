// Branch filter for CRE screens (Leads, Customers, Follow Ups, Dashboard).
//
// A CRE covers 1-2 branches. This dropdown narrows a screen to one of them.
// For every other role it renders nothing and adds no params, so the same
// page works unchanged for a PBA.
//
// Usage in a page:
//   const branch = useBranchFilter()                    // lists: "All my branches" allowed
//   const branch = useBranchFilter({ allowAll: false }) // dashboard: always one branch
//   ...wait for branch.ready, then api.get(url, { params: { ...branch.params } })
//   <BranchFilter branch={branch} />
//
// The pick is remembered while the tab is open, so moving from Leads to
// Follow Ups keeps the same branch.
import { useEffect, useState } from 'react'
import api from '../lib/api'
import { useAuth } from '../lib/auth'
import { isCre } from '../lib/roles'

const STORE_KEY = 'sk-crm-branch-filter'

// /me/branches is fetched once per logged-in user, then shared by every page.
let cache = { userId: null, promise: null }
function fetchMyBranches(userId) {
  if (cache.userId !== userId || !cache.promise) {
    cache = {
      userId,
      promise: api.get('/me/branches').then((r) => r.data).catch(() => {
        cache.promise = null   // let the next page try again
        return []
      }),
    }
  }
  return cache.promise
}

/** The logged-in user's branches: [{ branch_id, name }], or null while loading. */
export function useMyBranches() {
  const { user } = useAuth()
  const [branches, setBranches] = useState(null)
  useEffect(() => {
    if (!user) return
    let alive = true
    fetchMyBranches(user.user_id).then((b) => { if (alive) setBranches(b) })
    return () => { alive = false }
  }, [user?.user_id])
  return branches
}

function readStored() {
  try { return sessionStorage.getItem(STORE_KEY) || '' } catch { return '' }
}
function writeStored(v) {
  try { sessionStorage.setItem(STORE_KEY, v) } catch { /* ignore */ }
}

export function useBranchFilter({ allowAll = true } = {}) {
  const { user } = useAuth()
  const cre = isCre(user)
  const branches = useMyBranches()
  const [picked, setPicked] = useState(readStored)

  // Only CREs filter by branch. Use the stored pick if it's still one of
  // their branches; otherwise "all" (lists) or their first branch (dashboard).
  let branchId = ''
  if (cre && branches) {
    const valid = branches.some((b) => String(b.branch_id) === String(picked))
    if (valid) branchId = String(picked)
    else if (!allowAll && branches.length) branchId = String(branches[0].branch_id)
  }

  function setBranchId(v) {
    setPicked(v)
    writeStored(v)
  }

  return {
    show: cre,
    allowAll,
    branches: branches || [],
    branchId,                                   // '' = all my branches
    setBranchId,
    ready: !cre || branches !== null,           // don't fetch data before this
    params: branchId ? { branch_id: Number(branchId) } : {},
    branchName: branches?.find((b) => String(b.branch_id) === branchId)?.name || '',
  }
}

// onChange: optional, e.g. () => setPage(1) so a new branch starts on page 1
export default function BranchFilter({ branch, onChange, style }) {
  if (!branch?.show) return null
  if (branch.ready && branch.branches.length === 0) {
    return <span className="badge badge-amber" style={style}>No branches assigned — ask Admin</span>
  }
  return (
    <select className="input" style={{ maxWidth: 220, ...style }} value={branch.branchId}
            onChange={(e) => { branch.setBranchId(e.target.value); onChange?.(e.target.value) }}
            aria-label="Branch">
      {branch.allowAll && <option value="">All my branches</option>}
      {branch.branches.map((b) => (
        <option key={b.branch_id} value={b.branch_id}>{b.name}</option>
      ))}
    </select>
  )
}
