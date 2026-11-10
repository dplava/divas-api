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

app = Flask(__name__)

#there is only a root in OAI PMH
@app.route("/")
def main():
    verb = request.args.get('verb', '')
    
    if len(verb) > 0:
        if verb == "Identify":
            return identify(verb)
        else:
            return error(verb, code="badVerb")
    else:
        return error(verb, code="badVerb")


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
    
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, mimetype="application/xml")

#generate error responses by evaluating verbs or other parameters
def error(verb, code: str):
    root = construct_dom(verb)
    
    if code == "badVerb":
        ET.SubElement(root, "error", code="badVerb").text = "Illegal OAI verb"
    else:
        ET.SubElement(root, "error", code="other").text = "other"

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(body, mimetype="application/xml")
    
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
    uvicorn.run(app, port=8000)