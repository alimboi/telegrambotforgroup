from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import asyncio
import re
import os
import time

API_TOKEN = 'bot token'
OWNER_ID = userid

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

user_data = {}

class TaskManager:
    def __init__(self):
        # Tasks stored under each group_id
        self.tasks = {}

    async def _send_message_at_interval(self, group_id, message, interval, callback):
        while True:
            await callback(group_id, message)
            await asyncio.sleep(interval)

    def start_task(self, group_id, group_name, message, interval, callback):
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
        logging.info(f"Task started: {task_id}")
        append_task_to_file(task_id, group_id, message, interval)

    def stop_task(self, task_id):
        for group_id, tasks in self.tasks.items():
            for task_info in tasks:
                if task_info['task_id'] == task_id:
                    task_info['task'].cancel()
                    tasks.remove(task_info)
                    logging.info(f"Task stopped: {task_id} for group {group_id}")
                    return True
        logging.warning(f"Task not found: {task_id}")
        return False

    def get_active_tasks(self):
        active_tasks = []
        for group_id, group_tasks in self.tasks.items():
            active_tasks.extend(group_tasks)  # Use extend to add all tasks in the group
        return active_tasks

task_manager = TaskManager()

def sanitize_group_name(group_name):
    return re.sub(r'\W+', '', group_name.replace(' ', '_'))

def append_group_to_file(group_id, group_title):
    file_exists = os.path.exists("group_data.txt")
    new_line = f"{group_id}:{group_title}\n"
    if file_exists:
        with open("group_data.txt", "r+") as file:
            lines = file.readlines()
            file.seek(0)
            file.truncate()
            group_id_str = str(group_id)  # Convert group_id to string
            if any(group_id_str in line for line in lines):
                lines = [line if group_id_str not in line else new_line for line in lines]
            else:
                lines.append(new_line)
            file.writelines(lines)
    else:
        with open("group_data.txt", "w") as file:
            file.write(new_line)


def append_task_to_file(task_id, group_id, message, interval):
    with open("task_data.txt", "a") as file:
        file.write(f"{task_id}:{group_id}:{message}:{interval}\n")

def get_list_of_groups_as_commands():
    try:
        with open("group_data.txt", "r") as file:
            groups = file.readlines()
        if not groups:
            return ["No groups available"]
        return [f"/{sanitize_group_name(name.strip().split(':')[1])}" for name in groups if len(name.strip().split(':')) >= 2]
    except FileNotFoundError:
        return ["No groups available"]

async def send_message_to_group(group_id, message):
    await bot.send_message(chat_id=group_id, text=message)

@dp.my_chat_member_handler(ChatTypeFilter(chat_type=types.ChatType.SUPERGROUP))
async def bot_added_to_group(update: types.ChatMemberUpdated):
    if update.new_chat_member.status == 'member':
        group_id = update.chat.id
        group_title = update.chat.title
        append_group_to_file(group_id, group_title)
        logging.info(f"Added to group: {group_title} (ID: {group_id})")

@dp.message_handler(commands=['start'], user_id=OWNER_ID)
async def start_command_handler(message: types.Message):
    commands = get_list_of_groups_as_commands()
    command_list_message = "\n".join(commands)
    await message.reply(f"Select a group:\n{command_list_message}")
    user_data[message.from_user.id] = {'stage': 'awaiting_group_selection'}

