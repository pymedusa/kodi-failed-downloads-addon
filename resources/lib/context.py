# -*- coding: utf-8 -*-

import xbmc
import xbmcaddon
import xbmcgui
import requests
from requests.compat import urljoin
from requests.exceptions import HTTPError
import json
import os, sys
import jwt


addon = xbmcaddon.Addon()
addon_name = addon.getAddonInfo('name')
dialog = xbmcgui.Dialog()

TIMEOUT = 60


def dialog_notification(message, heading='Medusa failed downloads', icon=xbmcgui.NOTIFICATION_INFO):
    dialog.notification(heading, message, icon)


def dialog_ok(line1, *args, **kwargs):
    dialog.ok(addon_name, line1)


class MedusaApi(object):
    """Class for communicating with Medusa's apiv1, apiv2 and webroutes."""
    MEDUSA_SESSION = requests.Session()
    MEDUSA_API_V2_SESSION = requests.Session()
    MEDUSA_API_V1_SESSION = requests.Session()

    def __init__(self, settings):
        self.url = settings.url
        self.username = settings.username
        self.password = settings.password
        self.dialog = xbmcgui.Dialog()
        self.api_key = ''

    def authenticate(self):
        """
        Authenticate against /api/v2/authenticate and use the username/password to get the jwt token.
        The jwt token is decoded without verification to get the api-key
        """
        response = None
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            url = urljoin(self.url, 'api/v2/authenticate')
            data = {
                "username": self.username,
                "password": self.password
            }
            response = MedusaApi.MEDUSA_SESSION.post(url, json=data, headers=headers, verify=False, timeout=TIMEOUT)
            response.raise_for_status()
        except HTTPError as error:
            xbmc.log(
                'Oeps something went wrong, couldn not authenticate to {0} with error: {1}'.format(
                    self.url, error
                ),
                xbmc.LOGWARNING)
        except Exception as error:
            xbmc.log(
                'Oeps something went wrong, couldn not authenticate to {0} with error: {1}'.format(
                    self.url, error
                ), xbmc.LOGWARNING)

        try:
            jwt_encoded = response.json() if response else response
        except (AttributeError, ValueError):
            return None

        # Decode the jwt into the api-key
        if jwt_encoded.get('token'):
            decoded = jwt.decode(jwt_encoded['token'], '', algorithms=['HS256'], verify=False, timeout=TIMEOUT)
            MedusaApi.MEDUSA_API_V2_SESSION.headers.update({
                'X-Api-Key': decoded['apiKey']
            })
            self.api_key = decoded['apiKey']

    def get_series(self, tvdb_id=''):
        """
        Get all Medusa series.

        Because we can't currently search series using an IMDB id, we're retrieving all series, and mathing them one by one.
        """
        try:
            response = self.api_v2_request('api/v2/series')
            response.raise_for_status()
        except HTTPError:
            dialog_notification('Failed retrieving series', xbmcgui.NOTIFICATION_WARNING)
        except RequestException as error:
            dialog_notification(
                'Something went wrong trying to connect to {url}. Error: {error}'.format(
                    url=self.url, error=error
                ),
                xbmcgui.NOTIFICATION_WARNING
            )
        else:
            series = response.json()
            if not len(response.json()):
                dialog_notification("Your medusa library doesn't have any shows.", xbmcgui.NOTIFICATION_WARNING)
                return
            if tvdb_id:

                for show in series:
                    show_id = show['id']
                    show_tvdb = show_id.get('tvdb')
                    if str(show_tvdb) == tvdb_id:
                        return show
            else:
                return series

    def api_v1_request(self, params):
        """
        Request a resource using medusa's api v2.

        Example of full request: http://localhost:8081/mywebroot/api/v1/[apikey]/?cmd=episode.search&indexerid=260449&season=1&episode=1&tvdbid=260449
        """
        if not MedusaApi.MEDUSA_API_V2_SESSION.headers.get('X-Api-Key'):
            dialog_notification('Your not authenticated to medusas api v2!', xbmcgui.NOTIFICATION_WARNING)

        url_with_api_key = urljoin(self.url, 'api/v1/{key}/'.format(key=self.api_key))
        headers = {
            'X-Requested-With': 'XMLHttpRequest'
        }
        return MedusaApi.MEDUSA_API_V1_SESSION.get(url_with_api_key, params=params, headers=headers, verify=False, timeout=TIMEOUT)

    def api_v2_request(self, url):
        """Request a resource using medusa's api v2."""
        if not MedusaApi.MEDUSA_API_V2_SESSION.headers.get('X-Api-Key'):
            dialog_notification('Your not authenticated to medusas api v2!', xbmcgui.NOTIFICATION_WARNING)

        full_url = urljoin(self.url, url)
        return MedusaApi.MEDUSA_API_V2_SESSION.get(full_url, verify=False, timeout=TIMEOUT)

    def web_request(self, url, params):
        """Request a resource using medusa's web_request."""
        full_url = urljoin(self.url, url)
        return MedusaApi.MEDUSA_SESSION.get(full_url, params=params, verify=False, timeout=TIMEOUT)


