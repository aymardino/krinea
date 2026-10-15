import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "@/i18n/navigation";
import { Photo, PhotoCredit } from "@/components/marketing/photo";
import { cn } from "@/lib/utils";

type ProseImage = {
  slug: Parameters<typeof Photo>[0]["slug"];
  alt: string;
  credit: string;
  /** CSS object-position, for example "50% 60%". */
  position?: string;
};

/** Shared reading layout for the Markdown pages (about, privacy, terms, legal notice, security):
 *  a centred reading column of 48rem inside the site container, with an optional photograph
 *  between the title block and the text (wider than the column, credited underneath). */
export function ProseLayout({ title, description, image, children }: { title: string; description?: string; image?: ProseImage; children: ReactNode }) {
  return (
    <article className="container-site py-14 md:py-20 lg:py-24">
      <header className="mx-auto max-w-3xl">
        <h1 className="hero-in font-display max-w-[20ch] text-balance text-[32px] font-semibold leading-[1.08] tracking-[-0.025em] text-ink-950 md:text-[40px] lg:text-[44px]">{title}</h1>
        {description && <p className="hero-in mt-5 max-w-[36rem] text-[17px] leading-[1.5] text-ink-500 md:text-[19px] [animation-delay:70ms]">{description}</p>}
      </header>
      {image && (
        <figure className="mx-auto mt-10 max-w-5xl md:mt-12">
          <Photo
            slug={image.slug}
            alt={image.alt}
            sizes="(min-width: 1024px) 64rem, 100vw"
            width={1280}
            height={960}
            position={image.position}
            className="aspect-[3/2] overflow-hidden rounded-2xl md:aspect-[21/9]"
          />
          <PhotoCredit className="mt-3">{image.credit}</PhotoCredit>
        </figure>
      )}
      <div className={cn("prose-krinea mx-auto max-w-3xl", image ? "mt-10 md:mt-12" : "mt-10")}>{children}</div>
    </article>
  );
}

/** Heading ids that must be the same in both languages, so one footer link works on both pages. */
const HEADING_IDS: Record<string, string> = {
  "How to cite": "how-to-cite",
  "Comment citer": "how-to-cite",
  "Comment citer Krinea": "how-to-cite",
};

function textOf(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (typeof node === "object" && "props" in node) return textOf((node as { props: { children?: ReactNode } }).props.children);
  return "";
}

/** Kebab-case id from a heading: lower case, accents removed, anything else becomes a hyphen. */
export function slugify(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function headingId(children: ReactNode): string {
  const text = textOf(children).trim();
  return HEADING_IDS[text] ?? slugify(text);
}

const body = "text-base leading-[1.6] text-ink-700 lg:text-[17px]";

export function Markdown({ source }: { source: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        /* Section headings get a stable id so the footer and other pages can link to them;
           scroll-mt keeps the heading clear of the sticky header. */
        h2: ({ children }) => <h2 id={headingId(children)} className="scroll-mt-24">{children}</h2>,
        h3: ({ children }) => <h3 id={headingId(children)} className="scroll-mt-24">{children}</h3>,
        p: ({ children }) => <p className={body}>{children}</p>,
        li: ({ children }) => <li className={body}>{children}</li>,
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
