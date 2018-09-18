#!/usr/bin/env python
# -*- coding: utf-8 -*-

# rdfgraph.py v2.2 Copyright (c) 2018 Matjaz Rihtar
# Released under the GNU General Public License v2.0

import sys, os, glob, re
import ntpath, argparse
import traceback
import json
import textwrap
from pprint import pprint

# RedLand librdf python language binding
import RDF

# Default namespaces
defns = {
  'dbo':      'http://dbpedia.org/ontology/',
  'dbp':      'http://dbpedia.org/property/',
  'dc':       'http://purl.org/dc/elements/1.1/',
  'dcat':     'http://www.w3.org/ns/dcat#',
  'dcterms':  'http://purl.org/dc/terms/',
  'foaf':     'http://xmlns.com/foaf/0.1/',
  'geo':      'http://www.opengis.net/ont/geosparql#',
  'geonames': 'http://www.geonames.org/ontology#',
  'gr':       'http://purl.org/goodrelations/v1#',
  'org':      'http://www.w3.org/ns/org#',
  'owl':      'http://www.w3.org/2002/07/owl#',
  'rdf':      'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
  'rdfs':     'http://www.w3.org/2000/01/rdf-schema#',
  'sioc':     'http://rdfs.org/sioc/ns#',
  'skos':     'http://www.w3.org/2004/02/skos/core#',
  'skos-xl':  'http://www.w3.org/2008/05/skos-xl#',
  'xml':      'http://www.w3.org/XML/1998/namespace',
  'xsd':      'http://www.w3.org/2001/XMLSchema#'
}
debug = False
rdf_format = None
sel_lang = None
add_lit_type = False
shorten_lit = False
LIT_LINELEN = 40
LIT_MAXLEN = 4*LIT_LINELEN
max_count = sys.maxint

# ----------------------------------------------------------------------------
def ntdirname(path):
  try:
    head, tail = ntpath.split(path)
    dirname = head or ntpath.dirname(head)
  except: dirname = '.'
  if dirname.endswith('/'):
    return dirname
  else:
    return dirname + '/'

def ntbasename(path):
  try:
    head, tail = ntpath.split(path)
    basename = tail or ntpath.basename(head)
  except: basename = ''
  return basename

# ----------------------------------------------------------------------------
def clean(msg):
  msg = msg.rstrip()
  msg = msg.replace('Exception: ', '')
  return msg

# ----------------------------------------------------------------------------
def str_hook(obj):
  return {k.encode('utf-8') if isinstance(k, unicode) else k :
          v.encode('utf-8') if isinstance(v, unicode) else v
          for k,v in obj}

def read_defns(fname):
  global defns
  
  try:
    jf = open(fname, 'rb')
    defns = json.load(jf, object_pairs_hook=str_hook)
    jf.close()
    sys.stderr.write('Read {} ({} namespaces)\n'.format(fname, len(defns)))
  except:
    exc = traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1])
    lineno = sys.exc_info()[-1].tb_lineno
    #errmsg = 'Read defns(%d): %s' % (lineno, clean(exc[-1]))
    #sys.stderr.write(errmsg + '\n')
# read_defns

# ----------------------------------------------------------------------------
def replns(s, ns):
  ss = str(s)
  for n in ns:
    uri = str(ns[n])
    match = re.match(r'(' + uri + r')', ss)
    if match:
      if n is None: n = 'base'
      ss = re.sub(r'^' + uri, str(n) + ':', ss)
      break
  return ss
# replns

# -----------------------------------------------------------------------------
def simplify(text):
  chars = r' !#%&()*+,-./:;<=>?@[\]^`{|}~' # Missing: "$_'
  for c in chars:
    if c in text:
      text = text.replace(c, '_')
  return text

# -----------------------------------------------------------------------------
def shorten(text):
  unitext = text.decode('utf-8')
  if shorten_lit:
    unitext = unitext[:LIT_MAXLEN] + (text[LIT_MAXLEN:] and '...')
  wrapped = textwrap.fill(unitext, width=LIT_LINELEN, break_long_words=False)
  text = wrapped.encode('utf-8')
  return text

