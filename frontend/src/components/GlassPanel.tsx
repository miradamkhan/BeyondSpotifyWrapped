import type { ReactNode } from 'react'

type GlassPanelProps = {
  children: ReactNode
  className?: string
  strong?: boolean
}

export function GlassPanel({ children, className = '', strong = false }: GlassPanelProps) {
  return (
    <div className={`${strong ? 'glass' : 'glass-soft'} rounded-3xl ${className}`}>{children}</div>
  )
}
