import { describe, expect, it } from 'vitest'
import { calculerDisponibleSimule } from './format'

// NOTE: aucun test runner n'est configuré dans ce projet frontend (pas de
// script "test" dans package.json, ni vitest/@testing-library/react en
// devDependencies) au moment de l'écriture de ce fichier. Ce test suit la
// même convention que src/hooks/useTheme.test.ts (vitest, idiomatique pour
// un projet Vite) mais ne peut pas être exécuté via `npm test` tant que ces
// dépendances ne sont pas installées et qu'un script "test" n'est pas ajouté.

describe('calculerDisponibleSimule', () => {
  it('calcule un Disponible positif (scénario par défaut de la page Simulation)', () => {
    expect(calculerDisponibleSimule(3000, 1200, 400, 700)).toBe(700)
  })

  it('calcule un Disponible négatif (scénario déficitaire)', () => {
    expect(calculerDisponibleSimule(2000, 1500, 300, 500)).toBe(-300)
  })

  it('renvoie 0 quand toutes les valeurs sont nulles', () => {
    expect(calculerDisponibleSimule(0, 0, 0, 0)).toBe(0)
  })

  it('renvoie exactement 0 comme cas limite (Disponible ni positif ni négatif)', () => {
    expect(calculerDisponibleSimule(1000, 500, 300, 200)).toBe(0)
  })
})
