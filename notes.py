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

# pip3 install pandas
import pandas as pd

from bs4 import BeautifulSoup

from mytools import *

from macnotesapp import NotesApp

# #####################################################################################################################################################################################################
# INTERNALS
# #####################################################################################################################################################################################################

OK = True
KO = False

# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# INDENT_PRINT
# -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

def _indent_print(depth, text):
    print('  ' * depth + text)

# #####################################################################################################################################################################################################
# NOTES
# #####################################################################################################################################################################################################

class NOTES:
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # __INIT__
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def __init__ (self, output_directory=None ):

        self.notesapp = NotesApp()

        if output_directory:
            self.output_directory = output_directory
        else:
            self.output_directory = os.path.join( os.path.dirname(__file__), 'output' )

        self.output_directory = os.path.join( self.output_directory, 'notes' )

    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # CATALOG
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def catalog( self ):

        catalog = []
        
        # add command to list all local onenote        
        # catalog = [ { 'source': 'notes', 'object': 'account', 'name': 'Notes', 'url': 'list' } ]

        # add command to parse all notebooks        
        catalog += [ { 'source': 'notes', 'object': 'account', 'name': 'All Accounts', 'url': 'parse' } ] if len(self.notesapp.accounts) > 0 else []

        # add command to parse each notebook      
        for account in self.notesapp.accounts:
            catalog += [ { 'source': 'notes', 'object': 'account', 'name': account, 'url': 'parse&account={}'.format(account) } ]

        return catalog

    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # LIST
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def list( self ):
        catalog = []

        base = len(os.path.normpath(self.output_directory).split(os.sep))

        for root, subdirs, files in os.walk(self.output_directory):
            for file in files:
                element = { 'source': 'notes' }

                element['indent'] = len(os.path.normpath(root).split(os.sep)) - base

                root_ext = os.path.splitext(file)

                if root_ext[1] in ['.html']:

                    element['object'] = 'note'
                    element['name'] = root_ext[0]
                    element['file'] = os.path.join(root, file)
                    element['url'] = element['file']
                    element['date'] = dt.utcfromtimestamp(os.path.getmtime(element['file']))
                    element['command'] = [{'name': 'Display', 'url': 'display&file={}'.format(element['file'])}]

                    catalog += [ element ]

        return catalog

    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # PARSE
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def parse( self, accounts=None, force=False ):

        return KO

        # notes = self.notesapp.notes(accounts=accounts)

        # return OK

    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    # WRITE
    # -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

    def write( self, name, body, hierarchy=[], attachments=[], force=False ):

        soup = BeautifulSoup( body, features="html.parser" )
        whitelist=tuple()
        for tag in soup.findAll(True):
            for attr in [attr for attr in tag.attrs if attr not in whitelist]:
                del tag[attr]
        body = str(soup)

        account = self.notesapp.account()
        new_note = account.make_note( name=name, 
                                      body=body, 
                                      folder=None)

        print( body )
        return OK
