"""
Author: Ethan Gruber
Date: November 2026
Function: Generate OAI-PMH XML from the directory structure of Github repositories of Dublic Core metadata. 
This script operates on the command line for test purposes by providing OAI verbs to generate XML responses. It can be included to run as a Flask webapp.
Perform minor normalization of ETDF dates and make OAI-PMH more compatible with existing DPLA harvesting services
"""

import os, glob, sys, time, argparse, re, datetime, yaml
from dateutil.parser import isoparse
import xml.etree.ElementTree as ET
from edtf import parse_edtf, text_to_edtf, struct_time_to_date

with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

#directory of Github repositories
DATA_DIR = "../data"
#OAI prefix format used for identifiers in OAI results
PREFIX = "oai:" + config["repository_domain"]
#number of records returned in a single response
ROWS = 100
#acceptable metadataPrefixes
METADATA_PREFIXES = ["dplava", "dpla_map"]

#----------------------
#OAI-PMH VERB RESPONSES
#----------------------

# --- IDENTIFY --- #
#provide content hub metadata
def identify(verb):
    modified = get_earliest_date()
    
    root = construct_dom(verb)
    
    identify = ET.Element("Identify")
    ET.SubElement(identify, "repositoryName").text = config["repository_name"]
    ET.SubElement(identify, "baseURL").text = "https://" + config["repository_domain"]
    ET.SubElement(identify, "protocolVersion").text = "2.0"
    ET.SubElement(identify, "earliestDatestamp").text = time.strftime("%Y-%m-%dT%H:%M:%SZ", modified)
    ET.SubElement(identify, "deletedRecord").text = "no"
    ET.SubElement(identify, "granularity").text = "YYYY-MM-DDThh:mm:ssZ"  
    ET.SubElement(identify, "adminEmail").text = config["admin_email"]
    
    root.append(identify)
    
    return root

#extract a list of all XML files in DATA_DIR and order by modification ascending (oldest first)
def get_earliest_date():
    files = glob.glob(os.path.join(DATA_DIR, "**/*.xml"), recursive=True)
    files.sort(key=os.path.getmtime)
    
    modified = time.strptime(time.ctime(os.path.getmtime(files[0])))
    return modified

# --- LIST IDENTIFIERS AND LIST RECORDS --- #
def list_identifiers_records(verb, setSpec, metadataPrefix, fromDate, untilDate, resumptionToken):
    
    root = construct_dom(verb, metadataPrefix=metadataPrefix)
    
    #extract setSpect from resumptionToken
    if len(resumptionToken) > 0:
        setSpec = resumptionToken.split("/")[0]
    
    file_list = get_file_list(setSpec, fromDate, untilDate)
    
    if len(file_list) > 0:
        total = len(file_list)
        
        node = ET.Element(verb)
        
        #if there are more files than the ROWS constant, then split into number of rows, with an index established by the resumptionToken, which should be an integer value
        if total > ROWS:
            start = int(resumptionToken.split("/")[1]) if len(resumptionToken) > 0 else 0
            end = start + ROWS
                
            generate_items(verb, metadataPrefix, node, file_list[start:end])
            
            #add resumptionToken if there are more pages to harvest
            if start + ROWS < total:        
                resumptionToken = f"{setSpec}/{end}"
            else:
                resumptionToken = ''
            
            ET.SubElement(node, "resumptionToken", completeListSize=str(total), cursor=str(start)).text = resumptionToken
                
        else:
            #output metadata for sets less than 100 items
            generate_items(verb, metadataPrefix, node, file_list)        
        
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
def generate_items(verb, metadataPrefix, node, file_list):
    for path in file_list:
        #accommodate Windows and Unix paths
        path = path.replace("\\", "/")
        
        #parse directory and file structure without PATH in order to construct the setSpec and identifier
        sequence = path.replace(DATA_DIR, "").replace(".xml", "")
        sequence = sequence[1:] if sequence[0] == "/" else sequence
        
        #prepend institutional prefix and turn path structure into colons for unique identifier. 
        components = sequence.split("/")
        #print(components)
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
            
            model = process_xml_file(path, metadataPrefix)            
            metadata.append(model)
            record.append(metadata)
            
            #insert record element into ListRecords node
            node.append(record)
        
    return node

#generate header element for ListIdentifiers or ListRecords
def generate_header(identifier, modified, setSpec):
    header = ET.Element("header")        
    ET.SubElement(header, "identifier").text = identifier
    ET.SubElement(header, "datestamp").text = time.strftime("%Y-%m-%dT%H:%M:%SZ", modified)
    ET.SubElement(header, "setSpec").text = setSpec
    
    return header
       
