// Red borders on the fields a message is about - for every page, without editing each form.
//
// How it works
//  1. Any message box that appears with an error look (red background / "alert" / "error" class) is read.
//  2. Any failed API call (400/403/409/422...) is read too, using the form the person last clicked in.
//  3. In the form/section around that spot, every label whose name appears in the message ("Policy number is
//     required" -> "Policy number *") has its field outlined in red, the first one is focused, and the red goes away
//     as soon as the person edits that field.
// 422 answers from the server name the field (body -> policy_number); those are matched to labels the same way.
// Matching is by label text, so a message that never names a field marks nothing (the message box still shows).
const norm = (t) => String(t || '').toLowerCase().replace(/\([^)]*\)/g, ' ').replace(/[*:_\-/.,]/g, ' ').replace(/\s+/g, ' ').trim()
const STOP = new Set(['enter', 'your', 'the', 'please', 'select', 'choose', 'date', 'number', 'name', 'type', 'with', 'from', 'this', 'that', 'must', 'have', 'been', 'only', 'same', 'first', 'again', 'value', 'field'])
const CONTROL = 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]),select,textarea'

let lastEl = null
let installed = false

function controlOf(label) {
  if (label.control) return label.control
  const inner = label.querySelector(CONTROL); if (inner) return inner
  let n = label.nextElementSibling
  while (n) { if (n.matches?.(CONTROL)) return n; const c = n.querySelector?.(CONTROL); if (c) return c; n = n.nextElementSibling }
  const p = label.parentElement
  return p ? p.querySelector(CONTROL) : null
}

function candidates(root) {
  const out = []
  root.querySelectorAll('label').forEach((lb) => {
    const key = norm(lb.textContent)
    if (key.length < 3) return
    const c = controlOf(lb)
    if (c && !c.disabled && c.offsetParent !== null) out.push({ lb, c, key })
  })
  return out
}

function mark(items) {
  items.forEach(({ lb, c }) => {
    c.setAttribute('aria-invalid', 'true')
    const box = lb.closest('.field') || lb.parentElement
    if (box) box.classList.add('field-invalid')
    const clear = () => { c.removeAttribute('aria-invalid'); box && box.classList.remove('field-invalid'); c.removeEventListener('input', clear); c.removeEventListener('change', clear) }
    c.addEventListener('input', clear); c.addEventListener('change', clear)
  })
  const first = items[0]
  if (first) { first.c.scrollIntoView({ block: 'center', behavior: 'smooth' }); try { first.c.focus({ preventScroll: true }) } catch (e) { /* ignore */ } }
}

function clearAll(root) {
  (root || document).querySelectorAll('[aria-invalid="true"]').forEach((c) => c.removeAttribute('aria-invalid'));
  (root || document).querySelectorAll('.field-invalid').forEach((b) => b.classList.remove('field-invalid'))
}

// message text (+ optional server field names) and the element it relates to
export function markFields(message, anchor, names = []) {
  const msg = norm(message)
  if (!msg && !names.length) return
  let el = anchor && document.contains(anchor) ? anchor : document.querySelector('.content') || document.body
  const wanted = names.map(norm)
  for (let hop = 0; el && hop < 8; hop++, el = el.parentElement) {
    const items = candidates(el)
    if (!items.length) continue
    // strong: the whole label is named in the message, or the server named the field
    let hit = items.filter((i) => (` ${msg} `).includes(` ${i.key} `) || wanted.some((w) => w && (i.key.includes(w) || w.includes(i.key))))
    if (!hit.length) {   // weaker: a distinctive word of the label appears in the message
      hit = items.filter((i) => i.key.split(' ').some((w) => w.length >= 5 && !STOP.has(w) && msg.includes(w))).slice(0, 2)
    }
    if (hit.length) { clearAll(el); mark(hit); return }
  }
}

export function installFieldErrors(api) {
  if (installed) return; installed = true
  document.addEventListener('click', (e) => { lastEl = e.target }, true)
  document.addEventListener('submit', (e) => { lastEl = e.target }, true)
  document.addEventListener('focusin', (e) => { lastEl = e.target }, true)

  // failed API calls
  api.interceptors.response.use((r) => r, (error) => {
    const res = error.response
    if (res && [400, 403, 404, 409, 422].includes(res.status)) {
      const det = res.data?.detail
      const anchor = lastEl
      setTimeout(() => {
        if (Array.isArray(det)) markFields(det.map((d) => d.msg).join(' '), anchor, det.map((d) => (d.loc || []).slice(-1)[0]).filter((x) => typeof x === 'string'))
        else if (typeof det === 'string') markFields(det, anchor)
      }, 60)   // after React has drawn the message
    }
    return Promise.reject(error)
  })

  // error message boxes drawn by the pages themselves (including checks done in the browser before any request)
  const looksError = (n) => {
    const st = n.getAttribute?.('style') || '', cl = typeof n.className === 'string' ? n.className : ''
    return /red-light|#fdecea|#fef3f2|#f0b4ab/i.test(st) || /(^|\s)(alert-error|alert-danger|error|err)(\s|$)/i.test(cl)
  }
  new MutationObserver((muts) => {
    for (const m of muts) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue
      const box = looksError(n) ? n : [...n.querySelectorAll?.('[style],[class]') || []].find(looksError)
      if (box && (box.textContent || '').trim().length > 3) { markFields(box.textContent, box); return }
    }
  }).observe(document.body, { childList: true, subtree: true })
}
