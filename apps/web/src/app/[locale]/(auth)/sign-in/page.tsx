import { AuthForm } from "@/components/app/auth-forms";

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <AuthForm mode="sign-in" next={next || "/app"} />;
}
