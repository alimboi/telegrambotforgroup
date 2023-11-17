from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import ChatTypeFilter
import logging
import asyncio
from task_manager import TaskManager
from utils import sanitize_group_name, append_group_to_file, get_list_of_groups_as_commands

API_TOKEN = '5940765854:AAEvo4IUJEmrNuuv9EXEdFhvxSI15YDJoEE'
OWNER_ID = 5288036324 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
task_manager = TaskManager()

logging.basicConfig(level=logging.INFO)

user_data = {}

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
    commands = await get_list_of_groups_as_commands()
    command_list_message = "\n".join(commands)
    await message.reply(f"Guruhni tanlang:\n{command_list_message}")
    user_data[message.from_user.id] = {'stage': 'awaiting_group_selection'}

@dp.message_handler(user_id=OWNER_ID)
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    if message.get_command():
        command = message.get_command()[1:]
        if user_data.get(user_id, {}).get('stage') == 'awaiting_group_selection':
            await process_group_selection(user_id, command, message)
            return
        elif command in [sanitize_group_name(task_info['group_name']) for task_info in task_manager.get_active_tasks()]:
            await handle_stop_task_by_group_name(message, command)
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
        await message.reply("How often should I send this message?\n" + scheduling_options)

    elif user_data[user_id]['stage'] == 'awaiting_timer':
        if message.text.startswith('/har_'):
            interval = get_interval_from_command(message.text)
            if interval is not None:
                selected_group_id = user_data[user_id]['group']
                scheduled_message = user_data[user_id]['scheduled_message']

                group_name = None
                for group in open('group_data.txt', 'r').readlines():
                    gid, name = group.strip().split(':')
                    if gid == selected_group_id:
                        group_name = name
                        break

                if group_name:
                    task_manager.start_task(selected_group_id, group_name, scheduled_message, interval, send_message_to_group)
                    await message.reply(f"Quyidagi xabar: '{scheduled_message[:10]}...' har {message.text[7:]} da  {group_name} guruhga yuboriladi.")
                    user_data[user_id]['stage'] = None
                else:
                    await message.reply("Group not found.")
            else:
                await message.reply("Invalid option selected. Please try again.")
        else:
            await message.reply("Please select one of the given options.")

async def process_group_selection(user_id, command, message):
    selected_group_id = None
    for group in open('group_data.txt', 'r').readlines():
        gid, name = group.strip().split(':')
        if sanitize_group_name(name) == command:
            selected_group_id = gid
            break

    if selected_group_id:
        user_data[user_id] = {
            'stage': 'awaiting_message',
            'group': selected_group_id
        }
        await message.reply("Itimos guruhga yuborilishi kerak bo'lgan xabarni kiriting.")
    else:
        await message.reply("Invalid selection. Please enter a valid command.")

def get_interval_from_command(command):
    command_to_interval = {
        '/har_bir_soat': 3600,
        '/har_bir_kun': 86400,
        '/har_bir_hafta': 604800,
        '/har_3_sekund': 3
    }
    return command_to_interval.get(command)


async def handle_stop_task_by_group_name(message: types.Message, command_group_name: str):
    for task_info in task_manager.get_active_tasks():
        if sanitize_group_name(task_info['group_name']) == command_group_name:
            task_manager.stop_task(task_info['task_id'])
            await message.reply(f" {task_info['group_name']} guruhiga jo'natilayotgan xabar to'xtatildi")
            return
    await message.reply("Task not found.")

@dp.message_handler(commands=['stop'], user_id=OWNER_ID)
async def stop_command_handler(message: types.Message):
    active_tasks = task_manager.get_active_tasks()
    if not active_tasks:
        await message.reply("No active tasks.")
        return

    reply_message = ""
    for task_info in active_tasks:
        # Generate a command string for each task
        command = f"/{sanitize_group_name(task_info['group_name'])}"
        # Format task details
        task_details = f"Task ID: {task_info['task_id']} - {command} - Message: {task_info['message'][:10]}..., Interval: {task_info['interval']}s"
        # Append to the reply message
        reply_message += task_details + "\n"
        # Log the task details to the terminal
        logging.info(task_details)

    await message.reply(reply_message)

@dp.message_handler(commands=['stop_task'], user_id=OWNER_ID)
async def handle_stop_task(message: types.Message):
    # Extract the full command text (including task_id)
    full_command = message.get_full_command()[0]
    
    # Assuming the command format is "/stop_task_<task_id>"
    task_id_prefix = "/stop_task_"
    if full_command.startswith(task_id_prefix):
        task_id_to_stop = full_command[len(task_id_prefix):]

        # Attempt to stop the task with the given task ID
        task_stopped = task_manager.stop_task(task_id_to_stop)
        if task_stopped:
            await message.reply(f"Stopped task with ID {task_id_to_stop}")
        else:
            await message.reply("Task not found or already stopped.")
    else:
        await message.reply("Invalid task command format.")



if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