# --- LIST METADATA FORMATS --- #
def list_metadata_formats(verb):
    root = construct_dom(verb)
    
    node = ET.Element("ListMetadataFormats")
    
    #default dplava 'Dublin Core'-esque verbatim XML output
    metadataFormat = ET.Element("metadataFormat")    
    ET.SubElement(metadataFormat, "metadataPrefix").text = "dplava"
    ET.SubElement(metadataFormat, "schema").text = "http://dplava.lib.virginia.edu/dplava.xsd"
    ET.SubElement(metadataFormat, "metadataNamespace").text = "http://dplava.lib.virginia.edu"    
    node.append(metadataFormat)    
    
    #dpla_map
    metadataFormat = ET.Element("metadataFormat")    
    ET.SubElement(metadataFormat, "metadataPrefix").text = "dpla_map"
    ET.SubElement(metadataFormat, "metadataNamespace").text = "http://dp.la/about/map/"    
    node.append(metadataFormat)    
    
    root.append(node)
    return root           
        
# --- LIST SETS --- #
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

# --- GET RECORDS --- #
def get_record(verb, metadataPrefix, identifier):
    root = construct_dom(verb, metadataPrefix=metadataPrefix)
    
    path = identifier.replace(PREFIX, DATA_DIR).replace(":", "/") + ".xml"
    if os.path.exists(path):
        #generate header and load metadata from filesystem for single identifier
        
        #regenerate setSpec from identifier by stripping the OAI institutional prefix and excluding the filename
        components = identifier.replace(PREFIX + ":", "").split(":")
        setSpec = ":".join(components[0:-1])
        
        #convert modification timestamp of file to proper ISO date
        modified = time.strptime(time.ctime(os.path.getmtime(path)))
        
        record = ET.Element("record")
        #insert header
        header = generate_header(identifier, modified, setSpec)
        record.append(header)
        
        #insert metadata record from filesystem
        metadata = ET.Element("metadata")
        
        model = process_xml_file(path, metadataPrefix)
        metadata.append(model)
        record.append(metadata)
        
        #insert record element into ListRecords node
        root.append(record)
        
    else:
        ET.SubElement(root, "error", code="idDoesNotExist").text = "The value of the identifier argument is unknown or illegal in this repository."
    
    return root

