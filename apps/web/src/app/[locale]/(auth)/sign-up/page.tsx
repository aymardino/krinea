import { getTranslations } from "next-intl/server";
import { AuthForm } from "@/components/app/auth-forms";

export default async function SignUpPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  const t = await getTranslations("auth");
  return (
    <>
      <AuthForm mode="sign-up" next={next || "/app"} />
      {/* One plain line of reassurance under the form; the form itself is unchanged. */}
      <p className="mt-6 border-t border-ink-200 pt-4 text-sm leading-relaxed text-ink-500">{t("reassurance")}</p>
    </>
  );
}