# ----------------------------------------------------------------------------
def get_subject(s, ns):
  subj = replns(s.subject, ns)
  if s.subject.is_blank():
    subj = '_:' + subj
  subj_lit = s.subject.is_literal()
  if subj_lit:
    subj = shorten(subj)
  return subj, subj_lit
# get_subject

def get_predicate(s, ns):
  pred = replns(s.predicate, ns)
  if pred == 'rdf:type':
    pred = 'a'
  if s.predicate.is_blank():
    pred = '_:' + pred
  pred_lit = s.predicate.is_literal()
  if pred_lit:
    pred = shorten(pred)
  return pred, pred_lit
# get_predicate

def get_object(s, ns):
  obj = replns(s.object, ns)
  if s.object.is_blank():
    obj = '_:' + obj
  obj_lit = s.object.is_literal()
  if obj_lit:
    obj = shorten(obj)
  return obj, obj_lit
# get_object

# -----------------------------------------------------------------------------
def procfile(rdf_file):
  global rdf_format

  if rdf_format is None:
    head, tail = ntpath.splitext(rdf_file)
    if tail.lower() == '.rdf' or tail.lower() == '.owl':
      rdf_format = 'rdfxml'
    elif tail.lower() == '.nt':
      rdf_format = 'ntriples'
    elif tail.lower() == '.ttl':
      rdf_format = 'turtle'
    elif tail.lower() == '.rss':
      rdf_format = 'rss-tag-soup'
    else:
      rdf_format = 'unknown'

  if debug:
    RDF.debug(1)

  try:
    storage = RDF.Storage(storage_name='hashes', name='rdf_storage',
                          options_string="new='yes',hash-type='memory',dir='.'")
    if storage is None:
      sys.exit('RDF.Storage creation failed>')

    model = RDF.Model(storage)
    if model is None:
      sys.exit('RDF.Model creation failed>')

    sys.stderr.write('Parsing file {} as {}\n'.format(rdf_file, rdf_format))
    uri = RDF.Uri(string='file:' + rdf_file)

    parser = RDF.Parser(rdf_format)
    if parser is None:
      sys.exit('RDF.Parser({}) creation failed>'.format(rdf_format))
  except:
    exc = traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1])
    lineno = sys.exc_info()[-1].tb_lineno
    errmsg = 'RDF creation(%d): %s' % (lineno, clean(exc[-1]))
    sys.exit(errmsg)

  try:
    count = 0
    for s in parser.parse_as_stream(uri):
      if debug:
        sys.stderr.write('---------------------------------------- {}\n'.format(count+1))
        sys.stderr.write(str(s.subject) + '\n')
        sys.stderr.write(str(s.predicate) + '\n')
        sys.stderr.write(str(s.object) + '\n')
      model.add_statement(s)
      count += 1
      if count >= max_count:
        break
    if debug:
      sys.stderr.write('----------------------------------------\n')
  except:
    exc = traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1])
    lineno = sys.exc_info()[-1].tb_lineno
    errmsg = 'Parse stream(%d): %s' % (lineno, clean(exc[-1]))
    if re.search(r'RedlandError:..Adding statement failed', errmsg, flags=re.IGNORECASE):
      sys.stderr.write(errmsg + '\n')
    else:
      sys.exit(errmsg)

  sys.stderr.write('Found {} statements\n'.format(count))

  ns = parser.namespaces_seen() # {str: URI}
  for n in defns:
    if n not in ns:
      ns[n] = defns[n]
  for n in ns:
    ns[n] = str(ns[n])
    if debug:
      sys.stderr.write('@prefix {}: <{}> .\n'.format(n, ns[n]))

  print('@startuml')
