/**
 * MarkdownAnswer — Smart AI response renderer for FinPilot AI
 *
 * Renders any LLM-generated markdown string in a clean, professional layout.
 * Detects the content shape and chooses the best visual treatment:
 *   • Summary cards  → bold "Key: Value" lines with ₹ / number highlights
 *   • Data tables    → styled tables with right-aligned amounts, hover rows
 *   • Bullet lists   → clean reading-friendly lists
 *   • Headings       → visual hierarchy
 *   • Conversational → simple readable paragraphs
 *
 * Rules:
 *   - Never invents or changes data — only changes presentation
 *   - No hardcoded question patterns — adapts to actual content
 *   - Reuses the FinPilot green palette from styles.css
 */

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import type { ReactNode } from 'react'

// ─── helpers ────────────────────────────────────────────────────────────────

/** Returns true if a string looks like a currency / number value */
function looksLikeAmount(s: string): boolean {
  const clean = s.trim().replace(/,/g, '')
  return /^[₹$€£]?\s*\d[\d,]*(\.\d+)?$/.test(clean) || /^\d[\d,]*(\.\d+)?\s*[₹$€£]?$/.test(clean)
}

/** Returns true if a cell value is right-align worthy (number, ₹, %, count) */
function isNumericCell(text: string): boolean {
  const t = text.trim()
  return looksLikeAmount(t) || /^\d+$/.test(t) || /^\d+%$/.test(t)
}

/**
 * Pre-scan markdown text: returns flags that inform rendering decisions.
 * This is intentionally content-agnostic — no question-matching.
 */
function analyseContent(text: string) {
  const hasTable  = /\|.+\|/.test(text)
  const hasList   = /^(\s*[-*+]|\s*\d+\.)\s/m.test(text)
  const hasHeader = /^#{1,3}\s/m.test(text)

  // "Stat lines": bold label + value on a line, e.g. **Total Outstanding:** ₹1,23,456
  const statLineRe = /^\*{1,2}[^*]+\*{1,2}\s*:?\s*.+/m
  const hasStatLines = statLineRe.test(text)

  // If the whole thing is 2 sentences or fewer and no special structure → conversational
  const isConversational = !hasTable && !hasList && !hasHeader && !hasStatLines &&
    text.trim().split(/\n+/).every(line => line.length < 160)

  return { hasTable, hasList, hasHeader, hasStatLines, isConversational }
}

// ─── sub-components ──────────────────────────────────────────────────────────

/** Renders a table cell content, right-aligning numbers */
function CellContent({ children }: { children: ReactNode }) {
  const text = typeof children === 'string' ? children : ''
  if (looksLikeAmount(text)) {
    return <span className="mda-amount">{children}</span>
  }
  return <>{children}</>
}

// ─── main component ──────────────────────────────────────────────────────────

interface Props {
  text: string
}

export function MarkdownAnswer({ text }: Props) {
  const { isConversational } = analyseContent(text)

  // Track whether we're inside a thead to know if th/td is a header
  // (react-markdown passes this via the node tree — we use a closure flag)
  let inThead = false

  const components: Components = {

    // ── Headings ─────────────────────────────────────────────────────────────
    h1: ({ children }) => <h3 className="mda-h1">{children}</h3>,
    h2: ({ children }) => <h4 className="mda-h2">{children}</h4>,
    h3: ({ children }) => <h5 className="mda-h3">{children}</h5>,

    // ── Paragraphs ────────────────────────────────────────────────────────────
    p: ({ children }) => {
      // Detect "stat card" pattern: **Label:** Value  or  **Label** Value
      // We render these as a highlighted metric pill instead of plain text.
      const raw = typeof children === 'string' ? children : flattenChildren(children)

      // If the paragraph starts with bold text followed by a colon/value, make it a stat row
      if (typeof raw === 'string') {
        const statMatch = raw.match(/^\*{0,2}([^*:]+)\*{0,2}\s*:\s*(.+)/)
        if (statMatch && looksLikeAmount(statMatch[2].trim())) {
          return (
            <div className="mda-stat-row">
              <span className="mda-stat-label">{statMatch[1].trim()}</span>
              <span className="mda-stat-value">{statMatch[2].trim()}</span>
            </div>
          )
        }
      }

      return <p className="mda-p">{children}</p>
    },

    // ── Strong ────────────────────────────────────────────────────────────────
    strong: ({ children }) => {
      const text = flattenChildren(children)
      // Bold amounts get a green highlight
      if (typeof text === 'string' && looksLikeAmount(text)) {
        return <strong className="mda-strong mda-amount-inline">{children}</strong>
      }
      return <strong className="mda-strong">{children}</strong>
    },

    em: ({ children }) => <em className="mda-em">{children}</em>,

    // ── Lists ─────────────────────────────────────────────────────────────────
    ul: ({ children }) => <ul className="mda-ul">{children}</ul>,
    ol: ({ children }) => <ol className="mda-ol">{children}</ol>,
    li: ({ children }) => <li className="mda-li">{children}</li>,

    // ── Tables ────────────────────────────────────────────────────────────────
    table: ({ children }) => (
      <div className="mda-table-wrap">
        <table className="mda-table">{children}</table>
      </div>
    ),
    thead: ({ children }) => {
      inThead = true
      const el = <thead className="mda-thead">{children}</thead>
      inThead = false
      return el
    },
    tbody: ({ children }) => <tbody className="mda-tbody">{children}</tbody>,
    tr: ({ children }) => <tr className="mda-tr">{children}</tr>,

    th: ({ children }) => {
      const text = flattenChildren(children)
      const alignRight = typeof text === 'string' && isNumericCell(text)
      return (
        <th className={`mda-th${alignRight ? ' mda-th-num' : ''}`}>
          {children}
        </th>
      )
    },

    td: ({ children }) => {
      const text = flattenChildren(children)
      const alignRight = typeof text === 'string' && isNumericCell(text)
      return (
        <td className={`mda-td${alignRight ? ' mda-td-num' : ''}`}>
          {alignRight ? <CellContent>{text}</CellContent> : children}
        </td>
      )
    },

    // ── Code ─────────────────────────────────────────────────────────────────
    code: ({ children, className }) => {
      if (className) {
        return (
          <pre className="mda-pre">
            <code className="mda-code-block">{children}</code>
          </pre>
        )
      }
      return <code className="mda-code-inline">{children}</code>
    },
    pre: ({ children }) => <>{children}</>,

    // ── Blockquote ────────────────────────────────────────────────────────────
    blockquote: ({ children }) => (
      <blockquote className="mda-blockquote">{children}</blockquote>
    ),

    // ── Horizontal rule ───────────────────────────────────────────────────────
    hr: () => <hr className="mda-hr" />,
  }

  return (
    <div className={`mda-root${isConversational ? ' mda-conversational' : ''}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  )
}

// ─── utility ─────────────────────────────────────────────────────────────────

/** Flatten react children to a plain string for pattern matching */
function flattenChildren(children: ReactNode): string {
  if (typeof children === 'string') return children
  if (typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map(flattenChildren).join('')
  if (children && typeof children === 'object' && 'props' in (children as object)) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return flattenChildren((children as any).props.children)
  }
  return ''
}
