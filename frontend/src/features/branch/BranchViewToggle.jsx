// PBA under a branch login: "My customers" vs "Whole branch (view only)".
import { useState } from 'react'
import { useAuth } from '../../lib/auth'

const KEY = 'sk-crm-branch-view'

export function useBranchView() {
  const { user } = useAuth()
  const enabled = !!user?.via_branch
  const [whole, setWhole] = useState(() => { try { return sessionStorage.getItem(KEY) === '1' } catch (_) { return false } })
  const set = (v) => { setWhole(v); try { sessionStorage.setItem(KEY, v ? '1' : '0') } catch (_) {} }
  return { enabled, whole: enabled && whole, setWhole: set, params: enabled && whole ? { whole_branch: true } : {} }
}

export default function BranchViewToggle({ view, onChange }) {
  if (!view.enabled) return null
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
      <button className={'btn btn-sm ' + (!view.whole ? 'btn-primary' : 'btn-outline')} onClick={() => { view.setWhole(false); onChange && onChange() }}>My customers</button>
      <button className={'btn btn-sm ' + (view.whole ? 'btn-primary' : 'btn-outline')} onClick={() => { view.setWhole(true); onChange && onChange() }}>Whole branch (view only)</button>
    </div>
  )
}
