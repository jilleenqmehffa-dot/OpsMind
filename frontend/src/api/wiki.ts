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
