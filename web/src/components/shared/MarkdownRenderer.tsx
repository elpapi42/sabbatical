import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState, useEffect, type ReactNode } from "react";

// Lazy-load shiki
let highlighterPromise: Promise<{
  codeToHtml: (code: string, opts: { lang: string; theme: string }) => string;
}> | null = null;

function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then((mod) =>
      mod.createHighlighter({
        themes: ["github-dark"],
        langs: [
          "javascript",
          "typescript",
          "python",
          "bash",
          "json",
          "html",
          "css",
          "markdown",
          "yaml",
          "toml",
          "sql",
          "diff",
        ],
      }),
    );
  }
  return highlighterPromise;
}

function CodeBlock({
  className,
  children,
}: {
  className?: string;
  children?: ReactNode;
}) {
  const [html, setHtml] = useState<string | null>(null);
  const code = String(children).replace(/\n$/, "");
  const lang = className?.replace("language-", "") ?? "text";

  useEffect(() => {
    let cancelled = false;
    getHighlighter()
      .then((hl) => {
        if (!cancelled) {
          try {
            setHtml(hl.codeToHtml(code, { lang, theme: "github-dark" }));
          } catch {
            // Unsupported lang, fall back
            setHtml(null);
          }
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [code, lang]);

  if (html) {
    return (
      <div
        className="overflow-x-auto rounded-md text-sm [&_pre]:p-4"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  }

  return (
    <pre className="overflow-x-auto rounded-md bg-neutral-900 p-4 text-sm">
      <code>{code}</code>
    </pre>
  );
}

function processMentions(text: string): ReactNode[] {
  const parts = text.split(/(@[a-z][a-z0-9_]*)/g);
  return parts.map((part, i) =>
    part.startsWith("@") ? (
      <span
        key={i}
        className="inline-block rounded bg-primary-500/20 px-1 text-primary-400 font-medium"
      >
        {part}
      </span>
    ) : (
      part
    ),
  );
}

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className = "" }: Props) {
  return (
    <ReactMarkdown
      className={`prose prose-invert prose-sm max-w-none ${className}`}
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const isInline = !className;
          if (isInline) {
            return (
              <code
                className="rounded bg-neutral-800 px-1.5 py-0.5 text-sm"
                {...props}
              >
                {children}
              </code>
            );
          }
          return <CodeBlock className={className}>{children}</CodeBlock>;
        },
        p({ children }) {
          // Process @mentions in text children
          const processed = Array.isArray(children)
            ? children.map((child) =>
                typeof child === "string" ? processMentions(child) : child,
              )
            : typeof children === "string"
              ? processMentions(children)
              : children;
          return <p>{processed}</p>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
