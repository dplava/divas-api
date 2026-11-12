"""
Author: Ethan Gruber
Date: November 2026
Function: Generate OAI-PMH XML from the directory structure of Github repositories of Dublic Core metadata. 
This script operates on the command line for test purposes by providing OAI verbs to generate XML responses. It can be included to run as a Flask webapp.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, glob, sys, time, datetime, argparse
from dateutil.parser import isoparse
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date

OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
DATA_DIR = "../data"

PREFIX = "divas"
ROWS = 100

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

def list_identifiers(verb, setSpec, fromDate, untilDate):
    root = construct_dom(verb)
    
    file_list = get_file_list(setSpec, fromDate, untilDate)
    
    if len(file_list) > 0:
        list_identifiers = ET.Element("ListIdentifiers")
        
        #add
        
        root.append(list_identifiers)
    else:
        ET.SubElement(root, "error", code="noRecordsMatch").text = "The combination of the values of the from, until, and set arguments results in an empty list."
    
    return root

#with or without setSpec, use glob to get a list of XML files for ListIdentifers
def get_file_list(setSpec, fromDate, untilDate):
    
    file_list = []
    
    if len(setSpec) > 0:
        path = setSpec.split(":")
        files = glob.glob(os.path.join(DATA_DIR, f"{path[0]}/{path[1]}/*.xml"))
        if len(files) > 0:
            file_list = process_dates(files, fromDate, untilDate)
        
    else:
        files = glob.glob(os.path.join(DATA_DIR, "**/*.xml"), recursive=True)
        if len(files) > 0:
            file_list = process_dates(files, fromDate, untilDate)
        
    return file_list
    
#use the from and until parameters, if available, to reduce the XML files to a subset
def process_dates(files, fromDate, untilDate):
    file_list = []
    
    for path in files:
        modified = os.path.getmtime(path)
        #dateTime = time.strftime("%Y-%m-%d", time.strptime(modified))
        
        if modified >= fromDate and modified <= untilDate:
            file_list.append(path)
        
            
    return file_list
        

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
def error(verb, code: str, message: str = None):
    root = construct_dom(verb)
    
    if code == "badVerb":
        ET.SubElement(root, "error", code=code).text = "Value of the verb argument is not a legal OAI-PMH verb, the verb argument is missing, or the verb argument is repeated."
    elif code == "cannotDisseminateFormat":
        ET.SubElement(root, "error", code=code).text = "The metadata format identified by the value given for the metadataPrefix argument is not supported by the item or by the repository."
    elif code == "badArgument":
        if message is not None:
            text = message
        else:
            text = "Invalid parameter provided to API endpoint"
            
        ET.SubElement(root, "error", code=code).text = text
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

#validate ISO 8601 date times, from https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
def datetime_valid(dt_str):
    try:
        datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        return False
    return True

#there is only a root in OAI PMH
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--verb", help="OAI-PMH verb parameter")
    parser.add_argument("--metadataPrefix", help="metadataPrefox parameter for ListIdentifiers")
    parser.add_argument("--setSpec", help="setSpec parameter for ListIdentifiers")
    parser.add_argument("--fromDate", help="from parameter for ListIdentifiers")
    parser.add_argument("--untilDate", help="to parameter for ListIdentifiers")
    args = parser.parse_args()
    
    verb = '' if args.verb is None else args.verb
    metadataPrefix = '' if args.metadataPrefix is None else args.metadataPrefix
    setSpec = '' if args.setSpec is None else args.setSpec
    
    #validate from and until parameters. If they are blank, then set from to 0 time from Epoch and until to current time. Otherwise use provided parameters
    if args.fromDate is not None:
        fromDate_valid = datetime_valid(args.fromDate)
        if fromDate_valid == True:
            fromDate = args.fromDate
    else:
        fromDate_valid = True
        fromDate = 0
       
    if args.untilDate is not None:
        untilDate_valid = datetime_valid(args.untilDate)
        if untilDate_valid == True:
            untilDate = args.untilDate
    else:
        untilDate_valid = True
        untilDate = time.time() 
 
    if verb:
        if verb == "Identify":
            dom = identify(verb)
        elif verb == "ListSets":
            dom = list_sets(verb)
        elif verb == "ListIdentifiers":
            #validate other responses
            if metadataPrefix != 'oai_dc':
                dom = error(verb, code="cannotDisseminateFormat")
            elif fromDate_valid == False:
                dom = error(verb, code="badArgument", message = "from parameter is an invalid ISO dateTime")
            elif untilDate_valid == False:
                dom = error(verb, code="badArgument", message = "until parameter is an invalid ISO dateTime")
            else:
                dom = list_identifiers(verb, setSpec, fromDate, untilDate)
            
            
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
    