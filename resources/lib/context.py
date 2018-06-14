# -*- coding: utf-8 -*-

import xbmc
import xbmcaddon
import xbmcgui
import requests
from requests.compat import urljoin
from requests.exceptions import HTTPError, RequestException
from requests.auth import HTTPBasicAuth
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
        Use the apiv2 to get the series data with the tvdb_id provided.
        """
        try:
            response = self.api_v2_request('api/v2/series/tvdb{tvdb_id}'.format(tvdb_id=tvdb_id))
            response.raise_for_status()
        except HTTPError as error:
            dialog_notification(
                'Failed retrieving series with tvdb id {tvdb_id}'.format(tvdb_id=tvdb_id), xbmcgui.NOTIFICATION_WARNING
            )
            xbmc.log('Failed retrieving series, error: {0}'.format(error), xbmc.LOGERROR)
        except RequestException as error:
            dialog_notification(
                'Something went wrong trying to connect to {url}. Error: {error}'.format(
                    url=self.url, error=error
                ),
                xbmcgui.NOTIFICATION_WARNING
            )
            xbmc.log('Something went wrong trying to connect to {url}. Error: {error}'.format(
                url=self.url, error=error
            ), xbmc.LOGERROR)
        else:
            return response.json()

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
        # Increased timeout as the forced search call is synchronous. So on large providers lists we need to wait a
        # certain time, to get back results.
        return MedusaApi.MEDUSA_API_V1_SESSION.get(
            url_with_api_key, params=params, headers=headers, verify=False, timeout=600
        )

    def api_v2_request(self, url, params=None):
        """Request a resource using medusa's api v2."""
        if not MedusaApi.MEDUSA_API_V2_SESSION.headers.get('X-Api-Key'):
            dialog_notification('Your not authenticated to medusas api v2!', xbmcgui.NOTIFICATION_WARNING)

        full_url = urljoin(self.url, url)
        return MedusaApi.MEDUSA_API_V2_SESSION.get(full_url, params=params, verify=False, timeout=TIMEOUT)

    def web_request(self, url, params):
        """Request a resource using medusa's web_request."""

        # First login.
        login_data = {
            'username': self.username,
            'password': self.password,
            'remember_me': 1,
            'submit': 'Login'
        }
        MedusaApi.MEDUSA_SESSION.post(
            urljoin(self.url, 'login'), data=login_data, headers={'Content-Type': 'application/x-www-form-urlencoded'},
            verify=False, auth=(self.username, self.password), timeout=TIMEOUT
        )

        full_url = urljoin(self.url, url)
        xbmc.log('base url: {base}, added: {added}, full: {full}'.format(
            base=self.url, added=url, full=full_url
        ), xbmc.LOGINFO)

        headers = {
            'Content-Type': 'application/json'
        }
        return MedusaApi.MEDUSA_SESSION.get(
            full_url, params=params, headers=headers, verify=False, auth=(self.username, self.password), timeout=TIMEOUT
        )


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
            xbmc.log("Found a show for provided episode id, with tvdb id: {0}".format(tvdb_id), xbmc.LOGDEBUG)

        if tvdb_id:
            return self.medusa.get_series(tvdb_id)

    def search_episode(self, show, season, episode):
        """Search for episode using a normal forced search."""
        url = 'home/searchEpisode'
        params = {
            'indexername': 'tvdb',
            'seriesid': show['id']['tvdb'],
            'season': season,
            'episode': episode
        }
        return self.medusa.web_request(url=url, params=params)

    def retry_episode(self, show, season, episode):
        """Search for episode using the failed search process."""
        url = 'home/retryEpisode'
        params = {
            'indexername': 'tvdb',
            'seriesid': show['id']['tvdb'],
            'season': season,
            'episode': episode,
            'down_cur_quality': 1
        }
        return self.medusa.web_request(url=url, params=params)

    def start_search(self, show, season, episode):
        # Start a new forced search
        dialog_notification('Started search for for S{season}E{episode} of show {show}'.format(
            season=season, episode=episode, show=show.get('title')
        ), xbmcgui.NOTIFICATION_INFO)

        try:
            response = self.retry_episode(show, season, episode)
            response.raise_for_status()
        except HTTPError as error:
            dialog_notification(
                'Error while trying to start a search. Error: {error}'.format(error=error),
                xbmcgui.NOTIFICATION_WARNING
            )
            xbmc.log('Error while trying to start a search. Error: {error}'.format(error=error), xbmc.LOGERROR)
        except RequestException as error:
            dialog_notification(
                'Something went wrong trying to connect to {url}. Error: {error}'.format(
                    url=self.medusa.url, error=error
                ),
                xbmcgui.NOTIFICATION_WARNING
            )
            xbmc.log('Something went wrong trying to connect to {url}. Error: {error}'.format(
                    url=self.medusa.url, error=error
            ), xbmc.LOGERROR)
        else:
            xbmc.log(
                'Search url: {url}\nrequest: {request!r}\nresponse: {response!r}'.format(url=response.request.url,
                                                                                         request=response.request.headers,
                                                                                         response=response.content),
                xbmc.LOGDEBUG
            )
            json_response = response.json()
            if json_response.get('result') not in ('failure',):
                dialog_ok('Successful started search for S{season}E{episode} of show {show}'.format(
                    season=season, episode=episode, show=show.get('title')
                ))
            else:
                dialog_notification(
                    'Error while searching for episode. Error: {error}'.format(error=json_response.get('message')),
                    xbmcgui.NOTIFICATION_WARNING
                )
                xbmc.log(
                    'Error while searching for episode. Error: {error}'.format(error=json_response.get('message')),
                    xbmcgui.NOTIFICATION_WARNING
                )

    def run(self):
        """Run main of plugin."""
        list_item_show_title = sys.listitem.getVideoInfoTag().getTVShowTitle()
        list_item_season = sys.listitem.getVideoInfoTag().getSeason()
        list_item_episode = sys.listitem.getVideoInfoTag().getEpisode()

        # Let's match kodi's episode dbId -> kodi's series dbId -> medusa's tvdb id.
        show = self.match_series(sys.listitem.getVideoInfoTag().getDbId())

        if not show:
            dialog_notification("Medusa could not locate series {0}".format(
                list_item_show_title
            ), xbmcgui.NOTIFICATION_WARNING)
            xbmc.log("Medusa could not locate series {0}".format(list_item_show_title), xbmc.LOGWARNING)
            return

        # Give medusa the instruction to start a new forced search.
        self.start_search(show, list_item_season, list_item_episode)
