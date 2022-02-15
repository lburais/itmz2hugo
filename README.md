This plugin will do a quick and dirty import of iThoughts files in one directory.

To use it if you already have a Nikola site:

```
$ nikola plugin -i import_ithoughts
$ nikola import_ithoughts your_ithoughts_directory
```

To use it if you don't already have a Nikola site:

```
$ nikola plugin -i import_ithoughts --user
$ nikola import_ithoughts -o output_folder your_ithoughts_directory 
```