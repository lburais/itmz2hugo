import os
import re
import pprint
import glob

from tabulate import tabulate
from datetime import datetime as dt

# pip3 install XlsxWriter
# pip3 install openpyxl
import xlsxwriter

# pip3 install pandas
import pandas as pd

# #################################################################################################################################
# GLOBAL VARIABLES
# #################################################################################################################################

nan = float('NaN')

DEBUG = True

timestamp = None

# #################################################################################################################################
# ELEMENT
# #################################################################################################################################
# Must have columns:
#   - id
#   - source: [onenote | itmz | notes]
#   - what: [notebook | group | section | page | topic]
#   - type: [page | post | comment]
#   - title
#   - created
#   - modified
#   - authors
#   - parent
#   - childs
#   - body
#   - resources
#       - type: [image | fullres | object]
#       - name
#       - url
#       - filename
#       - date

ELEMENT_COLUMNS=['source','what','type','id','title','created','modified','authors','parent','childs','body','resources']

def empty_elements():
    return pd.DataFrame( columns = ELEMENT_COLUMNS )

def empty_resource():
    return { 'type': None, 'name': None, 'url': None, 'parent': None, 'filename': None, 'date': None, 'processed': False }

# #################################################################################################################################
# INTERNAL FUNCTIONS
# #################################################################################################################################

def slugify( value ):

    # remove invalid chars (replaced by '-')
    value = re.sub( r'[<>:"/\\|?*^%]', '-', value, flags=re.IGNORECASE )

    # remove non-alphabetical/whitespace/'-' chars
    value = re.sub( r'[^\w\s-]', '', value, flags=re.IGNORECASE )

    # replace whitespace by '-'
    value = re.sub( r'[\s]+', '-', value, flags=re.IGNORECASE )

    # lower case
    value = value.lower()

    # reduce multiple whitespace to single whitespace
    value = re.sub( r'[\s]+', ' ', value, flags=re.IGNORECASE)

    # reduce multiple '-' to single '-'
    value = re.sub( r'[-]+', '-', value, flags=re.IGNORECASE)

    # strip
    value = value.strip()

    return value  

# ===============================================================================================================================================
# myprint
# ===============================================================================================================================================

def myprint( content, line=False, prefix='', title='' ):
    if DEBUG:
        if line:
            if title == '':
                print( "-"*250 )
            else:
                print( "= {} {}".format(title, "="*(250-len(title)-3)) )
        if isinstance(content, pd.DataFrame):
            print( tabulate( content, headers='keys', tablefmt="fancy_grid", showindex="never" ) )
        elif content != '':
            print('    {}{}{}'.format(prefix, '' if prefix == '' else ' ', content))

# ===============================================================================================================================================
# get_catalog
# ===============================================================================================================================================

def get_catalog( directory ):
    catalog = [ { 'filename': 'FORCE', 'name': 'FORCE' } ]
    for d in glob.glob(glob.escape(directory) + "/jamstack*.xlsx"):
        display =  os.path.basename(d).replace('jamstack_', '').replace('.xlsx', '').replace('_', ' ').upper()
        if os.path.getsize(d) > 0:
            catalog += [ { 'filename': d, 'name': display } ]
    if len(catalog) > 1: catalog.insert(1, { 'filename': catalog[-1]['filename'], 'name': 'LAST' } )

    return catalog

# ===============================================================================================================================================
# load_excel
# ===============================================================================================================================================

def load_excel( filename ):

    if filename:
        if os.path.isfile( filename ):
            myprint( '', line=True, title='LOAD EXCEL FILE')
            myprint( 'Loading {} file'.format(filename))

            try:
                df = pd.read_excel( filename, sheet_name='Elements', engine='openpyxl')
                myprint( "{} rows loaded.".format(len(df)), prefix="..." ) 
                return df
            except:
                myprint( "Something went wrong with file {}.".format(filename), prefix="..." ) 
                  
    return empty_elements()         

# ===============================================================================================================================================
# save_excel
# ===============================================================================================================================================

def save_excel( directory, elements, type=None ):
    global timestamp

    myprint( '', line=True, title='SAVE EXCEL{}'.format( (' ' + type.upper()) if type else ''))

    try:
        if not timestamp: timestamp = dt.now().strftime("%d_%b_%Y_%H_%M_%S")

        for out_file in glob.glob(os.path.join( directory, 'jamstack_*_{}.xlsx'.format( timestamp ))):
            myprint( "removing {}".format(out_file), prefix='...' )
            os.remove( out_file )

        name = 'jamstack{}_{}.xlsx'.format( ('_' + type) if type else '', timestamp)

        out_file = os.path.join( directory, name )
        out_dir = os.path.dirname(out_file)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        writer = pd.ExcelWriter(out_file, engine='xlsxwriter')
        workbook  = writer.book
        elements.to_excel( writer, sheet_name='Elements', index=False, na_rep='')
        writer.close()

        if not type : timestamp = None

        myprint( "{} rows saved in file {}.".format(len(elements), out_file), prefix="..." )        

    except:
        myprint( "Something went wrong with file {}.".format(out_file), prefix="..." )            
