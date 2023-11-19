from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import ChatTypeFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import asyncio
import re
import os
import time

API_TOKEN = '5940765854:AAEvo4IUJEmrNuuv9EXEdFhvxSI15YDJoEE'
OWNER_ID = 5288036324

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

    def start_task(self, group_id, group_name, message, interval, callback, task_name):
        """
        Start a new task for sending messages at a specified interval.
        Uses the provided task_name as a unique identifier.
        """
        if not append_task_info_to_file(group_id, task_name):
            logging.warning(f"Task name already in use: {task_name}")
            return False  # Indicate that task start failed due to duplicate name

        task_id = task_name  # Unique task identifier based on user input

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

    def stop_task(self, task_name):
        """
        Stop an ongoing task by its name and remove it from the task_data.txt file.
        """
        task_stopped = False
        for group_id, tasks in self.tasks.items():
            for task_info in tasks:
                if task_info['task_id'] == task_name:
                    task_info['task'].cancel()
                    tasks.remove(task_info)
                    task_stopped = True
                    logging.info(f"Task stopped: {task_name} for group {group_id}")
                    break

            if task_stopped:
                break

        if task_stopped:
            self._remove_task_from_file(task_name)
            return True

        logging.warning(f"Task not found: {task_name}")
        return False

    def _remove_task_from_file(self, task_name):
        """
        Remove a task from the task_data.txt file.
        """
        with open("task_data.txt", "r") as file:
            lines = file.readlines()

        with open("task_data.txt", "w") as file:
            for line in lines:
                if task_name not in line:
                    file.write(line)

    def get_active_tasks(self):
        """
        Get a list of all active tasks.
        """
        active_tasks = []
        for group_id, group_tasks in self.tasks.items():
            for task_info in group_tasks:
                active_tasks.append(task_info)
        return active_tasks

    def is_task_name_in_use(self, task_name):
        """
        Check if the given task name is already in use.
        """
        try:
            with open("task_data.txt", "r") as file:
                for line in file:
                    if task_name in line:
                        return True
            return False
        except FileNotFoundError:
            return False


task_manager = TaskManager()

def sanitize_group_name(group_name):
    """
    Sanitizes the group name by replacing spaces with underscores
    and removing non-alphanumeric characters.
    """
    return re.sub(r'\W+', '', group_name.replace(' ', '_'))


def append_group_info_to_file(group_id, group_title):
    """
    Appends the group ID and title to the group_data.txt file.
    """
    with open("group_data.txt", "a") as file:
        file.write(f"{group_id}:{group_title}\n")

def append_task_info_to_file(group_id, task_name):
    """
    Appends the task information to the task_data.txt file.
    """
    with open("task_data.txt", "a") as file:
        file.write(f"{group_id}:{task_name}\n")


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
        append_group_info_to_file(group_id, group_title)
        logging.info(f"Added to group: {group_title} (ID: {group_id})")



@dp.message_handler(commands=['start'], user_id=OWNER_ID)
async def start_command_handler(message: types.Message):
    commands = get_list_of_groups_as_commands()
    command_list_message = "\n".join(commands)
    await message.reply(f"Please choose a group:\n{command_list_message}")
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
            await message.reply("Please use the following format to stop a task: /stop_task <group_name> <task_id>")
        return
    
    if user_id not in user_data:
        return
    
    if message.text.startswith('/stop'):
        await stop_command_handler(message)
        return

    if user_data[user_id]['stage'] == 'awaiting_group_selection':
        await process_group_selection(user_id, message.get_command()[1:], message)

    elif user_data[user_id]['stage'] == 'awaiting_task_name':
        task_name = message.text.strip()
        if task_manager.is_task_name_in_use(task_name):
            await message.reply("This task name already exists. Please try a different name.")
        else:
            user_data[user_id]['task_name'] = task_name
            user_data[user_id]['stage'] = 'awaiting_message'
            await message.reply("Please send the message you want to schedule.")

    elif user_data[user_id]['stage'] == 'awaiting_message':
        user_data[user_id]['scheduled_message'] = message.text
        user_data[user_id]['stage'] = 'awaiting_timer'
        scheduling_options = "/har_bir_soat \n/har_bir_kun \n/har_bir_hafta \n/har_3_sekund "
        await message.reply("How often should this message be sent?\n" + scheduling_options)

    elif user_data[user_id]['stage'] == 'awaiting_timer':
        command = message.text.split()[0]  # Extracts the first word of the message, assuming it's the command
        if command.startswith('/har'):
            interval = get_interval_from_command(command)
            if interval is not None:
                selected_group_id = user_data[user_id]['group']
                scheduled_message = user_data[user_id]['scheduled_message']
                task_name = user_data[user_id]['task_name']

                group_name = None
                try:
                    with open('group_data.txt', 'r') as file:
                        for group in file.readlines():
                            parts = group.strip().split(':')
                            if len(parts) >= 2 and parts[0] == selected_group_id:
                                group_name = parts[1]
                                break

                    if group_name:
                        if not task_manager.is_task_name_in_use(task_name):
                            task_manager.start_task(selected_group_id, group_name, scheduled_message, interval, send_message_to_group, task_name)
                            await message.reply(f"Task '{task_name}' will send '{scheduled_message[:20]}...' every {command[7:]} to {group_name} group.")
                            user_data[user_id]['stage'] = None
                        else:
                            await message.reply("Task name already in use. Please choose a different name.")
                    else:
                        await message.reply("Group not found.")
                except FileNotFoundError:
                    await message.reply("Group file not found.")
            else:
                await message.reply("Invalid choice. Please select one of the above options.")
        else:
            await message.reply("Please select one of the above options.")





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
                'stage': 'awaiting_task_name',  # Update to the new stage for task naming
                'group': selected_group_id
            }
            await message.reply("Please provide a unique name for the task.")
        else:
            await message.reply("Selection not recognized.")
    except FileNotFoundError:
        await message.reply("Group file not found.")



def get_interval_from_command(command):
    command_to_interval = {
        '/har_bir_soat': 3600,
        '/har_bir_kun': 86400,
        '/har_bir_hafta': 604800,
        '/har_3_sekund': 5
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
        await bot.send_message(callback_query.from_user.id, "Task not found")










if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
