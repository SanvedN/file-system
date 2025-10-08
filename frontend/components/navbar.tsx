"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

const links = [
  { href: "/tenants", label: "Tenants" },
  { href: "/files", label: "Files" },
  { href: "/embeddings", label: "Embeddings" },
]

export function Navbar() {
  const pathname = usePathname()
  return (
    <div className="sticky top-0 z-40 border-b border-b-zinc-800/60 bg-zinc-950/50 backdrop-blur-md">
      <nav className="container mx-auto flex items-center justify-between px-4 py-3">
        <Link href="/tenants" className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block h-3 w-3 rounded-full bg-[oklch(0.645_0.246_16.439)] shadow-[0_0_20px_oklch(0.645_0.246_16.439/.6)]"
          />
          <span className="text-pretty text-sm font-mono uppercase tracking-widest text-muted-foreground">
            FileRepo
          </span>
        </Link>
        <ul className="flex items-center gap-1">
          {links.map((l) => {
            const active = pathname?.startsWith(l.href)
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  className={cn(
                    "relative rounded-md px-3 py-2 text-sm text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  )}
                >
                  {l.label}
                  {active ? (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 -z-10 rounded-md bg-zinc-800/60"
                      transition={{ type: "spring", stiffness: 300, damping: 24 }}
                    />
                  ) : null}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>
    </div>
  )
}
