from typing import Dict
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from mypy_boto3_macie2 import Macie2Client


def handler(event, _) -> Dict[str, str]:

    # pull the needed data out of the event
    account_id = event["account"]
    event_name = event["detail"]["eventName"]
    bucket_name = event["detail"]["requestParameters"]["bucketName"]

    macie = boto3.client("macie2")

    # list active jobs to determine if bucket already has a related job (it shouldn't)
    active_jobs = list_macie_buckets(macie)

    if event_name == "CreateBucket":
        # check if bucket has a related job
        if bucket_name in active_jobs:
            return {"response": f"bucket ({bucket_name}) already exists in a job"}

        # create a simple classification job including the single bucket
        try:
            macie.create_classification_job(
                jobType="SCHEDULED",
                initialRun=True,
                scheduleFrequency={"dailySchedule": {}},
                s3JobDefinition={
                    "bucketDefinitions": [
                        {"accountId": account_id, "buckets": [bucket_name]},
                    ]
                },
            )
        except macie.exceptions.ClientError:
            raise
        else:
            return {"response": f"job has been created for bucket ({bucket_name})"}

    elif event_name == "DeleteBucket":
        # check if the bucket has a related job
        if bucket_name not in active_jobs:
            return {"response": "no related job found"}

        # get job details from dictionary
        job_details = active_jobs[bucket_name]

        # update the jobStatus to CANCELED
        try:
            macie.update_classification_job(
                jobId=job_details["jobId"], jobStatus="CANCELED"
            )
        except macie.exceptions.ClientError:
            raise
        else:
            return {"response": "canceled related job"}

    else:
        return {"response": "not sure what happened"}


def list_macie_buckets(
    macie: "Macie2Client" = boto3.client("macie2"),
) -> Dict[str, Dict[str, str]]:
    """
    return a dict of classification jobs in the form of:
    {"bucket_name": {"jobId": <jobId>, "accountId": <accountId>}, ...}
    """

    paginator = macie.get_paginator("list_classification_jobs")
    response_iter = paginator.paginate()

    output = dict()
    for response in response_iter:
        for job in response["items"]:
            account_id = job["bucketDefinitions"][0]["accountId"]
            bucket_name = job["bucketDefinitions"][0]["buckets"][0]
            output[bucket_name] = {"accountId": account_id, "jobId": job["jobId"]}

    return output
