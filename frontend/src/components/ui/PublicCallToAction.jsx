import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export function PublicCallToAction({ description, title }) {
  return (
    <section className="public-call-to-action" aria-labelledby="public-cta-title">
      <div>
        <p className="eyebrow">Private workspace</p>
        <h2 id="public-cta-title">{title}</h2>
        <p>{description}</p>
      </div>
      <Link className="primary-link" to="/signup">Create an account <ArrowRight aria-hidden="true" size={17} /></Link>
    </section>
  )
}
