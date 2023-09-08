"""Azure function collector code for LogScale."""
__version__ = "1.0.1"
# pylint: disable=W0703
import datetime
from typing import List
import logging
import json
import asyncio
import os
import sys
import warnings
import backoff
import requests
import azure.functions as func

LOG_BATCHES = 5000
warnings.filterwarnings("ignore", category=DeprecationWarning)


class CustomException(Exception):
    """Custom Exception raised while failure occurs."""


class Checkpoint:
    """Checkpoint helper class for azure function code."""

    def __init__(self) -> None:
        """Construct an instance of the class."""
        self.connect_str = os.environ.get("AzureWebJobsStorage")


@backoff.on_exception(backoff.expo,
                      requests.exceptions.RequestException,
                      max_tries=5,
                      raise_on_giveup=False,
                      max_time=30)
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
        url = os.environ.get("LogScaleHostURL").rstrip(
                '/')+"/api/v1/ingest/hec"
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
        elif response.status_code > 300:
            raise CustomException(
                f"Status-code {response.status_code} Exception {response.text}"
            )
    except CustomException as exception:
        logging.exception("CustomException in ingest to logscale")
        raise Exception

    except requests.exceptions.RequestException as exception:
        logging.exception(
            "Exception occurred while posting to LogScale")
        raise requests.exceptions.RequestException from exception
    else:
        return response.json()


class Eventhub:
    """Eventhub helper class for azure function code."""

    def __init__(self) -> None:
        """Construct an instance of the class."""
        self.event_data_dict = {}
        self.partitions_block_list = {}

    def validate_size_and_ingest(
            self,
            event_data: list,
            partition_key,
            sequence_number):
        """Validate event size.

        Event size of the less than 5mb and
        length of data less than 5000 records.

        Args:
            event_data (list)
            partition_id(string)
            sequence_number(string)
        """
        # Checking limitation of LogScale endpoint
        # as size of event must be less than 5 mb and
        # length of event must be less than 5000 records.
        try:
            # if (
            #     float(str(event_data).__sizeof__() / 10 ** 6) > 4.8
            #     or len(event_data) > LOG_BATCHES
            # ):
            #     logging.info("Data to big splitting up")
            #     self.validate_size_and_ingest(
            #         event_data[: len(event_data) //
            #                    2], partition_key, sequence_number
            #     )
            #     self.validate_size_and_ingest(
            #         event_data[len(event_data) //
            #                    2:], partition_key, sequence_number
            #     )
            # if (
            #     float(str(event_data).__sizeof__() / 10 ** 6) < 4.8
            #     and len(event_data) < LOG_BATCHES
            # ):
            logging.info("Sending data")
            # Ingesting chunks of records received into LogScale Instance.
            response = ingest_to_logscale(event_data)
            if response is None:
                self.partitions_block_list[partition_key] = False
                logging.info(
                    """Failure occurred at partition id %s so all the sequence number followed\
                    by %s will not be updated in this Schedule""",
                    partition_key,
                    sequence_number)
                return False
            if response["text"] == "Success" and response["eventCount"] > 0:
                logging.info(response)
                return True

            return False
        except Exception as exception:
            logging.exception(
                "Exception occurred at events validation")
            raise exception
        return None

    def send_events(self, events: List[func.EventHubEvent]):
        ##logging.info(events[0].get_body().decode())
        event_data = {}
        event_data["event"] = [ record 
                    for event in events 
                        for record in json.loads(event.get_body().decode())["records"]]        
        
        #logging.info("Send events: %i events, %s", len(event_data), events)
        self.validate_size_and_ingest(event_data, events[0].partition_key, events[0].sequence_number)

    def start_event(self, events: List[func.EventHubEvent]):
        """Set eventhub loop."""
        try:
            self.send_events(events)
        except Exception as exception:
            logging.exception("Exception occurred at start event %s", exception)
            raise exception

##def main(event: func.EventHubEvent) -> None:
def main(events: List[func.EventHubEvent]) -> None: #todo
    """Begin main routine."""
    #logging.info("Python eventhub trigger v1.2 function triggered with: %i events, %s", len(events), events[0].get_body().decode())

    utc_timestamp = (
        datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc).isoformat())
    event_obj = Eventhub()
    event_obj.start_event(events)
    ###event_obj.start_event([event])

    logging.info("Python eventhub trigger function executed at %s", utc_timestamp)
