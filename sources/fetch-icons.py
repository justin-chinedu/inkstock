import asyncio
from codecs import StreamWriter
import json
import aiofiles
from aiohttp import BasicAuth, ClientResponse, ClientSession
import requests
import multiprocessing as mp

session = requests.session()
session.headers["Authorization"] = "token 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"


async def get_dir_list(base_url, session):
    async with ClientSession(headers={"Authorization": "token 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"}) as session:
        resp: ClientResponse = await session.get(url=base_url)
        json = await resp.json()
        t = type(json)
        try:
            dir_list: list = list(map(lambda x: {
                "name": x["name"],
                "type": x["type"],
                "url": x["url"],
                "download_url": x["download_url"]}, json))
            return dir_list
        except:
            await asyncio.sleep(5)
            return get_dir_list(base_url, session)

async def getx_dir_list(base_url, session):
    response = session.get(base_url)
    json = response.json()
    t = type(json)
    try:
        dir_list: list = list(map(lambda x: {
            "name": x["name"],
            "type": x["type"],
            "url": x["url"],
            "download_url": x["download_url"]}, json))
        return dir_list
    except:
        await asyncio.sleep(5)
        return get_dir_list(base_url, session)


async def save_json_file(json_file):
    async with aiofiles.open('/sdcard/material-icons-final.json', mode='wt') as f:
        await f.write(json.dumps(json_file, indent=4))
        await f.flush()

count = 0
dir_count = 0
current_level = 0
current_dir = ""
dir_mapping = {}


async def get_files(base_url):
    global current_level
    global dir_mapping
    global save_json_file
    global count
    global dir_count
    global current_dir

    current_level += 1

    if current_level > 8:
        current_dir = current_dir[0:current_dir.rindex('/')]
        current_level -= 1
        return

    for dir in await get_dir_list(base_url, session):
        if dir["type"] == "dir":
            
            current_dir = current_dir + '/' + dir["name"]
            #dir_mapping[current_dir] = None
            dir_count += 1
            print(f"fetched {dir_count} dirs ... ")
            await get_files(dir["url"])
        elif dir["type"] == "file":
            # if not dir_mapping[current_dir]:
            #     dir_mapping[current_dir] = []
            #dir_mapping[current_dir].append(dir)
            dir_mapping[dir["name"][0:dir["name"].rindex('.svg')] + "-" + current_dir[1:]] = dir["url"]
            count += 1
            print(f"fetched {count} files ... ")

    if current_dir:
        current_dir = current_dir[0:current_dir.rindex('/')]
    current_level -= 1
    return

def main():
    base_url = "https://api.github.com/repos/google/material-design-icons/contents/src"
    fa_base_url = "https://api.github.com/repos/fortawesome/font-awesome/contents/svgs"

    asyncio.run(get_files(fa_base_url))

    # with open('/sdcard/material-icons.json') as f:
    #     icon_map: dict = json.load(f)
    # new_map : dict = {}
    # def create_links(key: str):
    #     if key.count('/') > 1:
    #         icon_name_list = key.split('/')
    #         icon_name = icon_name_list[2] + '-' + icon_name_list[1]
    #         new_map[icon_name] = "https://raw.githubusercontent.com/google/material-design-icons/master/src" + key + "/materialicons/24px.svg"
    #         new_map[icon_name  + "-outlined"] = "https://raw.githubusercontent.com/google/material-design-icons/master/src" + key + "/materialiconsoutlined/24px.svg"
    #         new_map[icon_name  + "-round"] = "https://raw.githubusercontent.com/google/material-design-icons/master/src" + key + "/materialiconsround/24px.svg"
    #         new_map[icon_name  + "-sharp"] = "https://raw.githubusercontent.com/google/material-design-icons/master/src" + key + "/materialiconssharp/24px.svg"
    #         new_map[icon_name  + "-twotone"] = "https://raw.githubusercontent.com/google/material-design-icons/master/src" + key + "/materialiconstwotone/24px.svg"
    # list(map(create_links, list(icon_map.keys())))
    asyncio.run(save_json_file(dir_mapping))

if __name__ == "__main__":
    main()
