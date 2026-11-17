// Makes every card that has a ".card-header" inside it collapsible (click the header). One wrapper around a page
// gives a clean, short screen: history lists start closed, key sections start open.
// Pure DOM toggle (data-collapsed), so it needs no change inside the existing sections.
import { useEffect, useRef } from 'react'

const CSS = `
.acc .card[data-acc] > .card-header { cursor: pointer; display: flex; align-items: center; justify-content: space-between; gap: 8px; user-select: none; }
.acc .card[data-acc] > .card-header::after { content: ''; flex: 0 0 auto; width: 8px; height: 8px; margin: 0 6px 3px 8px; border-right: 2px solid #6b7480;
  border-bottom: 2px solid #6b7480; transform: rotate(45deg); transition: transform .15s; }
.acc .card[data-collapsed="1"] > .card-header::after { transform: rotate(-45deg); margin-bottom: 0; }
.acc .card[data-collapsed="1"] > :not(.card-header) { display: none !important; }
.acc-tools { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 8px; }
`
const CLOSED_BY_DEFAULT = /history|log|whatsapp|documents|rto documents/i

export default function Accordion({ children }) {
  const ref = useRef(null)
  useEffect(() => {
    const root = ref.current
    if (!root) return undefined
    const setup = () => root.querySelectorAll('.card').forEach((card) => {
      const head = Array.from(card.children).find((c) => c.classList && c.classList.contains('card-header'))
      if (!head || card.hasAttribute('data-acc')) return
      card.setAttribute('data-acc', '1')
      if (CLOSED_BY_DEFAULT.test(head.textContent || '')) card.setAttribute('data-collapsed', '1')
    })
    setup()
    const mo = new MutationObserver(setup)
    mo.observe(root, { childList: true, subtree: true })
    const onClick = (e) => {
      const head = e.target.closest && e.target.closest('.card-header')
      if (!head || !root.contains(head) || e.target.closest('button, a, input, select, textarea, label')) return
      const card = head.parentElement
      if (!card || !card.hasAttribute('data-acc')) return
      if (card.getAttribute('data-collapsed') === '1') card.removeAttribute('data-collapsed')
      else card.setAttribute('data-collapsed', '1')
    }
    root.addEventListener('click', onClick)
    return () => { mo.disconnect(); root.removeEventListener('click', onClick) }
  }, [])
  const all = (open) => ref.current && ref.current.querySelectorAll('.card[data-acc]').forEach((c) => (open ? c.removeAttribute('data-collapsed') : c.setAttribute('data-collapsed', '1')))
  return (
    <div className="acc" ref={ref}>
      <style>{CSS}</style>
      <div className="acc-tools">
        <button className="btn btn-sm btn-outline" onClick={() => all(true)}>Expand all</button>
        <button className="btn btn-sm btn-outline" onClick={() => all(false)}>Collapse all</button>
      </div>
      {children}
    </div>
  )
}
