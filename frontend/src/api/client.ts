/** 统一请求封装：拼后端地址、携带当前检验员身份、抛网络错误。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export const INSPECTOR_STORAGE_KEY = 'current-inspector-id'

export function currentInspectorId(): string {
  return localStorage.getItem(INSPECTOR_STORAGE_KEY) ?? ''
}

export function setCurrentInspectorId(inspectorId: string) {
  if (inspectorId) {
    localStorage.setItem(INSPECTOR_STORAGE_KEY, inspectorId)
  } else {
    localStorage.removeItem(INSPECTOR_STORAGE_KEY)
  }
}

function authHeaders(init?: RequestInit): HeadersInit {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const inspectorId = currentInspectorId()
  if (inspectorId) {
    headers.set('X-Inspector-Id', inspectorId)
  }
  return headers
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, { ...init, headers: authHeaders(init) }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

/** 动作类接口：把后端 401/403 的受控原因原样抛出，供页面展示。 */
export async function postAction(
  path: string,
  body: unknown,
): Promise<{ ok: boolean; message: string; entry: Record<string, unknown> | null }> {
  const response = await request(path, { method: 'POST', body: JSON.stringify(body) })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload?.detail ?? `操作被拒绝（${response.status}），数据未变更`
    throw new Error(detail)
  }
  return payload
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
