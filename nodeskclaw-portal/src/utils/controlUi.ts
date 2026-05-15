export function buildControlUiUrl(baseUrl?: string | null, token?: string | null): string {
  if (!baseUrl) return ''
  try {
    const url = new URL(baseUrl)
    if (token) {
      url.searchParams.set('token', token)
    }
    return url.toString()
  } catch {
    return baseUrl
  }
}
