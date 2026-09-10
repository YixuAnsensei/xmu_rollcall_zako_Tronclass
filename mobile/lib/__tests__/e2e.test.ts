import { test, expect, beforeAll, afterAll, beforeEach, describe } from 'bun:test';
import {
  getSemesterInfo,
  getCourses,
  fetchRollcallOutcome,
  submitNumberCode,
  sendRadar,
  fmtTime,
  markSigned,
  isMarkedSigned,
} from '../api';
import { looksLikeSessionCookie } from '../auth';

const EARTH_R = 6371000.0;

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlam = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
  return 2 * EARTH_R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

interface Scenario {
  semesterAlive: boolean;
  gatewayDown: boolean;
  rejectAnswerPut: boolean;
  semester: { sem: string; year: string };
  courses: any[];
  rollcallsByCourse: Record<number, any[]>;
  numberRollcalls: Record<string, any>;
  radarActive: any[];
  radarTeacher: Record<string, { lat: number; lng: number; radius: number }>;
}

let sc: Scenario;
const submissions: { rid: string; body: any }[] = [];
const probes: { rid: string; payload: any; hit: boolean }[] = [];
const courseRequests: { body: any; cookie: string | null }[] = [];

function freshScenario(): Scenario {
  return {
    semesterAlive: true,
    gatewayDown: false,
    rejectAnswerPut: false,
    semester: { sem: '31', year: '13' },
    courses: [],
    rollcallsByCourse: {},
    numberRollcalls: {},
    radarActive: [],
    radarTeacher: {},
  };
}

const realFetch = globalThis.fetch;
let server: any;
let base = '';

beforeAll(() => {
  server = Bun.serve({
    port: 0,
    hostname: '127.0.0.1',
    async fetch(req) {
      const url = new URL(req.url);
      const p = url.pathname;
      const cookie = req.headers.get('cookie');
      if (sc.gatewayDown) {
        return new Response('bad gateway', { status: 502 });
      }
      if (p === '/api/profile') {
        return Response.json({ id: 2025001, name: '测试同学' });
      }
      if (p === '/api/current-semester-info') {
        if (!sc.semesterAlive) return new Response('server error', { status: 500 });
        return Response.json({
          semester: { id: sc.semester.sem },
          academic_year: { id: sc.semester.year },
        });
      }
      if (p === '/api/my-courses' && req.method === 'POST') {
        const body = await req.json();
        courseRequests.push({ body, cookie });
        return Response.json({ courses: sc.courses });
      }
      let m = p.match(/^\/api\/course\/(\d+)\/student\/(\d+)\/rollcalls$/);
      if (m) {
        return Response.json({ rollcalls: sc.rollcallsByCourse[Number(m[1])] ?? [] });
      }
      if (p === '/api/radar/rollcalls') {
        return Response.json({ rollcalls: sc.radarActive });
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/student_rollcalls$/);
      if (m) {
        return Response.json(sc.numberRollcalls[m[1]] ?? {});
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/answer_number_rollcall$/);
      if (m && req.method === 'PUT') {
        const body = await req.json();
        submissions.push({ rid: m[1], body });
        const meta = sc.numberRollcalls[m[1]];
        if (meta && meta.status === 'finished') {
          return Response.json({ message: 'finished' }, { status: 400 });
        }
        return Response.json({ status: 'success' });
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/answer$/);
      if (m && req.method === 'PUT') {
        const body = await req.json();
        if (sc.rejectAnswerPut) {
          probes.push({ rid: m[1], payload: body, hit: false });
          return Response.json({ message: 'forbidden' }, { status: 403 });
        }
        const t = sc.radarTeacher[m[1]];
        if (!t) return Response.json({ message: 'no such radar' }, { status: 404 });
        const dist = haversineM(body.latitude, body.longitude, t.lat, t.lng);
        const hit = dist <= t.radius;
        probes.push({ rid: m[1], payload: body, hit });
        if (hit) return Response.json({ status: 'success', distance: dist });
        return Response.json({ message: 'out of range', distance: dist }, { status: 400 });
      }
      return new Response('not found', { status: 404 });
    },
  });
  base = `http://127.0.0.1:${server.port}`;
  globalThis.fetch = (async (input: any, init: any) => {
    const raw =
      typeof input === 'string' ? input : input && input.url ? String(input.url) : String(input);
    if (raw.includes('lnt.xmu.edu.cn')) {
      return realFetch(raw.replace('https://lnt.xmu.edu.cn', base), init);
    }
    return realFetch(input, init);
  }) as any;
});

afterAll(() => {
  globalThis.fetch = realFetch;
  server.stop(true);
});

beforeEach(() => {
  submissions.length = 0;
  probes.length = 0;
  courseRequests.length = 0;
});

