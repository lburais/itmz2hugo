""" ###################################################################################################################################################
Filename:     jamstack.py

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
###################################################################################################################################################
""" 

import argparse
import os
import sys
import shutil

import microsoft_config

import onenote
import itmz
import nikola
import pelican

from mytools import *

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

import uuid

import msal

import platform

import glob

if __name__ == "__main__":

    # ##############################################################################################################################################
    # arguments
    # ##############################################################################################################################################

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

    # ##############################################################################################################################################
    # output folder
    # ##############################################################################################################################################

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
    @app.route("/empty")
    @app.route("/refresh")
    @app.route("/excel")
    @app.route("/remove")
    @app.route("/pelican")
    @app.route("/nikola")
    @app.route("/getfile")
    @app.route("/elements")
    @app.route("/parse")
    def actions():
        global elements, catalog

        try:
            action = request.base_url.split('/')[-1]

            if len(action) > 0: myprint( '', line=True, title='ACTION: {}'.format(action.upper()) )

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # CLEAR ELEMENTS DATAFRAME
            # ---------------------------------------------------------------------------------------------------------------------------------------
            if action in ['empty']:
                elements = empty_elements()

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # OPEN LAST EXCEL FILE
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['excel']:
                cat = pd.DataFrame( catalog )
                file = cat[cat['source'].isin(['directory'])]['filename'].to_list()[-1]
                if platform.system() == 'Darwin':
                    myprint( 'Opening {}'.format(file))
                    os.system('open "' + file + '"')
                else:
                    myprint( 'Cannot open {} on {}'.format( file, platform.system() ) )
                del cat

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # REMOVE ORPHAN FILES
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['remove']:
                nikola.clear( directory=FOLDER_SITE )
                pelican.clear( directory=FOLDER_SITE )
                itmz.clear( directory=FOLDER_STATIC, elements=elements )
                onenote.clear( directory=FOLDER_STATIC, elements=elements, all=False )

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # WRITE TO NIKOLA
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['nikola']:
                elements = nikola.write( directory = FOLDER_SITE,
                                         elements = elements )        

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # WRITE TO PELICAN
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['pelican']:
                elements = pelican.write( directory = FOLDER_SITE,
                                          elements = elements )        

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # LOAD EXCEL FILE
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['getfile']:
                filename = request.args.get('filename')
                if filename:
                    if os.path.isfile( filename ):
                        myprint( 'Loading {} file'.format(filename))

                        try:
                            elements = pd.read_excel( filename, sheet_name='Elements', engine='openpyxl')
                            myprint( "{} rows loaded.".format(len(elements)) ) 
                        except:
                            myprint( "Something went wrong with file {}.".format(filename) ) 

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # PARSE ELEMENTS
            # ---------------------------------------------------------------------------------------------------------------------------------------
            elif action in ['parse']:
                what = request.args.get('what')
                source = request.args.get('source')
                url = request.args.get('url')

                if source in ['all', 'onenote']:

                    if not session.get("user"):
                        return redirect(url_for("login"))

                    token = get_token(microsoft_config.SCOPE)

                    # http://localhost:5000/parse?what=notebooks&url=.../onenote/notebooks/0-34CFFB16AE39C6B3!4390&source=onenote
                    # http://localhost:5000/parse?what=content&url=None&source=onenote
                    # http://localhost:5000/parse?what=resources&url=None&source=onenote
                    # source=onenote
                    # ALL NOTEBOOKS    what=notebooks
                    # ALL CONTENTS     what=content
                    # ALL RESOURCES    what=resources
                    # ONE NOTEBOOK     what=OneNote notebook url=onenote_self
                    # REFRESH          what=refresh
                    # CLEAR            what=clear - remove unused resources - not yet implemented
                    # CLEAN            what=clean

                    onenote_elements = onenote.read( token = token['access_token'],
                                                     what = what,
                                                     url = url if url not in ['', 'nan', 'None'] else None,
                                                     directory = FOLDER_STATIC,
                                                     elements = elements if what in ['content', 'resources', 'refresh'] else empty_elements()
                                                )

                    elements = pd.concat( [ elements[~elements['source'].isin(['onenote'])], onenote_elements ], ignore_index = True )

                if source in ['all', 'itmz']:

                    itmz_elements = itmz.read( directory = FOLDER_STATIC,
                                            source = FOLDER_ITMZ, 
                                            elements = empty_elements() )

                    elements = pd.concat( [ elements[~elements['source'].isin(['itmz', nan])], itmz_elements ], ignore_index = True )
                
                if source in ['all', 'notes']:
                    pass
                
                save_excel(FOLDER_STATIC, elements)

            # ---------------------------------------------------------------------------------------------------------------------------------------
            # LOAD CATALOG
            # ---------------------------------------------------------------------------------------------------------------------------------------

            # directory
            catalog = [ { 'source': 'directory', 'filename': 'FORCE', 'name': 'FORCE' } ]
            for d in glob.glob(glob.escape(FOLDER_STATIC) + "/jamstack*.xlsx"):
                display =  os.path.basename(d).replace('jamstack_', '').replace('.xlsx', '').replace('_', ' ').upper()
                if os.path.getsize(d) > 0:
                    catalog += [ { 'source': 'directory', 'filename': d, 'name': display } ]
            if len(catalog) > 1: catalog.insert(1, { 'source': 'directory', 'filename': catalog[-1]['filename'], 'name': 'LAST' } )

            catalog = pd.DataFrame( catalog )

            # onenote
            if not session.get("user"):
                return redirect(url_for("login"))

            token = get_token(microsoft_config.SCOPE)

            catalog = pd.concat( [ catalog, onenote.catalog( token = token['access_token'] ) ], ignore_index=True )

            # itmz
            catalog = pd.concat( [ catalog, itmz.catalog(FOLDER_ITMZ) ], ignore_index=True )

            # convert
            catalog = catalog.to_dict('records')
        
        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            myprint("action error [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname))

        return render_template('index.html', result={ 'catalog': catalog,
                                                      'elements': elements.to_dict('records') })

    # ##############################################################################################################################################
    # ELEMENT
    # ##############################################################################################################################################

    # display button
    @app.route("/element")
    def one_element():
        element_id = request.args.get('id')
        tmp = elements[elements['id'] == element_id]
        if len(tmp) == 1:
            return '<!DOCTYPE html><html lang="en"><head></head><body!>' + tmp.iloc[0]['body'].replace(FOLDER,'')
        else:
            return '[{}]: {} ???\n{}'.format(element_id, len(tmp), tmp) + '</body></html>'

    # ##############################################################################################################################################
    # TOKEN CACHING AND AUTH FUNCTIONS
    # ##############################################################################################################################################

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
#        return redirect(url_for("index.html"))
        return redirect(url_for("actions"))

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
        session["state"] = str(uuid.uuid4())
        auth_url = _build_msal_app().get_authorization_request_url(
            microsoft_config.SCOPE,
            state=session["state"],
            redirect_uri=url_for("authorized", _external=True))
        # return "<a href='%s'>Login with Microsoft Identity</a>" % auth_url
        return render_template( 'login.html', auth_url=auth_url )

    @app.route("/logout")
    def logout():
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
