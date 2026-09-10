import { test, expect, describe } from 'bun:test';
import {
  __setRadarPutForTest,
  sendRadar,
  submitNumberCode,
  isRadarType,
  fmtTime,
  type RollcallRecord,
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

const CAMPUSES: [string, number, number][] = [
  ['翔安校区', 24.606, 118.31],
  ['思明校区', 24.4383, 118.0932],
  ['马来西亚校区', 2.8327, 101.7028],
  ['漳州校区', 24.34, 117.93],
];

function mockServer(tLat: number, tLng: number, radius = 50) {
  return async (
    _c: string,
    _r: string,
    lat: number,
    lng: number
  ): Promise<[number, any]> => {
    const dist = haversineM(lat, lng, tLat, tLng);
    if (dist <= radius) return [200, { status: 'success', distance: dist }];
    return [400, { distance: dist, message: 'out of range' }];
  };
}

describe('radar two-phase triangulation', () => {
  test('locates teacher in each campus within 50m', async () => {
    const spots: [string, number, number][] = [
      ['思明校区', 24.441, 118.095],
      ['翔安校区', 24.608, 118.312],
      ['漳州校区', 24.342, 117.933],
      ['马来西亚校区', 2.834, 101.704],
    ];
    for (const [campus, tLat, tLng] of spots) {
      __setRadarPutForTest(mockServer(tLat, tLng));
      const res = await sendRadar('c', '1', () => {});
      expect(res.success).toBe(true);
      expect(res.campus).toBe(campus);
      const [pLat, pLng] = res.position!;
      expect(haversineM(pLat, pLng, tLat, tLng)).toBeLessThan(50);
    }
    __setRadarPutForTest(null);
  });

  test('direct hit at campus center', async () => {
    const [, cLat, cLng] = CAMPUSES[0];
    __setRadarPutForTest(mockServer(cLat, cLng));
    const res = await sendRadar('c', '5', () => {});
    expect(res.success).toBe(true);
    expect(res.position).toEqual([cLat, cLng]);
    __setRadarPutForTest(null);
  });

  test('no distance data -> failure, campus null', async () => {
    __setRadarPutForTest(async () => [400, { message: 'fail' }]);
    const res = await sendRadar('c', '6', () => {});
    expect(res.success).toBe(false);
    expect(res.campus).toBeUndefined();
    __setRadarPutForTest(null);
  });

  test('network timeout (status 0) -> failure', async () => {
    __setRadarPutForTest(async () => [0, { error: 'timeout' }]);
    const res = await sendRadar('c', '7', () => {});
    expect(res.success).toBe(false);
    __setRadarPutForTest(null);
  });

  test('circles do not intersect -> locked campus but no fix', async () => {
    let n = 0;
    __setRadarPutForTest(async (_c, _r, lat, lng) => {
      n++;
      if (n <= 4) return n === 1 ? [400, { distance: 100 }] : [400, { distance: 50000 }];
      return [400, { distance: 10 }];
    });
    const res = await sendRadar('c', '8', () => {});
    expect(res.success).toBe(false);
    expect(res.campus).toBe('翔安校区');
    __setRadarPutForTest(null);
  });
});

describe('type detection parity', () => {
  test('isRadarType across field spellings', () => {
    const t = (r: Partial<RollcallRecord>) => isRadarType(r as RollcallRecord);
    expect(t({ is_radar: true })).toBe(true);
    expect(t({ isRadar: true })).toBe(true);
    expect(t({ rollcall_type: 'Radar' })).toBe(true);
    expect(t({ type: 'radar_position' })).toBe(true);
    expect(t({ type: 'number' })).toBe(false);
    expect(t({ is_qrcode: true })).toBe(false);
  });
});

describe('unified state-machine predicates', () => {
  const decideRadar = (active: any, latestStatus: string) =>
    active !== null || latestStatus === 'active' ? 'radar_active' : 'radar_past';

  test('finished radar not in active list -> radar_past', () => {
    expect(decideRadar(null, 'finished')).toBe('radar_past');
  });
  test('radar still in active list -> radar_active', () => {
    expect(decideRadar({ id: 1, is_radar: true }, '')).toBe('radar_active');
  });
  test('empty list but status active -> radar_active', () => {
    expect(decideRadar(null, 'active')).toBe('radar_active');
  });

  const isRadarFallback = (a: any) =>
    a !== null &&
    (a.is_radar ||
      a.isRadar ||
      String(a.rollcall_type ?? a.type ?? '').toLowerCase().includes('radar') ||
      (!a.is_number && !a.is_qrcode && !a.is_qr));

  test('qrcode-only record must NOT fall back to radar', () => {
    expect(isRadarFallback({ is_qrcode: true, is_number: false })).toBe(false);
    expect(isRadarFallback({ is_qr: true })).toBe(false);
  });
  test('unclassified active record falls back to radar', () => {
    expect(isRadarFallback({ is_number: false, is_qrcode: false, is_qr: false })).toBe(true);
    expect(isRadarFallback({ type: 'radar' })).toBe(true);
  });
});

describe('semester and time parsing', () => {
  test('fmtTime parses ISO Z to zh-CN', () => {
    expect(fmtTime('2026-09-08T10:00:00Z')).not.toBe('2026-09-08T10:00:00Z');
    expect(fmtTime('')).toBe('未知');
  });
});

describe('number sign-in submission (mocked fetch)', () => {
  const orig = globalThis.fetch;
  const jsonResp = (obj: any, status = 200) =>
    ({ ok: status >= 200 && status < 300, status, json: async () => obj } as any);

  const logs: string[] = [];
  const log = (m: string) => logs.push(m);

  test('fetches code then PUTs answer with deviceId+numberCode', async () => {
    const calls: { url: string; method: string; body: any }[] = [];
    globalThis.fetch = (async (url: any, init: any) => {
      const u = String(url);
      if (u.includes('/student_rollcalls')) {
        calls.push({ url: u, method: 'GET', body: null });
        return jsonResp({ number_code: '6688', status: 'active' });
      }
      if (u.includes('/answer_number_rollcall')) {
        calls.push({ url: u, method: init.method, body: JSON.parse(init.body) });
        return jsonResp({}, 200);
      }
      throw new Error('unexpected fetch ' + u);
    }) as any;

    const res = await submitNumberCode('ck', '999', log);
    globalThis.fetch = orig;

    expect(res.ok).toBe(true);
    expect(res.code).toBe('6688');
    expect(calls).toHaveLength(2);
    expect(calls[0].url).toContain('/api/rollcall/999/student_rollcalls');
    expect(calls[1].url).toContain('/api/rollcall/999/answer_number_rollcall');
    expect(calls[1].method).toBe('PUT');
    expect(calls[1].body.numberCode).toBe('6688');
    expect(typeof calls[1].body.deviceId).toBe('string');
    expect(calls[1].body.deviceId.length).toBeGreaterThan(10);
  });

  test('finished rollcall is not submitted', async () => {
    let putCalled = false;
    globalThis.fetch = (async (url: any) => {
      if (String(url).includes('/answer_number_rollcall')) putCalled = true;
      return jsonResp({ number_code: '1111', status: 'finished' });
    }) as any;
    const res = await submitNumberCode('ck', '1', log);
    globalThis.fetch = orig;
    expect(res.ok).toBe(false);
    expect(res.reason).toBe('finished');
    expect(putCalled).toBe(false);
  });

  test('missing code returns no_code without submitting', async () => {
    let putCalled = false;
    globalThis.fetch = (async (url: any) => {
      if (String(url).includes('/answer_number_rollcall')) putCalled = true;
      return jsonResp({ number_code: null, status: 'active' });
    }) as any;
    const res = await submitNumberCode('ck', '2', log);
    globalThis.fetch = orig;
    expect(res.reason).toBe('no_code');
    expect(putCalled).toBe(false);
  });
});
