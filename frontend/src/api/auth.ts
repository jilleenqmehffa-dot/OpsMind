import axios from "axios";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: number;
  username: string;
  email: string | null;
  display_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
}

export async function login(payload: LoginRequest): Promise<TokenResponse> {
  const response = await axios.post<TokenResponse>("/api/v1/auth/login", payload, {
    timeout: 8000,
  });

  return response.data;
}

export async function getCurrentUser(token: string): Promise<CurrentUser> {
  const response = await axios.get<CurrentUser>("/api/v1/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    timeout: 8000,
  });

  return response.data;
}
