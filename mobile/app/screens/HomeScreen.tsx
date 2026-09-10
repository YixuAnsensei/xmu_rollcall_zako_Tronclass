import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  StatusBar,
  BackHandler,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { isLoggedIn, getAuth } from '../../lib/auth';

export default function HomeScreen() {
  const router = useRouter();
  const [authState, setAuthState] = useState<{ cookie: string | null; studentId: number | null; userName: string }>({
    cookie: null,
    studentId: null,
    userName: '',
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthState(getAuth());
    setLoading(false);
  }, []);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (isLoggedIn()) {
        router.push('/screens/LoginScreen');
        return true;
      }
      return false;
    });
    return () => sub.remove();
  }, [router]);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" />
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF6B9D" />
          <Text style={styles.loadingText}>初始化中...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const loggedIn = isLoggedIn();

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />

      <View style={styles.topBar}>
        <Text style={styles.logoText}>🐾 Zako 签到助手</Text>
        {loggedIn && (
          <TouchableOpacity onPress={() => router.push('/screens/CoursesScreen')} activeOpacity={0.7}>
            <Text style={styles.courseBtn}>查看课程</Text>
          </TouchableOpacity>
        )}
      </View>

      <View style={styles.main}>
        <Text style={styles.title}>zako 签到助手</Text>
        <Text style={styles.subtitle}>点击猫爪，开始喵~</Text>

        <TouchableOpacity
          style={[styles.pawButton, loggedIn ? styles.pawLoggedIn : styles.pawLogin]}
          onPress={() =>
            loggedIn
              ? router.push('/screens/CoursesScreen')
              : router.push('/screens/LoginScreen')
          }
          activeOpacity={0.85}
        >
          <Text style={styles.pawIcon}>🐾</Text>
          <Text style={styles.pawText}>{loggedIn ? '查看课程' : '登录账号'}</Text>
        </TouchableOpacity>

        {loggedIn && (
          <View style={styles.infoCard}>
            <Text style={styles.infoLabel}>当前用户</Text>
            <Text style={styles.infoValue}>{authState.userName || authState.studentId || '未登录'}</Text>
            <Text style={styles.infoHint}>每次打开需重新登录，Cookie 仅在会话期间有效</Text>
          </View>
        )}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>厦大 CAS 畅课签到码查询工具 ❤</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F0E17',
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 14,
  },
  logoText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FF6B9D',
  },
  courseBtn: {
    fontSize: 14,
    color: '#06D6A0',
  },
  main: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#FF6B9D',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#A7A9BE',
    marginBottom: 52,
  },
  pawButton: {
    width: 170,
    height: 170,
    borderRadius: 85,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 32,
  },
  pawLogin: {
    backgroundColor: '#1A1828',
    borderWidth: 3,
    borderColor: '#FF6B9D',
    shadowColor: '#FF6B9D',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  pawLoggedIn: {
    backgroundColor: '#1A1828',
    borderWidth: 3,
    borderColor: '#06D6A0',
    shadowColor: '#06D6A0',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 8,
  },
  pawIcon: {
    fontSize: 72,
  },
  pawText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FFFFFE',
    marginTop: 8,
  },
  infoCard: {
    backgroundColor: '#1A1828',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginBottom: 32,
    borderWidth: 1,
    borderColor: '#221F33',
  },
  infoLabel: {
    fontSize: 12,
    color: '#A7A9BE',
    marginBottom: 4,
  },
  infoValue: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFFFFE',
    fontFamily: 'monospace',
  },
  infoHint: {
    fontSize: 12,
    color: '#A7A9BE',
    marginTop: 8,
  },
  footer: {
    paddingBottom: 32,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 12,
    color: '#A7A9BE',
    opacity: 0.7,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    color: '#A7A9BE',
    fontSize: 14,
  },
});
