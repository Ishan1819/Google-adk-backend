import os
import time
import requests
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

def instagram_post_run(image_path: str, caption: str = "✨ Check out this beautiful handmade creation! 🎨") -> dict:
    """
    Uploads image to Cloudinary, then posts the image to Instagram via the Graph API.
    """
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    if not access_token or not business_account_id:
        return {"post_status": "Missing Instagram API credentials.", "success": False}

    if not image_path or not os.path.exists(image_path):
        return {"post_status": f"Image file not found: {image_path}", "success": False}

    if not caption.strip():
        caption = "✨ Check out this beautiful handmade creation! 🎨 #handmade #artisan #craft"

    try:
        print(f"📤 Uploading image to Cloudinary: {image_path}")
        upload_result = cloudinary.uploader.upload(image_path)
        image_url = upload_result.get("secure_url")

        if not image_url:
            return {"post_status": "Cloudinary upload failed.", "success": False}

        print(f"✅ Cloudinary upload successful: {image_url}")

        # Step 1: Create Instagram media container
        print(f"📸 Creating Instagram media container with caption: {caption[:50]}...")
        upload_url = f"https://graph.facebook.com/v21.0/{business_account_id}/media"
        payload = {"image_url": image_url, "caption": caption, "access_token": access_token}
        upload_response = requests.post(upload_url, data=payload)
        upload_data = upload_response.json()
        print(f"📦 Container response: {upload_data}")

        if "id" not in upload_data:
            error_msg = upload_data.get("error", {}).get("message", str(upload_data))
            return {"post_status": f"Container creation failed: {error_msg}", "success": False}

        container_id = upload_data["id"]
        print(f"✅ Container created: {container_id}")

        # 🕒 Step 2: Wait or Poll for media to be ready
        print("⏳ Waiting for media to be processed by Instagram...")
        status_url = f"https://graph.facebook.com/v21.0/{container_id}?fields=status_code&access_token={access_token}"
        for attempt in range(5):  # retry up to 5 times (≈10 seconds total)
            status_resp = requests.get(status_url)
            status_json = status_resp.json()
            status = status_json.get("status_code", "")
            print(f"🧩 Attempt {attempt+1}: Media status = {status}")
            if status == "FINISHED":
                break
            time.sleep(2)

        if status != "FINISHED":
            print("⚠️ Media not ready after waiting. Trying to publish anyway...")

        # Step 3: Publish the container
        print("🚀 Publishing to Instagram...")
        publish_url = f"https://graph.facebook.com/v21.0/{business_account_id}/media_publish"
        publish_response = requests.post(publish_url, data={"creation_id": container_id, "access_token": access_token})
        publish_data = publish_response.json()
        print(f"📱 Publish response: {publish_data}")

        if "id" not in publish_data:
            error_msg = publish_data.get("error", {}).get("message", str(publish_data))
            return {"post_status": f"Publish failed: {error_msg}", "success": False}

        print(f"🎉 Successfully posted to Instagram! Media ID: {publish_data['id']}")
        return {
            "post_status": "Successfully posted to Instagram!",
            "success": True,
            "media_id": publish_data["id"],
            "caption": caption,
            "image_url": image_url,
        }

    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"post_status": f"Exception: {str(e)}", "success": False}


insta_tool = FunctionTool(func=instagram_post_run)

instagram_poster_agent = Agent(
    name="InstagramPosterAgent",
    model="gemini-2.0-flash-exp",
    instruction="""
You are an Instagram Poster Agent. Your job is to post images to Instagram.

When given an image path and caption:
1. ALWAYS call the instagram_post_run tool with the image_path and caption.
2. If the caption is empty, the tool auto-generates one.
3. Wait for the result and return it directly.
""",
    description="Uploads images to Cloudinary and posts to Instagram via Graph API.",
    tools=[insta_tool],
)
