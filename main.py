# -*- coding: utf-8 -*-
import xbmcaddon
import os, sys
import xbmc

__addon__ = xbmcaddon.Addon('context.medusa.failed')
__cwd__ = xbmc.translatePath(__addon__.getAddonInfo('path')).decode('utf-8')
__resource__ = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib'))
__settings__ = xbmcaddon.Addon('context.medusa.failed')
__language__ = __settings__.getLocalizedString

sys.path.append(os.path.join(__cwd__, 'resources', 'lib'))
xbmc.log('Addon dir: ' + __cwd__, xbmc.LOGINFO)

from resources.lib import context


class MySettings(object):
    def __init__(self, url, username, password, debug):
        self.url = url + '/' if not url[-1] == '/' else url
        self.username = username
        self.password = password
        self.debug = debug


debug = bool(__settings__.getSetting('debug').lower() == 'true')
remote = False
if debug:
    try:
        import pydevd
    except Exception:
        xbmc.log('Failed to import pydevd, stopping debugging', xbmc.LOGWARNING)
    else:
        if remote:
            sys.path.append('D:\JetBrains\PyCharm 2017.2.4\debug-eggs\pycharm-debug-py3k.egg')
            pydevd.settrace('192.168.1.103', port=51234, stdoutToServer=True, stderrToServer=True)
        else:
            sys.path.append('D:\JetBrains\PyCharm 2017.2.4\debug-eggs\pycharm-debug-py3k.egg')
            pydevd.settrace('localhost', port=51234, stdoutToServer=True, stderrToServer=True)

# Keep this file to a minimum, as Kodi
# doesn't keep a compiled copy of this
ADDON = xbmcaddon.Addon()

context = context.MedusaFailed(
    MySettings(
        __settings__.getSetting('medusaurl'),
        __settings__.getSetting('username'),
        __settings__.getSetting('password'),
        __settings__.getSetting('debug')
    )
)
context.run()
