import os
from dotenv import load_dotenv

load_dotenv()
from steam_web_api import Steam

import datetime as dt
from datetime import timezone
from dateutil.relativedelta import relativedelta
import requests
import logging
import time
from zoneinfo import ZoneInfo
import re
import unicodedata
from difflib import SequenceMatcher


logger = logging.getLogger(__name__)
KEY = os.getenv("STEAM_API_KEY")

steam = Steam(KEY)

def get_game_news_from_steam(appid_user_dictionary, news_filter):

    to_be_added_to_filter = []
    logger.info("Started looking for relevent news from Steam client")
    today = dt.datetime.now(timezone.utc)

    date_cutoff = today - dt.timedelta(days=1)

    for appid in appid_user_dictionary:
        try:
            url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&maxlength=150&count=5"
            request = requests.get(url, timeout= 20)
            request.raise_for_status()
            news = request.json()

        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not get news for appid {appid}: {e}")
            continue

        if not news.get("appnews", {}).get("newsitems"):
            logger.info(f"No news found for appid: {appid}")
            continue

        for article in news['appnews']['newsitems']:
            article_timestamp = article['date']
            article_title = article['title']
            article_date = dt.datetime.fromtimestamp(article_timestamp, timezone.utc)
            feed_type = article['feed_type']
            article_gid = int(article['gid'])
            if article_date <= date_cutoff:
                break
            
            if feed_type == 1 and article_gid not in news_filter:
                appid_user_dictionary[appid]['news_articles'].append(article['url'])
                news_filter.append(article_gid)

                to_be_added_to_filter.append((article_title, article_gid))

    logger.info(f"All relevant news has been recorded : {appid_user_dictionary}")
    # print(appid_user_dictionary)
    return appid_user_dictionary, to_be_added_to_filter


#get_game_news(1)

def get_recently_played_games(steam_id):
    games = steam.users.get_user_recently_played_games(steam_id)

    if len(games) == 0:
        logger.error("User recently played list was not able to be found")
        return None
    if games['total_count'] == 0:
        return None

    return games

def normalize_game_name(name):
    name = unicodedata.normalize("NFKD", name)
    name = name.lower()

    # Remove trademark/copyright/registered symbols
    name = name.replace("™", "")
    name = name.replace("®", "")
    name = name.replace("©", "")

    # Normalize whitespace
    name = re.sub(r"\s+", " ", name).strip()

    return name

def check_steam_game_availability(name):
    result = steam.apps.search_games(name)

    if len(result['apps']) == 0:
        return False, None

    normalized_name = normalize_game_name(name)

    best_match = None
    best_similarity = 0

    for game in result['apps']:
        steam_name = normalize_game_name(game['name'])

        similarity = SequenceMatcher(
            None,
            normalized_name,
            steam_name
        ).ratio()

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = game

    print(
        f"Best match: {name} -> {best_match['name']} "
        f"({best_similarity:.2%})"
    )

    if best_similarity < 0.90:
        return False, None

    return True, best_match


def print_price():
    title = 2246340
    game = steam.apps.get_app_details(title,None,"price_overview")
    pricef = game['{}'.format(title)]['data']['price_overview']['final_formatted']
    return pricef

def search_for_user(name):
    user = steam.users.search_user(name)
    if user == "No match":
        return 1, None

    if user['player']['communityvisibilitystate'] != 3:
        return 2, user

    return 0, user

def search_steam_user_with_custom_id(custom_id : str):
    user = steam.users.search_user(custom_id)
    if user == "No match":
        return None
    else:
        return user
    
def verify_steam_access(steam_id : str):
    user = search_steam_user_with_custom_id(steam_id)
    if user is None:
        user = steam.users.get_user_details(steam_id)
    # The user was not found
    if user['player'] == None:
        return 1, None
    
    # The user's profile is not private
    if user['player']['communityvisibilitystate'] != 3:
        return 2, user
    # might as well just return the whole user so we can get the profile pic

    return 0, user


def get_steam_game_library(steam_id : str):
    steam_library = steam.users.get_owned_games(steam_id)
    return steam_library

# details = steam.apps.get_app_details(1230)

def look_up_steam_image_and_price(appid : int):
    details = steam.apps.get_app_details(appid)
    if details is None:
        for attempt in range(5):
            logger.warning(f"Could not get app info for appid : {appid} on try : {attempt}")
            time.sleep(60)
            print(f"sleep on attempt {attempt}")
            details = steam.apps.get_app_details(appid)
            if details is not None:
                break
    if details is None or len(details) == 0:
        return None, None
    
    for attempt in range(5):
        try:

            response_key = next(iter(details))

            if details[response_key]['success'] and len(details[response_key]['data']) != 0:
                image = details[response_key]['data']['header_image']
            else:
                image = None

            details = steam.apps.get_app_details(appid, None, "price_overview")
            if details is None or len(details) == 0:
                return image, None
            
            response_key = next(iter(details))
            if details[response_key]['success'] and len(details[response_key]['data']) != 0:
                price_overview = details[response_key]['data'].get('price_overview')

                if price_overview is not None:
                    price = price_overview.get('initial')
                else:
                    price = None
            else:
                price = None

            return image, price

        except requests.exceptions.ReadTimeout as e:
            logger.warning(f"Could not get Steam data for {appid}: {e} on attempt: {attempt}")
            if attempt < 4:
                time.sleep(3)

    logger.error(f"Could not get Steam data for {appid}")
    return None,None


def enriched_info(appid : int):
    details = steam.apps.get_app_details(appid)
    if details is None or len(details) == 0:
        for attempt in range(5):
            logger.warning(f"Could not get app info for appid : {appid} on try : {attempt}")
            time.sleep(60)
            print(f"sleep on attempt {attempt}")
            details = steam.apps.get_app_details(appid)
            if details is not None:
                break
    if details is None or len(details) == 0:
        return None, None, None
    
    for attempt in range(5):
        try:
            response_key = next(iter(details))
            if details[response_key]['success'] and len(details[response_key]['data']) != 0:
                name = details[response_key]['data']['name']
                image = details[response_key]['data']['header_image']
            else:
                name = None
                image = None     
            
            details = steam.apps.get_app_details(appid,None, "price_overview")
            if details is None or len(details) == 0:
                return name, image, None
            
            response_key = next(iter(details))
            if details[response_key]['success'] and len(details[response_key]['data']) != 0:
                price = details[response_key]['data']['price_overview']['initial']
            else:
                price = None

            return name, image, price

        except requests.exceptions.ReadTimeout as e:
            logger.warning(f"Could not get Steam data for {appid}: {e} on attempt: {attempt}")
            if attempt < 4:
                time.sleep(3)

    logger.error(f"Could not get Steam data for {appid}")
    return None,None, None
# if __name__ == "__main__":
#     pass
    #link_steam_library(add_steam_game_library("76561198965639452",None))
    #print(add_steam_game_library("76561198965639452",None,None))

# games = get_recently_played_games(76561198138082742)
# print(games)