# divas-api
Python Flask web application for turning Digital Virginias metdata into OAI-PMH and/or other harvestable APIs

This API works by deploying the Digital Virginias Github repositories to a centralized folder on the filesystem, defined by the constant `DATA_DIR` in generate_oai_xml.py and webapp.py. The web application reads OAI-PMH request parameters and outputs the required XML, reporting errors according to the 2.0 specification. The endpoint supports date granularity to the nearest second, according the the modification date of the file on the filesystem. A nightly cron job could be established to pull changes from the Github repositories so that the endpoint is always up to date with the latest changes by Digital Virginias partners.

## File Description
**generate_oai_xml.py**: This script includes all of the functions necessary to process request parameters or command line arguments into OAI-PMH XML. The outputs of the API can be tested on the command line by passing arguments (see `python3 generate_oai_xml.py --help` for more information). 

**webapp.py**: This is a Flask webapp that maps the API to /oai. It includes the functions from generate_oai_xml.py for generating the output XML from the OAI-PMH endpoint.

## Metadata Formats
In the first phase, the OAI-PMH endpoint supports the `dplava` metadataPrefix, which will output the Digital Virginias Dublin Core metadata application profile verbatim from the XML file stored on the filesystem. Ultimately, more formats can be implemented that include minor normalization or transformation to improve quality and interoperability upon harvest into DPLA.

## Deployment
1. Create a folder in the filesystem and download all dplava Github repositories, except for the University of Virginia, which will have a different workflow (and also has an incompatible directory structure), for example, `/opt/dplava/data`
1. Download the divas-api Github repository elsewhere, for example, `/opt/dplava` 
1. Run in development/test mode on command line (which may require deploying a Python [virtual environment](https://python.land/virtual-environments/virtualenv)):
   1. Navigate to the divas-api folder and install required Python libraries: `pip install --no-cache-dir -r requirements.txt`
   1. Update the `DATA_DIR` constant in both Python files if necessary
   1. Start up the webapp: `flask --app webapp run`. Debug mode can be activated with `--debug` if actively testing code.
1. Production deployment with Docker with Gunicorn WSGI server:
   1. Navigate to the Github repository and run `sudo docker build -t divas-api-production .`
   1. Test that Docker puts up the web server by running `sudo docker run -p 5000:5000 divas-api-production`. It will be accessible at port 5000 on the server's domain name.
