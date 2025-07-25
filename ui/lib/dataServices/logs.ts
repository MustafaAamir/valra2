import axios from "axios";

import { LogEntry } from "@/types/logs";

const BASE = process.env.NEXT_PUBLIC_LOGS_API || "http://localhost:8000/api/v1";

export async function fetchLogs(filters: {
  region?: string;
  logGroup?: string;
  start?: string;
  end?: string;
}): Promise<LogEntry[]> {
  const { data } = await axios.get(`${BASE}/auditor/aws/logs-all`, {
    params: {
      ...filters,
      limit_per_group: 1000,
    },
  });
  return data;
}
