import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'

interface InfoTooltipProps {
  label: string
  children: ReactNode
  // 'right' pour les triggers proches du bord droit du viewport (ex. la dernière
  // colonne d'une grille) : évite que le panneau w-64 ne déborde de l'écran.
  align?: 'left' | 'right'
}

// Clic/tap uniquement (pas de survol) : un survol synthétique précède le clic sur
// tactile, ce qui ouvrirait puis refermerait immédiatement le panneau si les deux
// étaient combinés. `onFocus`/`onBlur` couvrent la navigation clavier.
function InfoTooltip({ label, children, align = 'left' }: InfoTooltipProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLSpanElement>(null)
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    function handleOutside(event: Event) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('touchstart', handleOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('touchstart', handleOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <span ref={containerRef} className="relative inline-block normal-case">
      <button
        type="button"
        aria-expanded={open}
        aria-describedby={open ? panelId : undefined}
        aria-label={`Formule : ${label}`}
        onClick={() => setOpen((value) => !value)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-current text-caption font-normal normal-case leading-none opacity-70 hover:opacity-100"
      >
        i
      </button>
      {open && (
        <span
          id={panelId}
          role="tooltip"
          className={`absolute top-full z-10 mt-1 w-64 rounded border border-border bg-surface p-2 text-caption font-normal normal-case text-ink shadow-lg ${
            align === 'right' ? 'right-0' : 'left-0'
          }`}
        >
          {children}
        </span>
      )}
    </span>
  )
}

export default InfoTooltip
