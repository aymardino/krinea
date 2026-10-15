import { cn } from "@/lib/utils";

type Slug = "library-laptop" | "team-papers" | "highlighter-textbook" | "accra-balme-library" | "lab-microscope" | "remote-call" | "library-shelves-band" | "researcher-portrait";

/** A photograph from public/photos (credits in public/photos/CREDITS.md): WebP sources at
 *  800, 1280 and 1920px with the 1280px JPEG as fallback. width and height are the intrinsic
 *  size of the fallback so the box is reserved before the file arrives. */
export function Photo({ slug, alt, sizes, width = 1280, height = 853, position, className, imgClassName, priority = false }: {
  slug: Slug; alt: string; sizes: string; width?: number; height?: number; position?: string; className?: string; imgClassName?: string; priority?: boolean;
}) {
  const base = `/photos/${slug}`;
  return (
    <picture className={cn("block", className)}>
      <source type="image/webp" srcSet={`${base}-800.webp 800w, ${base}-1280.webp 1280w, ${base}-1920.webp 1920w`} sizes={sizes} />
      <img
        src={`${base}-1280.jpg`}
        alt={alt}
        width={width}
        height={height}
        loading={priority ? "eager" : "lazy"}
        decoding="async"
        style={position ? { objectPosition: position } : undefined}
        className={cn("h-full w-full object-cover", imgClassName)}
      />
    </picture>
  );
}

/** The 13px credit line under a photograph. */
export function PhotoCredit({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("text-[13px] leading-5 text-ink-500", className)}>{children}</p>;
}
