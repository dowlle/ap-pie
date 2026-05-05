import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Shared markdown renderer for room descriptions (and any future surface
 * that needs the same treatment). XSS-safe: react-markdown does not render
 * raw HTML by default, and we deliberately do NOT pass `rehype-raw`.
 *
 * Behaviour notes worth preserving:
 *  - external links (http(s)://) open in a new tab with rel="noopener
 *    noreferrer" so a malicious link in a description can't repurpose
 *    window.opener or leak the referrer
 *  - internal-style links (anchors, relative paths) keep default behaviour
 *  - GFM extensions: tables, strikethrough, autolinks, task lists
 */
export default function MarkdownText({ source }: { source: string }) {
  if (!source) return null;
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => {
            const isExternal = !!href && /^https?:\/\//i.test(href);
            if (isExternal) {
              return (
                <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                  {children}
                </a>
              );
            }
            return (
              <a href={href} {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