#generate error responses by evaluating verbs or other parameters
def error(verb, code: str, message: str = None):
    root = construct_dom(verb)
    
    if code == "badVerb":
        ET.SubElement(root, "error", code=code).text = "Value of the verb argument is not a legal OAI-PMH verb, the verb argument is missing, or the verb argument is repeated."
    elif code == "cannotDisseminateFormat":
        ET.SubElement(root, "error", code=code).text = "The metadata format identified by the value given for the metadataPrefix argument is not supported by the item or by the repository."
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
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
def construct_dom(verb, metadataPrefix = None):
    ET.register_namespace('',"http://www.openarchives.org/OAI/2.0/")
    ET.register_namespace('oai_dc',"http://www.openarchives.org/OAI/2.0/oai_dc/")
    ET.register_namespace('dpla',"http://dp.la/about/map/")
    ET.register_namespace('dcterms',"http://purl.org/dc/terms/")
    ET.register_namespace('dc',"http://purl.org/dc/elements/1.1/")
    ET.register_namespace('edm',"http://www.europeana.eu/schemas/edm/")
    ET.register_namespace('dplava',"http://dplava.lib.virginia.edu")
    ET.register_namespace('xsi',"http://www.w3.org/2001/XMLSchema-instance")  
    
    #create root element 
    root = ET.Element('OAI-PMH', attrib={"xmlns": "http://www.openarchives.org/OAI/2.0/",
                                         "xmlns:dc": "http://purl.org/dc/elements/1.1/",
                                         "xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                                         "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd"}) 
    ET.indent(root, space="\t", level=0)
    
    #ET handling of namespaces is complex when embedding files from filesystem. This ensures no duplicate xmlns attributes
    if (verb != "ListRecords" and verb != "GetRecord") or metadataPrefix != "dplava":
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    
    #create propert ISO 8601 dateTime for GMT without milliseconds
    ET.SubElement(root, "responseDate").text = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ET.SubElement(root, "request", verb=verb).text = config["base_endpoint_url"]
    
    return root

#------------------------
#HELPER FUNCTIONS
#------------------------
#evaluate the metadataPrefix and either return the verbatim dplava model from filesystem or perform transformation into another model
def process_xml_file(path, metadataPrefix): 
    xml_file = ET.parse(path).getroot()
    
    if metadataPrefix == "dplava":
        return xml_file
    elif metadataPrefix == "dpla_map":
        #these are metadata elements written into other nodes and not carried in the dpla:SourceResource
        suppressed_elements = ["{http://www.europeana.eu/schemas/edm/}isShownAt",
                    "{http://www.europeana.eu/schemas/edm/}preview",
                    "{http://purl.org/dc/terms/}rights",
                    "{http://purl.org/dc/terms/}provenance"]
        
        root = ET.Element("rdf:RDF", attrib={"xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                                             "xmlns:ore": "http://www.openarchives.org/ore/terms/",
                                             "xmlns:dc": "http://purl.org/dc/elements/1.1/",                                         
                                             "xmlns:dpla": "http://dp.la/about/map/",
                                             "xmlns:edm": "http://www.europeana.eu/schemas/edm/"})
        
        
        cho_uri = xml_file.find("{http://www.europeana.eu/schemas/edm/}isShownAt").text
        thumbnail = xml_file.find("{http://www.europeana.eu/schemas/edm/}preview")
        rights = xml_file.find("{http://purl.org/dc/terms/}rights")
        
        #ore:Aggregation
        aggregation = ET.Element("ore:Aggregation")
        ET.SubElement(aggregation, "edm:aggregatedCHO", attrib={"rdf:resource": cho_uri})
        ET.SubElement(aggregation, "edm:provider").text = config["repository_name"]
        ET.SubElement(aggregation, "edm:dataProvider").text = xml_file.find("{http://purl.org/dc/terms/}provenance").text
        
        if thumbnail is not None:
            ET.SubElement(aggregation, "edm:preview", attrib={"rdf:resource": thumbnail.text})
        root.append(aggregation)
        
        if rights is not None:
            if bool(re.match("^https?:\/\/", rights.text)) == True:
                ET.SubElement(aggregation, "edm:rights", attrib={"rdf:resource": rights.text})
        
        #dpla:SourceResource metadata for cultural heritage object
        cho = ET.Element("dpla:SourceResource")        
        cho.set("rdf:about", cho_uri)
        
        for child in xml_file:
            
            #special processing for certain XML elements
            if child.tag == "{http://purl.org/dc/terms/}created" or child.tag == "{http://purl.org/dc/terms/}date":
                date_string = child.text.strip()
                try:
                    e = parse_edtf(date_string)
                except:
                    warn(f"Warning: {date} is not valid EDTF")   
                else:
                    fromDate = struct_time_to_date(e.lower_strict())
                    toDate = struct_time_to_date(e.upper_strict())
                    
                    date = ET.Element("dc:date")
                    time_span = ET.Element("edm:TimeSpan")
                    ET.SubElement(time_span, "edm:begin").text = str(fromDate)
                    ET.SubElement(time_span, "edm:end").text = str(toDate)
                    date.append(time_span)
                    cho.append(date)
            elif child.tag in suppressed_elements:
                pass
            else:
                cho.append(child)
        
        
        
        root.append(cho)
        
        return root

#validate ISO 8601 date times, from https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
def validate_dateTime(dt_str, prop):
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

def validate_token(resumptionToken, fromDate, untilDate):

    #resumptionToken_valid is True unless invalidated by the following conditions
    resumptionToken_valid = True
    
    if "/" in resumptionToken:
        pieces = resumptionToken.split("/")
        
        try:
            int(pieces[1])
        except:
            resumptionToken_valid = False
        else:
            setSpec = pieces[0]
            file_list = get_file_list(setSpec, fromDate, untilDate)
            
            if len(file_list) == 0:
                resumptionToken_valid = False
    else:
        resumptionToken_valid = False
    
    return resumptionToken_valid

#there is only a root in OAI PMH
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--verb", help="OAI-PMH verb parameter")
    parser.add_argument("--metadataPrefix", help="metadataPrefox parameter for ListIdentifiers/ListRecords/GetRecord")
    parser.add_argument("--setSpec", help="setSpec parameter for ListIdentifiers/ListRecords")
    parser.add_argument("--fromDate", help="from parameter for ListIdentifiers/ListRecords")
    parser.add_argument("--untilDate", help="until parameter for ListIdentifiers/ListRecords")
    parser.add_argument("--resumptionToken", help="resumptionToken parameter for ListIdentifiers/ListRecords")
    parser.add_argument("--identifier", help="identifier parameter for GetRecord")
    args = parser.parse_args()
    
    verb = '' if args.verb is None else args.verb
    metadataPrefix = '' if args.metadataPrefix is None else args.metadataPrefix
    setSpec = '' if args.setSpec is None else args.setSpec
    resumptionToken = '' if args.resumptionToken is None else args.resumptionToken
    identifier = '' if args.identifier is None else args.identifier
    
    #validate from and until parameters and convert to epoch time. If they are blank, then set from to 0 time from Epoch and until to current time. Otherwise use provided parameters
    if args.fromDate is not None:
        fromDate_valid = validate_dateTime(args.fromDate, 'from')
        if fromDate_valid == True:
            fromDate = isoparse(args.fromDate).timestamp()
    else:
        fromDate_valid = True
        fromDate = 0
       
    if args.untilDate is not None:
        untilDate_valid = validate_dateTime(args.untilDate, 'until')
        if untilDate_valid == True:
            untilDate = isoparse(args.untilDate).timestamp()
    else:
        untilDate_valid = True
        untilDate = time.time() 
        
        
    #validate resumptionToken to ensure it is an integer    
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
    
    #indent and serialize DOM into a string for output
    ET.indent(dom, space="\t", level=0)    
    xml_str = ET.tostring(dom, encoding="utf-8", xml_declaration=True)    
    print(xml_str.decode("utf-8"))
    
if __name__=="__main__":
    main()
    