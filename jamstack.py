# ###################################################################################################################################################
# Filename:     jamstack.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:    
# - Date:
#
# Configure:
#   mkdir /Volumes/library
#   mount_afp -i afp://Pharaoh.local/library /Volumes/library
#
#   cd /Volumes/library/Development/jamstack
#   python3 -m venv venv
#
# Run:
#   cd /Volumes/library/Development/jamstack
#   source venv/bin/activate
#   python3 jamstack.py --output site --nikola --html
#   python3 jamstack.py --output site --nikola --https
#
#
# Graph Explorer:
#   https://developer.microsoft.com/fr-fr/graph/graph-explorer
#
# ###################################################################################################################################################

import argparse
import os
import shutil

import microsoft_config
from onenote import *
from itmz import *
#from jamstack_write import *
from mytools import *

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

import uuid

import msal

import platform

import glob

# #################################################################################################################################
# MAIN
# #################################################################################################################################

if __name__ == "__main__":

    # =============================================================================================================================
    # arguments
    # =============================================================================================================================

    parser = argparse.ArgumentParser(
        description="Transform OneNote or iThoughts source into files for static site generators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # parser.add_argument(
    #     '-i', '--input', dest='source', default='onenote',
    #     help='Data source')

    parser.add_argument(
        '-o', '--output', dest='output', default='site',
        help='Output path')

    parser.add_argument(
        '-s', '--stack', dest='stack', default='nikola',
        help='Jamstack')
    parser.add_argument(
        '--nikola', action='store_true', dest='nikola',
        help='Create Nikola structure')
    parser.add_argument(
        '--hugo', action='store_true', dest='hugo',
        help='Create Hugo structure')
    parser.add_argument(
        '--pelican', action='store_true', dest='pelican',
        help='Create Pelican structure')

    parser.add_argument(
        '-f', '--format', dest='generate', default='rst',
        help='Output format')
    parser.add_argument(
        '--html', action='store_true', dest='html',
        help='Use html files')
    parser.add_argument(
        '--md', action='store_true', dest='md',
        help='Use markdown files')

    parser.add_argument(
        '--force', action='store_true', dest='force',
        help='Force refresh')

    parser.add_argument(
        '--https', action='store_true', dest='https',
        help='HTTPS server')

    args = parser.parse_args()

    if args.hugo: args.stack='hugo'
    if args.pelican: args.stack='pelican'
    if args.nikola: args.stack='nikola'

    if args.html: args.generate='html'
    if args.md: args.generate='md'

    # =============================================================================================================================
    # output folder
    # =============================================================================================================================

    args.output = os.path.join( args.output, args.stack )

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

    # =============================================================================================================================
    # Variable
    # =============================================================================================================================

    DIRECTORY = os.path.join( os.path.dirname(__file__), 'static')

    elements = empty_elements()

    onenote = None
    itmz = None

    # =============================================================================================================================
    # Flask
    # =============================================================================================================================

    app = Flask(__name__)

    app.config.from_object(microsoft_config)
    Session(app)
    app.debug = True

    # ROOT

    @app.route("/")
    def index():
        global elements

        elements = empty_elements()

        return render_template('index.html', result= get_catalog(DIRECTORY) )

    # ELEMENTS 
    
    @app.route("/element")
    def one_element():
        element_id = request.args.get('id')
        tmp = elements[elements['id'] == element_id]
        content = '<!DOCTYPE html><html lang="en"><head></head><body!>' + tmp.iloc[0]['body'] if len(tmp) == 1 else '[{}]: {} ???\n{}'.format(element_id, len(tmp), tmp) + '</body></html>'
        return content

    @app.route("/elements")
    def display_elements():
        global elements
        return render_template('elements.html', result=elements.to_dict('records'))

    @app.route("/getfile")
    def getfile():
        global elements

        filename = request.args.get('filename')

        elements = load_excel( filename )

        return render_template('elements.html', result=elements.to_dict('records'))

    # ONENOTE 
    
    @app.route("/onenote")
    def onenote_get():
        global onenote, elements
        
        if not session.get("user"):
            return redirect(url_for("login"))

        token = get_token(microsoft_config.SCOPE)

        if onenote: del onenote
        onenote = ONENOTE()

        onenote_elements = onenote.read( directory = DIRECTORY,
                                         token = token['access_token'], 
                                         elements = elements )

        elements = pd.concat( [ elements[~elements['source'].isin(['onenote',nan])], onenote_elements ], ignore_index = True )

        save_excel(DIRECTORY, elements)

        return render_template('elements.html', result=elements.to_dict('records'))

    # ITMZ 
    
    @app.route("/itmz")
    def itmz_get():
        global itmz, elements

        if itmz: del itmz
        itmz = ITMZ()

        itmz_elements = itmz.read( directory = DIRECTORY,
                                   source = "/Volumes/library/MindMap", 
                                   elements = empty_elements() )

        elements = pd.concat( [ elements[~elements['source'].isin(['itmz', nan])], itmz_elements ], ignore_index = True )

        save_excel(DIRECTORY, elements)

        return render_template('elements.html', result=elements.to_dict('records'))

    # NOTES
    
    @app.route("/notes")
    def notes():
        return render_template('index.html', result=get_catalog(DIRECTORY) )

    # ACTIONS 
    
    @app.route("/clean")
    def clean():
        global elements

        for col in ELEMENT_COLUMNS:
            if col in elements.columns.to_list():
                if col not in ['source']:
                    elements[col] = nan

        return render_template('elements.html', result=elements.to_dict('records'))

    @app.route("/refresh")
    def refresh():
        global elements

        return render_template('elements.html', result=elements.to_dict('records'))

    @app.route("/clear")
    def clear():
        global elements

        myprint( '', line=True, title='CLEAR FILES')

        for d in os.listdir(DIRECTORY):
            if os.path.isdir(os.path.join(DIRECTORY,d)):
                myprint( 'Removing {}...'.format(os.path.join(DIRECTORY,d)) )
                shutil.rmtree(os.path.join(DIRECTORY,d))
                os.makedirs(os.path.join(DIRECTORY,d))

        return render_template('elements.html', result=elements.to_dict('records'))

    # TOKEN CACHING AND AUTH FUNCTIONS

    # Its absolute URL must match your app's redirect_uri set in AAD
    @app.route("/getAToken")
    def authorized():
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
        return redirect(url_for("index"))

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
            client_credential=microsoft_config.CLIENT_SECRET, token_cache=cache)

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

    # LOGIN/LOGOUT FUNCTIONS

    @app.route("/login")
    def login():
        session["state"] = str(uuid.uuid4())
        auth_url = _build_msal_app().get_authorization_request_url(
            microsoft_config.SCOPE,
            state=session["state"],
            redirect_uri=url_for("authorized", _external=True))
        return "<a href='%s'>Login with Microsoft Identity</a>" % auth_url

    @app.route("/logout")
    def logout():
        session.clear()  # Wipe out the user and the token cache from the session
        return redirect(  # Also need to log out from the Microsoft Identity platform
            "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
            "?post_logout_redirect_uri=" + url_for("index", _external=True))

    # SERVE

    if platform.system() == 'Darwin':
        if args.https:
            app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)
        else:
            app.run(host='0.0.0.0')
    else:
        app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)
