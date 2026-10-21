import { useId } from 'react'

import { cn } from '@/lib/utils'

export function BrandMark({ className }: { className?: string }) {
  const gradientId = useId()
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn('size-8 shrink-0', className)}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <path fill="#fff" d="M9 9h14v3.2h-5.4V23h-3.2V12.2H9z" />
      <path fill="#a5b4fc" d="M19.6 15.4H23v3.2h-3.4z" />
    </svg>
  )
}

export function BrandLogo({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2.5 font-semibold tracking-tight', className)}>
      <BrandMark />
      <span>
        VCC<span className="text-sidebar-primary">TeamForge</span>
      </span>
    </span>
  )
}
