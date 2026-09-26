import requests 
from dotenv import load_dotenv
import os
load_dotenv()
import logging
import datetime as dt
from datetime import timezone

logger = logging.getLogger(__name__)

class IGDBClient():

    def __init__(self):
        access_token = None
        access_token_expiration_date = None
        self.create_access_token()


    def create_access_token(self):
        data = {
            "client_id" : os.getenv("CLIENTID"),
            "client_secret" : os.getenv("CLIENTSECRET"),
            "grant_type" : "client_credentials"
        }

        result = requests.post("https://id.twitch.tv/oauth2/token", data = data)

        self.access_token = result.json()['access_token']

        expiration_time = result.json()['expires_in']
        self.access_token_expiration_date = dt.datetime.now(tz= timezone.utc) + (dt.timedelta(seconds=expiration_time) - dt.timedelta(minutes=5))


    def get_alt_url(self, game_name):
        if dt.datetime.now(tz= timezone.utc) >= self.access_token_expiration_date:
            self.create_access_token()
        
        header = {
            "Client-ID" : os.getenv("CLIENTID"),
            "Authorization" : f"Bearer {self.access_token}"
        }
        url = "https://api.igdb.com/v4/games"
        data = f'''search "{game_name}"; fields name, cover.url; limit 1;'''

        request = requests.post(url = url, headers = header, data = data)

        # Refresh the token in the case it expires before the expiration time
        if request.status_code == 401:
            self.create_access_token()
            header = {
                "Client-ID" : os.getenv("CLIENTID"),
                "Authorization" : f"Bearer {self.access_token}"
            }
            request = requests.post(url = url, headers = header, data = data)

        result = request.json()
        if len(result) == 0:
            logger.info("Could not find any results")
            return None
        if not result or 'cover' not in result[0]:
            logger.info("Could not find a cover image")
            return None
        
        img = result[0]['cover']['url']

        return f"http:{img}"
