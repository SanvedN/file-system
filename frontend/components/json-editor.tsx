"use client"

import * as React from "react"

type Props = {
  value?: Record<string, unknown> | null
  onChange: (obj: Record<string, unknown>) => void
  onError?: (msg: string | null) => void
}

export function JsonEditor({ value, onChange, onError }: Props) {
  const [text, setText] = React.useState<string>(() => (value ? JSON.stringify(value, null, 2) : "{\n  \n}"))
  const [error, setError] = React.useState<string | null>(null)

  function handleBlur() {
    try {
      const obj = JSON.parse(text || "{}")
      setError(null)
      onError?.(null)
      onChange(obj)
    } catch (e: any) {
      const msg = e?.message || "Invalid JSON"
      setError(msg)
      onError?.(msg)
    }
  }

  return (
    <div className="grid gap-2">
      <textarea
        className="min-h-48 w-full rounded-md border border-zinc-800 bg-zinc-950/60 p-3 font-mono text-sm leading-6 text-foreground backdrop-blur-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={handleBlur}
        spellCheck={false}
        aria-invalid={!!error}
        aria-describedby={error ? "json-error" : undefined}
      />
      {error ? (
        <p id="json-error" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}
