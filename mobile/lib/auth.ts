let _cookie: string | null = null;
let _studentId: number | null = null;
let _userName: string = '';

const SESSION_COOKIE_NAMES = [
  'sessionid',
  'session_id',
  'tronclass_session',
  'session',
  'token',
  'jwt',
  'auth',
];

export function looksLikeSessionCookie(cookie: string): boolean {
  if (!cookie) return false;
  const hasSessionName = SESSION_COOKIE_NAMES.some((name) =>
    cookie
      .split(';')
      .some((pair) => pair.trim().toLowerCase().startsWith(name + '='))
  );
  return hasSessionName;
}

export interface AuthState {
  cookie: string | null;
  studentId: number | null;
  userName: string;
}

export function setAuth(cookie: string, studentId: number, userName = ''): void {
  _cookie = cookie;
  _studentId = studentId;
  _userName = userName;
}

export function getAuth(): AuthState {
  return { cookie: _cookie, studentId: _studentId, userName: _userName };
}

export function clearAuth(): void {
  _cookie = null;
  _studentId = null;
  _userName = '';
}

export function isLoggedIn(): boolean {
  return !!_cookie;
}
