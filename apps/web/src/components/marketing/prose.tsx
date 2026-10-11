import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "@/i18n/navigation";

/** Shared reading layout for the Markdown pages (about, privacy, terms, legal notice). */
export function ProseLayout({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl px-4 py-14 sm:px-6 md:py-20">
      <h1 className="font-display text-4xl font-semibold tracking-tight md:text-5xl">{title}</h1>
      {description && <p className="mt-4 text-lg text-muted-foreground">{description}</p>}
      <div className="prose-krinea mt-10">{children}</div>
    </article>
  );
}

export function Markdown({ source }: { source: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ href, children }) => {
          const h = href ?? "#";
          if (h.startsWith("/")) return <Link href={h}>{children}</Link>;
          const external = /^https?:\/\//.test(h);
          return <a href={h} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>{children}</a>;
        },
      }}
    >
      {source}
    </ReactMarkdown>
  );
}
