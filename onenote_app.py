import onenote_config
from onenote import onenote_all
from jamstack_write import jamstack_write

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

import uuid

import msal

import platform

# #################################################################################################################################
#
# onenote_flask
#
# #################################################################################################################################
# Code based on https://github.com/Azure-Samples/ms-identity-python-webapp

class onenote_flask:

    def __init__( self, args ): 
        app = Flask(__name__)

        app.config.from_object(onenote_config)
        Session(app)
        app.debug = True

        def action( what = '' ):
            if not session.get("user"):
                return redirect(url_for("login"))

            if what in ['load', 'get']:
                token = get_token(onenote_config.SCOPE)

                onenote_objects = onenote_all( token['access_token'], True if what == 'get' else False )

                jamstack_write( elements=onenote_objects, output=args.output )

            return render_template('index.html')

        @app.route("/")
        def index():
            return action()

        @app.route("/get")
        def get():
            return action('get')

        @app.route("/load")
        def load():
            return action('load')

        ###############################################################################

        #                       TOKEN CACHING AND AUTH FUNCTIONS                      #

        ###############################################################################

        # Its absolute URL must match your app's redirect_uri set in AAD
        @app.route("/getAToken")
        def authorized():
            if request.args['state'] != session.get("state"):
                return redirect(url_for("login"))
            cache = _load_cache()
            result = _build_msal_app(cache).acquire_token_by_authorization_code(
                request.args['code'],
                scopes=onenote_config.SCOPE,
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
                onenote_config.CLIENT_ID, authority=authority or onenote_config.AUTHORITY,
                client_credential=onenote_config.CLIENT_SECRET, token_cache=cache)

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

        ###############################################################################

        #                       LOGIN/LOGOUT FUNCTIONS                                #

        ###############################################################################

        @app.route("/login")
        def login():
            session["state"] = str(uuid.uuid4())
            auth_url = _build_msal_app().get_authorization_request_url(
                onenote_config.SCOPE,
                state=session["state"],
                redirect_uri=url_for("authorized", _external=True))
            return "<a href='%s'>Login with Microsoft Identity</a>" % auth_url

        @app.route("/logout")
        def logout():
            session.clear()  # Wipe out the user and the token cache from the session
            return redirect(  # Also need to log out from the Microsoft Identity platform
                "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
                "?post_logout_redirect_uri=" + url_for("index", _external=True))

        ###############################################################################

        #                                    SERVE                                    #

        ###############################################################################

        if platform.system() == 'Darwin':
            app.run(host='localhost')
        else:
            app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)

