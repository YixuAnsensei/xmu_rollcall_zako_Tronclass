import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  StatusBar,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { getAuth } from '../../lib/auth';
import { getCourses, getSemesterInfo, Course } from '../../lib/api';

export default function CoursesScreen() {
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCourses();
  }, []);

  const loadCourses = async () => {
    setLoading(true);
    setError(null);
    try {
      const { cookie } = await getAuth();
      if (!cookie) {
        router.replace('/screens/LoginScreen');
        return;
      }
      const sem = await getSemesterInfo(cookie);
      const result = await getCourses(cookie, sem.semester_id, sem.academic_year_id);
      setCourses(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const goToRollcall = (course: Course) => {
    router.push({
      pathname: '/screens/RollcallScreen',
      params: {
        courseId: String(course.id),
        courseName: course.display_name || course.name,
      },
    });
  };

  const renderCourse = ({ item }: { item: Course }) => (
    <TouchableOpacity
      style={styles.courseCard}
      onPress={() => goToRollcall(item)}
      activeOpacity={0.8}
    >
      <View style={styles.courseIconWrap}>
        <Text style={styles.courseIcon}>📚</Text>
      </View>
      <View style={styles.courseInfo}>
        <Text style={styles.courseName} numberOfLines={2}>
          {item.display_name || item.name}
        </Text>
        <Text style={styles.courseId}>ID: {item.id}</Text>
      </View>
      <Text style={styles.arrow}>›</Text>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" />
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backText}>← 返回</Text>
          </TouchableOpacity>
          <Text style={styles.title}>选择课程</Text>
        </View>
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#FF6B9D" />
          <Text style={styles.loadingText}>正在拉取课程列表...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" />
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backText}>← 返回</Text>
          </TouchableOpacity>
          <Text style={styles.title}>选择课程</Text>
        </View>
        <View style={styles.center}>
          <Text style={styles.errorText}>❌ {error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={loadCourses}>
            <Text style={styles.retryText}>重试</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" />

      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backText}>← 返回</Text>
        </TouchableOpacity>
        <Text style={styles.title}>选择课程</Text>
      </View>

      {courses.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emoji}>😿</Text>
          <Text style={styles.emptyText}>暂无课程，请检查 Cookie 是否有效</Text>
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => router.replace('/screens/LoginScreen')}
          >
            <Text style={styles.retryText}>重新登录</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <>
          <FlatList
            data={courses}
            keyExtractor={(item) => String(item.id)}
            renderItem={renderCourse}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
          />
          <Text style={styles.countText}>共 {courses.length} 门课</Text>
        </>
      )}
    </SafeAreaView>
  );
}

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
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFFFFE',
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  loadingText: {
    marginTop: 12,
    color: '#A7A9BE',
    fontSize: 14,
  },
  errorText: {
    color: '#EF476F',
    fontSize: 14,
    textAlign: 'center',
  },
  retryBtn: {
    marginTop: 16,
    backgroundColor: '#FF6B9D',
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 8,
  },
  retryText: {
    color: '#0F0E17',
    fontSize: 14,
    fontWeight: 'bold',
  },
  emoji: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyText: {
    color: '#A7A9BE',
    fontSize: 14,
    textAlign: 'center',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 24,
  },
  courseCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1A1828',
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#221F33',
  },
  courseIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: '#221F33',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  courseIcon: {
    fontSize: 24,
  },
  courseInfo: {
    flex: 1,
  },
  courseName: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFFFFE',
  },
  courseId: {
    fontSize: 12,
    color: '#A7A9BE',
    marginTop: 3,
    fontFamily: 'monospace',
  },
  arrow: {
    fontSize: 22,
    color: '#A7A9BE',
    marginLeft: 8,
  },
  countText: {
    textAlign: 'center',
    color: '#A7A9BE',
    fontSize: 12,
    paddingVertical: 14,
  },
});
