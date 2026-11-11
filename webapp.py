"""
Author: Ethan Gruber
Date: November 2026
Function: Create an OAI-PMH wrapper on top of DPLAVA Github repositories of Dublin Core metadata.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, sys, uvicorn, datetime
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date
from typing import Union
from flask import Flask, request, Response
from markupsafe import escape

#include local OAI-PMH output processing functions
from generate_oai_xml import error, identify, list_sets, list_identifiers

OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
DATA_DIR = "../data"

PREFIX = "divas"

app = Flask(__name__)

#there is only a root in OAI PMH
@app.route("/")
def main():
    verb = request.args.get('verb', '')
    metadataPrefix = request.args.get('metadataPrefix', '')
    
    if len(verb) > 0:
        if verb == "Identify":
            dom = identify(verb)
        elif verb == "ListSets":
            dom = list_sets(verb)
        elif verb == "ListIdentifiers":
            #validate other responses
            if metadataPrefix != 'oai_dc':
                dom = error(verb, code="cannotDisseminateFormat")
            else:
                dom = list_identifiers(verb)
            
            
        else:
            dom = error(verb, code="badVerb")
    else:
        dom = error(verb, code="badVerb")
    
    ET.indent(dom, space="\t", level=0)    
    xml_str = ET.tostring(dom, encoding="utf-8", xml_declaration=True)        
    return Response(xml_str, mimetype="application/xml")
    
if __name__=="__main__":
    app.run(debug=True)