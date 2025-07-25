// Add these types to your existing types file

export interface LogProps {
  id: string;
  type: "log";
  attributes: {
    timestamp: string;
    message: string;
    logGroup: string;
    logStream: string;
    ingestionTime: string;
    region: string;
    service?: string;
  };
  relationships?: {
    region?: {
      data: { id: string; type: "region" };
    };
    logGroup?: {
      data: { id: string; type: "logGroup" };
    };
  };
}

export interface LogFiltersProps {
  providerUIDs: string[];
  providerDetails: { [uid: string]: FilterEntity }[];
  completedScans: ScanProps[];
  completedScanIds: string[];
  scanDetails: { [uid: string]: ScanEntity }[];
  uniqueRegions: string[];
  uniqueServices: string[];
  uniqueResourceTypes: string[];
  uniqueLogGroups?: string[];
}
