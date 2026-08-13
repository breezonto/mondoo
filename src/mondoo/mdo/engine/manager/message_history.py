from mondoo.mdo.io.db.redis import *
from typing           import List

import uuid

class MessageHistoryManger:
    _message_cache_name = 'message_history'
    _cache_client       = CacheWrapper(_message_cache_name)

    def push_message(
        self,
        message_history_id : str,
        message            : dict
    ):
        record = {
            "message_id" : str(uuid.uuid4()),
            "role"       : message.role,
            "content"    : message.content
        }

        self._cache_client.write_data(
            record,
            id_field = "message_id",
            suffix = message_history_id
        )


    def query_messages(
        self,
        message_history_id: str
    ) -> List[Dict]:

        records = self._cache_client.read_all_data(message_history_id)

        return records


    def delete_first_n_messages(
        self,
        message_history_id: str,
        n: int
    ):
        messages = self.query_messages(message_history_id)

        # Delete the first n messages
        for msg in messages[:n]:
            message_id = msg.get("message_id")

            if message_id:
                self._cache_client.remove_record(
                    message_id,
                    suffix=message_history_id
                )


    def clear_messages(
        self,
        message_history_id: str
    ):
        self._cache_client.clear_all_data(message_history_id)