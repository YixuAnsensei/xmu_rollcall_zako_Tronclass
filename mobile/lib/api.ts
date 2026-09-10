const BASE_URL = 'https://lnt.xmu.edu.cn';

const HEADERS_BASE: Record<string, string> = {
  accept: 'application/json, text/plain, */*',
  'accept-language': 'zh-CN,zh;q=0.9',
  'user-agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Course {
  id: number;
  name: string;
  display_name?: string;
}

export interface RollcallRecord {
  id?: number;
  rollcall_id?: number;
  created_at?: string;
  rollcall_time?: string;
  status?: string;
  is_radar?: boolean;
  isRadar?: boolean;
  rollcall_type?: string;
  type?: string;
  kind?: string;
  is_number?: boolean;
  is_qrcode?: boolean;
  is_qr?: boolean;
}

export interface SemesterInfo {
  semester_id: string;
  academic_year_id: string;
}

export interface RadarResult {
  success: boolean;
  campus?: string;
  position?: [number, number];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeHeaders(cookie: string): Record<string, string> {
  return { ...HEADERS_BASE, cookie, 'content-type': 'application/json' };
}

function fetchWithTimeout(url: string, init: RequestInit, ms: number): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...init, signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

function parseListResponse(data: any, key: string): any[] {
  if (Array.isArray(data)) return data;
  return (data[key] || data.data || []) as any[];
}

export function fmtTime(value?: string): string {
  if (!value) return '未知';
  try {
    const dt = new Date(value.replace('Z', '+00:00'));
    if (isNaN(dt.getTime())) return String(value);
    const cn = new Date(dt.getTime() + 8 * 60 * 60 * 1000);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${cn.getUTCFullYear()}-${pad(cn.getUTCMonth() + 1)}-${pad(cn.getUTCDate())} ${pad(cn.getUTCHours())}:${pad(cn.getUTCMinutes())}`;
  } catch {
    return String(value);
  }
}

function uuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ---------------------------------------------------------------------------
// Auth flows
// ---------------------------------------------------------------------------

export async function getProfile(cookie: string): Promise<{ id: number; name: string }> {
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/profile`,
      { headers: makeHeaders(cookie) },
      10000
    );
    if (resp.ok) {
      const data = await resp.json();
      const id =
        data.id ??
        data.user_id ??
        data.userId ??
        data.student_id ??
        data.studentId ??
        null;
      if (typeof id === 'number' || (typeof id === 'string' && !isNaN(Number(id)))) {
        return {
          id: Number(id),
          name: data.name ?? data.username ?? '',
        };
      }
    }
  } catch {}
  throw new Error('无法获取用户信息');
}

export async function getSemesterInfo(cookie: string): Promise<SemesterInfo> {
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/current-semester-info`,
      { headers: makeHeaders(cookie) },
      5000
    );
    if (resp.ok) {
      const data = await resp.json();
      return {
        semester_id: String(data.semester?.id ?? '29'),
        academic_year_id: String(data.academic_year?.id ?? '12'),
      };
    }
  } catch {}
  return { semester_id: '29', academic_year_id: '12' };
}

export async function getCourses(
  cookie: string,
  semId: string,
  yearId: string
): Promise<Course[]> {
  const payload = {
    conditions: {
      semester_id: [semId],
      academic_year_id: [yearId],
      keyword: '',
      classify_type: 'recently_started',
      display_studio_list: false,
    },
    fields: 'id,name,display_name',
    page: 1,
    page_size: 30,
    showScorePassedStatus: false,
  };

  const resp = await fetchWithTimeout(
    `${BASE_URL}/api/my-courses`,
    {
      method: 'POST',
      headers: {
        ...makeHeaders(cookie),
        referer: `${BASE_URL}/user/index`,
      },
      body: JSON.stringify(payload),
    },
    15000
  );

  const data = await resp.json();
  const list = parseListResponse(data, 'courses') as Course[];

  const seen = new Set<number>();
  return list.filter((c) => {
    if (seen.has(c.id)) return false;
    seen.add(c.id);
    return true;
  });
}

// ---------------------------------------------------------------------------
// Rollcall queries
// ---------------------------------------------------------------------------

export async function getLatestRollcall(
  courseId: number,
  cookie: string,
  studentId: number
): Promise<RollcallRecord | null> {
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/course/${courseId}/student/${studentId}/rollcalls?page=1&page_size=99`,
      { headers: makeHeaders(cookie) },
      15000
    );
    const data = await resp.json();
    const rollcalls = parseListResponse(data, 'rollcalls') as RollcallRecord[];
    return rollcalls.length > 0 ? rollcalls[rollcalls.length - 1] : null;
  } catch {
    return null;
  }
}

