# rt_notify
A notification app for OSX for new tickets in Request Tracker

## Requirements
This application requires python 2.7 and the following packages (which can be installed with pip):

- beautifulsoup4 >= version 4.3.2
- requests >= version 2.7.0
- pync >= version 1.6.1
- keyring >= version 5.3
- rumps >= version 0.2.1
- pyobjc >= version 3.0.4

Furthermore, pync requires that you have terminal-notifier installed, which can be found in Homebrew, amongst others.

## Usage

Call the application with --help to see the commandline options and usage.

This application works best if you set "terminal-notifier" in the Notifications Preference pane to display 
"Alerts" instead of "Banners", so that the notifications will remain on-screen.