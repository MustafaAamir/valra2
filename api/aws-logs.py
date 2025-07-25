"""
AWS CloudWatch Logs Auditor API

This module provides a FastAPI endpoint to query CloudWatch logs across all AWS regions.

The IAM user/role requires specific permissions and actions to run this API.
Check out iam/policy-cloudwatch-logs-reader.json for all the actions required.
"""

import boto3
import datetime
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
import os
from dotenv import load_dotenv
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

app = FastAPI()
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)
load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Provide your AWS credentials (or use instance role if on EC2)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Thread pool for concurrent operations
executor = ThreadPoolExecutor(max_workers=10)

# Cache for regions (rarely changes)
@lru_cache(maxsize=1)
def get_all_regions() -> List[str]:
    ec2 = boto3.client(
        "ec2",
        region_name="us-east-1",  # safe default
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    response = ec2.describe_regions(AllRegions=False)
    logger.debug("Available regions: %s", response["Regions"])
    return sorted(r["RegionName"] for r in response["Regions"])

# Get log client for specific region
def get_logs_client(region: str):
    return boto3.client(
        "logs",
        region_name=region,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )

def list_all_groups(region: str) -> List[Dict[str, Any]]:
    logger.debug("Querying DescribeLogGroups in %s", region)
    cwl = get_logs_client(region)
    groups = []
    try:
        paginator = cwl.get_paginator("describe_log_groups")
        for page in paginator.paginate():
            for group in page["logGroups"]:
                groups.append({
                    "name": group["logGroupName"],
                    "region": region,
                    "creationTime": group.get("creationTime"),
                    "retentionInDays": group.get("retentionInDays"),
                    "storedBytes": group.get("storedBytes", 0),
                })
    except Exception as e:
        logger.warning("Failed to list groups in region %s: %s", region, e)
    return groups

def query_single_group(log_group: str, start: int, end: int, limit: int, region: str) -> List[dict]:
    logger.debug("Query group %s in region %s", log_group, region)
    cwl = get_logs_client(region)
    query = f"""
        fields @timestamp, @message, @logStream, @ingestionTime
        | sort @timestamp desc
        | limit {limit}
    """
    try:
        qid = cwl.start_query(
            logGroupName=log_group,
            startTime=start,
            endTime=end,
            queryString=query
        )["queryId"]
        logger.debug("Started query id %s in %s", qid, region)

        # Wait for results
        while True:
            out = cwl.get_query_results(queryId=qid)
            if out["status"] in ("Complete", "Failed", "Cancelled"):
                break

        results = []
        for row in out["results"]:
            event = {f["field"]: f["value"] for f in row}
            results.append({
                "timestamp": event.get("@timestamp"),
                "message": event.get("@message"),
                "logGroup": log_group,
                "logStream": event.get("@logStream"),
                "ingestionTime": event.get("@ingestionTime"),
                "region": region
            })
        return results
    except Exception as e:
        logger.warning("Query failed for %s (%s): %s", log_group, region, e)
        return []

def extract_service_from_log_group(log_group: str) -> str:
    """Extract service name from log group name"""
    if log_group.startswith('/aws/lambda/'):
        return 'lambda'
    elif log_group.startswith('/aws/apigateway/'):
        return 'apigateway'
    elif log_group.startswith('/aws/ecs/'):
        return 'ecs'
    elif log_group.startswith('/aws/eks/'):
        return 'eks'
    elif log_group.startswith('/aws/rds/'):
        return 'rds'
    elif log_group.startswith('/aws/codebuild/'):
        return 'codebuild'
    elif log_group.startswith('CloudTrail/'):
        return 'cloudtrail'
    elif log_group.startswith('/aws/'):
        parts = log_group.split('/')
        return parts[2] if len(parts) > 2 else 'aws'
    else:
        return 'other'

@app.get("/api/v1/auditor/aws/logs-all")
def auditor_aws_logs_all(
        start: datetime.datetime = Query(...),
        end: datetime.datetime = Query(...),
        limit_per_group: int = Query(50, le=5000),
        regions: Optional[str] = Query(None, description="Comma-separated list of regions"),
        log_groups: Optional[str] = Query(None, description="Comma-separated list of log groups"),
        services: Optional[str] = Query(None, description="Comma-separated list of services")
):
    """Fetch logs from all regions or specified regions/log groups"""
    logger.info("Fetching logs across regions...")
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    all_events = []
    
    # Determine which regions to query
    target_regions = regions.split(',') if regions else get_all_regions()
    target_log_groups = log_groups.split(',') if log_groups else None
    target_services = services.split(',') if services else None
    
    logger.info("Target regions: %s", target_regions)
    
    for region in target_regions:
        try:
            if target_log_groups:
                # Query specific log groups
                groups = [{"name": lg, "region": region} for lg in target_log_groups]
            else:
                # Get all groups in region
                groups = list_all_groups(region)
            
            # Filter by services if specified
            if target_services:
                groups = [g for g in groups if extract_service_from_log_group(g["name"]) in target_services]
            
            logger.info("Region %s has %d groups to query", region, len(groups))
            
            for group_info in groups:
                group_name = group_info["name"] if isinstance(group_info, dict) else group_info
                events = query_single_group(group_name, start_ts, end_ts, limit_per_group, region)
                
                # Add service information to each event
                for event in events:
                    event["service"] = extract_service_from_log_group(event["logGroup"])
                
                all_events.extend(events)
                
        except Exception as e:
            logger.warning("Failed to list/query logs in region %s: %s", region, e)

    all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    logger.info("Returning %d total log events", len(all_events))
    return all_events

@app.get("/api/logs/meta/regions")
def list_regions():
    """Get all available AWS regions"""
    return get_all_regions()

@app.get("/api/logs/meta/groups")
def list_groups(region: str = Query(...)):
    """Get all log groups in a specific region"""
    try:
        groups = list_all_groups(region)
        return [g["name"] for g in groups]
    except Exception as e:
        logger.error("Error listing groups for region %s: %s", region, e)
        raise HTTPException(status_code=500, detail=f"Failed to list groups: {str(e)}")

@app.get("/api/logs/meta/groups-detailed")
def list_groups_detailed(region: str = Query(...)):
    """Get detailed information about log groups in a specific region"""
    try:
        return list_all_groups(region)
    except Exception as e:
        logger.error("Error listing detailed groups for region %s: %s", region, e)
        raise HTTPException(status_code=500, detail=f"Failed to list groups: {str(e)}")

@app.get("/api/logs/meta/services")
def list_services():
    """Get unique services across all regions (sample from key regions)"""
    services = set()
    key_regions = ["us-east-1", "us-west-2", "eu-west-1"]  # Sample key regions
    
    for region in key_regions:
        try:
            groups = list_all_groups(region)
            for group in groups:
                service = extract_service_from_log_group(group["name"])
                services.add(service)
        except Exception as e:
            logger.warning("Failed to get services from region %s: %s", region, e)
    
    return sorted(list(services))

@app.get("/api/logs/meta/all")
def get_all_metadata():
    """Get all metadata (regions, services, sample log groups)"""
    try:
        regions = get_all_regions()
        services = set()
        sample_groups = []
        
        # Sample from key regions to get services and groups
        key_regions = regions[:3]  # First 3 regions
        
        for region in key_regions:
            try:
                groups = list_all_groups(region)
                for group in groups[:10]:  # Sample first 10 groups per region
                    service = extract_service_from_log_group(group["name"])
                    services.add(service)
                    sample_groups.append(group["name"])
            except Exception as e:
                logger.warning("Failed to get metadata from region %s: %s", region, e)
        
        return {
            "regions": regions,
            "services": sorted(list(services)),
            "sample_log_groups": sample_groups[:50],  # Limit sample groups
            "resource_types": ["log-event", "log-group", "log-stream"]
        }
    except Exception as e:
        logger.error("Error getting all metadata: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
