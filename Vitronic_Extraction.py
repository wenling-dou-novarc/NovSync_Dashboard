import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define scope to files created by the app
SCOPES = ['https://www.googleapis.com/auth/drive.file']
WATCH_DIRECTORY = R"E:\Results\SingleWeldResults"
TARGET_FOLDER_ID = '1XDjdg-0XBK07QA-K1vZ2qKDGjqsX95Qt'

def authenticate_drive():
    # Verfifies previous login
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If the login expired or doesn't exist, a browser window is used to authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
           creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Return a live connection to the Google Drive API
    return build('drive', 'v3', credentials=creds)

# Package and send the xml file and send it to Google Drive
def upload_xml_to_drive(file_path, service):
    try:
        # Delay to ensure the file is fully written before uploading
        time.sleep(1.5)

        file = type('File', (), {'name': os.path.basename(file_path)})()
        file_metadata = {'name': file.name, 'parents': [TARGET_FOLDER_ID]}

        # Package the local xml, MediaFileUpload packages the contents of the original file without modifying it
        media = MediaFileUpload(file_path, mimetype='text/xml', resumable=True)

        # Upload the packaged xml to Google Drive
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"[{time.strftime('%H:%M:%S')}] Success! Uploaded {file.name} to Drive (ID: {file.get('id')})")
   
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Error uploading {file_path}: {e}")

# Configure the watchdog library to monitor the directory for new xml files
class XMLFileHandler(FileSystemEventHandler):
    def __init__(self, drive_service):
        self.drive_service = drive_service

    def on_created(self, event):
        filename = os.path.basename(event.src_path)

        # Filter for xml files starting with "WeldResult"
        if not event.is_directory and filename.lower().endswith('.xml') and filename.startswith('WeldResult'):
            print(f"[{time.strftime('%H:%M:%S')}] New WeldResult detected: {filename}. Uploading...")
            upload_xml_to_drive(event.src_path, self.drive_service)

# Login into Google Drive and start monitoring the directory for new xml files
if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        print(f"Error: The directory {WATCH_DIRECTORY} does not exist.")
        exit()

    # 1. Log into Google Drive right when the script starts
    print("Authenticating with Google Drive...")
    drive_service = authenticate_drive()
    print("Authentication successful.")

    # 2. Set up the folder watcher
    event_handler = XMLHandler(drive_service)
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=True)
    
    # 3. Start watching forever
    observer.start()
    print(f"\nWatching for new WeldResult XML files in {WATCH_DIRECTORY}...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nMonitoring stopped by user.")
        
    observer.join()
                         