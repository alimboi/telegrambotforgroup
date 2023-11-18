from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import asyncio
import re
import os
import time

API_TOKEN = 'bot_token'
OWNER_ID = user_id

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

        append_group_to_file(group_id, group_name, task_id)  
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
                    logging.info(f"Task stopped: {task_id} for group {group_id}")
                    return True

        logging.warning(f"topshiriq topilmadi: {task_id}")  # If task is not found
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

def sanitize_group_name(group_name):
    """
    Sanitizes the group name by replacing spaces with underscores
    and removing non-alphanumeric characters.
    """
    return re.sub(r'\W+', '', group_name.replace(' ', '_'))


def append_group_to_file(group_id, group_title, task_id=None):
    """
    Appends or updates the group ID, title, and task ID (if provided) in the group_data.txt file.
    If the file doesn't exist, it creates it.
    """
    file_exists = os.path.exists("group_data.txt")
    new_line = f"{group_id}:{group_title}:{task_id if task_id else ''}\n"
    
    if file_exists:
        # Read existing lines
        with open("group_data.txt", "r") as file:
            lines = file.readlines()
        
        # Check if group_id already exists
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{group_id}:"):
                lines[i] = new_line  # Update the existing line
                updated = True
                break

        # Write back the updated lines
        with open("group_data.txt", "w") as file:
            file.writelines(lines)
        
        if not updated:
            # Append new group
            with open("group_data.txt", "a") as file:
                file.write(new_line)
    else:
        # Create new file with the group
        with open("group_data.txt", "w") as file:
            file.write(new_line)


# Reviewing and potentially modifying the get_list_of_groups_as_commands function

def get_list_of_groups_as_commands():
    """
    Reads the group_data.txt file and generates a list of commands
    based on the group titles.
    """
    try:
        with open("group_data.txt", "r") as file:
            groups = file.readlines()

        if not groups:
            return ["No groups available"]

        # Generating commands for each group
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
    commands = get_list_of_groups_as_commands()  # Removed 'await' here
    command_list_message = "\n".join(commands)
    await message.reply(f"Guruhni tanlang:\n{command_list_message}")
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
            await message.reply("iltimos quyidagi buyruq orqali buyruqni kiriting: /guruhga jonatilayotgan xabarni tanlash")
        return
    
    if user_id not in user_data:
        return
    
    if message.text.startswith('/stop'):
        await stop_command_handler(message)
        return

    if user_data[user_id]['stage'] == 'awaiting_group_selection':
        await process_group_selection(user_id, message.get_command()[1:], message)

    elif user_data[user_id]['stage'] == 'awaiting_message':
        user_data[user_id]['scheduled_message'] = message.text
        user_data[user_id]['stage'] = 'awaiting_timer'
        scheduling_options = "/har_bir_soat \n/har_bir_kun \n/har_bir_hafta \n/har_3_sekund "
        await message.reply("bu xabar qancha vaqt oraligida jonatilishi kerak?\n" + scheduling_options)

    elif user_data[user_id]['stage'] == 'awaiting_timer':
        if message.text.startswith('/har_'):
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
                        await message.reply(f" '{scheduled_message[:20]}...' xabari har {message.text[7:]} da {group_name} guruhiga yuboriladi.")
                        user_data[user_id]['stage'] = None
                    else:
                        await message.reply("guruh topilmadi.")
                except FileNotFoundError:
                    await message.reply("guruh topilmadi.")
            else:
                await message.reply("tanlov togri emas. yuqoridagilardan birini tanlang.")
        else:
            await message.reply("yuqoridagilardan birini tanlang.")

async def process_group_selection(user_id, command, message):
    selected_group_id = None
    try:
        with open('group_data.txt', 'r') as file:
            for group in file.readlines():
                parts = group.strip().split(':')
                if len(parts) >= 2:
                    gid, name = parts[0], parts[1]
                    if sanitize_group_name(name) == command:
                        selected_group_id = gid
                        break

        if selected_group_id:
            user_data[user_id] = {
                'stage': 'awaiting_message',
                'group': selected_group_id
            }
            await message.reply("iltimos guruhga jonatiladigan xabarni kiriting.")
        else:
            await message.reply("togri tanlanmadi")
    except FileNotFoundError:
        await message.reply("guruh topilmadi")


def get_interval_from_command(command):
    command_to_interval = {
        '/har_bir_soat': 3600,
        '/har_bir_kun': 86400,
        '/har_bir_hafta': 604800,
        '/har_3_sekund': 3
    }
    return command_to_interval.get(command)


async def handle_stop_task_by_group_name_and_id(message: types.Message, command_group_name: str, task_id: str):
    for task_info in task_manager.get_active_tasks():
        sanitized_group_name = sanitize_group_name(task_info['group_name'])
        if sanitized_group_name == command_group_name and task_info['task_id'] == task_id:
            task_manager.stop_task(task_info['task_id'])
            await message.reply(f" {task_id}  {sanitized_group_name} guruhiga jonatilayotgan xabar toxtatildi")
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
        # Enhancing button text to include more information about the task
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
        await bot.send_message(callback_query.from_user.id, "jonatilayotgan xabar mavjud emas")









if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
