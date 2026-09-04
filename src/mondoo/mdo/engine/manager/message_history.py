from mondoo.mdo.io.db.cache import *

from typing import List

import uuid


class MsgHistoryManager:
    """
    @TODO comment
    """

    _cache_name   = 'message-history'
    _cache_client = CacheHelper(_cache_name)

    def push_message(
        self,
        history_id : str,
        message    : dict
    ):
        """
        @TODO comment
        """
            
        _message = message.copy()

        # @TODO message id should be timestamp encoded serial number
        # for convenience, temporally set it as random number

        # _message['id'] = str(uuid.uuid4())

        self._cache_client.write_item(
            _message,
            id_field = 'id',
            suffix = history_id
        )


    def query_messages(
        self,
        history_id: str
    ) -> List[Dict]:
        """
        @TODO comment
        """

        messages = self._cache_client.read_all_items(history_id)

        return messages


    def delete_first_n_messages(
        self,
        history_id: str,
        n: int
    ):
        """
        @TODO comment
        """

        messages = self.query_messages(history_id)

        # Delete the first n messages
        for msg in messages[:n]:
            message_id = msg.get('id')

            if message_id:
                self._cache_client.remove_item(
                    message_id,
                    suffix=history_id
                )


    def clear_messages(
        self,
        history_id: str
    ):
        """
        @TODO comment
        """

        self._cache_client.clear_all_items(history_id)