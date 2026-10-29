import 'katex/dist/katex.min.css'
import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

/**
 * Normalise math delimiters so remark-math renders them reliably:
 *  - \( \) and \[ \] (some models use them) become $ and $$
 *  - a line that is just "$$ ... $$" becomes a fenced display block on its own,
 *    so it is centred and never merges with the following sentence.
 */
function normaliseMath(md: string) {
  return md
    .replace(/\\\[([\s\S]+?)\\\]/g, (_m, inner) => `\n$$\n${inner.trim()}\n$$\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_m, inner) => `$${inner}$`)
    .replace(/^[ \t]*\$\$([^\n]+?)\$\$[ \t]*$/gm, (_m, inner) => `\n$$\n${inner.trim()}\n$$\n`)
}

export const MathMarkdown = memo(function MathMarkdown({ content }: { content: string }) {
  return (
    <div
      className="prose-math prose prose-neutral max-w-none text-[15px] leading-relaxed text-ink
        prose-headings:text-ink prose-h3:mt-6 prose-h3:mb-2 prose-h3:text-[1.15rem] first:prose-h3:mt-0
        prose-p:my-2 prose-li:my-0.5 prose-strong:text-ink prose-a:text-accent
        prose-blockquote:border-l-accent prose-blockquote:bg-accent-soft prose-blockquote:py-1 prose-blockquote:px-3
        prose-blockquote:not-italic prose-blockquote:font-normal prose-blockquote:text-ink prose-blockquote:rounded-r-md
        prose-code:text-accent prose-th:text-ink prose-td:text-ink"
    >
      <ReactMarkdown
        remarkPlugins={[remarkMath, remarkGfm]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
      >
        {normaliseMath(content)}
      </ReactMarkdown>
    </div>
  )
})