# print('scale max 100000')

  # Populate objects with their attributes
  objects = {}; alias = {}
  for s in model:
    # Subject
    subj, subj_lit = get_subject(s, ns)
    ox = subj
    if ox not in objects:
      objects[ox] = []
    alias[ox] = simplify(ox)

    # Predicate
    pred, pred_lit = get_predicate(s, ns)

    # Object
    obj, obj_lit = get_object(s, ns)
    if pred != 'a' and not obj_lit:
      ox = obj
      if ox not in objects:
        objects[ox] = []
      alias[ox] = simplify(ox)

    # Add attributes
    attrs = objects[ox]
    if pred == 'a':
      val = '{} {}'.format(pred, obj)
      if val not in attrs:
        attrs.append(val)
    elif obj_lit:
      obj_lang = s.object.literal[1]
      obj_type = s.object.literal[2]
      if sel_lang is not None:
        if obj_lang is None or obj_lang == sel_lang:
          val = '{} "{}"'.format(pred, obj)
          if add_lit_type and obj_type is not None:
            val += ' [{}]'.format(replns(obj_type, ns))
          if val not in attrs:
            attrs.append(val)
      else:
        val = '{} "{}"'.format(pred, obj)
        if add_lit_type and obj_type is not None:
          val += ' [{}]'.format(replns(obj_type, ns))
        if val not in attrs:
          attrs.append(val)
    objects[ox] = attrs

  # Print objects and their aliases at the beginning
  for o in objects:
    # Print object's alias if needed
    if o != alias[o]:
      if o.startswith('_:'): # blank node
        sys.stdout.write('object " " as {}\n'.format(alias[o]))
      else:
        sys.stdout.write('object "{}" as {}\n'.format(o, alias[o]))
    # Print object's attributes if any
    if len(objects[o]):
      sys.stdout.write('object {} {{\n'.format(alias[o]))

      attrs = objects[o]
      for a in attrs:
        sys.stdout.write('  {}\n'.format(a))

      sys.stdout.write('}\n')

  # Print connections between objects
  for s in model:
    subj, subj_lit = get_subject(s, ns)
    pred, pred_lit = get_predicate(s, ns)
    obj, obj_lit = get_object(s, ns)

    if pred == 'a':
      continue
    elif obj_lit:
      continue

    sys.stdout.write('{}'.format(alias[subj]))
    sys.stdout.write(' --> ')
    sys.stdout.write('{} : {}'.format(alias[obj], pred))
    sys.stdout.write('\n')

  print('@enduml')
  return 0
# procfile

# =============================================================================
def main(argv):
  global debug, rdf_format, sel_lang, add_lit_type, shorten_lit, max_count

# argv = ['rdfgraph.py', 'sample.ttl']
  prog = ntbasename(argv[0]).replace('.py', '').replace('.PY', '')

  parser = argparse.ArgumentParser(description='Creates PlantUML file from RDF file(s)',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('rdf_files', metavar='file.rdf', nargs='+',
                      help='RDF file(s) to process')
  parser.add_argument('-d', action='store_true', default=False, dest='debug',
                      help='Print debug info')
  parser.add_argument('-f', metavar='FORMAT', dest='rdf_format',
                      choices=['rdfxml', 'ntriples', 'turtle', 'rss-tag-soup'],
                      help='Input FORMAT: rdfxml, ntriples, turtle or rss-tag-soup')
  parser.add_argument('-l', metavar='LANG', dest='sel_lang',
                      help='Literal LANGUAGE: en, en-us, de, fr, ...')
  parser.add_argument('-t', action='store_true', default=False, dest='add_lit_type',
                      help='Display literal type')
  parser.add_argument('-s', action='store_true', default=False, dest='shorten_lit',
                      help='Shorten literals (to max. %d chars)' % LIT_MAXLEN)
  parser.add_argument('-m', metavar='MAX_COUNT', dest='max_count',
                      help='Read max. MAX_COUNT input statements')
  args = parser.parse_args()
  debug = args.debug
  rdf_format = args.rdf_format
  sel_lang = args.sel_lang
  add_lit_type = args.add_lit_type
  shorten_lit = args.shorten_lit
  if args.max_count is not None:
    max_count = int(args.max_count)

  # Read in external default namespaces
  fname = ntdirname(argv[0]) + 'defns.json'
  read_defns(fname)

  rc = 0

  nfiles = 0
  for arg in args.rdf_files:
    files = glob.glob(arg)
    for file in files:
      nfiles += 1
      rc += procfile(file)

  if nfiles == 0:
    sys.exit('No files found')
  return rc
# main

# -----------------------------------------------------------------------------
if __name__ == '__main__':
  # reopen sys.stdout with buffer size 0 (unbuffered)
  #sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

  rc = main(sys.argv)
  sys.exit(rc)
