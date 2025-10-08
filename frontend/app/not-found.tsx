import Link from "next/link"

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl rounded-lg border bg-card/60 p-6 backdrop-blur-md">
      <h1 className="text-balance text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-muted-foreground">
        The page you are looking for doesn&apos;t exist. Head back to tenants to get started.
      </p>
      <div className="mt-4">
        <Link
          href="/tenants"
          className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Go to Tenants
        </Link>
      </div>
    </div>
  )
}
