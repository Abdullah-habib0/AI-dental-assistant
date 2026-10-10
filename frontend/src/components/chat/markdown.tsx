import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * The assistant's replies, which use Markdown (bold, lists, tables).
 *
 * react-markdown never renders raw HTML from the text, so a reply can't inject
 * scripts or markup into the page.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: (props) => <p className="leading-relaxed [&:not(:last-child)]:mb-2" {...props} />,
        ul: (props) => <ul className="my-2 list-disc space-y-1 pl-5" {...props} />,
        ol: (props) => <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />,
        strong: (props) => <strong className="font-semibold" {...props} />,
        a: (props) => (
          <a className="font-medium underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...props} />
        ),
        table: (props) => (
          <div className="my-2 overflow-x-auto rounded-lg border border-border/70 bg-card">
            <table className="w-full text-left text-xs" {...props} />
          </div>
        ),
        th: (props) => <th className="border-b border-border/70 px-2.5 py-1.5 font-semibold" {...props} />,
        td: (props) => <td className="border-b border-border/40 px-2.5 py-1.5 last:border-b-0" {...props} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
