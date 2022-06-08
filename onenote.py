# https://www.codeproject.com/Articles/5318952/Microsoft-Graph-Authentication-in-Python
# https://portal.azure.com/#home

import uuid
import requests
from flask import Flask, render_template, session, request, redirect, url_for, send_file
from flask_session import Session
import msal
from markdownify import markdownify as md
import json
import pprint

import platform

import onenote_config

# Code based on https://github.com/Azure-Samples/ms-identity-python-webapp

app = Flask(__name__)
app.config.from_object(onenote_config)
Session(app)
app.debug = True

@app.route("/")
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template('index.html')


@app.route("/user")
def user():
    if not session.get("user"):
        return redirect(url_for("login"))
    token = get_token(onenote_config.SCOPE)
    graph_data = requests.get(  # Use token to call downstream service
        'https://graph.microsoft.com/v1.0/me',
        headers={'Authorization': 'Bearer ' + token['access_token']},
    ).json()        
    return render_template('user/index.html', result=graph_data, user=session["user"])

@app.route("/onenote")
def onenote():
    if not session.get("user"):
        return redirect(url_for("login"))

    token = get_token(onenote_config.SCOPE)

    data = onenote_data( token['access_token'] )

    # return render_template('onenote/index.html', result=data)
    return render_template('index.html')


@app.route("/onenotepage")
def fetch_onenote_page():
    token = get_token(onenote_config.SCOPE)
    page = requests.get(  # Use token to call downstream service
        request.args['page_url'],
        headers={'Authorization': 'Bearer ' + token['access_token']},
    )
    return page.text # returns HTML

@app.route("/onenotepagemd")
def fetch_onenote_page_md():
    token = get_token(onenote_config.SCOPE)
    page = requests.get(  # Use token to call downstream service
        request.args['page_url'],
        headers={'Authorization': 'Bearer ' + token['access_token']},
    )
    markdown = md(page.text, heading_style='ATX')
    return markdown

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

#                               ONENOTE DATA                                  #

###############################################################################

def onenote_data( token, what='notebook', url='', level=0 ):
    run = True

    if url == '':
        if what == 'notebook': url='https://graph.microsoft.com/v1.0/me/onenote/notebooks/0-34CFFB16AE39C6B3!335920'
        #if what == 'notebook': url='https://graph.microsoft.com/v1.0/me/onenote/notebooks'
        elif what == 'section': url='https://graph.microsoft.com/v1.0/me/onenote/sections'
        elif what == 'group': url='https://graph.microsoft.com/v1.0/me/onenote/sectionGroups'
        elif what == 'page': url='https://graph.microsoft.com/v1.0/me/onenote/pages'
        else: run = False

    while run:
        if what in ['content']:
            run = False
            onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} )

            pprint.pprint( onenote_response.text )

        else:
            onenote_response = requests.get( url, headers={'Authorization': 'Bearer ' + token} ).json()

            if 'error' in onenote_response:
                run = False
                print( '{}[{}] error: {} {} elements'.format("   "*level, what, onenote_response['error']['code'], onenote_response['error']['message']) )
            else:
                if 'value' in onenote_response: onenote_elements = onenote_response['value']
                else: onenote_elements = [ onenote_response ]

                for element in onenote_elements:
                    if 'displayName' in element: data = element["displayName"]
                    elif 'title' in element: data = element["title"]
                    else: data = 'no info'

                    print( '{}[{}] {}'.format(" "*4*(level + (element["level"] if 'level' in element else 0)), what, data) )

                    if what in ['page']:
                        indent = (len('[page]')+2+4*(level + (element["level"] if 'level' in element else 0)))
                        print( '{} created:  {}'.format( " "*indent, element["createdDateTime"]) )
                        print( '{} modified: {}'.format( " "*indent, element["lastModifiedDateTime"]) )
                        pprint.pprint( element )

                    if 'sectionsUrl' in element:
                        onenote_data( token, 'section', element["sectionsUrl"], level+1 )

                    if 'sectionGroupsUrl' in element:
                        onenote_data( token, 'group', element["sectionGroupsUrl"], level+1 )

                    if 'pagesUrl' in element:
                        onenote_data( token, 'page', element["pagesUrl"] + '?pagelevel=true&orderby=order', level+1 )

                    if 'contentUrl' in element:
                        #onenote_data( token, 'content', element["contentUrl"], level+1 )
                        onenote_data( token, 'content', element["self"] + "/$value", level+1 )

                if '@odata.nextLink' in onenote_response:
                    url = onenote_response['@odata.nextLink']
                else:
                    run = False


            # if element in ['content']:

            #     onenote_responses = requests.get(  # Use token to call downstream service
            #         url,
            #         headers={'Authorization': 'Bearer ' + token},
            #     )  
            #     # print( '{}'.format(onenote_responses.text) )

            #     pass

            # else:
            #     onenote_responses = requests.get(  # Use token to call downstream service
            #         url,
            #         headers={'Authorization': 'Bearer ' + token},
            #     ).json()  

###############################################################################

#                                    MAIN                                     #

###############################################################################

if __name__ == "__main__":

    if platform.system() == 'Darwin':
        app.run(host='localhost')
    else:
        app.run(ssl_context='adhoc', host='0.0.0.0', port=8888)
