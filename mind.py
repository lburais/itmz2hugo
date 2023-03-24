""" ###################################################################################################################################################################################################
Filename:     mind.py

- Author:     [Laurent Burais](mailto:lburais@cisco.com)
- Release:    
- Date:

Configure:
  mkdir /Volumes/library
  mount_afp -i afp://Pharaoh.local/library /Volumes/library
  cd /Volumes/development/jamstack
  python3 -m venv venv
  pip3 install requests pandas bs4 tabulate xlsxwriter openpyxl  markdown flask flask_session msal pelican

Run:
  cd /Volumes/development/jamstack
  source venv/bin/activate
  python3 jamstack.py --output site --nikola --html
  python3 jamstack.py --output site --nikola --https
  python3 jamstack.py

Graph Explorer:
  https://developer.microsoft.com/fr-fr/graph/graph-explorer
#######################################################################################################################################################################################################
""" 

import argparse
import os
import sys
import shutil

from mytools import *

from flask import Flask, render_template, request, redirect
from flask_session import Session

import platform

#import glob

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

output_directory = None

# MICROSOFT ONENOTE -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import microsoft_config

from onenote import ONENOTE

onenote = None

def get_onenote():
    global onenote, output_directory

    if not onenote:
        onenote = ONENOTE( output_directory )

    return onenote

# APPLE NOTES -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import notes as NOTES

notes = None

def get_notes():

    return NOTES.notes

    global notes, output_directory

    if not notes:
        notes = NOTES( output_directory )

    return notes

# ITHOUGHSX -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# WORDPRESS -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# #####################################################################################################################################################################################################
# MAIN
# #####################################################################################################################################################################################################

if __name__ == "__main__":

    # ##############################################################################################################################################
    # arguments
    # ##############################################################################################################################################

    parser = argparse.ArgumentParser(
        description="Transform OneNote or iThoughts source into files for static site generators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '-o', '--output', dest='output', default='output',
        help='Output path')

    parser.add_argument(
        '--force', action='store_true', dest='force',
        help='Force refresh')

    parser.add_argument(
        '--https', action='store_true', dest='https',
        help='HTTPS server')

    args = parser.parse_args()

    # ##############################################################################################################################################
    # output folder
    # ##############################################################################################################################################

    args.output = os.path.join( args.output )

    if args.force:
        if os.path.exists(args.output):
            try:
                shutil.rmtree(args.output)
            except OSError:
                error = 'Unable to remove the output folder: ' + args.output
                exit(error)

        if not os.path.exists(args.output):
            try:
                os.makedirs(args.output)
            except OSError:
                error = 'Unable to create the output folder: ' + args.output
                exit(error)

    output_directory = args.output

    # ##############################################################################################################################################
    # Variable
    # ##############################################################################################################################################

    FOLDER = os.path.dirname(__file__)
    FOLDER_STATIC = os.path.join( FOLDER, 'static')
    FOLDER_SITE = os.path.join( FOLDER, 'site')

    FOLDER_ITMZ = "/Volumes/library/MindMap"

    # ##############################################################################################################################################
    # Flask
    # ##############################################################################################################################################

    app = Flask(__name__)

    app.config.from_object(microsoft_config)
    Session(app)
    app.debug = True

    # ##############################################################################################################################################
    # ROOT 
    # ##############################################################################################################################################

    @app.route("/")
    @app.route("/index")
    def index():

        return render_template('base.html')

    # ##############################################################################################################################################
    # ACTIONS 
    # ##############################################################################################################################################

    @app.route("/catalog")
    @app.route("/content")
    @app.route("/onenote")
    @app.route("/notes")
    def processing():
        action = request.base_url.split('/')[-1]
        command = request.args.get('command') 
        print( f'ACTION [{action.upper()}] COMMAND [{command.upper() if command else ""}] URL [{request.url.upper()}]')

        catalog = []
        elements = []

        for source in [ 'onenote', 'notes']:

            # PROCESS URL 

            if source in ['onenote']:
                onenote = get_onenote()
                if onenote: 
                    response = onenote.process_url()
                else:
                    response = {}
            elif source in ['notes']:
                response = NOTES.process_url()
            else:
                response = {}

            # PROCESS RESOPNSE 

            if 'catalog' in response:
                print( f'CATALOG [{len(response["catalog"])}]')
                catalog += response['catalog']

            if 'elements' in response:
                print( f'ELEMENTS [{len(response["elements"])}]')
                elements += response['elements']

            if 'note' in response:
                note = response['note']
                response['comment']= clean_html( note['body'] )

            if 'body' in response:
                return clean_html( response['body'] )

        if len(elements) > 0:
            return render_template('content.html', result={ 'comment': response['comment'] if 'comment' in response else None, 'catalog': catalog, 'elements': elements })
        elif len(catalog) >0:
            return render_template('index.html', result={ 'comment': response['comment'] if 'comment' in response else None, 'catalog': catalog })
        else:
            return render_template('base.html', result={ 'comment': response['comment'] if 'comment' in response else None })

    # ##############################################################################################################################################
    # MICROSOFT LOGIN 
    # ##############################################################################################################################################

    @app.route("/getAToken")
    @app.route("/login")
    @app.route("/logout")
    def microsoft():
        action = request.base_url.split('/')[-1]

        onenote = get_onenote()
        if action in ['login']:
            return render_template( 'login.html', auth_url=onenote.get(request.base_url) )
        else:
            return redirect( onenote.get(request.base_url) )

    # ##############################################################################################################################################
    # SERVE
    # ##############################################################################################################################################

    if platform.system() == 'Darwin':
        if args.https:
            app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)
        else:
            app.run(host='0.0.0.0')
    else:
        app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)
