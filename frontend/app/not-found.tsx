import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center text-center py-24">
      <h1 className="text-3xl font-bold mb-2">404</h1>
      <p className="text-sm text-muted-foreground mb-4">
        That page wandered into a circuit-breaker halt.
      </p>
      <Link href="/" className="text-primary text-sm hover:underline">
        Back to dashboard →
      </Link>
    </div>
  );
}
