export async function unwrap<T>(response: Response): Promise<T> {
  let body: { data?: T; detail?: unknown }
  try {
    body = await response.json()
  } catch {
    throw new Error('Erreur inattendue')
  }
  if (!response.ok) {
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Erreur inattendue')
  }
  return body.data as T
}
