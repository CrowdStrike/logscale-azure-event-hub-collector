"""Azure function collector code for LogScale."""
# pylint: disable=W0703
import datetime
import logging
import json
import asyncio
import os
import sys
import warnings
import backoff
import requests
import azure.functions as func
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub import EventHubConsumerClient as sync_client
from azure.storage.blob import ContainerClient

LOG_BATCHES = 5000
CONTAINER_NAME = "logscale-checkpoint-store"
BLOB_NAME = "logscale-checkpoint.json"
warnings.filterwarnings("ignore", category=DeprecationWarning)


class CustomException(Exception):
    """Custom Exception raised while failure occurs."""


class Checkpoint:
    """Checkpoint helper class for azure function code."""

    def __init__(self) -> None:
        """Construct an instance of the class."""
        self.connect_str = os.environ.get("AzureWebJobsStorage")

    def get_checkpoint(self, checkpoint, partition_ids):
        """Get the checkpoint json from blob storage.

        Args:
            checkpoint (dict): latest checkpoint json
            partition_ids (list): List of partition ids

        Returns:
            dict: latest checkpoint json from blob storage
        """
        checkpoint_dict = ""
        checkpnt = ""
        try:
            service = ContainerClient.from_connection_string(
                conn_str=self.connect_str, container_name=CONTAINER_NAME
            )
            if not service.exists():
                service.create_container()
                for partition_id in partition_ids:
                    checkpoint[partition_id] = -1
                checkpoint_str = json.dumps(checkpoint)
                # Uploading default checkpoint.json file in blob storage
                blob_client = service.get_blob_client(blob=BLOB_NAME)
                blob_client.upload_blob(checkpoint_str, overwrite=True)
                checkpnt = -1
            else:
                # Reading latest checkpoint file from blob storage
                blob_client = service.get_blob_client(BLOB_NAME)
                streamdownloader = blob_client.download_blob()
                checkpoint_dict = json.loads(streamdownloader.readall())
                checkpnt = checkpoint_dict
                checkpoint = checkpoint_dict
                partition_ids = checkpoint_dict.keys()
                logging.info(
                    "CHECKPOINT: starting data fetching from ['partition_id':'sequence_number'] %s",
                    checkpoint_dict)
        except Exception as exception:
            logging.error(
                "Exception occurred while obtaining latest checkpoint value %s",
                exception)

        else:
            return checkpnt, checkpoint, partition_ids

        return None

    @staticmethod
    def update_checkpoint(
            checkpoint,
            partition_id,
            seq_number,
            partition_ids):
        """Update the checkpoint locally.

        Args:
            checkpoint (dict): checkpoint dict
            partition_id (list): list of partition ids
            seq_number (int): sequence number attached with event
            partition_ids (list): list of partiton ids

        Returns:
            dict: checkpoint dict
        """
        try:

            if partition_id not in partition_ids:
                partition_ids.append(partition_id)
            checkpoint[partition_id] = seq_number
            logging.info(checkpoint)
        except Exception as exception:
            logging.error(
                "Exception occurred while updating checkpoint %s",
                exception)
        else:
            return checkpoint, partition_ids
        return None

    def update_checkpoint_file(self, checkpoint):
        """Update the Checkpoint file on blob storage.

        Args:
            checkpoint (dict): latest checkpoint updated
        """
        try:
            checkpoint_str = json.dumps(checkpoint)
            service = ContainerClient.from_connection_string(
                conn_str=self.connect_str, container_name=CONTAINER_NAME
            )
            blob_client = service.get_blob_client(blob=BLOB_NAME)
            blob_client.upload_blob(checkpoint_str, overwrite=True)
        except IOError:
            pass
        except Exception as exception:
            logging.info(
                "Exception occurred while updating checkpoint file to blob storage %s",
                exception)


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
        logscale_token = os.environ.get("LogScaleIngestToken")
        response = requests.post(
            url=os.environ.get("LogScaleHostURL").rstrip('/')+"/api/v1/ingest/hec",
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
    except CustomException as exception:
        logging.error("%s", exception)
        sys.exit(1)

    except requests.exceptions.RequestException as exception:
        logging.error(
            "Exception occurred while posting to LogScale %s",
            exception)
        raise requests.exceptions.RequestException from exception
    else:
        return response.json()


class Eventhub:
    """Eventhub helper class for azure function code."""

    def __init__(self) -> None:
        """Construct an instance of the class."""
        self.partition_ids = {}
        self.checkpoint = {}
        self.event_data_dict = {}
        self.partitions_block_list = {}
        self.receive = True
        self.event_hub_connec_str = os.environ.get("Eventhubconnstring")
        self.event_hub_name = os.environ.get("EventhubName")

    def auth_client(self):
        """Authenticate to Eventhub.

        Returns: Eventhub client
        """
        try:
            client = EventHubConsumerClient.from_connection_string(
                conn_str=self.event_hub_connec_str,
                consumer_group=os.environ.get('ConsumerGroup'),
                eventhub_name=self.event_hub_name,
            )
        except Exception as exception:
            logging.info(
                "Exception occurred while creating an Eventhub client %s",
                exception)
        else:
            return client
        return None

    def validate_size_and_ingest(
            self,
            event_data: list,
            partition_id,
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
            if (
                float(str(event_data).__sizeof__() / 10 ** 6) > 4.8
                or len(event_data) > LOG_BATCHES
            ):
                self.validate_size_and_ingest(
                    event_data[: len(event_data) //
                               2], partition_id, sequence_number
                )
                self.validate_size_and_ingest(
                    event_data[len(event_data) //
                               2:], partition_id, sequence_number
                )
            if (
                float(str(event_data).__sizeof__() / 10 ** 6) < 4.8
                and len(event_data) < LOG_BATCHES
            ):
                self.event_data_dict["event"] = event_data
                # Ingesting chunks of records received into LogScale Instance.
                response = ingest_to_logscale(self.event_data_dict)
                if response is None:
                    self.partitions_block_list[partition_id] = False
                    logging.info(
                        """Failure occurred at partition id %s so all the sequence number followed\
                        by %s will not be updated in this Schedule""",
                        partition_id,
                        sequence_number)
                    return False
                if response["text"] == "Success" and response["eventCount"] > 0:
                    logging.info(response)
                    return True

            return False
        except Exception as exception:
            logging.info(
                "Exception occurred at events validation: %s",
                exception)
        return None

    @staticmethod
    async def close(client):
        """Close method for azure function.

        Args:
            client (client): Eventhub client
        """
        await client.close()

    async def on_event(self, partitions, event):
        """Collect event from eventhub.

        Args:
            partitions (list): list of partition ids
            event: event fetched from eventhub
        """
        try:
            partition_id = partitions.partition_id
            checkpoint_obj_update = Checkpoint()
            if event is not None:
                if self.partitions_block_list[partition_id] is True:
                    event_data_str = event.body_as_str(encoding="UTF-8")
                    event_data_str = event_data_str.replace("records", "event")
                    event_data = json.loads(event_data_str)
                    flag_checkpoint = self.validate_size_and_ingest(
                        event_data["event"], partition_id, event.sequence_number)
                    if flag_checkpoint:
                        # Update the checkpoint so that the
                        # program doesn't read the events that it
                        # has already read when you run it next time.
                        (
                            self.checkpoint,
                            self.partition_ids,
                        ) = checkpoint_obj_update.update_checkpoint(
                            self.checkpoint,
                            partition_id,
                            event.sequence_number,
                            self.partition_ids,
                        )
                else:
                    logging.info(
                        "Not ingesting events for partition id %d, failure occurred.",
                        partition_id)

            else:
                checkpoint_obj_update.update_checkpoint_file(self.checkpoint)
                self.receive = False
        except Exception as exception:
            logging.error("Exception occurred %s", exception)

    async def fetch_events(self, client):
        """Create eventhub event by ensure_future."""
        try:
            checkpoint_obj = Checkpoint()
            checkpoint, self.checkpoint, self.partition_ids = checkpoint_obj.get_checkpoint(
                self.checkpoint, self.partition_ids)

            event_hub_event = asyncio.ensure_future(
                client.receive(
                    on_event=self.on_event,
                    starting_position=checkpoint,
                    max_wait_time=30,
                )
            )
            while True:
                await asyncio.sleep(5)
                if not self.receive:
                    event_hub_event.cancel()
                    break
        except Exception as exception:
            logging.error(
                "Exception occurred while fetching events %s",
                exception)

    def get_eventhub_partitions(self):
        """Get partitions of eventhub.

        Returns:
            list: list of partition_ids
        """
        try:
            client = sync_client.from_connection_string(
                conn_str=self.event_hub_connec_str,
                consumer_group=os.environ.get('ConsumerGroup'),
                eventhub_name=self.event_hub_name,
            )
            for partiton_id in client.get_partition_ids():
                self.partitions_block_list[partiton_id] = True
        except Exception as exception:
            logging.error(
                "Exception occurred while fetching Eventhub partitions %s",
                exception)
        else:
            return client.get_partition_ids()
        return None

    def start_event(self):
        """Set eventhub loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Authenticating the eventhub client
            auth_client = self.auth_client()
            eventhub_obj = Eventhub()
            self.partition_ids = self.get_eventhub_partitions()
            loop.run_until_complete(self.fetch_events(auth_client))
            loop.run_until_complete(eventhub_obj.close(auth_client))
        except Exception as exception:
            logging.info("Exception occurred at start event %s", exception)


def main(mytimer: func.TimerRequest) -> None:
    """Begin main routine."""
    utc_timestamp = (
        datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc).isoformat())
    event_obj = Eventhub()
    event_obj.start_event()

    if mytimer.past_due:
        logging.info("The timer is past due!")

    logging.info("Python timer trigger function executed at %s", utc_timestamp)
