import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    if not firebase_admin._apps:
        # ✅ Render secret file path (mounted automatically)
        render_secret_path = "/etc/secrets/FIREBASE_SERVICE_ACCOUNT_KEY"

        # ✅ Local fallback for development
        local_secret_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "keys/FirebaseServiceAccountKey.json")

        # Pick whichever exists
        if Path(render_secret_path).exists():
            service_account_path = render_secret_path
        elif Path(local_secret_path).exists():
            service_account_path = local_secret_path
        else:
            raise FileNotFoundError(
                f"Service account key not found in either {render_secret_path} or {local_secret_path}. "
                "Please upload to Render Secret Files or add it locally."
            )

        cred = credentials.Certificate(str(service_account_path))

        # Firebase bucket
        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")

        if not storage_bucket:
            raise ValueError(
                "FIREBASE_STORAGE_BUCKET not found in environment variables. "
                "Please check your .env or Render environment variables."
            )

        firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket})
        print("✅ Firebase initialized successfully")
        print(f"📦 Storage bucket: {storage_bucket}")

# Initialize
initialize_firebase()

# Export clients
db = firestore.client()
bucket = storage.bucket()
