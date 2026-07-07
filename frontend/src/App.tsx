import { Link, Route, Routes } from 'react-router'
import Budget from './pages/Budget'
import Comptes from './pages/Comptes'
import Dashboard from './pages/Dashboard'
import Import from './pages/Import'
import ModifierTransaction from './pages/ModifierTransaction'
import NouvelleTransaction from './pages/NouvelleTransaction'
import Projection from './pages/Projection'
import Recurrentes from './pages/Recurrentes'
import Transactions from './pages/Transactions'

function App() {
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
          <Link
            to="/transactions/nouvelle"
            className="rounded-lg bg-accent px-3 py-1.5 text-body-strong text-surface"
          >
            + Transaction
          </Link>
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
      </Routes>
    </div>
  )
}

export default App
