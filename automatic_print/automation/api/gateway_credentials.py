"""Shared restricted client key for Supabase ERP gateway functions."""

import os


def gateway_client_key():
    packaged_key = ""
    try:
        from .s2b.deployment import S2B_BATCH_INFO_KEY
        packaged_key = str(S2B_BATCH_INFO_KEY).strip()
    except ImportError:
        pass
    return os.environ.get("AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY", "").strip() or packaged_key
