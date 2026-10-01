const tokenKey = 'trustlens_access_token'
const userKey = 'trustlens_current_user'

export function getAccessToken() {
  return window.localStorage.getItem(tokenKey)
}

export function setAccessToken(token) {
  window.localStorage.setItem(tokenKey, token)
}

export function getCurrentUser() {
  try {
    const value = window.localStorage.getItem(userKey)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function setCurrentUser(user) {
  if (!user || typeof user !== 'object') return
  window.localStorage.setItem(userKey, JSON.stringify({
    id: user.id,
    name: typeof user.name === 'string' ? user.name : null,
    email: user.email,
    role: typeof user.role === 'string' ? user.role : null,
    created_at: user.created_at,
    last_login: typeof user.last_login === 'string' ? user.last_login : null,
  }))
}

export function clearAccessToken() {
  window.localStorage.removeItem(tokenKey)
  window.localStorage.removeItem(userKey)
}
