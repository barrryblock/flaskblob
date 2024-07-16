from azure.cosmos import CosmosClient, exceptions
from azure.storage.blob import BlobServiceClient
from flask import Flask, abort, jsonify, request, redirect
import os


app = Flask(__name__)

os.environ['AZURE_STORAGE_CONNECTION_STRING'] = 'BlobEndpoint=https://flaskserver.blob.core.windows.net/;QueueEndpoint=https://flaskserver.queue.core.windows.net/;FileEndpoint=https://flaskserver.file.core.windows.net/;TableEndpoint=https://flaskserver.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiyx&se=2024-07-14T03:09:05Z&st=2024-07-13T19:09:05Z&spr=https&sig=mkwroHgG%2BswzCaTXyfkwYyfZSnxjAbcCDbxb2%2B0cvcs%3D'
os.environ['AZURE_COSMOS_ENDPOINT'] = ''
os.environ['AZURE_COSMOS_KEY'] = ''

connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING') # retrieve the connection string from the environment variable
container_name = "uploaded-files" # container name in which images will be store in the storage account
cosmos_endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
cosmos_key = os.getenv('AZURE_COSMOS_KEY')
database_name = 'DeviceDatabase'
container_name = 'devices'

blob_service_client = BlobServiceClient.from_connection_string(conn_str=connect_str) # create a blob service client to interact with the storage account
try:
    container_client = blob_service_client.get_container_client(container=container_name) # get container client to interact with the container in which images will be stored
    container_client.get_container_properties() # get properties of the container to force exception to be thrown if container does not exist
except Exception as e:
    print(e)
    print("Creating container...")
    container_client = blob_service_client.create_container(container_name) # create a container in the storage account if it does not exist

# Initialize Azure Cosmos DB client
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.create_database_if_not_exists(id=database_name)
device_container = database.create_container_if_not_exists(
    id=container_name,
    partition_key=CosmosClient.PartitionKey(path="/deviceId"),
    offer_throughput=400
)

# Middleware to validate device
@app.before_request
def validate_device():
    if request.path.startswith('/api') or request.path.startswith('/upload-files'):
        device_id = request.headers.get('Device-ID')
        device_token = request.headers.get('Device-Token')

        if not device_id or not device_token:
            abort(401, 'Device authentication required.')
        
        try:
            device = device_container.read_item(item=device_id, partition_key=device_id)
            if device['deviceToken'] != device_token:
                abort(403, 'Invalid device token.')
        except exceptions.CosmosResourceNotFoundError:
            abort(403, 'Device not registered.')

# Endpoint to register a device
@app.route("/register-device", methods=["POST"])
def register_device():
    device_id = request.json.get('deviceId')
    device_token = request.json.get('deviceToken')

    if not device_id or not device_token:
        abort(400, 'Device ID and token are required.')

    try:
        device_container.create_item(body={'deviceId': device_id, 'deviceToken': device_token})
    except exceptions.CosmosResourceExistsError:
        abort(409, 'Device already registered.')

    return jsonify({'message': 'Device registered successfully.'}), 201

# Endpoint to attest a device
@app.route("/attest-device", methods=["POST"])
def attest_device():
    device_id = request.json.get('deviceId')
    device_token = request.json.get('deviceToken')

    if not device_id or not device_token:
        abort(400, 'Device ID and token are required.')

    try:
        device = device_container.read_item(item=device_id, partition_key=device_id)
        if device['deviceToken'] == device_token:
            return jsonify({'message': 'Device attested successfully.'}), 200
        else:
            abort(403, 'Invalid device token.')
    except exceptions.CosmosResourceNotFoundError:
        abort(403, 'Device not registered.')

@app.route("/")
def view_files():
    blob_items = container_client.list_blobs() # list all the blobs in the container

    img_html = "<div style='display: flex; justify-content: space-between; flex-wrap: wrap;'>"

    for blob in blob_items:
        blob_client = container_client.get_blob_client(blob=blob.name) # get blob client to interact with the blob and get blob url
        img_html += "<img src='{}' width='auto' height='200' style='margin: 0.5em 0;'/>".format(blob_client.url) # get the blob url and append it to the html
    
    img_html += "</div>"

    # return the html with the images
    return """
    <head>
    <!-- CSS only -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3" crossorigin="anonymous">
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
            <div class="container">
                <a class="navbar-brand" href="/">files App</a>
            </div>
        </nav>
        <div class="container">
            <div class="card" style="margin: 1em 0; padding: 1em 0 0 0; align-items: center;">
                <h3>Upload new File</h3>
                <div class="form-group">
                    <form method="post" action="/upload-files" 
                        enctype="multipart/form-data">
                        <div style="display: flex;">
                            <input type="file" accept=".png, .jpeg, .jpg, .gif" name="files" multiple class="form-control" style="margin-right: 1em;">
                            <input type="submit" class="btn btn-primary">
                        </div>
                    </form>
                </div> 
            </div>
        
    """ + img_html + "</div></body>"

@app.route("/api/files", methods=["GET"])
def get_files_json():
    blob_items = container_client.list_blobs()  # list all the blobs in the container
    files = []

    for blob in blob_items:
        blob_client = container_client.get_blob_client(blob=blob.name)  # get blob client to interact with the blob and get blob url
        files.append({
            "name": blob.name,
            "url": blob_client.url
        })

    return jsonify(files)

#flask endpoint to upload a photo
@app.route("/upload-files", methods=["POST"])
def upload_files():
    filenames = ""

    for file in request.files.getlist("uploaded-files"):
        try:
            container_client.upload_blob(file.filename, file) # upload the file to the container using the filename as the blob name
            filenames += file.filename + "<br /> "
        except Exception as e:
            print(e)
            print("Ignoring duplicate filenames") # ignore duplicate filenames
        
    return redirect('/') 

if __name__ == "__main__":
    app.run(debug=True)