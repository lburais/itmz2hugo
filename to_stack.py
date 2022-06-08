import argparse
import os

import itmz
import onenote

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform iThoughts files into reST files for static site generators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '-i', '--itmz', dest='itmz', default='',
        help='The ITMZ input file to read or directory to parse')

    parser.add_argument(
        '-o', '--output', dest='output', default='content',
        help='Output path')
    parser.add_argument(
        '--force', action='store_true', dest='force',
        help='Force refresh of all iThoughtsX files')

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
        '--html', action='store_true', dest='html',
        help='Use html files')
    parser.add_argument(
        '--md', action='store_true', dest='md',
        help='Use markdown files')

    args = parser.parse_args()

    stack = None
    if args.hugo: stack='hugo'
    if args.pelican: stack='pelican'
    if args.nikola: stack='nikola'

    output = "html" # None
    if args.html: output='html'
    if args.md: output='md'

    if os.path.exists(args.output):
        try:
            # shutil.rmtree(args.output)
            pass
        except OSError:
            error = 'Unable to remove the output folder: ' + args.output
            exit(error)

    if not os.path.exists(args.output):
        try:
            os.makedirs(args.output)
        except OSError:
            error = 'Unable to create the output folder: ' + args.output
            exit(error)

    if args.itmz == '':
        onenote.onenote_main()
    else:           
        itmz = ITMZ( source=args.itmz, site=args.output, stack=stack, output=output )
        itmz._parse_source( args.force or False )
