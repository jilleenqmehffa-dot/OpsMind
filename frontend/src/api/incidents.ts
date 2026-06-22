import axios from "axios";

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export type IncidentSeverity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "investigating" | "resolved" | "closed";

export interface IncidentListItem {
  id: number;
  title: string;
  system_name: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  occurred_at: string | null;
  resolved_at: string | null;
  wiki_page_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentCase extends IncidentListItem {
  symptom: string;
  cause: string | null;
  investigation_process: string | null;
  solution: string | null;
  review_conclusion: string | null;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
}

export interface IncidentPayload {
  title: string;
  system_name: string | null;
  severity: IncidentSeverity;
  status: IncidentStatus;
  symptom: string;
  cause: string | null;
  investigation_process: string | null;
  solution: string | null;
  review_conclusion: string | null;
  occurred_at: string | null;
  resolved_at: string | null;
}

export interface IncidentListParams {
  q?: string;
  system_name?: string;
  severity?: IncidentSeverity;
  status?: IncidentStatus;
}

export interface PublishedWikiPage {
  id: number;
  title: string;
  slug: string;
  page_type: string;
  status: string;
}

export interface IncidentRelationshipBuildResult {
  incident_id: number;
  wiki_page_id: number;
  created_page_ids: number[];
  updated_page_ids: number[];
  relationship_ids: number[];
  similar_incident_ids: number[];
}

export async function listIncidents(token: string, params: IncidentListParams = {}): Promise<IncidentListItem[]> {
  const response = await axios.get<IncidentListItem[]>("/api/v1/incidents", {
    headers: authHeaders(token),
    params,
  });
  return response.data;
}

export async function readIncident(token: string, incidentId: number): Promise<IncidentCase> {
  const response = await axios.get<IncidentCase>(`/api/v1/incidents/${incidentId}`, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function createIncident(token: string, payload: IncidentPayload): Promise<IncidentCase> {
  const response = await axios.post<IncidentCase>("/api/v1/incidents", payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function updateIncident(token: string, incidentId: number, payload: IncidentPayload): Promise<IncidentCase> {
  const response = await axios.put<IncidentCase>(`/api/v1/incidents/${incidentId}`, payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function deleteIncident(token: string, incidentId: number): Promise<void> {
  await axios.delete(`/api/v1/incidents/${incidentId}`, { headers: authHeaders(token) });
}

export async function publishIncidentToWiki(token: string, incidentId: number): Promise<PublishedWikiPage> {
  const response = await axios.post<PublishedWikiPage>(
    `/api/v1/incidents/${incidentId}/publish-to-wiki`,
    {},
    { headers: authHeaders(token) },
  );
  return response.data;
}

export async function buildIncidentWikiRelationships(
  token: string,
  incidentId: number,
): Promise<IncidentRelationshipBuildResult> {
  const response = await axios.post<IncidentRelationshipBuildResult>(
    `/api/v1/incidents/${incidentId}/build-wiki-relationships`,
    {},
    { headers: authHeaders(token) },
  );
  return response.data;
}