@dp.message_handler(user_id=OWNER_ID)
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    if message.text.startswith('/stop_task'):
        parts = message.text.split()
        if len(parts) == 3:
            _, command_group_name, task_id = parts
            await handle_stop_task_by_group_name_and_id(message, command_group_name, task_id)
        else:
            await message.reply("Please use the following command format: /stop_task [group_name] [task_id]")
        return

    if user_id not in user_data:
        return
    
    if message.text.startswith('/stop'):
        await stop_command_handler(message)
        return

    if user_data[user_id]['stage'] == 'awaiting_group_selection':
        command = message.get_command()[1:]  # Extract command from message
        selected_group_id = None
        try:
            with open('group_data.txt', 'r') as file:
                for group in file:
                    parts = group.strip().split(':')
                    if len(parts) >= 2:
                        gid, name = parts[0], parts[1]
                        if sanitize_group_name(name) == command:
                            selected_group_id = gid
                            break

            if selected_group_id:
                user_data[user_id] = {'stage': 'awaiting_message', 'group': selected_group_id}
                await message.reply("Please enter the message to be sent to the group.")
            else:
                await message.reply("Incorrect selection. Please ensure you've entered the correct group name.")
        except FileNotFoundError:
            await message.reply("Group data file not found.")
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            await message.reply("An error occurred while processing your request.")

    elif user_data[user_id]['stage'] == 'awaiting_message':
        user_data[user_id]['scheduled_message'] = message.text
        user_data[user_id]['stage'] = 'awaiting_timer'
        scheduling_options = "/every_hour \n/every_day \n/every_week \n/every_3_seconds "
        await message.reply("How often should this message be sent?\n" + scheduling_options)

    elif user_data[user_id]['stage'] == 'awaiting_timer':
        if message.text.startswith('/every_'):
            interval = get_interval_from_command(message.text)
            if interval is not None:
                selected_group_id = user_data[user_id]['group']
                scheduled_message = user_data[user_id]['scheduled_message']
                group_name = None
                try:
                    with open('group_data.txt', 'r') as file:
                        for group in file.readlines():
                            parts = group.strip().split(':')
                            if len(parts) >= 2 and parts[0] == selected_group_id:
                                group_name = parts[1]
                                break
                    if group_name:
                        task_manager.start_task(selected_group_id, group_name, scheduled_message, interval, send_message_to_group)
                        await message.reply(f"Message '{scheduled_message[:20]}...' will be sent every {message.text[7:]} to {group_name} group.")
                        user_data[user_id]['stage'] = None
                    else:
                        await message.reply("Group not found.")
                except FileNotFoundError:
                    await message.reply("Group not found.")
            else:
                await message.reply("Invalid selection. Please choose one of the following.")
        else:
            await message.reply("Please choose one of the following.")


def get_interval_from_command(command):
    command_to_interval = {
        '/every_hour': 3600,
        '/every_day': 86400,
        '/every_week': 604800,
        '/every_3_seconds': 6
    }
    return command_to_interval.get(command)

async def handle_stop_task_by_group_name_and_id(message: types.Message, command_group_name: str, task_id: str):
    for task_info in task_manager.get_active_tasks():
        sanitized_group_name = sanitize_group_name(task_info['group_name'])
        if sanitized_group_name == command_group_name and task_info['task_id'] == task_id:
            task_manager.stop_task(task_info['task_id'])
            await message.reply(f"Task {task_id} for group {sanitized_group_name} has been stopped")
            return
    await message.reply("Task not found.")

@dp.message_handler(commands=['stop'], user_id=OWNER_ID)
async def stop_command_handler(message: types.Message):
    active_tasks = task_manager.get_active_tasks()
    if not active_tasks:
        await message.reply("No active tasks.")
        return

    inline_kb = InlineKeyboardMarkup(row_width=1)
    for task_info in active_tasks:
        button_text = f"Stop: {task_info['group_name']} - '{task_info['message'][:80]}...' (every {task_info['interval']}s)"
        callback_data = f"stop_{task_info['task_id']}"
        inline_kb.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await message.reply("Select a task to stop:", reply_markup=inline_kb)


@dp.callback_query_handler(lambda c: c.data.startswith('stop_'), user_id=OWNER_ID)
async def handle_callback_stop_task(callback_query: types.CallbackQuery):
    task_id_to_stop = '_'.join(callback_query.data.split('_')[1:])

    stopped_task_info = None
    for task in task_manager.get_active_tasks():
        if task_id_to_stop == task['task_id']:
            stopped_task_info = task
            break

    if stopped_task_info and task_manager.stop_task(task_id_to_stop):
        response_message = (
            f"Stopped task with ID {task_id_to_stop}\n"
            f"Group: {stopped_task_info['group_name']}\n"
            f"Message: '{stopped_task_info['message']}'\n"
            f"Interval: {stopped_task_info['interval']}s"
        )
        await bot.send_message(callback_query.from_user.id, response_message)
    else:
        await bot.send_message(callback_query.from_user.id, "Task not found.")


def clear_task_data_file():
    open("task_data.txt", "w").close()

if __name__ == '__main__':
    clear_task_data_file()
    executor.start_polling(dp, skip_updates=True)
