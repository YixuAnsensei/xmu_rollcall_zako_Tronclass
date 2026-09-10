import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { WebView } from 'react-native-webview';
import XmuCookie from '../../modules/xmu-cookie/src/XmuCookieModule';
import { setAuth, looksLikeSessionCookie } from '../../lib/auth';
import { getProfile } from '../../lib/api';

const BASE_URL = 'https://lnt.xmu.edu.cn';

export default function LoginScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [attempt, setAttempt] = useState(0);
  const [mode, setMode] = useState<'entry' | 'web'>('entry');
  const [status, setStatus] = useState('🐾 请进行登录，登录后将自动获取 Cookie 喵~');
  const [pageLoading, setPageLoading] = useState(false);
  const handlingRef = React.useRef(false);

  const resetSession = () => {
    handlingRef.current = false;
    setAttempt((a) => a + 1);
  };

  useEffect(() => {
    if (mode === 'web') {
      XmuCookie.clearCookiesAsync().catch(() => {});
    }
  }, [mode, attempt]);

  const beginLogin = () => {
    setStatus('正在连接厦大 CAS 系统喵…');
    handlingRef.current = false;
    setAttempt((a) => a + 1);
    setMode('web');
  };

  const abortLogin = () => {
    setMode('entry');
    setStatus('已取消登录');
  };

  const handleLoginSuccess = async (cookie: string) => {
    const profile = await getProfile(cookie);
    setAuth(cookie, profile.id, profile.name);
    router.replace('/screens/HomeScreen');
  };

  const checkUrlAndCookie = async (url?: string) => {
    if (!url || handlingRef.current) return;
    if (url.includes('lnt.xmu.edu.cn') && !url.includes('ids.xmu.edu.cn')) {
      const cookie =
        (await XmuCookie.getCookieForUrlAsync('https://lnt.xmu.edu.cn')) ?? '';
      if (looksLikeSessionCookie(cookie)) {
        handlingRef.current = true;
        setStatus('✅ 登录成功喵❤ 正在验证身份…');
        try {
          await handleLoginSuccess(cookie);
        } catch {
          handlingRef.current = false;
          setStatus('🐾 请完成登录，会自动获取 Cookie 喵~（若刚登录请点刷新）');
        }
      } else {
        setStatus('🐾 请进行登录，登录后将自动获取 Cookie 喵~');
      }
    }
  };

  if (mode === 'web') {
    return (
      <View style={styles.container}>
        <View style={[styles.webHeader, { paddingTop: insets.top + 8 }]}>
          {pageLoading && (
            <ActivityIndicator size="small" color="#FF6B9D" style={styles.webSpinner} />
          )}
          <Text style={styles.statusText} numberOfLines={1}>
            {status}
          </Text>
        </View>
        <WebView
          key={attempt}
          source={{ uri: BASE_URL }}
          sharedCookiesEnabled
          thirdPartyCookiesEnabled
          javaScriptEnabled
          domStorageEnabled
          cacheEnabled={false}
          cacheMode="LOAD_NO_CACHE"
          userAgent="Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
          onShouldStartLoadWithRequest={(e) => {
            checkUrlAndCookie(e.url);
            return true;
          }}
          onLoadStart={(e) => {
            setPageLoading(true);
            checkUrlAndCookie(e.nativeEvent.url);
          }}
          onLoadEnd={(e) => {
            setPageLoading(false);
            checkUrlAndCookie(e.nativeEvent.url);
          }}
          onError={() => {
            setPageLoading(false);
            if (!handlingRef.current) {
              setStatus('🐾 页面加载异常，请点刷新重试喵~');
            }
          }}
          style={styles.webview}
        />
        <View style={[styles.webFooter, { paddingBottom: insets.bottom + 10 }]}>
          <TouchableOpacity style={styles.webActionBtn} onPress={resetSession} activeOpacity={0.8}>
            <Text style={styles.webActionText}>🔄 刷新页面</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.webActionBtn, styles.webActionBtnClose]}
            onPress={abortLogin}
            activeOpacity={0.8}
          >
            <Text style={[styles.webActionText, styles.webActionTextClose]}>✖ 关闭登录</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>🐾 Zako 签到助手</Text>
        <Text style={styles.subtitle}>连接厦大 CAS 系统登录</Text>
      </View>

      <View style={styles.content}>
        <Text style={styles.icon}>🔐</Text>

        <TouchableOpacity
          style={styles.loginBtn}
          onPress={beginLogin}
          activeOpacity={0.8}
        >
          <Text style={styles.loginBtnText}>🐾 打开 CAS 登录</Text>
        </TouchableOpacity>

        <Text style={styles.hint}>
          学校 Cookie 时效很短，每次使用都需重新登录。{'\n'}
          在打开的页面中输入统一认证账号密码，登录成功后会自动返回喵❤
        </Text>

        <View style={styles.statusWrap}>
          <ActivityIndicator
            size="small"
            color={
              status.includes('✅')
                ? '#06D6A0'
                : status.includes('❌')
                ? '#EF476F'
                : '#FF6B9D'
            }
          />
          <Text style={styles.status}>{status}</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F0E17',
  },
  header: {
    paddingTop: 32,
    paddingBottom: 16,
    paddingHorizontal: 20,
    alignItems: 'center',
  },
  title: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FF6B9D',
  },
  subtitle: {
    fontSize: 14,
    color: '#A7A9BE',
    marginTop: 4,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  icon: {
    fontSize: 64,
    marginBottom: 24,
  },
  loginBtn: {
    backgroundColor: '#FF6B9D',
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 48,
    minWidth: 220,
    alignItems: 'center',
    marginBottom: 24,
  },
  loginBtnText: {
    color: '#0F0E17',
    fontSize: 16,
    fontWeight: 'bold',
  },
  hint: {
    fontSize: 12,
    color: '#A7A9BE',
    textAlign: 'center',
    marginBottom: 16,
    lineHeight: 20,
    opacity: 0.8,
  },
  statusWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    marginBottom: 24,
  },
  status: {
    marginLeft: 8,
    fontSize: 14,
    color: '#A7A9BE',
  },
  webHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingBottom: 8,
    backgroundColor: '#1A1828',
    borderBottomWidth: 1,
    borderBottomColor: '#221F33',
  },
  webSpinner: {
    marginRight: 8,
  },
  statusText: {
    flex: 1,
    color: '#A7A9BE',
    fontSize: 12,
  },
  webFooter: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 10,
    backgroundColor: '#1A1828',
    borderTopWidth: 1,
    borderTopColor: '#221F33',
  },
  webActionBtn: {
    flex: 1,
    backgroundColor: '#FF6B9D',
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: 'center',
    marginRight: 10,
  },
  webActionBtnClose: {
    backgroundColor: '#221F33',
    borderWidth: 1,
    borderColor: '#2E2C3F',
    marginRight: 0,
  },
  webActionText: {
    color: '#0F0E17',
    fontSize: 14,
    fontWeight: 'bold',
  },
  webActionTextClose: {
    color: '#A7A9BE',
  },
  webview: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
});
