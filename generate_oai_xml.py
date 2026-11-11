"""
Author: Ethan Gruber
Date: November 2026
Function: Generate OAI-PMH XML from the directory structure of Github repositories of Dublic Core metadata. 
This script operates on the command line for test purposes by providing OAI verbs to generate XML responses. It can be included to run as a Flask webapp.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, sys, datetime, argparse
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date

OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
DATA_DIR = "../data"

PREFIX = "divas"

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
    
    return root

def list_identifiers(verb):
    root = construct_dom(verb)
    
    return root

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
    
    return root

#generate error responses by evaluating verbs or other parameters
def error(verb, code: str):
    root = construct_dom(verb)
    
    if code == "badVerb":
        ET.SubElement(root, "error", code=code).text = "Value of the verb argument is not a legal OAI-PMH verb, the verb argument is missing, or the verb argument is repeated."
    elif code == "cannotDisseminateFormat":
        ET.SubElement(root, "error", code=code).text = "The metadata format identified by the value given for the metadataPrefix argument is not supported by the item or by the repository."
    else:
        ET.SubElement(root, "error", code="other").text = "other"

    return root
    
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

#there is only a root in OAI PMH
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--verb", help="OAI-PMH verb parameter")
    parser.add_argument("--metadataPrefix", help="metadataPrefox parameter for ListIdentifiers")
    args = parser.parse_args()
    
    verb = args.verb
      
    if verb:
        if verb == "Identify":
            dom = identify(verb)
        elif verb == "ListSets":
            dom = list_sets(verb)
        elif verb == "ListIdentifiers":
            #validate other responses
            if args.metadataPrefix != 'oai_dc':
                dom = error(verb, code="cannotDisseminateFormat")
            else:
                dom = list_identifiers(verb)
            
            
        else:
            dom = error(verb, code="badVerb")
    else:
        dom = error(verb, code="badVerb")
    
    #indent and serialize DOM into a string for output
    ET.indent(dom, space="\t", level=0)    
    xml_str = ET.tostring(dom, encoding="utf-8", xml_declaration=True)    
    print(xml_str.decode("utf-8"))
    
if __name__=="__main__":
    main()
    