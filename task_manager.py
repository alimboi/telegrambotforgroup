import asyncio
import time
import logging

class TaskManager:
    def __init__(self):
        # Tasks stored under each group_id
        self.tasks = {}

    async def _send_message_at_interval(self, group_id, message, interval, callback):
        while True:
            await callback(group_id, message)
            await asyncio.sleep(interval)

    def start_task(self, group_id, group_name, message, interval, callback):
        """
        Start a new task for sending messages at a specified interval.
        Allows multiple tasks per group.
        """
        task_id = f"{group_id}_{int(time.time())}"  # Unique task identifier

        task_info = {
            'task_id': task_id,
            'group_id': group_id,
            'group_name': group_name,
            'message': message,
            'interval': interval,
            'task': asyncio.create_task(self._send_message_at_interval(group_id, message, interval, callback))
        }

        if group_id not in self.tasks:
            self.tasks[group_id] = []
        self.tasks[group_id].append(task_info)

        logging.info(f"Task started: {task_id}")  # Log the task ID

        return task_id  # Optionally return the task_id for reference

    def stop_task(self, task_id):
        """
        Stop an ongoing task.
        """
        for group_id, tasks in self.tasks.items():
            for task_info in tasks:
                if task_info['task_id'] == task_id:
                    task_info['task'].cancel()
                    tasks.remove(task_info)
                    logging.info(f"Task stopped: {task_id} for group {group_id}")  # Log the task stop event
                    return True

        logging.warning(f"Task to stop not found: {task_id}")  # If task is not found
        return False

    def get_active_tasks(self):
        """
        Get a list of all active tasks.
        """
        active_tasks = []
        for group_id, group_tasks in self.tasks.items():
            for task_info in group_tasks:
                active_tasks.append(task_info)
        return active_tasks
