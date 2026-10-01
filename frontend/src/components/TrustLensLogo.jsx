export function TrustLensLogo({ className = '', ...props }) {
  return (
    <svg className={['trustlens-logo', className].filter(Boolean).join(' ')} fill="none" viewBox="0 0 32 32" {...props}>
      <path d="M16 3.5 26 7.7v7.7c0 6.2-4.1 10.8-10 13.1C10.1 26.2 6 21.6 6 15.4V7.7L16 3.5Z" fill="currentColor" opacity=".18" />
      <path d="M16 4.8 24.7 8.4v6.8c0 5.4-3.5 9.5-8.7 11.6-5.2-2.1-8.7-6.2-8.7-11.6V8.4L16 4.8Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="m11.3 16.1 3 3 6.6-7" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
      <circle cx="23.9" cy="7.8" fill="currentColor" r="2.2" />
    </svg>
  )
}
