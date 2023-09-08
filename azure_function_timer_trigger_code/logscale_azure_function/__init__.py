"""Azure function collector code for LogScale."""
__version__ = "1.0.1"
# pylint: disable=W0703
import datetime
from typing import List
import logging
import json
import os
import warnings
import backoff
import requests
import azure.functions as func

LOG_BATCHES = 5000
warnings.filterwarnings("ignore", category=DeprecationWarning)


class CustomException(Exception):
    """Custom Exception raised while failure occurs."""


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    raise_on_giveup=False,
    max_time=30,
)
def ingest_to_logscale(records):
    """Ingesting records into LogScale Instance.

    Args:
        records (dict)

    Raises:
        CustomException: Raises Custom
        Exception when Failure occurs
        at status_code 400,401,403,404

    Returns:
        dict: Returns the response json of POST request.
    """
    try:
        url = os.environ.get("LogScaleHostURL").rstrip("/") + "/api/v1/ingest/hec"
        logscale_token = os.environ.get("LogScaleIngestToken")
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {logscale_token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(records),
            timeout=30,
        )
        if response.status_code in [400, 401, 403, 404]:
            raise CustomException(
                f"Status-code {response.status_code} Exception {response.text}"
            )
        if response.status_code > 300:
            raise CustomException(
                f"Status-code {response.status_code} Exception {response.text}"
            )
    except CustomException as exception:
        logging.exception("CustomException in ingest to logscale")
        raise exception

    except requests.exceptions.RequestException as exception:
        logging.exception("Exception occurred while posting to LogScale")
        raise requests.exceptions.RequestException from exception
    return response.json()


def validate_size_and_ingest(event_data: dict):
    """Validate event size.

    Event size of the less than 5mb and
    length of data less than 5000 records.

    Args:
        event_data (list)
    """
    # Checking limitation of LogScale endpoint
    # as size of event must be less than 5 mb and
    # length of event must be less than 5000 records.
    try:
        logging.info("Sending data")
        # Ingesting chunks of records received into LogScale Instance.
        response = ingest_to_logscale(event_data)
        if response is None:
            return False
        if response["text"] == "Success" and response["eventCount"] > 0:
            logging.info(response)
            return True

        return False
    except Exception as exception:
        logging.exception("Exception occurred at events validation")
        raise exception


def transform_events(events: List[func.EventHubEvent]) -> dict[str, List[str]]:
    """Set eventhub loop."""
    try:
        event_data = {}
        event_data["event"] = [
            record
            for event in events
            for record in json.loads(event.get_body().decode())["records"]
        ]
        return event_data

    except Exception as exception:
        logging.exception("Exception occurred at start event %s", exception)
        raise exception


def main(events: List[func.EventHubEvent]):
    """Begin main routine."""
    utc_timestamp = (
        datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
    )

    event_data = transform_events(events)

    # logging.info("Send events: %i events, %s", len(event_data), events)
    validate_size_and_ingest(event_data)

    logging.info("Python eventhub trigger function executed at %s", utc_timestamp)
