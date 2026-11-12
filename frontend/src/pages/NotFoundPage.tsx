import { Link } from 'react-router'

import { es } from '../i18n/es'

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-2xl space-y-3">
      <h1 className="text-2xl font-semibold">{es.notFound.title}</h1>
      <p className="text-muted-foreground">{es.notFound.body}</p>
      <Link to="/" className="font-semibold text-accent underline underline-offset-4 hover:text-primary">
        {es.notFound.back}
      </Link>
    </section>
  )
}
