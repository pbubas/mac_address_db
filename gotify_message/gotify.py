import requests
import json

class GotifyNotification:
        CONTENT_TYPE='plain'

        def __init__(self, url, app_token:str, title:str, message:str, priority:int=5):
                self.url = url + '/message'
                self.headers={'X-Gotify-Key': app_token, 'Content-type': 'application/json'}
                self.payload = {
                        "title": title,
                        "priority": priority,
                        "message": message,
                        "extras": { 'client::display': 
                                { 'contentType': 'text/'+self.CONTENT_TYPE } 
                        }
                }

        def send(self):
                return requests.post(self.url, 
                                headers=self.headers, 
                                json=self.payload
                                )
        @property
        def json(self):
                return json.dumps(self.__dict__, indent=4)


