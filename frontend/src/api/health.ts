import axios from "axios";

export interface HealthResponse {
  status: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await axios.get<HealthResponse>("/api/v1/health", {
    timeout: 5000,
  });

  return response.data;
}
