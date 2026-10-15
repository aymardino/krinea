import { SiteHeader } from "@/components/marketing/site-header";
import { SiteFooter } from "@/components/marketing/site-footer";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Without JavaScript nothing waits for an IntersectionObserver: everything is visible. */}
      <noscript>
        <style>{`.reveal,.reveal>.reveal-item{opacity:1;transform:none}.hero-in{animation:none}`}</style>
      </noscript>
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </>
  );
}
