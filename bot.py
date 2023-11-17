

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import ChatTypeFilter
import asyncio
import re
import logging

API_TOKEN = '5940765854:AAEvo4IUJEmrNuuv9EXEdFhvxSI15YDJoEE'
OWNER_ID = 5288036324 
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

user_data = {}

def sanitize_group_name(group_name):
    return re.sub(r'\W+', '', group_name.replace(' ', '_'))

def append_group_to_file(group_id, group_title):
    with open("group_data.txt", "a") as file:
        file.write(f"{group_id}:{group_title}\n")

async def get_list_of_groups_as_commands():
    try:
        with open("group_data.txt", "r") as file:
            groups = file.readlines()
        return [f"/{sanitize_group_name(name.strip().split(':')[1])}" for name in groups]
    except FileNotFoundError:
        return ["No groups available"]

@dp.my_chat_member_handler(ChatTypeFilter(chat_type=types.ChatType.SUPERGROUP))
async def bot_added_to_group(update: types.ChatMemberUpdated):
    if update.new_chat_member.status == 'member':
        group_id = update.chat.id
        group_title = update.chat.title
        append_group_to_file(group_id, group_title)
        logging.info(f"Added to group: {group_title} (ID: {group_id})")

@dp.message_handler(commands=['start'], user_id=OWNER_ID)
async def start_command(message: types.Message):
    commands = await get_list_of_groups_as_commands()
    command_list_message = "\n".join(commands)
    await message.reply(f"Select a group by clicking a command:\n{command_list_message}")
    user_data[message.from_user.id] = {'stage': 'awaiting_group_selection'}

@dp.message_handler(user_id=OWNER_ID)
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    if user_data[user_id]['stage'] == 'awaiting_group_selection':
        command = message.get_command()
        if command:
            sanitized_command = command[1:]
            selected_group_id = None
            for group in open('group_data.txt', 'r').readlines():
                gid, name = group.strip().split(':')
                if sanitize_group_name(name) == sanitized_command:
                    selected_group_id = gid
                    break

            if selected_group_id:
                user_data[user_id] = {
                    'stage': 'awaiting_message',
                    'group': selected_group_id
                }
                await message.reply("Please send the text you want to schedule.")
            else:
                await message.reply("Invalid selection. Please enter a valid command.")
        else:
            await message.reply("Please select a group by clicking a command.")

    elif user_data[user_id]['stage'] == 'awaiting_message':
        user_data[user_id]['scheduled_message'] = message.text
        user_data[user_id]['stage'] = 'awaiting_timer'
        await message.reply("How often should I send this message? (in seconds)")

    elif user_data[user_id]['stage'] == 'awaiting_timer':
        try:
            delay = int(message.text)
            user_data[user_id]['delay'] = delay
            await message.reply(f"Got it! I'll send the message every {delay} seconds.")
            asyncio.create_task(send_messages(user_id))
        except ValueError:
            await message.reply("Please enter a valid number of seconds.")

async def send_messages(user_id):
    while user_id in user_data:
        scheduled_message = user_data[user_id].get('scheduled_message')
        delay = user_data[user_id].get('delay', 60)
        selected_group = user_data[user_id].get('group')
        if scheduled_message and selected_group:
            await bot.send_message(chat_id=selected_group, text=scheduled_message)
        await asyncio.sleep(delay)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
