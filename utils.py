import re

def sanitize_group_name(group_name):
    """
    Sanitizes the group name by replacing spaces with underscores
    and removing non-alphanumeric characters.
    """
    return re.sub(r'\W+', '', group_name.replace(' ', '_'))

def append_group_to_file(group_id, group_title):
    """
    Appends the group ID and title to the group_data.txt file.
    """
    with open("group_data.txt", "a") as file:
        file.write(f"{group_id}:{group_title}\n")

async def get_list_of_groups_as_commands():
    """
    Reads the group_data.txt file and generates a list of commands
    based on the group titles.
    """
    try:
        with open("group_data.txt", "r") as file:
            groups = file.readlines()
        # Ensure that each line has two parts after splitting
        return [f"/{sanitize_group_name(name.strip().split(':')[1])}" for name in groups if len(name.strip().split(':')) == 2]
    except FileNotFoundError:
        return ["No groups available"]
