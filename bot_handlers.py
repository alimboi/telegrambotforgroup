from aiogram import types
from utils import get_list_of_groups_as_commands
from task_manager import TaskManager

async def start_command(message: types.Message, user_data):
    commands = await get_list_of_groups_as_commands()
    command_list_message = "\n".join(commands)
    await message.reply(f"Select a group by clicking a command:\n{command_list_message}")
    user_data[message.from_user.id] = {'stage': 'awaiting_group_selection'}

async def stop_command(message: types.Message, task_manager: TaskManager):
    active_tasks = task_manager.get_active_tasks()
    tasks_info = []
    for group_id, task in active_tasks.items():
        tasks_info.append(f"/stop_{group_id} - Task info here")  # Modify as needed
    reply_message = "\n".join(tasks_info) if tasks_info else "No active tasks."
    await message.reply(reply_message)

async def handle_stop_task(message: types.Message, task_manager: TaskManager):
    group_id = message.text.split('_')[1]
    task_manager.stop_task(group_id)
    await message.reply(f"Stopped task for group {group_id}")