export async function getNumberCode(
  rollcallId: string,
  cookie: string
): Promise<{
  code: string | null;
  status: string | null;
  endTime: string | null;
  signed: boolean;
}> {
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/rollcall/${rollcallId}/student_rollcalls`,
      { headers: makeHeaders(cookie) },
      15000
    );
    const data = await resp.json();
    const signed = Boolean(
      data.signed ??
        data.is_signed ??
        data.isSigned ??
        data.answered ??
        data.is_answered ??
        data.isAnswered ??
        (data.result !== undefined && data.result !== null && data.result !== '')
    );
    return {
      code: data.number_code ?? null,
      status: data.status ?? null,
      endTime: data.end_time ?? null,
      signed,
    };
  } catch {
    return { code: null, status: null, endTime: null, signed: false };
  }
}

export async function findActiveRadarRecord(
  cookie: string,
  rollcallId: string
): Promise<any | null> {
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/radar/rollcalls`,
      { headers: makeHeaders(cookie) },
      15000
    );
    const data = await resp.json();
    const rollcalls: any[] = Array.isArray(data)
      ? data
      : (data?.rollcalls ?? []);
    const target = String(rollcallId);
    for (const rc of rollcalls) {
      if (!rc || typeof rc !== 'object') continue;
      const rid = String(rc.rollcall_id ?? rc.id ?? '');
      if (rid === target) return rc;
    }
    return null;
  } catch {
    return null;
  }
}

