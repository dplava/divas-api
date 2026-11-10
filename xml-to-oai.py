"""
Author: Ethan Gruber
Date: November 2026
Function: Create an OAI-PMH wrapper on top of DPLAVA Github repositories of Dublin Core metadata.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, glob, sys, uvicorn, datetime
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date
from typing import Union
from flask import Flask, request, Response
from markupsafe import escape

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
            body = identify(verb)
        elif verb == "ListSets":
            body = list_sets(verb)
        elif verb == "ListIdentifiers":
            #validate other responses
            if metadataPrefix != 'oai_dc':
                body = error(verb, code="cannotDisseminateFormat")
            else:
                body = list_identifiers(verb)
            
            
        else:
            body = error(verb, code="badVerb")
    else:
        body = error(verb, code="badVerb")
        
    return Response(body, mimetype="application/xml")

#----------------------
#OAI-PMH VERB RESPONSES
#----------------------

#provide content hub metadata
def identify(verb):
    root = construct_dom(verb)
    
    identify = ET.Element("Identify")
    ET.SubElement(identify, "repositoryName").text = "Digital Virginias"
    
    #remaining metadata goes here
    
    root.append(identify)
    
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def list_identifiers(verb):
    root = construct_dom(verb)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def list_sets(verb):
    
    root = construct_dom(verb)
    
    #iterate through DATA_DIR and evaluate whether there are folders in the Github repo that can represent sets or if the set is for the entire organization
    sets = []
    for org in os.scandir(DATA_DIR):    
        if os.path.isdir(org):
            list = os.scandir(os.path.join(DATA_DIR, org))
            
            collections = []
            
            for item in list:
                if os.path.isdir(item) and not item.name.startswith("."):
                    collections.append(item.name)
                    
            if len(collections) > 0:
                for collection in collections:
                    sets.append(f"{org.name}:{collection}")
            else:
                sets.append(org.name)    
            
    #create ListSets
    list_sets = ET.Element("ListSets")
    for set in sets:
        set_node = ET.Element("set")
        ET.SubElement(set_node, "setSpec").text = set
        ET.SubElement(set_node, "setName").text = set
        list_sets.append(set_node)
        
    root.append(list_sets)
    
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

#generate error responses by evaluating verbs or other parameters
def error(verb, code: str):
    root = construct_dom(verb)
    
    if code == "badVerb":
        ET.SubElement(root, "error", code=code).text = "Value of the verb argument is not a legal OAI-PMH verb, the verb argument is missing, or the verb argument is repeated."
    elif code == "cannotDisseminateFormat":
        ET.SubElement(root, "error", code=code).text = "The metadata format identified by the value given for the metadataPrefix argument is not supported by the item or by the repository."
    else:
        ET.SubElement(root, "error", code="other").text = "other"

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    
def construct_dom(verb):
    ET.register_namespace('',"http://www.openarchives.org/OAI/2.0/")
    ET.register_namespace('oai_dc',"http://www.openarchives.org/OAI/2.0/oai_dc/")
    ET.register_namespace('dcterms',"http://purl.org/dc/terms/")
    ET.register_namespace('xsi',"http://www.w3.org/2001/XMLSchema-instance")   
    root = ET.Element('OAI-PMH', attrib={"xmlns": "http://www.openarchives.org/OAI/2.0/",
                                         "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                                         "xmlns:dcterms": "http://purl.org/dc/terms/",
                                         "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                         "xsi:schemaLocation": OAI_SCHEMA}) 
    ET.indent(root, space="\t", level=0)
    
    ET.SubElement(root, "responseDate").text = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ET.SubElement(root, "request", verb=verb).text = "url"
    
    return root
    
if __name__=="__main__":
    app.run(debug=True)