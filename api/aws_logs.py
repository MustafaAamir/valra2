"""
AWS CloudWatch Logs Auditor API

This module provides a FastAPI endpoint to query CloudWatch logs across all AWS regions.

The IAM user/role requires specific permissions and actions to run this API.
Check out iam/policy-cloudwatch-logs-reader.json for all the actions required.
"""

import boto3
import datetime
import logging
from typing import List, Optional
from fastapi import FastAPI, Query
import os
from dotenv import load_dotenv
app = FastAPI()
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.DEBUG)
load_dotenv
# Provide your AWS credentials (or use instance role if on EC2)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

# Get all public AWS regions
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

def list_all_groups(region: str) -> List[str]:
    logger.debug("Querying DescribeLogGroups in %s", region)
    cwl = get_logs_client(region)
    groups = []
    paginator = cwl.get_paginator("describe_log_groups")
    for page in paginator.paginate():
        names = [g["logGroupName"] for g in page["logGroups"]]
        groups.extend(names)
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

@app.get("/api/v1/auditor/aws/logs-all")
def auditor_aws_logs_all(
        start: datetime.datetime = Query(...),
        end: datetime.datetime = Query(...),
        limit_per_group: int = Query(50, le=5000)
):
    logger.info("Fetching logs across all regions...")
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    all_events = []
    logger.info(get_all_regions())
    for region in get_all_regions():
        try:
            groups = list_all_groups(region)
            logger.info("Region %s has %d groups", region, len(groups))
            for g in groups:
                events = query_single_group(g, start_ts, end_ts, limit_per_group, region)
                all_events.extend(events)
        except Exception as e:
            logger.warning("Failed to list/query logs in region %s: %s", region, e)

    all_events.sort(key=lambda x: x["timestamp"], reverse=True)
    logger.info("Returning %d total log events", len(all_events))
    return all_events

