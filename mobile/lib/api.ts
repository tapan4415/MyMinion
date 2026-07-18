import Constants from "expo-constants";
import type { AgentResponse } from "../../shared/types/contracts";

const apiUrl = process.env.EXPO_PUBLIC_AGENT_API_URL ??
  (Constants.expoConfig?.extra?.agentApiUrl as string) ?? "http://localhost:8000";

export async function sendGoal(message: string): Promise<AgentResponse> {
  const response = await fetch(`${apiUrl}/v1/agent/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: "demo-user", session_id: "ios-demo", message }),
  });
  if (!response.ok) throw new Error(`Agent request failed (${response.status})`);
  return response.json() as Promise<AgentResponse>;
}
