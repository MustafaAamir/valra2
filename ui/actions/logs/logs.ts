"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { parseStringify } from "@/lib";

const API_BASE_URL = "http://localhost:8000";

export const getLogs = async ({
  page = 1,
  pageSize = 10,
  query = "",
  sort = "",
  filters = {},
  start,
  end,
}) => {
  if (isNaN(Number(page)) || page < 1) {
    redirect("logs");
  }

  // Calculate offset for pagination
  const offset = (page - 1) * pageSize;

  try {
    const url = new URL(`${API_BASE_URL}/api/v1/auditor/aws/logs-all`);
    
    if (start) url.searchParams.append("start", start);
    if (end) url.searchParams.append("end", end);
    url.searchParams.append("limit_per_group", "5000"); // Get max data from API
    
    const response = await fetch(url.toString());
    
    if (!response.ok) {
      throw new Error(`Failed to fetch logs: ${response.statusText}`);
    }
    
    let data = await response.json();
    
    // Apply client-side filtering if query is provided
    if (query) {
      data = data.filter((log: any) => 
        log.message?.toLowerCase().includes(query.toLowerCase()) ||
        log.logGroup?.toLowerCase().includes(query.toLowerCase()) ||
        log.logStream?.toLowerCase().includes(query.toLowerCase()) ||
        log.region?.toLowerCase().includes(query.toLowerCase())
      );
    }

    // Apply additional filters
    Object.entries(filters).forEach(([key, value]) => {
      if (value && key !== "filter[search]") {
        const filterKey = key.replace(/^filter\[|\]$/g, '').replace(/__in$/, '');
        if (Array.isArray(value)) {
          data = data.filter((log: any) => value.includes(log[filterKey]));
        } else {
          data = data.filter((log: any) => log[filterKey] === value);
        }
      }
    });

    // Apply sorting
    if (sort) {
      const sortFields = sort.split(',');
      data.sort((a: any, b: any) => {
        for (const field of sortFields) {
          const isDesc = field.startsWith('-');
          const fieldName = field.replace(/^-/, '');
          
          let aVal = a[fieldName];
          let bVal = b[fieldName];
          
          if (fieldName === 'timestamp' || fieldName === 'ingestionTime') {
            aVal = new Date(aVal).getTime();
            bVal = new Date(bVal).getTime();
          }
          
          if (aVal < bVal) return isDesc ? 1 : -1;
          if (aVal > bVal) return isDesc ? -1 : 1;
        }
        return 0;
      });
    }

    // Apply pagination
    const total = data.length;
    const paginatedData = data.slice(offset, offset + pageSize);

    // Format response to match findings structure
    const formattedResponse = {
      data: paginatedData.map((log: any, index: number) => ({
        id: `${log.region}-${log.logGroup}-${log.logStream}-${offset + index}`,
        type: "log",
        attributes: {
          timestamp: log.timestamp,
          message: log.message,
          logGroup: log.logGroup,
          logStream: log.logStream,
          ingestionTime: log.ingestionTime,
          region: log.region,
        },
        relationships: {
          region: { data: { id: log.region, type: "region" } },
          logGroup: { data: { id: log.logGroup, type: "logGroup" } },
        }
      })),
      meta: {
        page: {
          current: page,
          size: pageSize,
          total: Math.ceil(total / pageSize),
        },
        total_count: total,
      },
      included: []
    };

    const parsedData = parseStringify(formattedResponse);
    revalidatePath("/logs");
    return parsedData;
  } catch (error) {
    console.error("Error fetching logs:", error);
    return undefined;
  }
};

export const getLatestLogs = async ({
  page = 1,
  pageSize = 10,
  query = "",
  sort = "",
  filters = {},
}) => {
  // For logs, "latest" means recent logs (last 24 hours by default)
  const end = new Date().toISOString();
  const start = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(); // 24 hours ago
  
  return getLogs({
    page,
    pageSize,
    query,
    sort,
    filters,
    start,
    end,
  });
};

export const getMetadataInfo = async ({
  query = "",
  sort = "",
  filters = {},
}) => {
  try {
    const [regionsResponse, groupsResponse] = await Promise.all([
      fetch(`${API_BASE_URL}/api/logs/meta/regions`),
      // Get groups from a default region or all regions
      Promise.resolve([]) // We'll populate this differently
    ]);

    const regions = regionsResponse.ok ? await regionsResponse.json() : [];
    
    // Get unique log groups across regions (this might be expensive, consider caching)
    const logGroups: string[] = [];
    const services: string[] = [];
    
    // Extract services from log group names (common AWS pattern)
    for (const region of regions.slice(0, 3)) { // Limit to first 3 regions for performance
      try {
        const groupsUrl = new URL(`${API_BASE_URL}/api/logs/meta/groups`);
        groupsUrl.searchParams.append("region", region);
        const response = await fetch(groupsUrl.toString());
        if (response.ok) {
          const regionGroups = await response.json();
          logGroups.push(...regionGroups);
          
          // Extract services from log group names
          regionGroups.forEach((group: string) => {
            const serviceName = extractServiceFromLogGroup(group);
            if (serviceName && !services.includes(serviceName)) {
              services.push(serviceName);
            }
          });
        }
      } catch (error) {
        console.error(`Error fetching groups for region ${region}:`, error);
      }
    }

    const formattedResponse = {
      data: {
        type: "metadata",
        id: "logs-metadata",
        attributes: {
          regions: [...new Set(regions)],
          services: [...new Set(services)],
          resource_types: ["log-event", "log-group", "log-stream"], // Standard log resource types
          log_groups: [...new Set(logGroups)],
        }
      }
    };

    return parseStringify(formattedResponse);
  } catch (error) {
    console.error("Error fetching metadata info:", error);
    return undefined;
  }
};

export const getLatestMetadataInfo = async ({
  query = "",
  sort = "",
  filters = {},
}) => {
  // For logs, latest metadata is the same as regular metadata
  return getMetadataInfo({ query, sort, filters });
};

// Helper function to extract service name from log group
function extractServiceFromLogGroup(logGroup: string): string | null {
  // Common AWS log group patterns
  const patterns = [
    /^\/aws\/lambda\/(.+)$/,
    /^\/aws\/apigateway\/(.+)$/,
    /^\/aws\/ecs\/(.+)$/,
    /^\/aws\/eks\/(.+)$/,
    /^\/aws\/rds\/(.+)$/,
    /^\/aws\/cloudtrail\/(.+)$/,
    /^\/aws\/codebuild\/(.+)$/,
    /^CloudTrail\/(.+)$/,
  ];

  for (const pattern of patterns) {
    const match = logGroup.match(pattern);
    if (match) {
      const servicePart = logGroup.split('/')[2];
      return servicePart || 'unknown';
    }
  }

  // If no pattern matches, try to extract from the beginning
  if (logGroup.startsWith('/aws/')) {
    const parts = logGroup.split('/');
    return parts[2] || 'aws';
  }

  return 'other';
}
