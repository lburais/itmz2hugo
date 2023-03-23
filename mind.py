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

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

import uuid

import platform

import glob

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

output_directory = None

# MICROSOFT ONENOTE -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

import microsoft_config

import msal

from onenote import ONENOTE

onenote = None

def get_onenote():
    global onenote, output_directory

    if not onenote:
        onenote = ONENOTE( output_directory=output_directory, app=app )

    return onenote

    if not onenote:
        token = get_token(microsoft_config.SCOPE)
    
        if token:
            onenote = ONENOTE( token, output_directory )

    return onenote

# APPLE NOTES -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

from notes import NOTES

notes = None

def get_notes():
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

    elements = empty_elements()
    catalog = []

    # ##############################################################################################################################################
    # Flask
    # ##############################################################################################################################################

    app = Flask(__name__)

    app.config.from_object(microsoft_config)
    Session(app)
    app.debug = True

    # ##############################################################################################################################################
    # ACTIONS 
    # ##############################################################################################################################################

    @app.route("/")
    @app.route("/index")
    def index():

        return render_template('base.html')

        catalog = []
        elements = []

        onenote = get_onenote()
        if onenote: 
            catalog += onenote.catalog()
            elements += onenote.list()

        notes = get_notes()
        if notes: 
            catalog += notes.catalog()
            elements += notes.list()

        return render_template('content.html', result={ 'catalog': catalog, 'elements': elements })

    @app.route("/catalog")
    def catalog():
        catalog = []

        onenote = get_onenote()
        if onenote: 
            catalog += onenote.catalog()

        notes = get_notes()
        if notes: 
            catalog += notes.catalog()

        return render_template('index.html', result={ 'catalog': catalog })

    @app.route("/content")
    def content():
        catalog = []
        elements = []

        return render_template('base.html')

    @app.route("/onenote")
    def onenote_processing():

        action = request.base_url.split('/')[-1]
        
        command = request.args.get('command')
        notebook = request.args.get('notebook')
        id = request.args.get('id')

        catalog = []
        elements = []

        onenote = get_onenote()
        if onenote: 
            catalog = onenote.catalog()

            if command in ['parse']:
                onenote.parse( [ notebook ] if notebook else None )

            elif command in ['list']:
                elements = onenote.list()

            elif command in ['display']:
                page = onenote.page( id )
                if page: 
                    out_html = page.body
                    # NEED TO FIX IMAGES AND ATTACHMENTS
                else:
                    out_html = '<!DOCTYPE html><html lang="en"><head></head><body!>' + "FILE DOES NOT EXIST"
                    out_html += "FILE [{}] DOES NOT EXIST".format(file)
                    out_html += '</body></html>'

                return out_html

            elif command in ['write']:
                notes = get_notes()
                if notes:
                    page = onenote.page( id )
                    if page:
                        print( f'write note {page}')
                        print( f'write note [{page.name}]: [{len(page.body)}] {page.hierarchy} {page.attachments}')
                        out_html = notes.write( name=page.name, body=page.body, hierarchy=page.hierarchy, attachments=page.attachments )

        return render_template('index.html')

    @app.route("/notes")
    def notes_processing():

        action = request.base_url.split('/')[-1]
        
        command = request.args.get('command')
        account = request.args.get('account')
        file = request.args.get('file')

        catalog = []
        elements = []

        print( f'command: {command}, account: {account}' )

        notes = get_notes()
        if notes: 
            catalog = notes.catalog()

            if command in ['parse']:
                notes.parse( [ account ] if account else None )

            elif command in ['list']:
                elements = notes.list()

            elif command in ['display']:
                if os.path.exists( file ): 
                    with open(file, 'r') as f:
                        out_html = f.read()
                        # NEED TO FIX IMAGES AND ATTACHMENTS
                else:
                    out_html = '<!DOCTYPE html><html lang="en"><head></head><body!>' + "FILE DOES NOT EXIST"
                    out_html += "FILE [{}] DOES NOT EXIST".format(file)
                    out_html += '</body></html>'

                return out_html

        return render_template('content.html', result={ 'catalog': catalog, 'elements': elements })

    @app.route("/ithoughtsx")
    def ithoughtsx_processing():
        pass

    @app.route("/wordpress")
    def wordpress_processing():
        pass

    # ##############################################################################################################################################
    # TOKEN CACHING AND AUTH FUNCTIONS
    # ##############################################################################################################################################

    # Its absolute URL must match your app's redirect_uri set in AAD
    @app.route("/getAToken")
    def authorized():

        onenote = get_onenote()
        return redirect( onenote.get(request.base_url) )

        if request.args['state'] != session.get("state"):
            return redirect(url_for("login"))
        cache = _load_cache()
        result = _build_msal_app(cache).acquire_token_by_authorization_code(
            request.args['code'],
            scopes=microsoft_config.SCOPE,
            redirect_uri=url_for("authorized", _external=True))
        if "error" in result:
            return "Login failure: %s, %s" % (
                result["error"], result.get("error_description"))
        session["user"] = result.get("id_token_claims")
        _save_cache(cache)
        return redirect("/")

    def _load_cache():
        cache = msal.SerializableTokenCache()
        if session.get("token_cache"):
            cache.deserialize(session["token_cache"])
        return cache

    def _save_cache(cache):
        if cache.has_state_changed:
            session["token_cache"] = cache.serialize()

    def _build_msal_app(cache=None, authority=None):
        return msal.ConfidentialClientApplication(
            microsoft_config.CLIENT_ID, authority=authority or microsoft_config.AUTHORITY,
            client_credential=microsoft_config.SECRET_VALUE, token_cache=cache)

    def _get_token_from_cache(scope=None):
        cache = _load_cache()  # This web app maintains one cache per session
        cca = _build_msal_app(cache)
        accounts = cca.get_accounts()
        if accounts:  # So all accounts belong to the current signed-in user
            result = cca.acquire_token_silent(scope, account=accounts[0])
            _save_cache(cache)
            return result

    def get_token(scope):
        token = _get_token_from_cache(scope)
        if not token:
            return redirect(url_for("login"))
        return token

    # ##############################################################################################################################################
    # LOGIN/LOGOUT FUNCTIONS
    # ##############################################################################################################################################

    @app.route("/login")
    def login():
        onenote = get_onenote()
        return render_template( 'login.html', auth_url=onenote.get(request.base_url) )

        session["state"] = str(uuid.uuid4())
        auth_url = _build_msal_app().get_authorization_request_url(
            microsoft_config.SCOPE,
            state=session["state"],
            redirect_uri=url_for("authorized", _external=True))
        # return "<a href='%s'>Login with Microsoft Identity</a>" % auth_url
        return render_template( 'login.html', auth_url=auth_url )

    @app.route("/logout")
    def logout():
        onenote = get_onenote()
        return redirect( onenote.get(request.base_url) )

        session.clear()  # Wipe out the user and the token cache from the session
        return redirect(  # Also need to log out from the Microsoft Identity platform
            "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
            "?post_logout_redirect_uri=" + url_for("login", _external=True))

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
