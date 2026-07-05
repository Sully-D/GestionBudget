import { unwrap } from './http'

export interface Tag {
  tag_id: number
  name: string
  parent_id: number | null
  level: number
}

export interface TagCreatePayload {
  name: string
  parent_id?: number
}

export interface TagUpdatePayload {
  name: string
}

export async function getTags(): Promise<Tag[]> {
  const response = await fetch('/tags')
  return unwrap<Tag[]>(response)
}

export async function createTag(payload: TagCreatePayload): Promise<Tag> {
  const response = await fetch('/tags', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Tag>(response)
}

export async function updateTag(tagId: number, payload: TagUpdatePayload): Promise<Tag> {
  const response = await fetch(`/tags/${tagId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return unwrap<Tag>(response)
}

export async function deleteTag(tagId: number): Promise<void> {
  const response = await fetch(`/tags/${tagId}`, { method: 'DELETE' })
  await unwrap<null>(response)
}
