import os
import logging

def is_admin(user_id: int, admin_ids: list = None) -> bool:
    """
    Check if user is admin
    
    Args:
        user_id (int): Telegram user ID
        admin_ids (list, optional): List of admin IDs. If None, will try to get from env
    """
    if admin_ids is None:
        # Fallback to env if not provided
        from os import getenv
        admin_ids = list(map(int, getenv('ADMIN_IDS', '').split(',')))
    
    logging.info(f"Checking admin access for user_id={user_id}, admin_ids={admin_ids}")
    is_admin = user_id in admin_ids
    logging.info(f"Admin access result for user_id={user_id}: {is_admin}")
    
    return is_admin 