class MedusaFailed(object):
    def __init__(self, settings):
        self.settings = settings
        self.addon = xbmcaddon.Addon()
        self.addon_name = self.addon.getAddonInfo('name')
        self.medusa = MedusaApi(settings)
        self.medusa.authenticate()

    def match_series(self, episode_db_id):
        tvdb_id = None

        # Get episode details
        json_data = {
            "jsonrpc": "2.0", "id": "1", "method": "VideoLibrary.GetEpisodeDetails",
            "params": {
                "episodeid": int(episode_db_id), "properties": ["tvshowid"]
            }
        }
        response = xbmc.executeJSONRPC(json.dumps(json_data))
        json_response = json.loads(response.decode('utf-8', 'replace'))

        # Get show details
        json_data = {
            "jsonrpc": "2.0", "id": 1,
            "method": "VideoLibrary.GetTVShowDetails",
            "params": {"tvshowid": json_response['result']['episodedetails']['tvshowid'], "properties": ["imdbnumber"]}
        }
        response = xbmc.executeJSONRPC(json.dumps(json_data))
        json_response = json.loads(response.decode('utf-8', 'replace'))

        if json_response.get('result'):
            tvdb_id = json_response['result']['tvshowdetails']['imdbnumber']

        if tvdb_id:
            return self.medusa.get_series(tvdb_id)

    def run(self):
        # Implement what your contextmenu aims to do here
        # For example you could call executebuiltin to call another addon
        #   xbmc.executebuiltin("RunScript(script.example,action=show)")
        # You might want to check your addon.xml for the visible condition of your contextmenu
        # Read more here http://kodi.wiki/view/Context_Item_Add-ons

        list_item_show_title = sys.listitem.getVideoInfoTag().getTVShowTitle()
        list_item_season = sys.listitem.getVideoInfoTag().getSeason()
        list_item_episode = sys.listitem.getVideoInfoTag().getEpisode()

        # Let's match kodi's episode dbId -> kodi's series dbId -> medusa's tvdb id.
        series = self.match_series(sys.listitem.getVideoInfoTag().getDbId())

        if not series:
            dialog_notification("Medusa could not locate series {0}".format(
                list_item_show_title), xbmcgui.NOTIFICATION_WARNING
            )
            return

        # Start a new forced search
        dialog_notification('Started search for for S{season}E{episode} of show {show}'.format(
                season=list_item_season, episode=list_item_episode, show=list_item_show_title
        ), xbmcgui.NOTIFICATION_INFO)

        try:
            response = self.medusa.api_v1_request(params={
                'cmd': 'episode.search', 'indexerid': series['id']['tvdb'],
                'season': list_item_season, 'episode': list_item_episode, 'tvdbid': series['id']['tvdb']
            })
            response.raise_for_status()
        except HTTPError as error:
            dialog_notification(
                'Error while trying to start a search. Error: {error}'.format(error=error),
                xbmcgui.NOTIFICATION_WARNING
            )
        except RequestException as error:
            dialog_notification(
                'Something went wrong trying to connect to {url}. Error: {error}'.format(
                    url=self.medusa.url, error=error
                ),
                xbmcgui.NOTIFICATION_WARNING
            )
        else:
            json_response = response.json()
            if json_response.get('result') not in ('failure',):
                dialog_ok('Successful started search for S{season}E{episode} of show {show}'.format(
                    season=list_item_season, episode=list_item_episode, show=list_item_show_title
                ))
            else:
                dialog_notification(
                    'Error while searching for episode. Error: {error}'.format(error=json_response.get('message')),
                    xbmcgui.NOTIFICATION_WARNING
                )
