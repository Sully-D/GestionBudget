import { Link, useParams } from 'react-router'
import { TransactionForm } from './NouvelleTransaction'

function ModifierTransaction() {
  const { id } = useParams()
  const transactionId = Number(id)

  if (!Number.isInteger(transactionId)) {
    return (
      <main className="mx-auto max-w-md px-4 py-6 sm:px-4 lg:px-7">
        <p className="text-body text-alert">Identifiant de transaction invalide.</p>
        <Link to="/transactions" className="mt-2 inline-block text-body-strong text-accent underline">
          Retour aux transactions
        </Link>
      </main>
    )
  }

  return <TransactionForm transactionId={transactionId} />
}

export default ModifierTransaction
