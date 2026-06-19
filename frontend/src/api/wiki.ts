import axios from "axios";

function authHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
  };
}

export interface WikiCategory {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  created_at: string;
}

export interface WikiTag {
  id: number;
  name: string;
  slug: string;
  created_at: string;
}

export interface WikiPageListItem {
  id: number;
  title: string;
  slug: string;
  status: string;
  category_id: number | null;
  author_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface WikiPage extends WikiPageListItem {
  content: string;
  tag_ids: number[];
}

export interface WikiVersion {
  id: number;
  page_id: number;
  title: string;
  content: string;
  version_number: number;
  created_by_user_id: number | null;
  created_at: string;
}

export interface WikiAttachment {
  id: number;
  page_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_path: string;
  uploaded_by_user_id: number | null;
  created_at: string;
}

export interface WikiPageRelationship {
  id: number;
  source_page_id: number;
  target_page_id: number;
  relation_type: string;
  description: string | null;
  source_type: string;
  source_job_id: number | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface WikiSearchRelationship {
  id: number;
  source_page_id: number;
  target_page_id: number;
  relation_type: string;
  related_page_id: number;
  related_page_title: string;
}

export interface WikiSearchResult {
  id: number;
  title: string;
  slug: string;
  status: string;
  summary: string;
  category_id: number | null;
  updated_at: string;
  relationships: WikiSearchRelationship[];
}

export interface WikiSearchParams {
  q: string;
  status?: string;
  category_id?: number;
  tag_id?: number;
  limit?: number;
}

export interface KnowledgeCompilationJob {
  id: number;
  page_id: number | null;
  attachment_id: number;
  status: string;
  knowledge_unit_count: number;
  created_page_count: number;
  updated_page_count: number;
  relationship_count: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeUnit {
  id: number;
  job_id: number;
  source_attachment_id: number;
  source_page_id: number | null;
  title: string;
  unit_type: string;
  summary: string;
  content: string;
  source_location: string;
  confidence: number;
  merge_hint_page_id: number | null;
  merge_hint_title: string | null;
  apply_status: string;
  review_note: string | null;
  created_page_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface WikiPagePayload {
  title: string;
  slug: string;
  content: string;
  status: string;
  category_id: number | null;
  tag_ids: number[];
}

export interface AttachmentPayload {
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_path: string;
}

export interface WikiPageRelationshipPayload {
  target_page_id: number;
  relation_type: string;
  description: string | null;
}

export async function listCategories(token: string): Promise<WikiCategory[]> {
  const response = await axios.get<WikiCategory[]>("/api/v1/wiki/categories", {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function createCategory(token: string, name: string, slug: string): Promise<WikiCategory> {
  const response = await axios.post<WikiCategory>(
    "/api/v1/wiki/categories",
    { name, slug },
    { headers: authHeaders(token) },
  );
  return response.data;
}

export async function listTags(token: string): Promise<WikiTag[]> {
  const response = await axios.get<WikiTag[]>("/api/v1/wiki/tags", {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function createTag(token: string, name: string, slug: string): Promise<WikiTag> {
  const response = await axios.post<WikiTag>(
    "/api/v1/wiki/tags",
    { name, slug },
    { headers: authHeaders(token) },
  );
  return response.data;
}

export async function listPages(token: string): Promise<WikiPageListItem[]> {
  const response = await axios.get<WikiPageListItem[]>("/api/v1/wiki/pages", {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function readPage(token: string, pageId: number): Promise<WikiPage> {
  const response = await axios.get<WikiPage>(`/api/v1/wiki/pages/${pageId}`, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function createPage(token: string, payload: WikiPagePayload): Promise<WikiPage> {
  const response = await axios.post<WikiPage>("/api/v1/wiki/pages", payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function updatePage(token: string, pageId: number, payload: WikiPagePayload): Promise<WikiPage> {
  const response = await axios.put<WikiPage>(`/api/v1/wiki/pages/${pageId}`, payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function deletePage(token: string, pageId: number): Promise<void> {
  await axios.delete(`/api/v1/wiki/pages/${pageId}`, {
    headers: authHeaders(token),
  });
}

export async function listVersions(token: string, pageId: number): Promise<WikiVersion[]> {
  const response = await axios.get<WikiVersion[]>(`/api/v1/wiki/pages/${pageId}/versions`, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function listPageRelationships(
  token: string,
  pageId: number,
  direction = "both",
): Promise<WikiPageRelationship[]> {
  const response = await axios.get<WikiPageRelationship[]>(`/api/v1/wiki/pages/${pageId}/relationships`, {
    headers: authHeaders(token),
    params: { direction },
  });
  return response.data;
}

export async function searchWikiPages(token: string, params: WikiSearchParams): Promise<WikiSearchResult[]> {
  const response = await axios.get<WikiSearchResult[]>("/api/v1/wiki/search", {
    headers: authHeaders(token),
    params,
  });
  return response.data;
}

export async function createPageRelationship(
  token: string,
  pageId: number,
  payload: WikiPageRelationshipPayload,
): Promise<WikiPageRelationship> {
  const response = await axios.post<WikiPageRelationship>(`/api/v1/wiki/pages/${pageId}/relationships`, payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function updatePageRelationship(
  token: string,
  relationshipId: number,
  payload: WikiPageRelationshipPayload,
): Promise<WikiPageRelationship> {
  const response = await axios.put<WikiPageRelationship>(`/api/v1/wiki/relationships/${relationshipId}`, payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function deletePageRelationship(token: string, relationshipId: number): Promise<void> {
  await axios.delete(`/api/v1/wiki/relationships/${relationshipId}`, {
    headers: authHeaders(token),
  });
}

export async function listAttachments(token: string, pageId: number): Promise<WikiAttachment[]> {
  const response = await axios.get<WikiAttachment[]>(`/api/v1/wiki/pages/${pageId}/attachments`, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function createAttachment(
  token: string,
  pageId: number,
  payload: AttachmentPayload,
): Promise<WikiAttachment> {
  const response = await axios.post<WikiAttachment>(`/api/v1/wiki/pages/${pageId}/attachments`, payload, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function compileAttachment(token: string, attachmentId: number): Promise<KnowledgeCompilationJob> {
  const response = await axios.post<KnowledgeCompilationJob>(
    `/api/v1/wiki/attachments/${attachmentId}/compile`,
    {},
    { headers: authHeaders(token) },
  );
  return response.data;
}

export async function readAttachmentCompilation(
  token: string,
  attachmentId: number,
): Promise<KnowledgeCompilationJob> {
  const response = await axios.get<KnowledgeCompilationJob>(`/api/v1/wiki/attachments/${attachmentId}/compile`, {
    headers: authHeaders(token),
  });
  return response.data;
}

export async function listKnowledgeUnits(token: string, attachmentId: number): Promise<KnowledgeUnit[]> {
  const response = await axios.get<KnowledgeUnit[]>("/api/v1/wiki/knowledge-units", {
    headers: authHeaders(token),
    params: { attachment_id: attachmentId },
  });
  return response.data;
}
