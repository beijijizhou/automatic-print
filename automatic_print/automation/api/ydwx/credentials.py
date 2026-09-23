"""Compatibility facade for the shared factory gateway key."""

from automatic_print.automation.api.gateway_credentials import (
    cache_key_file, gateway_client_key, share_key_file, shared_client_key,
)


def client_key(*, refresh_share=False):
    return shared_client_key(
        refresh_share=refresh_share,
        packaged_key=gateway_client_key(),
    )