const CAMPUS_CENTERS: [string, number, number][] = [
  ['翔安校区', 24.606, 118.31],
  ['思明校区', 24.4383, 118.0932],
  ['马来西亚校区', 2.8327, 101.7028],
  ['漳州校区', 24.34, 117.93],
];

describe('e2e: semester and courses', () => {
  test('dynamic semester flows into course query with cookie', async () => {
    sc = freshScenario();
    sc.semester = { sem: '31', year: '13' };
    sc.courses = [{ id: 1, name: '高等数学', display_name: '高等数学(上)' }];
    const sem = await getSemesterInfo('sessionid=abc');
    expect(sem).toEqual({ semester_id: '31', academic_year_id: '13' });
    const list = await getCourses('sessionid=abc', sem.semester_id, sem.academic_year_id);
    expect(courseRequests).toHaveLength(1);
    expect(courseRequests[0].cookie).toBe('sessionid=abc');
    expect(courseRequests[0].body.conditions.semester_id).toEqual(['31']);
    expect(courseRequests[0].body.conditions.academic_year_id).toEqual(['13']);
    expect(courseRequests[0].body.conditions.classify_type).toBe('recently_started');
    expect(courseRequests[0].body.page_size).toBe(30);
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(1);
  });

  test('semester endpoint down falls back to builtin 29/12', async () => {
    sc = freshScenario();
    sc.semesterAlive = false;
    const sem = await getSemesterInfo('sessionid=abc');
    expect(sem).toEqual({ semester_id: '29', academic_year_id: '12' });
  });
});

describe('e2e: number sign-in scenarios', () => {
  test('active digital: outcome shows code and submission lands on server', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [
      { id: 101, rollcall_type: 'number', status: 'active', rollcall_time: '2026-09-09T02:00:00Z' },
    ];
    sc.numberRollcalls['101'] = {
      number_code: '6688',
      status: 'active',
      end_time: '2026-09-09T02:10:00Z',
    };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('digital');
    if (outcome?.type !== 'digital') return;
    expect(outcome.code).toBe('6688');
    expect(outcome.status).toBe('active');
    expect(outcome.rid).toBe('101');
    expect(outcome.time).not.toBe('2026-09-09T02:00:00Z');
    const res = await submitNumberCode('ck', '101', () => {});
    expect(res.ok).toBe(true);
    expect(res.code).toBe('6688');
    expect(submissions).toHaveLength(1);
    expect(submissions[0].body.numberCode).toBe('6688');
    expect(typeof submissions[0].body.deviceId).toBe('string');
    expect(submissions[0].body.deviceId.length).toBeGreaterThan(10);
  });

  test('finished digital: short-circuit, nothing reaches server', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 102, rollcall_type: 'number', status: 'finished' }];
    sc.numberRollcalls['102'] = {
      number_code: '1111',
      status: 'finished',
      end_time: '2026-09-09T02:10:00Z',
    };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('digital');
    const res = await submitNumberCode('ck', '102', () => {});
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('finished');
    expect(submissions).toHaveLength(0);
  });

  test('qrcode rollcall without code lands on other with no rid', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 303, is_qrcode: true, status: 'active' }];
    sc.numberRollcalls['303'] = { number_code: null, status: 'active' };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome).toEqual({ type: 'other', time: expect.any(String) });
  });

  test('course with no records returns null', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[9] = [];
    const outcome = await fetchRollcallOutcome(9, 'ck', 2025001);
    expect(outcome).toBeNull();
  });
});

