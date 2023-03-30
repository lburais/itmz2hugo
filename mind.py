""" ###################################################################################################################################################################################################
Filename:     mind.py

- Author:     [Laurent Burais](mailto:lburais@cisco.com)
- Release:    
- Date:

Configure:
  mkdir /Volumes/library
  mount_afp -i afp://Pharaoh.local/library /Volumes/library
  cd /Volumes/development/mind
  python3 -m venv venv
  pip3 install requests pandas bs4 tabulate xlsxwriter openpyxl  markdown flask flask_session msal pelican

Run:
  cd /Volumes/development/mind
  source venv/bin/activate
  python3 mind.py

Graph Explorer:
  https://developer.microsoft.com/fr-fr/graph/graph-explorer
#######################################################################################################################################################################################################
""" 

import argparse
import os

from mytools import *

from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_session import Session

from bs4 import BeautifulSoup

import platform

#import glob

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

# MICROSOFT ONENOTE -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import microsoft_config

import onenote as ONENOTE

# APPLE NOTES -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import notes as NOTES

# ITHOUGHSX -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import itmz as ITMZ

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
        '--https', action='store_true', dest='https',
        help='HTTPS server')

    args = parser.parse_args()

    # ##############################################################################################################################################
    # Variable
    # ##############################################################################################################################################

    FOLDER = os.path.dirname(__file__)
    FOLDER_OUTPUT = os.path.join( FOLDER, 'output')

    # FOLDER_STATIC = os.path.join( FOLDER, 'static')
    # FOLDER_SITE = os.path.join( FOLDER, 'site')

    # FOLDER_ITMZ = "/Volumes/library/MindMap"

    # ##############################################################################################################################################
    # Flask
    # ##############################################################################################################################################

    app = Flask(__name__, static_url_path='/output')

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

    @app.route('/files/')
    def files():
        filenames = []
        for root, subdirs, files in os.walk(FOLDER_OUTPUT):
            for file in files:
                filenames += [ os.path.join( os.path.relpath(root, start=FOLDER_OUTPUT), file) ]
        return render_template('files.html', files=filenames)

    @app.route('/files/<path:filename>')
    def log(filename):
        print( f'filename: {filename}')
        x=1/0
        return send_file( filename )

    @app.route("/catalog")
    @app.route("/content")
    @app.route("/onenote")
    @app.route("/notes")
    @app.route("/itmz")
    def processing():
        action = request.base_url.split('/')[-1]
        command = request.args.get('command') 
        print( f'ACTION [{action.upper()}] COMMAND [{command.upper() if command else ""}] URL [{request.url.upper()}]')

        results = {}

        for source in [ 'onenote', 'itmz' ]: #[ 'onenote', 'notes']:

            # PROCESS URL 

            if source in ['onenote']:
                response = ONENOTE.process_url()
            elif source in ['notes']:
                response = NOTES.process_url()
            elif source in ['itmz']:
                response = ITMZ.process_url()
            else:
                response = {}

            # PROCESS RESPONSE 

            if 'catalog' in response:
                print( f'.. CATALOG [{len(response["catalog"])}]')
                if 'catalog' not in results: results['catalog'] = []
                results['catalog'] += response['catalog']

            if 'elements' in response:
                print( f'.. ELEMENTS [{len(response["elements"])}]')
                if 'elements' not in results: results['elements'] = []
                results['elements'] += response['elements']

            if 'comments' in response:
                print( f'.. ELEMENTS [{len(response["comments"])}]')
                results['comments'] = response['comments']

            if 'note' in response:
                print( '.. NOTE')
                note = response['note']

                if 'html' in note:
                    print( '.. BODY')
                    # ADD {{ url_for('static', filename = 'subfolder/some_image.jpg') }} FOR FLASK / IMAGES AND ATTACHMENTS
                    # <img src="images/some_image.jpg" --> <img src=url_for('static', filename = 'subfolder/images/some_image.jpg')
                    # <object data="attachments/some_attachment.pdf" --> <object data=url_for('static', filename = 'attachments/some_attachment.pdf')
                    rel_folder = os.path.relpath(note['folder'], start=FOLDER_OUTPUT)
                    soup = BeautifulSoup( note['html'], features="html.parser" )

                    for image in soup.findAll("img"):
                        image['src'] = url_for('static', filename = os.path.join(rel_folder, image['src']) )

                    for attachment in soup.findAll("object"):
                        attachment['data'] = url_for('static', filename = os.path.join(rel_folder, attachment['data']) )

                    # prefix with a link to the page

                    href = soup.new_tag('a')
                    href.attrs['href'] = note['url'] if 'url' in note else '#'
                    href.attrs['target'] = "_blank"
                    href.string = ">> " + href.attrs['href'] + " <<"
                    soup.body.insert(1, href)

                    return str(soup)

            # WRITE ONENOTE TO NOTES
             
            if source in ['onenote'] and command in ['write'] and 'note' in response:
                print( f'name {response["note"]["name"]} folder {response["note"]["folder"]}')
                response['comment'] = NOTES.write( response['note']['name'], response['note']['body'], response['note']['folder'], response['note']['hierarchy'], response['note']['attachments'] )

        return render_template('base.html', result=results)

    # ##############################################################################################################################################
    # MICROSOFT LOGIN 
    # ##############################################################################################################################################

    @app.route("/getAToken")
    def microsoft_token():
        return redirect( ONENOTE.process_url() )

    @app.route("/login")
    def microsoft_login():
        auth_url = ONENOTE.process_url()
        #return "<a href='%s'>Login with Microsoft Identity</a>" % auth_url
        return render_template( 'login.html', auth_url=auth_url )

    @app.route("/logout")
    def microsoft_logout():
        return redirect( ONENOTE.process_url() )

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
