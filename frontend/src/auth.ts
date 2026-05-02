const KEY = 'coffee_username'

export function getUsername(): string | null {
  return localStorage.getItem(KEY)
}

export function setUsername(name: string): void {
  localStorage.setItem(KEY, name)
}

export function clearUsername(): void {
  localStorage.removeItem(KEY)
}
