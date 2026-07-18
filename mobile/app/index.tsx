import { Ionicons } from "@expo/vector-icons";
import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { AgentResponse, TaskStatus } from "../../shared/types/contracts";
import { sendGoal } from "../lib/api";

const statusColor: Record<TaskStatus, string> = {
  todo: "#738095", researching: "#B18CFF", waiting: "#F5B85D", completed: "#62D6A6",
};

export default function HomeScreen() {
  const [goal, setGoal] = useState("I am moving to Seattle");
  const [result, setResult] = useState<AgentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!goal.trim()) return;
    setLoading(true); setError(null);
    try { setResult(await sendGoal(goal)); } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reach your agent");
    } finally { setLoading(false); }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
        <View style={styles.brand}><View style={styles.mark}><Ionicons name="sparkles" size={18} color="#101116" /></View><Text style={styles.brandText}>LifeOps</Text></View>
        <Text style={styles.eyebrow}>YOUR LIFE, IN MOTION</Text>
        <Text style={styles.title}>What are we{`\n`}getting done?</Text>
        <View style={styles.composer}>
          <TextInput value={goal} onChangeText={setGoal} placeholder="Tell me a goal…" placeholderTextColor="#6E7480" multiline style={styles.input} />
          <Pressable accessibilityRole="button" accessibilityLabel="Start voice input" style={styles.mic}><Ionicons name="mic" size={23} color="#EEEAF7" /></Pressable>
          <Pressable onPress={submit} disabled={loading} style={styles.go}>{loading ? <ActivityIndicator color="#101116" /> : <Ionicons name="arrow-up" size={22} color="#101116" />}</Pressable>
        </View>
        {error && <Text style={styles.error}>{error}</Text>}
        {result && <>
          <View style={styles.sectionRow}><Text style={styles.sectionTitle}>Journey</Text><Text style={styles.pill}>{result.journey.tasks.length} STEPS</Text></View>
          <Text style={styles.response}>{result.message}</Text>
          {result.journey.tasks.map((task, index) => <View key={task.id} style={styles.card}>
            <View style={[styles.dot, { backgroundColor: statusColor[task.status] }]} />
            <View style={styles.cardBody}><Text style={styles.cardKicker}>STEP {index + 1} · {task.status.toUpperCase()}</Text><Text style={styles.cardTitle}>{task.title}</Text><Text style={styles.cardText}>{task.description}</Text></View>
          </View>)}
          {result.recommendations.length > 0 && <><Text style={[styles.sectionTitle, { marginTop: 28 }]}>Recommendations</Text>{result.recommendations.map(item => <View key={item.id} style={styles.evidence}><Text style={styles.cardKicker}>{Math.round(item.score * 100)}% MATCH</Text><Text style={styles.cardTitle}>{item.title}</Text><Text style={styles.cardText}>{item.rationale}</Text></View>)}</>}
          {result.contact_intelligence && <><Text style={[styles.sectionTitle, { marginTop: 28 }]}>Relationship</Text><View style={styles.card}><View style={styles.cardBody}><Text style={styles.cardKicker}>PUBLIC CONTEXT + INTERACTION</Text><Text style={styles.cardTitle}>{result.contact_intelligence.name ?? "Contact"}</Text>{result.contact_intelligence.recommendations.map(item => <Text key={item} style={styles.cardText}>→ {item}</Text>)}</View></View></>}
          {result.research.length > 0 && <><Text style={[styles.sectionTitle, { marginTop: 28 }]}>Evidence</Text>{result.research.map(item => <View key={item.id} style={styles.evidence}><Text style={styles.cardKicker}>{Math.round(item.confidence * 100)}% CONFIDENCE</Text><Text style={styles.cardTitle}>{item.title}</Text><Text style={styles.cardText}>{item.summary}</Text></View>)}</>}
        </>}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#101116" }, page: { padding: 22, paddingBottom: 56 },
  brand: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 44 }, mark: { width: 34, height: 34, borderRadius: 11, backgroundColor: "#B8F36B", alignItems: "center", justifyContent: "center" }, brandText: { color: "#F6F2FC", fontSize: 20, fontWeight: "700" },
  eyebrow: { color: "#A58BCE", fontSize: 11, fontWeight: "700", letterSpacing: 2 }, title: { color: "#F6F2FC", fontSize: 40, lineHeight: 44, fontWeight: "700", marginTop: 10, marginBottom: 24 },
  composer: { backgroundColor: "#1A1B22", borderColor: "#30313A", borderWidth: 1, borderRadius: 20, padding: 14, minHeight: 126, flexDirection: "row", alignItems: "flex-end", gap: 10 }, input: { color: "#F6F2FC", fontSize: 17, flex: 1, alignSelf: "stretch", textAlignVertical: "top" }, mic: { width: 44, height: 44, borderRadius: 22, backgroundColor: "#2B2C35", alignItems: "center", justifyContent: "center" }, go: { width: 44, height: 44, borderRadius: 22, backgroundColor: "#B8F36B", alignItems: "center", justifyContent: "center" }, error: { color: "#FF8B8B", marginTop: 12 },
  sectionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 34, marginBottom: 12 }, sectionTitle: { color: "#F6F2FC", fontSize: 22, fontWeight: "700" }, pill: { color: "#B8F36B", backgroundColor: "#202A1B", overflow: "hidden", borderRadius: 8, paddingHorizontal: 9, paddingVertical: 5, fontSize: 10, fontWeight: "700" }, response: { color: "#A7A8B2", fontSize: 15, lineHeight: 22, marginBottom: 14 },
  card: { flexDirection: "row", backgroundColor: "#191A20", borderColor: "#292A33", borderWidth: 1, borderRadius: 16, padding: 16, marginBottom: 10 }, dot: { width: 9, height: 9, borderRadius: 5, marginTop: 5, marginRight: 12 }, cardBody: { flex: 1 }, cardKicker: { color: "#858795", fontSize: 9, fontWeight: "700", letterSpacing: 1.1, marginBottom: 6 }, cardTitle: { color: "#F0EDF6", fontSize: 16, fontWeight: "600", marginBottom: 5 }, cardText: { color: "#9597A2", fontSize: 13, lineHeight: 19 }, evidence: { borderLeftColor: "#A58BCE", borderLeftWidth: 2, paddingLeft: 14, marginTop: 15 },
});
