import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";
import { KrineaWordmark } from "@/components/brand/logo";
import { LanguageSwitch } from "@/components/marketing/site-header";

export const metadata: Metadata = { robots: { index: false, follow: false } };

/** Sign-in, sign-up, magic link and invitation pages: a white page with the wordmark at the
 *  far left, as on the public site, and one bordered card. */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col bg-white">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8 xl:h-[72px]">
        <Link href="/" className="flex items-center" aria-label="Krinea"><KrineaWordmark /></Link>
        <LanguageSwitch bare />
      </div>
      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-6 sm:px-6 sm:pt-12">
        <div className="hero-in w-full max-w-md rounded-2xl border border-ink-200 bg-white p-6 shadow-card sm:p-8">{children}</div>
      </div>
    </main>
  );
}