describe('e2e: radar sign-in scenarios', () => {
  test('active radar: triangulation hits teacher with consistent deviceId', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 202, is_radar: true, status: 'active' }];
    sc.radarActive = [{ rollcall_id: 202, is_radar: true, status: 'active' }];
    sc.radarTeacher['202'] = { lat: 24.441, lng: 118.095, radius: 50 };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('radar_active');
    if (outcome?.type !== 'radar_active') return;
    const res = await sendRadar('ck', outcome.rid, () => {});
    expect(res.success).toBe(true);
    expect(res.campus).toBe('思明校区');
    expect(probes.length).toBeGreaterThanOrEqual(7);
    const ids = new Set(probes.map((p) => p.payload.deviceId));
    expect(ids.size).toBe(1);
    const first = probes[0].payload;
    expect(first.accuracy).toBe(35);
    expect(first.altitude).toBe(0);
    expect(first.altitudeAccuracy).toBeNull();
    expect(first.heading).toBeNull();
    expect(first.speed).toBeNull();
    const centers = CAMPUS_CENTERS.map(([, lat, lng]) => `${lat},${lng}`);
    const firstFour = probes.slice(0, 4).map((p) => `${p.payload.latitude},${p.payload.longitude}`);
    expect([...firstFour].sort()).toEqual([...centers].sort());
    expect(probes[4].payload.latitude).toBeCloseTo(24.4423, 6);
    expect(probes[4].payload.longitude).toBeCloseTo(118.0932, 6);
    expect(probes[5].payload.latitude).toBeCloseTo(24.4383, 6);
    expect(probes[5].payload.longitude).toBeCloseTo(118.0972, 6);
    const last = probes[probes.length - 1];
    expect(last.hit).toBe(true);
    if (res.position) {
      expect(haversineM(res.position[0], res.position[1], 24.441, 118.095)).toBeLessThan(50);
    } else {
      throw new Error('position missing');
    }
  });

  test('direct hit: teacher exactly at campus center, single probe', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 205, is_radar: true, status: 'active' }];
    sc.radarActive = [{ rollcall_id: 205, is_radar: true }];
    sc.radarTeacher['205'] = { lat: 24.606, lng: 118.31, radius: 50 };
    const res = await sendRadar('ck', '205', () => {});
    expect(res.success).toBe(true);
    expect(res.campus).toBe('翔安校区');
    expect(probes).toHaveLength(1);
    expect(res.position).toEqual([24.606, 118.31]);
  });

  test('finished radar: radar_past without actionable rid', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 203, is_radar: true, status: 'finished' }];
    sc.radarActive = [];
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome).toEqual({ type: 'radar_past', time: expect.any(String) });
    expect(probes).toHaveLength(0);
  });

  test('unclassified active record falls back to radar_active', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 207, status: 'active' }];
    sc.numberRollcalls['207'] = { number_code: null, status: null };
    sc.radarActive = [{ rollcall_id: 207 }];
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('radar_active');
  });

  test('unreachable teacher fails cleanly with locked campus', async () => {
    sc = freshScenario();
    sc.radarTeacher['206'] = { lat: 24.441, lng: 118.095, radius: 0.001 };
    const res = await sendRadar('ck', '206', () => {});
    expect(res.success).toBe(false);
    expect(res.campus).toBe('思明校区');
  });

  test('teacher probe rejected with 403 -> radar fails, no crash', async () => {
    sc = freshScenario();
    sc.rejectAnswerPut = true;
    sc.radarTeacher['208'] = { lat: 24.441, lng: 118.095, radius: 50 };
    const res = await sendRadar('ck', '208', () => {});
    expect(res.success).toBe(false);
    expect(probes).toHaveLength(4);
    const ids = new Set(probes.map((p) => p.payload.deviceId));
    expect(ids.size).toBe(1);
  });
});

describe('e2e: network degradation (desktop-parity fallbacks)', () => {
  test('gateway 502: latest rollcall degrades to null (desktop try/except)', async () => {
    sc = freshScenario();
    sc.gatewayDown = true;
    sc.rollcallsByCourse[1] = [{ id: 301, rollcall_type: 'number', status: 'active' }];
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome).toBeNull();
    expect(probes).toHaveLength(0);
    const res = await sendRadar('ck', '301', () => {});
    expect(res.success).toBe(false);
  });

  test('gateway 502: courses query surfaces error to screen for retry', async () => {
    sc = freshScenario();
    sc.gatewayDown = true;
    await expect(getCourses('ck', '31', '13')).rejects.toThrow();
    const sem = await getSemesterInfo('ck');
    expect(sem).toEqual({ semester_id: '29', academic_year_id: '12' });
  });

  test('gateway 502: number submission returns no_code, no crash', async () => {
    sc = freshScenario();
    sc.gatewayDown = true;
    const res = await submitNumberCode('ck', '310', () => {});
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('no_code');
  });
});

describe('e2e: desktop-parity field aliases and time', () => {
  test('kind field recognized as radar alias', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 401, kind: 'Radar', status: 'active' }];
    sc.radarActive = [{ rollcall_id: 401, kind: 'radar' }];
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('radar_active');
  });

  test('time formatted as fixed UTC+8 regardless of device timezone', async () => {
    expect(fmtTime('2026-09-09T02:05:00Z')).toBe('2026-09-09 10:05');
    expect(fmtTime('2026-01-01T16:30:00Z')).toBe('2026-01-02 00:30');
    expect(fmtTime(undefined)).toBe('未知');
    expect(fmtTime('garbage')).toBe('garbage');
  });
});

