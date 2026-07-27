import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import InfoTooltip from './InfoTooltip'

// NOTE: aucun test runner n'est configuré dans ce projet frontend (pas de
// script "test" dans package.json, ni vitest/@testing-library/react en
// devDependencies) au moment de l'écriture de ce fichier. Ce test suit la
// même convention que src/hooks/useTheme.test.ts (vitest + @testing-library/react,
// idiomatique pour un projet Vite) mais ne peut pas être exécuté via `npm test`
// tant que ces dépendances ne sont pas installées et qu'un script "test" n'est
// pas ajouté à package.json.

describe('InfoTooltip', () => {
  it('le panneau est fermé par défaut', () => {
    render(<InfoTooltip label="Disponible">Formule</InfoTooltip>)

    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('un clic ouvre le panneau, un second clic le referme (tap mobile : pas de survol)', () => {
    render(<InfoTooltip label="Disponible">Formule du Disponible</InfoTooltip>)
    const trigger = screen.getByRole('button', { name: 'Formule : Disponible' })

    fireEvent.click(trigger)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Formule du Disponible')

    fireEvent.click(trigger)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('un clic ailleurs dans le document referme le panneau ouvert', () => {
    render(
      <div>
        <InfoTooltip label="Disponible">Formule</InfoTooltip>
        <button>Ailleurs</button>
      </div>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Formule : Disponible' }))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByRole('button', { name: 'Ailleurs' }))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('la touche Échap referme le panneau ouvert', () => {
    render(<InfoTooltip label="Disponible">Formule</InfoTooltip>)

    fireEvent.click(screen.getByRole('button', { name: 'Formule : Disponible' }))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('le focus clavier ouvre le panneau, le blur le referme (accessibilité clavier)', () => {
    render(<InfoTooltip label="Disponible">Formule</InfoTooltip>)
    const trigger = screen.getByRole('button', { name: 'Formule : Disponible' })

    fireEvent.focus(trigger)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    fireEvent.blur(trigger)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('le trigger référence le panneau via aria-describedby une fois ouvert (pattern ARIA tooltip)', () => {
    render(<InfoTooltip label="Disponible">Formule</InfoTooltip>)
    const trigger = screen.getByRole('button', { name: 'Formule : Disponible' })

    fireEvent.click(trigger)

    const panel = screen.getByRole('tooltip')
    expect(trigger).toHaveAttribute('aria-describedby', panel.id)
  })
})
