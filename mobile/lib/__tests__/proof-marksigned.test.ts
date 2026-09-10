import { test, expect, beforeAll, afterAll, describe } from 'bun:test';
import {
  submitNumberCode,
  sendRadar,
  fetchRollcallOutcome,
  getNumberCode,
  isMarkedSigned,
} from '../api';

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

let server: any;
let base = '';
const realFetch = globalThis.fetch;

const state: {
  rollcallsByCourse: Record<number, any[]>;
  numberRollcalls: Record<string, any>;
  radarActive: any[];
  radarTeacher: Record<string, { lat: number; lng: number; radius: number }>;
  numberPuts: number;
  radarPuts: number;
} = {
  rollcallsByCourse: {},
  numberRollcalls: {},
  radarActive: [],
  radarTeacher: {},
  numberPuts: 0,
  radarPuts: 0,
};

beforeAll(() => {
  server = Bun.serve({
    port: 0,
    hostname: '127.0.0.1',
    async fetch(req) {
      const url = new URL(req.url);
      const p = url.pathname;
      let m = p.match(/^\/api\/course\/(\d+)\/student\/(\d+)\/rollcalls$/);
      if (m) {
        return Response.json({ rollcalls: state.rollcallsByCourse[Number(m[1])] ?? [] });
      }
      if (p === '/api/radar/rollcalls') {
        return Response.json({ rollcalls: state.radarActive });
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/student_rollcalls$/);
      if (m) {
        return Response.json(state.numberRollcalls[m[1]] ?? {});
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/answer_number_rollcall$/);
      if (m && req.method === 'PUT') {
        state.numberPuts += 1;
        return Response.json({ status: 'success' });
      }
      m = p.match(/^\/api\/rollcall\/(\d+)\/answer$/);
      if (m && req.method === 'PUT') {
        state.radarPuts += 1;
        const t = state.radarTeacher[m[1]];
        if (!t) return Response.json({ message: 'no radar' }, { status: 404 });
        const body = await req.json();
        const dist = haversineM(body.latitude, body.longitude, t.lat, t.lng);
        if (dist <= t.radius) return Response.json({ status: 'success', distance: dist });
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

describe('PROOF: markSigned wiring is live (API-layer, end-to-end)', () => {
  test('digital: submitNumberCode PUT-200 flips local marker; re-fetch outcome carries signed=true; UI button condition goes false', async () => {
    state.rollcallsByCourse[1] = [
      { id: 900, rollcall_type: 'number', status: 'active', rollcall_time: '2026-09-10T02:00:00Z' },
    ];
    state.numberRollcalls['900'] = { number_code: '6688', status: 'active' };

    const before = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (before?.type !== 'digital') throw new Error('expected digital before submit');
    expect(before.signed).toBe(false);
    expect(isMarkedSigned('900')).toBe(false);

    const detailBefore = await getNumberCode('900', 'ck');
    expect(detailBefore.signed).toBe(false);

    const res = await submitNumberCode('ck', '900', () => {});
    expect(res.ok).toBe(true);
    expect(state.numberPuts).toBe(1);

    expect(isMarkedSigned('900')).toBe(true);

    state.numberRollcalls['900'] = { number_code: '6688', status: 'active' };

    const after = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (after?.type !== 'digital') throw new Error('expected digital after submit');
    expect(after.signed).toBe(true);
    expect(after.rid).toBe('900');
    expect(after.code).toBe('6688');

    const isFinished = after.status === 'finished';
    const isSigned = after.signed;
    expect(isFinished).toBe(false);
    expect(isSigned).toBe(true);
    expect(!isFinished && !isSigned).toBe(false);
  });

  test('radar: sendRadar success flips marker; radar_active outcome carries signed=true; does NOT fall to radar_past while teacher still broadcasting', async () => {
    state.rollcallsByCourse[1] = [{ id: 901, is_radar: true, status: 'active' }];
    state.radarActive = [{ rollcall_id: 901, is_radar: true, status: 'active' }];
    state.radarTeacher['901'] = { lat: 24.4383, lng: 118.0932, radius: 50 };

    const before = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (before?.type !== 'radar_active') throw new Error('expected radar_active before');
    expect(before.signed ?? false).toBe(false);

    const res = await sendRadar('ck', '901', () => {});
    expect(res.success).toBe(true);
    expect(res.campus).toBe('思明校区');
    expect(isMarkedSigned('901')).toBe(true);

    const after = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (after?.type !== 'radar_active') {
      throw new Error(`expected radar_active after radar sign, got ${after?.type}`);
    }
    expect(after.signed).toBe(true);
  });

  test('radar signed marker survives teacher ending the rollcall (radar_past still shows, marker persists)', async () => {
    state.radarActive = [];
    state.rollcallsByCourse[1] = [{ id: 901, is_radar: true, status: 'finished' }];
    const outcome = await fetchRollcallOutcome(1, 'ck', 2025001);
    if (outcome?.type !== 'radar_past') {
      throw new Error(`expected radar_past after teacher ended, got ${outcome?.type}`);
    }
    expect(isMarkedSigned('901')).toBe(true);
  });

  test('HTTP failure does NOT flip marker (no false success)', async () => {
    state.rollcallsByCourse[1] = [
      { id: 902, rollcall_type: 'number', status: 'active' },
    ];
    state.numberRollcalls['902'] = { number_code: '1111', status: 'active' };
    const throws = () => {
      state.numberRollcalls['902'] = { number_code: null, status: 'active' };
    };
    throws();
    const res = await submitNumberCode('ck', '902', () => {});
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('no_code');
    expect(isMarkedSigned('902')).toBe(false);
  });
});