describe('e2e: classroom scenario regressions (2026-09-10 field test)', () => {
  test('student_rollcalls omits status -> falls back to record status, NOT finished', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 501, rollcall_type: 'number', status: 'active' }];
    sc.numberRollcalls['501'] = { number_code: '7744', end_time: '2026-09-10T01:50:00Z' };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('digital');
    if (outcome?.type !== 'digital') return;
    expect(outcome.status).toBe('active');
    expect(outcome.endTime).toBe('2026-09-10T01:50:00Z');
    const res = await submitNumberCode('ck', '501', () => {});
    expect(res.ok).toBe(true);
    expect(submissions).toHaveLength(1);
  });

  test('record and student_rollcalls both omit status -> badge evidence is null, never finished', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 502, rollcall_type: 'number' }];
    sc.numberRollcalls['502'] = { number_code: '3355' };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('digital');
    if (outcome?.type !== 'digital') return;
    expect(outcome.status).toBeNull();
    const res = await submitNumberCode('ck', '502', () => {});
    expect(res.ok).toBe(true);
  });

  test('explicit finished still short-circuits', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 503, rollcall_type: 'number' }];
    sc.numberRollcalls['503'] = { number_code: '1100', status: 'finished' };
    const res = await submitNumberCode('ck', '503', () => {});
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('finished');
    expect(submissions).toHaveLength(0);
  });

  test('already-signed student (no fresh code) still shows digital with signed flag', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 504, rollcall_type: 'number', status: 'active' }];
    sc.numberRollcalls['504'] = { number_code: null, status: 'active', signed: true };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    expect(outcome?.type).toBe('digital');
    if (outcome?.type !== 'digital') return;
    expect(outcome.signed).toBe(true);
    expect(outcome.status).toBe('active');
  });

  test('server marks signed after submission, outcome reflects it on re-query', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 505, rollcall_type: 'number', status: 'active' }];
    sc.numberRollcalls['505'] = { number_code: '8899', status: 'active' };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);
    const res = await submitNumberCode('ck', '505', () => {});
    expect(res.ok).toBe(true);
    sc.numberRollcalls['505'] = { number_code: null, status: 'active', signed: true };
    const requery = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (requery?.type !== 'digital') throw new Error('expected digital');
    expect(requery.signed).toBe(true);
  });

  test('local signed marker: PUT 200 sticks even when server never reports signed', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 510, rollcall_type: 'number', status: 'active' }];
    sc.numberRollcalls['510'] = { number_code: '4242', status: 'active' };
    const before = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (before?.type !== 'digital') throw new Error('expected digital');
    expect(before.signed).toBe(false);
    const res = await submitNumberCode('ck', '510', () => {});
    expect(res.ok).toBe(true);
    expect(isMarkedSigned('510')).toBe(true);
    sc.numberRollcalls['510'] = { number_code: '4242', status: 'active' };
    const after = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (after?.type !== 'digital') throw new Error('expected digital');
    expect(after.signed).toBe(true);
  });

  test('local signed marker flows to radar_active outcome', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 511, is_radar: true, status: 'active' }];
    sc.radarActive = [{ rollcall_id: 511, is_radar: true }];
    sc.radarTeacher['511'] = { lat: 24.606, lng: 118.31, radius: 50 };
    const before = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (before?.type !== 'radar_active') throw new Error('expected radar_active');
    expect(before.signed).toBeFalsy();
    const res = await sendRadar('ck', '511', () => {});
    expect(res.success).toBe(true);
    const after = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (after?.type !== 'radar_active') throw new Error('expected radar_active');
    expect(after.signed).toBe(true);
  });

  test('explicitly-unsigned markSigned survives reload', async () => {
    markSigned('511');
    expect(isMarkedSigned('511')).toBe(true);
  });

  test('explicitly-unsigned field values NEVER read as signed (button must stay)', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 506, rollcall_type: 'number', status: 'active' }];
    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', signed: false };
    let outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);

    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', answered: false };
    outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);

    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', result: false };
    outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);

    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', is_answered: 0 };
    outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);

    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', answered: 'no' };
    outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);

    sc.numberRollcalls['506'] = { number_code: '6626', status: 'active', result: '' };
    outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(false);
  });

  test('signed true-value variants across alias family are recognized', async () => {
    sc = freshScenario();
    sc.rollcallsByCourse[1] = [{ id: 507, rollcall_type: 'number', status: 'active' }];
    for (const v of [true, 1, 'true', 'yes', 'ok']) {
      sc.numberRollcalls['507'] = { number_code: null, status: 'active', is_signed: v };
      const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
      if (outcome?.type !== 'digital') throw new Error('expected digital');
      expect(outcome.signed).toBe(true);
    }
    sc.numberRollcalls['507'] = { number_code: null, status: 'active', is_answered: 'success' };
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'digital') throw new Error('expected digital');
    expect(outcome.signed).toBe(true);
  });
});

describe('cookie session heuristic', () => {
  test('csrf-only cookie is NOT a session (field-test false positive)', () => {
    expect(looksLikeSessionCookie('csrftoken=AbCdEf123; HWWAFSESID=xyz')).toBe(false);
  });
  test('real session cookies are recognized', () => {
    expect(looksLikeSessionCookie('sessionid=abc123; csrftoken=x')).toBe(true);
    expect(looksLikeSessionCookie('tronclass_session=zzz')).toBe(true);
    expect(looksLikeSessionCookie('')).toBe(false);
  });
});
