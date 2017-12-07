"""
Facebook platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.facebook/
"""
import logging

from aiohttp.hdrs import CONTENT_TYPE
from requests_toolbelt import MultipartEncoder

import json
import mimetypes
import os
import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA, ATTR_TARGET, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONTENT_TYPE_JSON
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_PAGE_ACCESS_TOKEN = 'page_access_token'
BASE_URL = 'https://graph.facebook.com/v2.6/me/messages'
TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PAGE_ACCESS_TOKEN): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Facebook notification service."""
    return FacebookNotificationService(config[CONF_PAGE_ACCESS_TOKEN])


class FacebookNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Facebook service."""

    def __init__(self, access_token):
        """Initialize the service."""
        self.page_access_token = access_token

    def send_message(self, message="", **kwargs):
        """Send some message."""
        params = {'access_token': self.page_access_token}
        targets = kwargs.get(ATTR_TARGET)
        data = kwargs.get(ATTR_DATA)
        body = {}

        if not targets:
            _LOGGER.error("At least 1 target recipient is required")
            return

        _LOGGER.warn('data: {}'.format(data))

        # Only one of text or attachment can be specified
        if data is None:
            body['message'] = {'text': message}
        else:
            if 'filepath' in data:
                file_path = data.pop('filepath')
                file_type, _ = mimetypes.guess_type(file_path)
                # body['filedata'] =  '@{};type={}'.format(file_path, file_type)
                body['filedata'] = (os.path.basename(file_path), open(file_path, 'rb'), file_type)

            body['message'] = data

            if message:
                _LOGGER.warn(
                    "Facebook text ('{}') ignored. It cannot be sent in the "
                    "same request as file data".format(message)
                )

        for target in targets:
            # If the target starts with a "+", we suppose it's a phone number,
            # otherwise it's a user id.
            if target.startswith('+'):
                recipient = {'phone_number': target}
            else:
                recipient = {'id': target}

            body['recipient'] = recipient

            _LOGGER.warn('body: {}'.format(body))

            if 'filedata' in body:
                file_data = {
                    'recipient': json.dumps(body['recipient']),
                    'message': json.dumps(body['message']),
                    'filedata': body['filedata']
                }

                # multipart encode the entire payload
                multipart_data = MultipartEncoder(file_data)

                # multipart header from multipart_data
                multipart_header = {
                    'Content-Type': multipart_data.content_type
                }

                _LOGGER.warn("postin filedata: {}".format(multipart_data))

                resp = requests.post(
                    BASE_URL,
                    data=multipart_data,
                    params=params,
                    headers=multipart_header,
                    timeout=TIMEOUT
                    # files=file_data,  # Multipart
                )
            else:
                _LOGGER.warn("postin regular stuffs")
                resp = requests.post(
                    BASE_URL,
                    data=json.dumps(body),
                    params=params,
                    headers={CONTENT_TYPE: CONTENT_TYPE_JSON},
                    timeout=TIMEOUT
                )

            if resp.status_code != 200:
                obj = resp.json()
                error_message = obj['error']['message']
                error_code = obj['error']['code']
                _LOGGER.error(
                    "Error %s : %s (Code %s)", resp.status_code, error_message,
                    error_code)
