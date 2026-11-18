"""
Author: Ethan Gruber
Date: November 2026
Function: Create an OAI-PMH wrapper on top of DPLAVA Github repositories of Dublin Core metadata.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, sys, datetime, time
from dateutil.parser import isoparse
import xml.etree.ElementTree as ET
from typing import Union
from flask import Flask, request, redirect, Response
from markupsafe import escape

#include local OAI-PMH output processing functions
from generate_oai_xml import error, identify, list_sets, list_metadata_formats, list_identifiers_records, get_record, validate_token

#acceptable metadataPrefixes
METADATA_PREFIXES = ["dplava", "dpla_map"]

app = Flask(__name__)

@app.route("/")
def main():
     return redirect("/oai", code=302)

#there is only a root in OAI PMH
@app.route("/oai")
def oai_pmh():
    
    verb = request.args.get('verb', '')
    metadataPrefix = request.args.get('metadataPrefix', '')
    setSpec = request.args.get('setSpec', '')
    resumptionToken = request.args.get('resumptionToken', '')
    identifier = request.args.get('identifier', '')
    
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
        elif verb == "GetRecord":   
            if metadataPrefix not in METADATA_PREFIXES:
                dom = error(verb, code="cannotDisseminateFormat")
            elif len(identifier) == 0:    
                dom = error(verb, code="badArgument", message = "identifier is not set")   
            else:
                dom = get_record(verb, metadataPrefix, identifier)                
        elif verb == "ListIdentifiers" or verb == "ListRecords":
            #validate other responses
            if metadataPrefix not in METADATA_PREFIXES and len(resumptionToken) == 0:
                #metadataPrefix is not necessary for resumptionTokens
                dom = error(verb, code="cannotDisseminateFormat")
            elif fromDate_valid == False:
                dom = error(verb, code="badArgument", message = "from parameter is an invalid ISO dateTime")
            elif untilDate_valid == False:
                dom = error(verb, code="badArgument", message = "until parameter is an invalid ISO dateTime")
            elif len(resumptionToken) > 0 and resumptionToken_valid == False:
                dom = error(verb, code="badResumptionToken", message = "The value of the resumptionToken argument is invalid or expired.")
            else:
                dom = list_identifiers_records(verb, setSpec, metadataPrefix, fromDate, untilDate, resumptionToken)
        else:
            dom = error(verb, code="badVerb")
    else:
        dom = error(verb, code="badVerb")
    
    ET.indent(dom, space="\t", level=0)    
    xml_str = ET.tostring(dom, encoding="utf-8", xml_declaration=True)        
    return Response(xml_str, mimetype="application/xml")
    
if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)