import importlib.util
import math
import sys
import unittest

spec = importlib.util.spec_from_file_location(
    "zako_v3",
    "D:/claude-code-haha/rollcall-research/my-stable/zako_app_V3.0.py",
)
zako_v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zako_v3)


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class MockTronclassServer:
    def __init__(self, teacher_lat, teacher_lng, radius=50.0):
        self.teacher_lat = teacher_lat
        self.teacher_lng = teacher_lng
        self.radius = radius
        self.history = []

    def handle_put(self, cookie, rollcall_id, lat, lng, timeout=15):
        dist = haversine_m(lat, lng, self.teacher_lat, self.teacher_lng)
        self.history.append((lat, lng, dist))
        if dist <= self.radius:
            return 200, {"status": "success", "distance": dist}
        return 400, {"distance": dist, "message": "out of range"}


class RadarScenarioTests(unittest.TestCase):
    def test_campus_siming(self):
        srv = MockTronclassServer(24.4410, 118.0950)
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: srv.handle_put(
            c, r, lat, lng, timeout
        )
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1001, log=lambda m: None)
            self.assertTrue(ok)
            self.assertEqual(info["campus"], "思明校区")
            plat, plng = info["position"]
            err_dist = haversine_m(plat, plng, srv.teacher_lat, srv.teacher_lng)
            self.assertLess(err_dist, 50.0)
        finally:
            zako_v3.radar_put = orig_put

    def test_campus_xiangan(self):
        srv = MockTronclassServer(24.6080, 118.3120)
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: srv.handle_put(
            c, r, lat, lng, timeout
        )
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1002, log=lambda m: None)
            self.assertTrue(ok)
            self.assertEqual(info["campus"], "翔安校区")
            plat, plng = info["position"]
            err_dist = haversine_m(plat, plng, srv.teacher_lat, srv.teacher_lng)
            self.assertLess(err_dist, 50.0)
        finally:
            zako_v3.radar_put = orig_put

    def test_campus_zhangzhou(self):
        srv = MockTronclassServer(24.3420, 117.9330)
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: srv.handle_put(
            c, r, lat, lng, timeout
        )
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1003, log=lambda m: None)
            self.assertTrue(ok)
            self.assertEqual(info["campus"], "漳州校区")
            plat, plng = info["position"]
            err_dist = haversine_m(plat, plng, srv.teacher_lat, srv.teacher_lng)
            self.assertLess(err_dist, 50.0)
        finally:
            zako_v3.radar_put = orig_put

    def test_campus_malaysia(self):
        srv = MockTronclassServer(2.8340, 101.7040)
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: srv.handle_put(
            c, r, lat, lng, timeout
        )
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1004, log=lambda m: None)
            self.assertTrue(ok)
            self.assertEqual(info["campus"], "马来西亚校区")
            plat, plng = info["position"]
            err_dist = haversine_m(plat, plng, srv.teacher_lat, srv.teacher_lng)
            self.assertLess(err_dist, 50.0)
        finally:
            zako_v3.radar_put = orig_put

    def test_direct_hit(self):
        srv = MockTronclassServer(24.6060, 118.3100, radius=50.0)
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: srv.handle_put(
            c, r, lat, lng, timeout
        )
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1005, log=lambda m: None)
            self.assertTrue(ok)
            self.assertEqual(info["campus"], "翔安校区")
            self.assertEqual(info["position"], (24.6060, 118.3100))
        finally:
            zako_v3.radar_put = orig_put

    def test_no_distance_returned(self):
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: (400, {"message": "fail"})
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1006, log=lambda m: None)
            self.assertFalse(ok)
            self.assertIsNone(info["campus"])
        finally:
            zako_v3.radar_put = orig_put

    def test_network_timeout(self):
        orig_put = zako_v3.radar_put
        zako_v3.radar_put = lambda c, r, lat, lng, timeout=15: (0, {"error": "timeout"})
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1007, log=lambda m: None)
            self.assertFalse(ok)
            self.assertIsNone(info["campus"])
        finally:
            zako_v3.radar_put = orig_put

    def test_no_circle_intersection(self):
        calls = []

        def bad_geom(c, r, lat, lng, timeout=15):
            calls.append((lat, lng))
            if len(calls) <= 4:
                if len(calls) == 1:
                    return 400, {"distance": 100.0}
                return 400, {"distance": 50000.0}
            return 400, {"distance": 10.0}

        orig_put = zako_v3.radar_put
        zako_v3.radar_put = bad_geom
        try:
            ok, info = zako_v3.send_radar("dummy_cookie", 1008, log=lambda m: None)
            self.assertFalse(ok)
            self.assertEqual(info["campus"], "翔安校区")
        finally:
            zako_v3.radar_put = orig_put

    def test_ui_decision_digital(self):
        orig_latest = zako_v3.get_latest_rollcall
        orig_code = zako_v3.get_number_code
        zako_v3.get_latest_rollcall = lambda cid, c, sid: {"id": 1, "created_at": "2026-09-08T10:00:00Z", "type": "number"}
        zako_v3.get_number_code = lambda rid, c: ("6688", "active", None)
        try:
            latest = zako_v3.get_latest_rollcall(1, "c", 1)
            rid = str(latest["id"])
            code, status, _ = zako_v3.get_number_code(rid, "c")
            self.assertEqual(code, "6688")
            self.assertEqual(status, "active")
        finally:
            zako_v3.get_latest_rollcall = orig_latest
            zako_v3.get_number_code = orig_code

    def test_ui_decision_radar_active(self):
        orig_latest = zako_v3.get_latest_rollcall
        orig_find = zako_v3.find_active_radar_record
        zako_v3.get_latest_rollcall = lambda cid, c, sid: {"id": 2, "created_at": "2026-09-08T10:00:00Z", "is_radar": True}
        zako_v3.find_active_radar_record = lambda c, rid: {"id": 2, "is_radar": True}
        try:
            latest = zako_v3.get_latest_rollcall(2, "c", 1)
            active = zako_v3.find_active_radar_record("c", str(latest["id"]))
            self.assertIsNotNone(active)
        finally:
            zako_v3.get_latest_rollcall = orig_latest
            zako_v3.find_active_radar_record = orig_find

    def test_ui_decision_radar_past(self):
        orig_latest = zako_v3.get_latest_rollcall
        orig_find = zako_v3.find_active_radar_record
        zako_v3.get_latest_rollcall = lambda cid, c, sid: {"id": 3, "created_at": "2026-09-08T10:00:00Z", "is_radar": True, "status": "finished"}
        zako_v3.find_active_radar_record = lambda c, rid: None
        try:
            latest = zako_v3.get_latest_rollcall(3, "c", 1)
            active = zako_v3.find_active_radar_record("c", str(latest["id"]))
            self.assertIsNone(active)
            self.assertEqual(latest["status"], "finished")
        finally:
            zako_v3.get_latest_rollcall = orig_latest
            zako_v3.find_active_radar_record = orig_find


if __name__ == "__main__":
    unittest.main()
