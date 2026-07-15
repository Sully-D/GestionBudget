import { useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'

export interface UseThemeResult {
  theme: Theme
  toggleTheme: () => void
}

// Source unique de vérité pour le thème clair/sombre. L'état initial est lu
// depuis la classe `dark` déjà posée (ou non) sur <html> par le script
// anti-flash inline dans index.html, pour rester cohérent avec le premier
// paint. La persistance en localStorage est best-effort : en navigation
// privée stricte (ou tout environnement où localStorage lève), le toggle
// continue de fonctionner pour la session React en cours, sans crash.
export function useTheme(): UseThemeResult {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  )

  const toggleTheme = () => {
    setTheme((prev) => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark'

      document.documentElement.classList.toggle('dark', next === 'dark')

      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // localStorage indisponible (ex. navigation privée stricte) : on
        // conserve le comportement visuel pour la session en cours, sans
        // persistance ni erreur non interceptée.
      }

      return next
    })
  }

  return { theme, toggleTheme }
}
