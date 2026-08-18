from mondoo.mdo.io.db.redis import *

from typing import List

import uuid


class MsgHistoryManager:
    _message_cache_name = 'message_history'
    _cache_client       = CacheHelper(_message_cache_name)

    def push_message(
        self,
        history_id : str,
        message    : dict
    ):
        record = {
            'message_id' : str(uuid.uuid4()),
            'role'       : message.role,
            'content'    : message.content
        }

        self._cache_client.write_item(
            record,
            id_field = 'message_id',
            suffix = history_id
        )


    def query_messages(
        self,
        history_id: str
    ) -> List[Dict]:

        records = self._cache_client.read_all_items(history_id)

        return records


    def delete_first_n_messages(
        self,
        history_id: str,
        n: int
    ):
        messages = self.query_messages(history_id)

        # Delete the first n messages
        for msg in messages[:n]:
            message_id = msg.get('message_id')

            if message_id:
                self._cache_client.remove_item(
                    message_id,
                    suffix=history_id
                )


    def clear_messages(
        self,
        history_id: str
    ):
        self._cache_client.clear_all_items(history_id)