export async function submitNumberCode(
  cookie: string,
  rollcallId: string,
  onLog: (msg: string) => void
): Promise<{ ok: boolean; code?: string; reason?: string }> {
  onLog(`🐾 开始数字签到提交 rollcall_id=${rollcallId}`);
  const { code, status } = await getNumberCode(rollcallId, cookie);

  if (!code) {
    onLog('❌ 未获取到数字签到码，无法提交');
    return { ok: false, reason: 'no_code' };
  }
  if (status === 'finished') {
    onLog('⏰ 签到已结束，不提交');
    return { ok: false, reason: 'finished' };
  }

  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/rollcall/${rollcallId}/answer_number_rollcall`,
      {
        method: 'PUT',
        headers: makeHeaders(cookie),
        body: JSON.stringify({ deviceId: uuid(), numberCode: String(code) }),
      },
      15000
    );
    if (resp.status === 200) {
      onLog(`✅ 数字签到成功喵❤ 签到码：${code}`);
      return { ok: true, code: String(code) };
    }
    onLog(`❌ 提交失败 HTTP ${resp.status}`);
    return { ok: false, reason: 'http', code: String(code) };
  } catch (e) {
    onLog(`❌ 提交异常：${e}`);
    return { ok: false, reason: 'exception', code: String(code) };
  }
}

// ---------------------------------------------------------------------------
// Radar sign-in engine
// ---------------------------------------------------------------------------

interface Campus {
  name: string;
  lat: number;
  lng: number;
}

const CAMPUSES: Campus[] = [
  { name: '翔安校区', lat: 24.6060, lng: 118.3100 },
  { name: '思明校区', lat: 24.4383, lng: 118.0932 },
  { name: '马来西亚校区', lat: 2.8327, lng: 101.7028 },
  { name: '漳州校区', lat: 24.3400, lng: 117.9300 },
];

const EARTH_R = 6371000.0;
const PROBE_ACCURACY = 35;

function radarDistance(data: any): number | null {
  if (!data || typeof data !== 'object') return null;
  for (const key of ['distance', 'dist', 'distance_m', 'distanceMeters']) {
    const val = data[key];
    if (typeof val === 'number') return val;
  }
  return null;
}

function latlonToXY(lat: number, lng: number, lat0: number, lng0: number): [number, number] {
  const x = (lng - lng0) * (Math.PI / 180) * EARTH_R * Math.cos((lat0 * Math.PI) / 180);
  const y = (lat - lat0) * (Math.PI / 180) * EARTH_R;
  return [x, y];
}

function circleIntersections(
  x1: number, y1: number, d1: number,
  x2: number, y2: number, d2: number
): [number, number][] | null {
  const dist = Math.hypot(x2 - x1, y2 - y1);
  if (dist === 0) return null;
  if (dist > d1 + d2) {
    if (dist - (d1 + d2) <= 50) {
      const r = d1 / (d1 + d2);
      const px = x1 + (x2 - x1) * r;
      const py = y1 + (y2 - y1) * r;
      return [[px, py], [px, py]];
    }
    return null;
  }
  if (dist < Math.abs(d1 - d2)) {
    if (Math.abs(d1 - d2) - dist <= 50) {
      if (d1 > d2) {
        const r = d1 / dist;
        const px = x1 + (x2 - x1) * r;
        const py = y1 + (y2 - y1) * r;
        return [[px, py], [px, py]];
      }
      const r = d2 / dist;
      const px = x2 + (x1 - x2) * r;
      const py = y2 + (y1 - y2) * r;
      return [[px, py], [px, py]];
    }
    return null;
  }
  const along = (d1 * d1 - d2 * d2 + dist * dist) / (2 * dist);
  const hSq = d1 * d1 - along * along;
  const h = Math.sqrt(Math.max(0, hSq));
  const mx = x1 + along * (x2 - x1) / dist;
  const my = y1 + along * (y2 - y1) / dist;
  const ox = -(y2 - y1) * h / dist;
  const oy = (x2 - x1) * h / dist;
  return [[mx + ox, my + oy], [mx - ox, my - oy]];
}

function xyToLatlon(x: number, y: number, lat0: number, lng0: number): [number, number] {
  const lat = lat0 + (y / EARTH_R) * (180 / Math.PI);
  const lng = lng0 + (x / (EARTH_R * Math.cos((lat0 * Math.PI) / 180))) * (180 / Math.PI);
  return [lat, lng];
}

function solveTwoPoints(
  lat1: number, lng1: number,
  lat2: number, lng2: number,
  d1: number, d2: number
): [number, number][] | null {
  const lat0 = (lat1 + lat2) / 2;
  const lng0 = (lng1 + lng2) / 2;
  const [x1, y1] = latlonToXY(lat1, lng1, lat0, lng0);
  const [x2, y2] = latlonToXY(lat2, lng2, lat0, lng0);
  const sols = circleIntersections(x1, y1, d1, x2, y2, d2);
  if (!sols) return null;
  return sols.map(([x, y]) => xyToLatlon(x, y, lat0, lng0));
}

async function realRadarPut(
  cookie: string,
  rollcallId: string,
  lat: number,
  lng: number,
  deviceId: string
): Promise<[number, any]> {
  const payload = {
    accuracy: PROBE_ACCURACY,
    altitude: 0,
    altitudeAccuracy: null,
    deviceId,
    heading: null,
    latitude: lat,
    longitude: lng,
    speed: null,
  };
  try {
    const resp = await fetchWithTimeout(
      `${BASE_URL}/api/rollcall/${rollcallId}/answer`,
      {
        method: 'PUT',
        headers: makeHeaders(cookie),
        body: JSON.stringify(payload),
      },
      15000
    );
    let data: any = {};
    try { data = await resp.json(); } catch {}
    return [resp.status, data];
  } catch (e) {
    return [0, { error: String(e) }];
  }
}

type RadarPutFn = (
  cookie: string,
  rollcallId: string,
  lat: number,
  lng: number,
  deviceId: string
) => Promise<[number, any]>;

let radarPutImpl: RadarPutFn = realRadarPut;

async function radarPut(
  cookie: string,
  rollcallId: string,
  lat: number,
  lng: number,
  deviceId: string
): Promise<[number, any]> {
  return radarPutImpl(cookie, rollcallId, lat, lng, deviceId);
}

export function __setRadarPutForTest(fn: RadarPutFn | null): void {
  radarPutImpl = fn ?? realRadarPut;
}

export async function radarLockCampus(
  cookie: string,
  rollcallId: string,
  deviceId: string,
  log: (msg: string) => void
): Promise<[Campus | null, number]> {
  let best: { campus: Campus; dist: number } | null = null;
  for (const c of CAMPUSES) {
    const [status, data] = await radarPut(cookie, rollcallId, c.lat, c.lng, deviceId);
    if (status === 200) {
      log(`🎯 校区探针直接命中：${c.name}`);
      return [c, 0];
    }
    const d = radarDistance(data);
    log(`📡 ${c.name} 探针 distance=${d}`);
    if (d !== null && (best === null || d < best.dist)) {
      best = { campus: c, dist: d };
    }
  }
  return [best?.campus ?? null, best?.dist ?? Infinity];
}

export async function radarTriangulate(
  cookie: string,
  rollcallId: string,
  center: Campus,
  deviceId: string,
  log: (msg: string) => void
): Promise<[boolean, [number, number] | null]> {
  const { lat: lat0, lng: lng0 } = center;
  const dlat = 0.004;
  const dlng = 0.004;

  const [s1, d1Data] = await radarPut(cookie, rollcallId, lat0 + dlat, lng0, deviceId);
  const dist1 = radarDistance(d1Data);
  if (s1 === 200) return [true, [lat0 + dlat, lng0]];

  const [s2, d2Data] = await radarPut(cookie, rollcallId, lat0, lng0 + dlng, deviceId);
  const dist2 = radarDistance(d2Data);
  if (s2 === 200) return [true, [lat0, lng0 + dlng]];

  if (dist1 === null || dist2 === null) {
    log('⚠️ 探针未回传 distance，无法三边定位');
    return [false, null];
  }

  const sols = solveTwoPoints(lat0 + dlat, lng0, lat0, lng0 + dlng, dist1, dist2);
  if (!sols) {
    log('⚠️ 两圆不相交，定位失败');
    return [false, null];
  }

  for (const [plat, plng] of sols) {
    log(`🧮 候选教师坐标 (${plat.toFixed(6)}, ${plng.toFixed(6)})`);
    const [s3] = await radarPut(cookie, rollcallId, plat, plng, deviceId);
    if (s3 === 200) return [true, [plat, plng]];
  }
  return [false, null];
}

export async function sendRadar(
  cookie: string,
  rollcallId: string,
  log: (msg: string) => void
): Promise<RadarResult> {
  log(`🛰 开始雷达签到 rollcall_id=${rollcallId}`);
  const deviceId = uuid();
  const [center, hitDist] = await radarLockCampus(cookie, rollcallId, deviceId, log);
  if (!center) {
    log('❌ 四校区探针均未回传距离，雷达签到失败');
    return { success: false };
  }
  if (hitDist === 0) {
    log(`✅ 雷达签到成功（校区中心直接命中：${center.name}）`);
    return { success: true, campus: center.name, position: [center.lat, center.lng] };
  }
  log(`📍 锁定校区：${center.name}`);
  const [ok, pos] = await radarTriangulate(cookie, rollcallId, center, deviceId, log);
  if (ok && pos) {
    log(`✅ 雷达签到成功，教师位置≈(${pos[0].toFixed(6)}, ${pos[1].toFixed(6)})`);
  } else {
    log('❌ 校区内精确定位失败');
  }
  return { success: ok, campus: center.name, position: pos ?? undefined };
}

// ---------------------------------------------------------------------------
// Type detection
// ---------------------------------------------------------------------------

export function isRadarType(record: RollcallRecord): boolean {
  return (
    Boolean(record.is_radar) ||
    Boolean(record.isRadar) ||
    ((record.rollcall_type || record.type || record.kind || '').toLowerCase().includes('radar'))
  );
}

// ---------------------------------------------------------------------------
// Unified rollcall state machine (parity with desktop _show_code fetch())
// ---------------------------------------------------------------------------

export type RollcallOutcome =
  | { type: 'none' }
  | { type: 'radar_active'; rid: string; time: string }
  | { type: 'radar_past'; time: string }
  | { type: 'digital'; code: string; status: string | null; endTime: string | null; signed: boolean; time: string; rid: string }
  | { type: 'other'; time: string };

export async function fetchRollcallOutcome(
  courseId: number,
  cookie: string,
  studentId: number
): Promise<RollcallOutcome | null> {
  const latest = await getLatestRollcall(courseId, cookie, studentId);
  if (!latest) return null;
  const rid = String(latest.id ?? latest.rollcall_id ?? '');
  const time = fmtTime(latest.rollcall_time || latest.created_at);
  const radar = isRadarType(latest);
  if (radar) {
    const active = await findActiveRadarRecord(cookie, rid);
    if (active !== null || String(latest.status ?? '') === 'active') {
      return { type: 'radar_active', rid, time };
    }
    return { type: 'radar_past', time };
  }
  const { code, status, endTime, signed } = await getNumberCode(rid, cookie);
  if (code || signed) {
    const evidence = status ?? latest.status ?? null;
    return {
      type: 'digital',
      code: code ?? '',
      status: evidence,
      endTime,
      signed,
      time,
      rid,
    };
  }
  const active = await findActiveRadarRecord(cookie, rid);
  if (
    active !== null &&
    (
      active.is_radar ||
      active.isRadar ||
      String(active.rollcall_type ?? active.type ?? '').toLowerCase().includes('radar') ||
      (!active.is_number && !active.is_qrcode && !active.is_qr)
    )
  ) {
    return { type: 'radar_active', rid, time };
  }
  return { type: 'other', time };
}
