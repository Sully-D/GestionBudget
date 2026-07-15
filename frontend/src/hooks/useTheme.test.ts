import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useTheme } from './useTheme'

// NOTE: aucun test runner n'est configuré dans ce projet frontend (pas de
// script "test" dans package.json, ni vitest/@testing-library/react en
// devDependencies) au moment de l'écriture de ce fichier. Ce test est écrit
// selon la convention idiomatique pour un projet Vite (vitest +
// @testing-library/react) mais ne peut pas être exécuté via `npm test`
// tant que ces dépendances ne sont pas installées et qu'un script "test"
// n'est pas ajouté à package.json.

function resetHtmlAndStorage() {
  document.documentElement.classList.remove('dark')
  localStorage.clear()
}

describe('useTheme', () => {
  beforeEach(() => {
    resetHtmlAndStorage()
  })

  it('démarre en thème clair quand <html> n’a pas la classe dark (aucune préférence stockée)', () => {
    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('lit l’état initial depuis la classe dark déjà posée sur <html> (cohérence avec le script anti-flash)', () => {
    document.documentElement.classList.add('dark')

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('dark')
  })

  it('bascule vers sombre : met à jour la classe sur <html> et persiste en localStorage', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('theme')).toBe('dark')
  })

  it('bascule à nouveau vers clair : retire la classe et met à jour localStorage', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.toggleTheme()
    })
    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.theme).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('ne plante pas si localStorage.setItem lève (navigation privée stricte) et applique quand même le changement visuel', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    const { result } = renderHook(() => useTheme())

    expect(() => {
      act(() => {
        result.current.toggleTheme()
      })
    }).not.toThrow()

    expect(result.current.theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    setItemSpy.mockRestore()
  })
})
