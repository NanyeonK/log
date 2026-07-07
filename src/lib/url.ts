/** base(-'/log') 대응 내부 URL 헬퍼 — 절대경로('/...')에 BASE_URL을 접두. */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

export function withBase(path: string): string {
  if (/^(?:[a-z]+:)?\/\//i.test(path)) return path; // 외부/프로토콜 상대 URL은 그대로
  if (!path.startsWith('/')) return path; // 상대경로 그대로
  if (path === BASE || path.startsWith(`${BASE}/`)) return path; // 이미 접두됨
  return `${BASE}${path}`;
}
