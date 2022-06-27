import argparse
import os

###############################################################################

#                                    MAIN                                     #

###############################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transform OneNote or iThoughts source into files for static site generators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '-i', '--input', dest='source', default='onenote',
        help='Data source')

    parser.add_argument(
        '-o', '--output', dest='output', default='site/nikola',
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

    args = parser.parse_args()

    if args.hugo: args.stack='hugo'
    if args.pelican: args.stack='pelican'
    if args.nikola: args.stack='nikola'

    if args.html: args.generate='html'
    if args.md: args.generate='md'

    if args.hugo: args.stack='hugo'
    if args.pelican: args.stack='pelican'
    if args.nikola: args.stack='nikola'

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

    if args.source == 'onenote':
        from onenote_app import onenote_flask 

        onenote_app = onenote_flask( args )
    else:    
        import itmz

        itmz = ITMZ( source=args.itmz, site=args.output, stack=args.stack, output=args.generate )
        itmz._parse_source()
