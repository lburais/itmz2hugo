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

# ELEMENT_COLUMNS=[
#     'source',       # onenote | itmz | notes
#     'what',
#     'type',
#     'id',           # unique identifier
#     'number',
#     'title',
#     'created',
#     'modified',
#     'authors',
#     'slug',
#     'top',
#     'parent',
#     'childs',
#     'publish',      # should be published: True | False
#     'body'
# ]

# def empty_elements():
#     return pd.DataFrame( columns = ELEMENT_COLUMNS )

# #################################################################################################################################
# INTERNAL FUNCTIONS
# #################################################################################################################################

def slugify( value, isDir = False ):

    # remove invalid chars (replaced by '-' or space)
    if isDir: value = re.sub( r'[<>:"/\\|?*^%]', ' ', value, flags=re.IGNORECASE )
    else: value = re.sub( r'[<>:"/\\|?*^%]', '-', value, flags=re.IGNORECASE )

    # remove non-alphabetical/whitespace/'-' chars
    if not isDir: value = re.sub( r'[^\w\s-]', '', value, flags=re.IGNORECASE )

    # replace whitespace by '-'
    if not isDir: value = re.sub( r'[\s]+', '-', value, flags=re.IGNORECASE )

    # lower case
    if not isDir: value = value.lower()

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

def myprint( content, line=False, prefix='', title='', na=True ):
    if DEBUG:
        if line:
            if title == '':
                print( "-"*250 )
            else:
                print( "= {} {}".format(title, "="*(250-len(title)-3)) )
        if isinstance(content, pd.DataFrame):
            tmp = content.copy()
            if not na: tmp.dropna( axis='columns', how='all', inplace=True)
            print( tabulate( tmp, headers='keys', tablefmt="fancy_grid", showindex="never" ) )
            del tmp
        elif content != '':
            print('    {}{}{}'.format(prefix, '' if prefix == '' else ' ', content))

# ===============================================================================================================================================
# save_excel
# ===============================================================================================================================================

def save_excel( directory, elements, type=None ):
    global timestamp

    myprint( '', line=True, title='SAVE EXCEL{}'.format( (' ' + type.upper()) if type else ''))

    try:
        if not timestamp: timestamp = dt.now().strftime("%d_%b_%Y_%H_%M_%S")

        for out_file in glob.glob(os.path.join( directory, 'jamstack_*_{}.xlsx'.format( timestamp ))):
            myprint( "removing {}".format(out_file) )
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

# #####################################################################################################################################################################################################
# CLEAN_HTML
# #####################################################################################################################################################################################################

def clean_html( html ):
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup( html, features="html.parser" )

    # clean tags

    blacklist=['style', 'lang', 'data-absolute-enabled', 'span', 'p']
    whitelist=['href', 'alt']

    for tag in soup.findAll(True):
        for attr in [attr for attr in tag.attrs if( attr in blacklist and attr not in whitelist)]:
            del tag[attr]
        if tag.name in blacklist and tag.name not in whitelist:
            tag.unwrap()

    # inline images

    def guess_type(filepath):
        try:
            import magic  # python-magic
            return magic.from_file(filepath, mime=True)
        except ImportError:
            import mimetypes
            return mimetypes.guess_type(filepath)[0]

    def file_to_base64(filepath):
        import base64
        with open(filepath, 'rb') as f:
            encoded_str = base64.b64encode(f.read())
        return encoded_str.decode('utf-8')
    
    for img in soup.find_all('img-age'):
        img_path = os.path.join(basepath, img.attrs['src'])
        mimetype = guess_type(img_path)
        img.attrs['src'] = "data:%s;base64,%s" % (mimetype, file_to_base64(img_path))

    return str(soup)
