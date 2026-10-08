import { Link } from "@/i18n/navigation";
import { TamisWordmark } from "@/components/brand/logo";
import { LanguageSwitch } from "@/components/marketing/site-header";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="mesh-bg flex min-h-screen flex-col">
      <div className="flex items-center justify-between px-6 py-5">
        <Link href="/"><TamisWordmark /></Link>
        <LanguageSwitch />
      </div>
      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-6 sm:pt-12">
        <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-pop">{children}</div>
      </div>
    </main>
  );
}
