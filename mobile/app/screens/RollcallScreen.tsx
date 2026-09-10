import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  StatusBar,
  Alert,
  Clipboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { getAuth } from '../../lib/auth';
import {
  fetchRollcallOutcome,
  submitNumberCode,
  sendRadar,
  getProfile,
  fmtTime,
  type RollcallOutcome,
} from '../../lib/api';

type ResultType = RollcallOutcome | { type: 'loading' };

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function RollcallScreen() {
  const router = useRouter();
  const { courseId, courseName } = useLocalSearchParams<{ courseId: string; courseName: string }>();

  const [result, setResult] = useState<ResultType>({ type: 'loading' });
  const [submitting, setSubmitting] = useState(false);
  const [radarRunning, setRadarRunning] = useState(false);
  const [radarLog, setRadarLog] = useState<string[]>([]);

  useEffect(() => {
    fetchRollcall();
  }, [courseId]);

  const fetchRollcall = async () => {
    setResult({ type: 'loading' });
    try {
      const { cookie, studentId } = await getAuth();
      if (!cookie) {
        router.replace('/screens/LoginScreen');
        return;
      }
      const resolvedStudentId = studentId || (await getProfile(cookie)).id;
      const outcome = await fetchRollcallOutcome(
        parseInt(courseId, 10),
        cookie,
        resolvedStudentId
      );
      setResult(outcome ?? { type: 'none' });
    } catch (e) {
      Alert.alert('查询错误', String(e));
      setResult({ type: 'none' });
    }
  };

  const handleCopyCode = () => {
    if (result.type === 'digital') {
      Clipboard.setString(result.code);
      Alert.alert('已复制', `签到码 ${result.code} 已复制到剪贴板`);
    }
  };

  const handleSubmitNumber = async () => {
    if (result.type !== 'digital' || !result.rid || submitting) return;
    setSubmitting(true);
    try {
      const { cookie } = await getAuth();
      if (!cookie) return;
      const log = (msg: string) => console.log(msg);
      const res = await submitNumberCode(cookie, result.rid, log);
      if (res.ok) {
        Alert.alert('🎉 签到成功喵❤', `签到码：${res.code}\n本次签到已完成~`);
        fetchRollcall();
      } else {
        const reason = res.reason;
        const msg =
          reason === 'finished'
            ? '签到已结束，无法提交喵~'
            : reason === 'no_code'
            ? '获取签到码失败，请再查一次喵~'
            : '提交失败，请检查网络喵~';
        Alert.alert('❌ 签到失败', msg);
      }
    } catch (e) {
      Alert.alert('错误', String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRadarSign = async () => {
    if (result.type !== 'radar_active' || !result.rid || radarRunning) return;
    setRadarRunning(true);
    setRadarLog([]);
    try {
      const { cookie } = await getAuth();
      if (!cookie) return;
      const log = (msg: string) => {
        console.log(msg);
        setRadarLog((prev) => [...prev.slice(-30), msg]);
      };
      const res = await sendRadar(cookie, result.rid, log);
      if (res.success) {
        Alert.alert(
          '🎉 雷达签到成功喵❤',
          res.campus ? `校区：${res.campus}\n本次签到已完成~` : '本次签到已完成~'
        );
        fetchRollcall();
      } else {
        Alert.alert('❌ 雷达签到失败', '定位未成功，请重试喵~');
      }
    } catch (e) {
      Alert.alert('错误', String(e));
    } finally {
      setRadarRunning(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />

      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backText}>← 返回</Text>
        </TouchableOpacity>
        <Text style={styles.title} numberOfLines={1}>
          {courseName}
        </Text>
      </View>

      <View style={styles.content}>
        {renderResult(result, {
          onCopy: handleCopyCode,
          onSubmit: handleSubmitNumber,
          onRadar: handleRadarSign,
          submitting,
          radarRunning,
          radarLog,
        })}
      </View>

      <TouchableOpacity style={styles.refreshBtn} onPress={fetchRollcall} activeOpacity={0.8}>
        <Text style={styles.refreshText}>🔄 再查一次</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

function renderResult(
  result: ResultType,
  actions: {
    onCopy: () => void;
    onSubmit: () => void;
    onRadar: () => void;
    submitting: boolean;
    radarRunning: boolean;
    radarLog: string[];
  }
) {
  const { onCopy, onSubmit, onRadar, submitting, radarRunning, radarLog } = actions;

  switch (result.type) {
    case 'loading':
      return (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF6B9D" />
          <Text style={styles.loadingText}>正在查询签到喵~</Text>
        </View>
      );

    case 'none':
      return (
        <View style={styles.card}>
          <Text style={styles.emoji}>😿</Text>
          <Text style={styles.heading}>暂无签到记录</Text>
          <Text style={styles.subtext}>这门课还没有签到喵~</Text>
        </View>
      );

    case 'digital': {
      const isFinished = result.status === 'finished';
      const isSigned = result.signed;
      const badge = isFinished
        ? { text: '🔒 已结束', color: '#A7A9BE' }
        : isSigned
        ? { text: '🎉 已签到', color: '#06D6A0' }
        : { text: '✅ 进行中', color: '#FFD166' };
      if (isSigned && !isFinished) {
        return (
          <View style={[styles.card, styles.signedCard]}>
            <Text style={styles.signedEmoji}>🎉</Text>
            <Text style={styles.signedHeading}>签到成功喵❤</Text>
            <View style={styles.signedBadge}>
              <Text style={styles.signedBadgeText}>✓ 已完成</Text>
            </View>
            {result.code ? (
              <TouchableOpacity onPress={onCopy} activeOpacity={0.8}>
                <Text style={styles.codeText}>{result.code}</Text>
                <Text style={styles.copyHint}>点击签到码可复制</Text>
              </TouchableOpacity>
            ) : null}
            <Text style={styles.timeText}>发起时间：{result.time}</Text>
            {result.endTime && (
              <Text style={styles.timeText}>截止时间：{fmtTime(result.endTime)}</Text>
            )}
            <Text style={styles.signedNote}>本次签到已完成，无需重复提交喵~</Text>
          </View>
        );
      }
      return (
        <View style={styles.card}>
          <Text style={styles.emoji}>🐾</Text>
          <Text style={styles.heading}>签到码</Text>
          <TouchableOpacity onPress={onCopy} activeOpacity={0.8}>
            <Text style={styles.codeText}>{result.code}</Text>
          </TouchableOpacity>
          <View style={styles.statusBadge}>
            <Text style={[styles.statusText, { color: badge.color }]}>{badge.text}</Text>
          </View>
          <Text style={styles.timeText}>发起时间：{result.time}</Text>
          {result.endTime && (
            <Text style={styles.timeText}>截止时间：{fmtTime(result.endTime)}</Text>
          )}
          {!isFinished && !isSigned && (
            <TouchableOpacity
              style={[styles.actionBtn, submitting && styles.actionBtnDisabled]}
              onPress={onSubmit}
              disabled={submitting}
              activeOpacity={0.8}
            >
              {submitting ? (
                <ActivityIndicator size="small" color="#0F0E17" />
              ) : (
                <Text style={styles.actionText}>🐾 一键数字签到</Text>
              )}
            </TouchableOpacity>
          )}
          {isFinished && (
            <Text style={styles.finishedText}>签到已结束，无需提交喵~</Text>
          )}
        </View>
      );
    }

    case 'radar_active':
      if (result.signed) {
        return (
          <View style={[styles.card, styles.signedCard]}>
            <Text style={styles.signedEmoji}>🎉</Text>
            <Text style={styles.signedHeading}>雷达签到成功喵❤</Text>
            <View style={styles.signedBadge}>
              <Text style={styles.signedBadgeText}>✓ 已完成</Text>
            </View>
            <Text style={styles.timeText}>签到时间：{result.time}</Text>
            <Text style={styles.signedNote}>本次签到已完成，无需重复提交喵~</Text>
            {radarLog.length > 0 && (
              <View style={styles.radarLogBox}>
                {radarLog.map((line, i) => (
                  <Text key={i} style={styles.radarLogLine}>
                    {line}
                  </Text>
                ))}
              </View>
            )}
          </View>
        );
      }
      return (
        <View style={styles.card}>
          <Text style={styles.emoji}>📡</Text>
          <Text style={styles.heading}>雷达签到进行中喵❤</Text>
          <Text style={styles.subtext}>教师在实时广播位置，点击按钮自动定位签到</Text>
          <Text style={styles.timeText}>签到时间：{result.time}</Text>
          <TouchableOpacity
            style={[styles.actionBtn, radarRunning && styles.actionBtnDisabled]}
            onPress={onRadar}
            disabled={radarRunning}
            activeOpacity={0.8}
          >
            {radarRunning ? (
              <ActivityIndicator size="small" color="#0F0E17" />
            ) : (
              <Text style={styles.actionText}>🛰 一键雷达签到</Text>
            )}
          </TouchableOpacity>
          {radarLog.length > 0 && (
            <View style={styles.radarLogBox}>
              {radarLog.map((line, i) => (
                <Text key={i} style={styles.radarLogLine}>
                  {line}
                </Text>
              ))}
            </View>
          )}
        </View>
      );

    case 'radar_past':
      return (
        <View style={styles.card}>
          <Text style={styles.emoji}>📡</Text>
          <Text style={styles.heading}>上一次是雷达签到喵❤</Text>
          <Text style={styles.subtext}>当前没有进行中的雷达签到喵~</Text>
          <Text style={styles.timeText}>签到时间：{result.time}</Text>
        </View>
      );

    case 'other':
      return (
        <View style={styles.card}>
          <Text style={styles.emoji}>📍</Text>
          <Text style={styles.heading}>无数字签到码</Text>
          <Text style={styles.subtext}>可能是 GPS / 扫码等其他签到方式喵~</Text>
          <Text style={styles.timeText}>签到时间：{result.time}</Text>
        </View>
      );

    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F0E17',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#221F33',
  },
  backBtn: {
    padding: 8,
    marginRight: 8,
  },
  backText: {
    color: '#A7A9BE',
    fontSize: 14,
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFE',
    flex: 1,
  },
  content: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 24,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    color: '#A7A9BE',
    fontSize: 14,
  },
  card: {
    backgroundColor: '#1A1828',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    flex: 1,
    borderWidth: 1,
    borderColor: '#221F33',
  },
  emoji: {
    fontSize: 52,
    marginBottom: 12,
  },
  heading: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFFFFE',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtext: {
    fontSize: 13,
    color: '#A7A9BE',
    textAlign: 'center',
    marginBottom: 8,
  },
  codeText: {
    fontSize: 52,
    fontWeight: '900',
    color: '#FF6B9D',
    fontFamily: 'monospace',
    letterSpacing: 10,
    paddingVertical: 12,
    textAlign: 'center',
  },
  statusBadge: {
    backgroundColor: '#221F33',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 6,
    marginBottom: 10,
  },
  statusText: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#06D6A0',
  },
  timeText: {
    fontSize: 12,
    color: '#A7A9BE',
    marginBottom: 16,
  },
  finishedText: {
    fontSize: 13,
    color: '#A7A9BE',
    marginBottom: 16,
  },
  actionBtn: {
    backgroundColor: '#FF6B9D',
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 32,
    marginTop: 8,
    minWidth: 200,
    alignItems: 'center',
  },
  actionBtnDisabled: {
    opacity: 0.6,
  },
  actionText: {
    color: '#0F0E17',
    fontSize: 15,
    fontWeight: 'bold',
  },
  refreshBtn: {
    marginHorizontal: 20,
    marginBottom: 24,
    backgroundColor: '#221F33',
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2E2C3F',
  },
  refreshText: {
    color: '#A7A9BE',
    fontSize: 14,
  },
  signedCard: {
    borderColor: '#06D6A0',
    borderWidth: 2,
    backgroundColor: '#12182B',
  },
  signedEmoji: {
    fontSize: 72,
    marginBottom: 8,
  },
  signedHeading: {
    fontSize: 26,
    fontWeight: '900',
    color: '#06D6A0',
    textAlign: 'center',
    marginBottom: 12,
  },
  signedBadge: {
    backgroundColor: '#06D6A0',
    borderRadius: 24,
    paddingHorizontal: 24,
    paddingVertical: 8,
    marginBottom: 16,
  },
  signedBadgeText: {
    color: '#0F0E17',
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 2,
  },
  copyHint: {
    fontSize: 11,
    color: '#A7A9BE',
    textAlign: 'center',
    marginBottom: 8,
  },
  signedNote: {
    fontSize: 13,
    color: '#06D6A0',
    textAlign: 'center',
    marginTop: 4,
    marginBottom: 16,
  },
  radarLogBox: {
    marginTop: 12,
    width: '100%',
    backgroundColor: '#0A0912',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    maxHeight: 180,
  },
  radarLogLine: {
    color: '#A7A9BE',
    fontSize: 11,
    fontFamily: 'monospace',
    lineHeight: 16,
  },
});
