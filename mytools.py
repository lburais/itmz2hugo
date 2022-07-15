import os
import re
import pprint
import glob

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

def myprint( content, line=False, prefix='', title='' ):
    if DEBUG:
        if line:
            if title == '':
                print( "-"*250 )
            else:
                print( "= {} {}".format(title, "="*(250-len(title)-3)) )
        if isinstance(content, pd.DataFrame):
            pprint.pprint( content )
        elif content != '':
            print('{}{}{}'.format(prefix, '' if prefix == '' else ' ', content))

# ===============================================================================================================================================
# get_catalog
# ===============================================================================================================================================

def get_catalog( directory ):
        catalog = [ { 'filename': 'FORCE', 'name': 'FORCE' } ]
        for d in glob.glob(glob.escape(directory) + "/jamstack*.xlsx"):
            display =  os.path.basename(d).replace('jamstack_', '').replace('.xlsx', '').replace('_', ' ').upper()
            catalog += [ { 'filename': d, 'name': display } ]
        catalog.insert(1, { 'filename': catalog[-1]['filename'], 'name': 'LAST' } )

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
                return pd.read_excel( filename, sheet_name='Elements', engine='openpyxl')
            except:
                myprint( "Something went wrong with file {}.".format(filename), prefix="..." ) 
                  
    return pd.DataFrame()           

# ===============================================================================================================================================
# save_excel
# ===============================================================================================================================================

def save_excel( directory, elements, type='' ):

    myprint( '', line=True, title='SAVE EXCEL')

    try:
        if not timestamp: timestamp = dt.now().strftime("%d_%b_%Y_%H_%M_%S")

        for out_file in glob.glob(os.path.join( directory, 'jamstack_*_{}.xlsx'.format( timestamp ))):
            myprint( "... removing {}".format(out_file) )
            os.remove( out_file )

        name = 'jamstack{}_{}.xlsx'.format( '' if type == '' else ('_' + type), self.timestamp)

        out_file = os.path.join( directory, name )
        out_dir = os.path.dirname(out_file)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        writer = pd.ExcelWriter(out_file, sheet_name='Elements', engine='xlsxwriter')
        workbook  = writer.book
        elements.to_excel( writer, index=False, na_rep='')
        writer.close()

        myprint( "{} rows saved in file {}.".format(len(elements), out_file) )        

    except:
        myprint( "Something went wrong with file {}.".format(out_file) )            
