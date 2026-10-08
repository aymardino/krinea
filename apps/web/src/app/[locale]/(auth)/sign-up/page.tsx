import { AuthForm } from "@/components/app/auth-forms";

export default async function SignUpPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return <AuthForm mode="sign-up" next={next || "/app"} />;
}
