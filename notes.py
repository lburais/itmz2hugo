# #####################################################################################################################################################################################################
# Filename:     notes.py
# 
# - Author:     [Laurent Burais](mailto:lburais@cisco.com)
# - Release:
# - Date:
#
#
# #####################################################################################################################################################################################################
# Apple Notes structure
# ---------------------
#
# #####################################################################################################################################################################################################

import json
import requests
import re
import os
import sys
import shutil
import string
import time

from datetime import datetime as dt
import pytz

from flask import Flask, render_template, session, request, redirect, url_for
from flask_session import Session

from bs4 import BeautifulSoup

from mytools import *

from macnotesapp import NotesApp

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

OK = True
KO = False

notesapp = None

output_directory = os.path.join( os.path.dirname(__file__), 'output', 'notes' )

# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# INDENT_PRINT
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _indent_print(depth, text):
    print('  ' * depth + text)

# #####################################################################################################################################################################################################
# INIT
# #####################################################################################################################################################################################################

def init( output=None ):
    global notesapp, output_directory

    notesapp = NotesApp()

    if output:
        output = output_directory

# #####################################################################################################################################################################################################
# PROCESS_URL
# #####################################################################################################################################################################################################

def process_url( force=False ):
    global notesapp, output_directory

    try:
    
        action = request.base_url.split('/')[-1]
        command = request.args.get('command') 

        print( f'[notes] action: {action}, command: {command}, url: {request.url}' )

        catalog = []
        elements = []
        note = { 'name': '', 'body': '', 'hierarchy': [], 'attachments': [] }

        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
        # COMMAND
        # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

        if action in ['catalog', 'content', 'notes']:

            if not command: command = action

            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # CATALOG
            # -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # requires to be online

            if command in ['catalog']:

                if not notesapp: notesapp = NotesApp()

                accounts = notesapp.accounts

                print( f'accounts: {accounts}')

                # add command to parse all notebooks        
                catalog += [ { 'source': 'notes', 'object': 'account', 'name': 'All Accounts', 'url': 'parse' } ] if len(accounts) > 0 else []

                # add command to parse each notebook      
                for acc in accounts:
                    catalog += [ { 'source': 'notes', 'object': 'account', 'name': acc, 'url': 'parse&account={}'.format(acc) } ]
                
                return { 'catalog': catalog }

            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # PARSE
            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # requires to be online

            if command in ['parse']:

                account = request.args.get('account')

                # if not notesapp: notesapp = NotesApp()
                # notes = notesapp.notes(accounts=accounts)

            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
            # CONTENT
            # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

            find = request.args.get("file")

            print( f'file: {find}')

            base = len(os.path.normpath(output_directory).split(os.sep))

            for root, subdirs, files in os.walk(output_directory):
                for file in files:
                    element = { 'source': 'notes' }

                    element['indent'] = len(os.path.normpath(root).split(os.sep)) - base

                    root_ext = os.path.splitext(file)

                    if root_ext[1] in ['.html']:

                        element['object'] = 'note'
                        element['name'] = root_ext[0]
                        element['folder'] = root
                        element['file'] = os.path.join(root, file)
                        element['url'] = element['file']
                        element['date'] = dt.utcfromtimestamp(os.path.getmtime(element['file']))
                        element['command'] = [{'name': 'Display', 'url': 'display&file={}'.format(element['file'])}]

                        print( f'file: {find} element {element["file"]}')
                        if (find == None) or (element['file'] == find):
                            print( '..added')
                            elements += [ element ]

            print( f'elements [{len(elements)}]')

            if command in ['content']:

                return { 'catalog': catalog, 'elements': elements }  

            if command in ['get', 'read', 'display'] and len(elements) == 1:

                element = elements[0]

                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # GET
                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                if os.path.exists( element['file'] ): 
                    note['name'] = element['name']

                    with open(element['file'], 'r') as f:
                        note['body'] = f.read()
                        # NEED TO FIX IMAGES AND ATTACHMENTS

                    note['hierarchy'] = os.path.relpath(element['folder'], start=output_directory).split(os.sep)
                    note['hierarchy'].pop()
                    note['hierarchy'].insert(0, 'notes')

                    # attachments = os.path.join( page['folder'], 'attachments')
                    # if os.path.exists( attachments ): 
                    #     for root, subdirs, files in os.walk(attachments):
                    #         for file in files:
                    #             note['attachments'] += [ os.path.join( root, file )]

                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # DISPLAY
                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                if command in ['display']:

                    note['body'] = clean_html( note['body'])

                    return { 'catalog': catalog, 'body': note['body'] }
                
                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
                # READ
                # ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

                if command in ['read']:

                    return { 'catalog': catalog, 'note': note, 'comment': note['body'] }

            else:
                ll = "\n".join([ item["file"] for item in elements ])
                return { 'comment': f'too many elements [{len(elements)}] for criteria {find}\n{ll}', 'catalog': catalog }

        return {}

    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error = "Something went wrong [{} - {}] at line {} in {}.".format(exc_type, exc_obj, exc_tb.tb_lineno, fname)
        print( error )
        return { 'comments': error }

# #####################################################################################################################################################################################################
# WRITE
# #####################################################################################################################################################################################################

def write( name, body, hierarchy=[], attachments=[], force=False ):
    global notesapp

    if not notesapp: notesapp = NotesApp()
                    
    body = clean_html( body )

    account = notesapp.account()
    new_note = account.make_note( name=name, 
                                    body=body, 
                                    folder=None)

    print( body )
    return { 'comment': body }
