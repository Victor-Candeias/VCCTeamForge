import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">Página não encontrada</h1>
      <Link to="/" className="text-primary underline-offset-4 hover:underline">
        Voltar ao dashboard
      </Link>
    </div>
  )
}
