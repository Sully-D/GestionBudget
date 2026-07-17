import { Link, Route, Routes } from 'react-router'
import { useTheme } from './hooks/useTheme'
import Budget from './pages/Budget'
import Comparaison from './pages/Comparaison'
import Comptes from './pages/Comptes'
import Dashboard from './pages/Dashboard'
import Export from './pages/Export'
import Import from './pages/Import'
import ModifierTransaction from './pages/ModifierTransaction'
import NouvelleTransaction from './pages/NouvelleTransaction'
import Projection from './pages/Projection'
import Recurrentes from './pages/Recurrentes'
import Simulation from './pages/Simulation'
import Synthese from './pages/Synthese'
import Transactions from './pages/Transactions'

function App() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="min-h-screen bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-4 sm:px-4 lg:px-7">
        <span className="text-brand-mark font-bold tracking-[0.3px] text-ink">
          GestionDuBudget
        </span>
        <nav className="flex items-center gap-4">
          <Link to="/" className="text-body text-ink-muted hover:text-ink">
            Tableau de bord
          </Link>
          <Link to="/comptes" className="text-body text-ink-muted hover:text-ink">
            Comptes
          </Link>
          <Link to="/transactions" className="text-body text-ink-muted hover:text-ink">
            Transactions
          </Link>
          <Link to="/budget" className="text-body text-ink-muted hover:text-ink">
            Budget
          </Link>
          <Link to="/recurrentes" className="text-body text-ink-muted hover:text-ink">
            Récurrentes
          </Link>
          <Link to="/projection" className="text-body text-ink-muted hover:text-ink">
            Projection
          </Link>
          <Link to="/comparaison" className="text-body text-ink-muted hover:text-ink">
            Comparaison
          </Link>
          <Link to="/synthese" className="text-body text-ink-muted hover:text-ink">
            Synthèse
          </Link>
          <Link to="/simulation" className="text-body text-ink-muted hover:text-ink">
            Simulation
          </Link>
          <Link to="/export" className="text-body text-ink-muted hover:text-ink">
            Export
          </Link>
          <Link
            to="/transactions/nouvelle"
            className="rounded-lg bg-accent px-3 py-1.5 text-body-strong text-surface"
          >
            + Transaction
          </Link>
          <button
            type="button"
            onClick={toggleTheme}
            aria-pressed={theme === 'dark'}
            aria-label={theme === 'dark' ? 'Activer le mode clair' : 'Activer le mode sombre'}
            className="rounded-lg border border-border px-3 py-1.5 text-body text-ink-muted hover:text-ink"
          >
            {theme === 'dark' ? 'Mode clair' : 'Mode sombre'}
          </button>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/comptes" element={<Comptes />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/transactions/import" element={<Import />} />
        <Route path="/transactions/nouvelle" element={<NouvelleTransaction />} />
        <Route path="/transactions/:id/modifier" element={<ModifierTransaction />} />
        <Route path="/budget" element={<Budget />} />
        <Route path="/recurrentes" element={<Recurrentes />} />
        <Route path="/projection" element={<Projection />} />
        <Route path="/comparaison" element={<Comparaison />} />
        <Route path="/synthese" element={<Synthese />} />
        <Route path="/simulation" element={<Simulation />} />
        <Route path="/export" element={<Export />} />
      </Routes>
    </div>
  )
}

export default App
