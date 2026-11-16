"""
Author: Ethan Gruber
Date: November 2026
Function: Create an OAI-PMH wrapper on top of DPLAVA Github repositories of Dublin Core metadata.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, sys, uvicorn, datetime, time
from dateutil.parser import isoparse
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date
from typing import Union
from flask import Flask, request, Response
from markupsafe import escape

#include local OAI-PMH output processing functions
from generate_oai_xml import error, identify, list_sets, list_metadata_formats, list_identifiers_records, validate_token

OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
DATA_DIR = "../data"

PREFIX = "divas"

app = Flask(__name__)

#there is only a root in OAI PMH
@app.route("/")
def main():
    verb = request.args.get('verb', '')
    metadataPrefix = request.args.get('metadataPrefix', '')
    setSpec = request.args.get('setSpec', '')
    resumptionToken = request.args.get('resumptionToken', '')
    
    #validate from and until parameters and convert to epoch time. If they are blank, then set from to 0 time from Epoch and until to current time. Otherwise use provided parameters
    if request.args.get('from') is not None:
        fromDate_valid = datetime_valid(request.args.get('from'), 'from')
        if fromDate_valid == True:
            fromDate = isoparse(request.args.get('from')).timestamp()
    else:
        fromDate_valid = True
        fromDate = 0
       
    if request.args.get('until') is not None:
        untilDate_valid = datetime_valid(request.args.get('until'), 'until')
        if untilDate_valid == True:
            untilDate = isoparse(request.args.get('until')).timestamp()
    else:
        untilDate_valid = True
        untilDate = time.time()        
    
    #validate both the setSpec path (if applicable) and next page integer
    resumptionToken_valid = validate_token(resumptionToken, fromDate, untilDate)
 
    #evaluate verb parameter to determine the particular OAI-PMH XML response
    if verb:
        if verb == "Identify":
            dom = identify(verb)
        elif verb == "ListMetadataFormats":
            dom = list_metadata_formats(verb)
        elif verb == "ListSets":
            dom = list_sets(verb)
        elif verb == "ListIdentifiers" or verb == "ListRecords":
            #validate other responses
            if metadataPrefix != 'dplava' and len(resumptionToken) == 0:
                #metadataPrefix is not necessary for resumptionTokens
                dom = error(verb, code="cannotDisseminateFormat")
            elif fromDate_valid == False:
                dom = error(verb, code="badArgument", message = "from parameter is an invalid ISO dateTime")
            elif untilDate_valid == False:
                dom = error(verb, code="badArgument", message = "until parameter is an invalid ISO dateTime")
            elif len(resumptionToken) > 0 and resumptionToken_valid == False:
                dom = error(verb, code="badResumptionToken", message = "The value of the resumptionToken argument is invalid or expired.")
            else:
                dom = list_identifiers_records(verb, setSpec, fromDate, untilDate, resumptionToken)
        else:
            dom = error(verb, code="badVerb")
    else:
        dom = error(verb, code="badVerb")
    
    ET.indent(dom, space="\t", level=0)    
    xml_str = ET.tostring(dom, encoding="utf-8", xml_declaration=True)        
    return Response(xml_str, mimetype="application/xml")
    
if __name__=="__main__":
    app.run(debug=True)