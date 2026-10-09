"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { LogOut, Settings, LayoutGrid } from "lucide-react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { KrineaWordmark } from "@/components/brand/logo";
import { LanguageSwitch } from "@/components/marketing/site-header";
import { Avatar, Skeleton } from "@/components/ui/misc";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useMe, useSignOut } from "@/lib/auth";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { data: me, isLoading } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations("common");
  const signOut = useSignOut();

  useEffect(() => {
    if (!isLoading && me === null) router.replace({ pathname: "/sign-in", query: { next: pathname } });
  }, [isLoading, me, router, pathname]);

  if (isLoading || !me) {
    return (
      <div className="mx-auto max-w-6xl p-6"><Skeleton className="h-8 w-48" /><Skeleton className="mt-6 h-40 w-full" /></div>
    );
  }
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-border bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/app"><KrineaWordmark size={24} /></Link>
            <nav className="hidden items-center gap-1 text-sm md:flex">
              <Link href="/app" className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"><LayoutGrid className="size-4" />{t("reviews")}</Link>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitch className="hidden sm:block" />
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"><Avatar name={me.name || me.email} /></DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="truncate font-normal"><span className="block text-sm font-medium text-foreground">{me.name || "—"}</span><span className="block truncate text-xs">{me.email}</span></DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => router.push("/app/settings")}><Settings />{t("settings")}</DropdownMenuItem>
                <DropdownMenuItem onSelect={async () => { await signOut(); router.push("/"); }}><LogOut />{t("signOut")}</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
