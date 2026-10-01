import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'

export function PasswordField({ autoComplete, error = '', helperText, id, inputRef, minLength, onBlur, onChange, value }) {
  const [isVisible, setIsVisible] = useState(false)
  const describedBy = error ? `${id}-error` : helperText ? `${id}-help` : undefined

  return (
    <div className="auth-field">
      <label htmlFor={id}>Password</label>
      <div className="auth-field__control">
        <input aria-describedby={describedBy} aria-invalid={Boolean(error)} autoComplete={autoComplete} id={id} minLength={minLength} onBlur={onBlur} onChange={onChange} ref={inputRef} required type={isVisible ? 'text' : 'password'} value={value} />
        <button aria-label={isVisible ? 'Hide password' : 'Show password'} aria-pressed={isVisible} className="password-visibility-toggle" onClick={() => setIsVisible((visible) => !visible)} type="button">
          {isVisible ? <EyeOff aria-hidden="true" size={18} /> : <Eye aria-hidden="true" size={18} />}
        </button>
      </div>
      {error ? <p className="auth-field__error" id={`${id}-error`} role="alert">{error}</p> : helperText && <p id={`${id}-help`}>{helperText}</p>}
    </div>
  )
}
