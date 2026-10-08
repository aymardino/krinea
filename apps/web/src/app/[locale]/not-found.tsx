import { Link } from "@/i18n/navigation";

export default function NotFound() {
  return (
    <main className="flex flex-1 items-center justify-center p-10 text-center">
      <div>
        <p className="font-display text-6xl text-brand-700">404</p>
        <p className="mt-2 text-muted-foreground">This page does not exist.</p>
        <Link href="/" className="mt-6 inline-block text-primary underline">Back to Tamis</Link>
      </div>
    </main>
  );
}
