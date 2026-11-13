"""
Author: Ethan Gruber
Date: November 2026
Function: Generate OAI-PMH XML from the directory structure of Github repositories of Dublic Core metadata. 
This script operates on the command line for test purposes by providing OAI verbs to generate XML responses. It can be included to run as a Flask webapp.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, glob, sys, time, argparse, re, datetime
from dateutil.parser import isoparse
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date

OAI_SCHEMA = "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
DATA_DIR = "../data"

PREFIX = "oai:" + "digitalvirginias.org"
ROWS = 100

#----------------------
#OAI-PMH VERB RESPONSES
#----------------------

# --- IDENTIFY ---
#provide content hub metadata
def identify(verb):
    root = construct_dom(verb)
    
    identify = ET.Element("Identify")
    ET.SubElement(identify, "repositoryName").text = "Digital Virginias"
    ET.SubElement(identify, "protocolVersion").text = "2.0"
    ET.SubElement(identify, "deletedRecord").text = "no"
    ET.SubElement(identify, "granularity").text = "YYYY-MM-DDThh:mm:ssZ"
    
    
    #remaining metadata goes here
    
    root.append(identify)
    
    return root

# --- LIST IDENTIFIERS AND LIST RECORDS ---
def list_identifiers_records(verb, setSpec, fromDate, untilDate, resumptionToken):
    root = construct_dom(verb)
    
    file_list = get_file_list(setSpec, fromDate, untilDate)
    
    if len(file_list) > 0:
        total = len(file_list)
        
        node = ET.Element(verb)
        
        #if there are more files than the ROWS constant, then split into number of rows, with an index established by the resumptionToken, which should be an integer value
        if total > ROWS:
            start = int(resumptionToken)
            end = start + ROWS
                
            generate_items(verb, node, file_list[start:end])
            
            #add resumptionToken if there are more pages to harvest
            if start + ROWS < total:
                resumptionToken = str(end)
            else:
                resumptionToken = ''
            
            ET.SubElement(node, "resumptionToken", completeListSize=str(total), cursor=str(start)).text = resumptionToken
                
        else:
            #output metadata for sets less than 100 items
            generate_items(verb, node, file_list)        
        
        root.append(node)
    else:
        ET.SubElement(root, "error", code="noRecordsMatch").text = "The combination of the values of the from, until, and set arguments results in an empty list."
    
    return root

#with or without setSpec, use glob to get a list of XML files for ListIdentifers
def get_file_list(setSpec, fromDate, untilDate):
    
    file_list = []
    
    if len(setSpec) > 0:
        path = setSpec.split(":")
        if len(path) == 2:
            files = glob.glob(os.path.join(DATA_DIR, f"{path[0]}/{path[1]}/*.xml"))
        else:
            files = glob.glob(os.path.join(DATA_DIR, f"{path[0]}/*.xml"))
            
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
        #get modification date in epoch time and ensure it is before the start and end date.
        modified = os.path.getmtime(path)
        #dateTime = time.strftime("%Y-%m-%d", time.strptime(modified))
        
        if modified >= fromDate and modified <= untilDate:
            file_list.append(path)
        
            
    return file_list

#generate each header with included OAI_DC metadata, extracted directly from XML file on filesystem
def generate_items(verb, node, file_list):
    for path in file_list:
        
        #parse directory and file structure without PATH in order to construct the setSpec and identifier
        sequence = path.replace(DATA_DIR, "").replace(".xml", "")
        sequence = sequence[1:] if sequence[0] == "/" else sequence
        
        #prepend institutional prefix and turn path structure into colons for unique identifier
        components = sequence.split("/")
        setSpec = ":".join(components[0:-1])
        identifier = PREFIX + ":" + ":".join(components)
       
        #convert modification timestamp of file to proper ISO date
        modified = time.strptime(time.ctime(os.path.getmtime(path)))
        
        if verb == "ListIdentifiers":
            header = generate_header(identifier, modified, setSpec)
            node.append(header)
            
        elif verb == "ListRecords":
            record = ET.Element("record")
            #insert header
            header = generate_header(identifier, modified, setSpec)
            record.append(header)
            
            #insert metadata record from filesystem
            metadata = ET.Element("metadata")
            xml_file = ET.parse(path).getroot()
            metadata.append(xml_file)
            record.append(metadata)
            
            #insert record element into ListRecords node
            node.append(record)
        
    return node

def generate_header(identifier, modified, setSpec):
    header = ET.Element("header")        
    ET.SubElement(header, "identifier").text = identifier
    ET.SubElement(header, "datestamp").text = time.strftime("%Y-%m-%dT%H:%M:%SZ", modified)
    ET.SubElement(header, "setSpec").text = setSpec
    
    return header
       
# --- LISTMETADATAFORMATS ---
def list_metadata_formats(verb):
    root = construct_dom(verb)
    
    node = ET.Element("ListMetadataFormats")
    metadataFormat = ET.Element("metadataFormat")
    
    ET.SubElement(metadataFormat, "metadataPrefix").text = "dplava"
    ET.SubElement(metadataFormat, "schema").text = "http://dplava.lib.virginia.edu/dplava.xsd"
    ET.SubElement(metadataFormat, "metadataNamespace").text = "http://dplava.lib.virginia.edu"
    
    node.append(metadataFormat)    
    root.append(node)
    return root           
        
# --- LIST SETS ---
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
    elif code == "badArgument" or code == "badResumptionToken":
        if message is not None:
            text = message
        else:
            text = "Invalid parameter provided to API endpoint"
            
        ET.SubElement(root, "error", code=code).text = text
    else:
        ET.SubElement(root, "error", code="other").text = "other"

    return root

# CONSTRUCT DOM for OAI-PMH ROOT ELEMENT
def construct_dom(verb):
    ET.register_namespace('',"http://www.openarchives.org/OAI/2.0/")
    ET.register_namespace('oai_dc',"http://www.openarchives.org/OAI/2.0/oai_dc/")
    ET.register_namespace('dcterms',"http://purl.org/dc/terms/")
    ET.register_namespace('edm',"http://www.europeana.eu/schemas/edm/")
    ET.register_namespace('dplava',"http://dplava.lib.virginia.edu")
    ET.register_namespace('xsi',"http://www.w3.org/2001/XMLSchema-instance")  
    
    #create root element 
    root = ET.Element('OAI-PMH', attrib={"xmlns": "http://www.openarchives.org/OAI/2.0/",
                                         "xmlns:dc": "http://purl.org/dc/elements/1.1/",
                                         "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                                         "xmlns:dcterms": "http://purl.org/dc/terms/",
                                         "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                                         "xmlns:edm": "http://www.europeana.eu/schemas/edm/",
                                         "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                         "xsi:schemaLocation": OAI_SCHEMA}) 
    ET.indent(root, space="\t", level=0)
    
    #create propert ISO 8601 dateTime for GMT without milliseconds
    ET.SubElement(root, "responseDate").text = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ET.SubElement(root, "request", verb=verb).text = "url"
    
    return root

#------------------------
#HELPER FUNCTIONS
#------------------------

#validate ISO 8601 date times, from https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
def datetime_valid(dt_str, prop):
    #test regex for ISO date (YYYY-MM-DD)
    iso_date = bool(re.search(r"^\d{4}-([0][1-9]|1[0-2])-([0][1-9]|[1-2]\d|3[01])$", dt_str))
    
    #append start or end time in seconds to an ISO date
    if iso_date == True:
        if prop == "from":
            dt_str = dt_str + "T00:00:00+00:00"
        elif prop == "until":
            dt_str = dt_str + "T23:59:59+00:00"
    
    #validate dateTime
    try:
        datetime.datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False

#there is only a root in OAI PMH
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--verb", help="OAI-PMH verb parameter")
    parser.add_argument("--metadataPrefix", help="metadataPrefox parameter for ListIdentifiers")
    parser.add_argument("--setSpec", help="setSpec parameter for ListIdentifiers")
    parser.add_argument("--fromDate", help="from parameter for ListIdentifiers")
    parser.add_argument("--untilDate", help="until parameter for ListIdentifiers")
    parser.add_argument("--resumptionToken", help="resumptionToken parameter for ListIdentifiers")
    args = parser.parse_args()
    
    verb = '' if args.verb is None else args.verb
    metadataPrefix = '' if args.metadataPrefix is None else args.metadataPrefix
    setSpec = '' if args.setSpec is None else args.setSpec
    resumptionToken = 0 if args.resumptionToken is None else args.resumptionToken
    
    #validate from and until parameters and convert to epoch time. If they are blank, then set from to 0 time from Epoch and until to current time. Otherwise use provided parameters
    if args.fromDate is not None:
        fromDate_valid = datetime_valid(args.fromDate, 'from')
        if fromDate_valid == True:
            fromDate = isoparse(args.fromDate).timestamp()
    else:
        fromDate_valid = True
        fromDate = 0
       
    if args.untilDate is not None:
        untilDate_valid = datetime_valid(args.untilDate, 'until')
        if untilDate_valid == True:
            untilDate = isoparse(args.untilDate).timestamp()
    else:
        untilDate_valid = True
        untilDate = time.time() 
        
        
    #validate resumptionToken to ensure it is an integer    
    try:
        int(resumptionToken)
        resumptionToken_valid = True
    except:
        resumptionToken_valid = False
 
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
            if metadataPrefix != 'dplava':
                dom = error(verb, code="cannotDisseminateFormat")
            elif fromDate_valid == False:
                dom = error(verb, code="badArgument", message = "from parameter is an invalid ISO dateTime")
            elif untilDate_valid == False:
                dom = error(verb, code="badArgument", message = "until parameter is an invalid ISO dateTime")
            elif resumptionToken_valid == False:
                dom = error(verb, code="badResumptionToken", message = "The value of the resumptionToken argument is invalid or expired.")
            else:
                dom = list_identifiers_records(verb, setSpec, fromDate, untilDate, resumptionToken)
            
            
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
    