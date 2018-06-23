# Kodi failed download addon

An addon that works together with Medusa to mark a downloaded episode as failed, and attempt a new download.

## Requirements
* Medusa (https://github.com/pymedusa): configured and accessible from your kodi setup.
* Kodi: Minimal supported (tested) version is Kodi 17

## Installation
1. Download the addon from the releases section. For example for the current version 0.0.3. Download the .zip file: context.medusa.failed-v0.0.3.zip
2. Move the file to a location where it will be accessible from your Kodi installation
3. In kodi navigate to Addon - My Addons - Navigate back up to the root folder, containing "Install from zip file".
4. Select the zip file

## Configuration
The addon should now be installed in the sub-menu `Context menus`. Configure the addon.
* Add the Medusa url. If your using addiontitonal authentication methods like Basic authentication icw with a reverse proxy. This will not work. Make sure that Medusa is directly accessible, with it's defualt authentication enabled.
* Username
* Password
* Debug should only be used by developers who want to make use of remote debugging. Enabling Kodi debugging will also provide you with additional debugging logs, when troubleshooting the addon.

## FAQ

Q: When trying to fail a download, i'm getting an error that it can't find the tvdb id.
A: You'll probably haven't properly indexed the show in Kodi. Make sure that you've set TVDB as the "Set content" option on the series folder. If it has the wrong id set, try to re-index the show.
