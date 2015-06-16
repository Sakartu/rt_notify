# rt_notify
A notification app for OSX for new tickets in Request Tracker

## Requirements
This application requires python 2.7 or python 3 and the following packages (which can be installed with pip):

- beautifulsoup4
- docopt
- requests
- pync

Furthermore, pync requires that you have terminal-notifier installed, which can be found in Homebrew, amongst others.

## Usage

Call the application with --help to see the commandline options and usage.

This application works best if you set "terminal-notifier" in the Notifications Preference pane to display 
"Alerts" instead of "Banners", so that the notifications will remain on-screen.