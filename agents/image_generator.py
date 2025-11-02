import os
import requests
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from PIL import Image

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET")
)

def resize_for_instagram(image_path: str) -> str:
    """
    Resize image to Instagram-compatible aspect ratio (1:1 square).
    Returns path to resized image.
    """
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # Calculate aspect ratio
        aspect_ratio = width / height
        
        # Instagram supported ratios:
        # 1:1 (square), 4:5 (portrait), 1.91:1 (landscape)
        # We'll convert to 1:1 (square) for maximum compatibility
        
        # Determine the smaller dimension
        min_dimension = min(width, height)
        
        # Crop to square (center crop)
        left = (width - min_dimension) // 2
        top = (height - min_dimension) // 2
        right = left + min_dimension
        bottom = top + min_dimension
        
        img_cropped = img.crop((left, top, right, bottom))
        
        # Resize to Instagram's recommended size (1080x1080)
        img_resized = img_cropped.resize((1080, 1080), Image.Resampling.LANCZOS)
        
        # Save to new file
        resized_path = image_path.replace('.png', '_instagram.png').replace('.jpg', '_instagram.jpg')
        img_resized.save(resized_path, quality=95)
        
        print(f"✅ Image resized to 1080x1080 (1:1 aspect ratio): {resized_path}")
        return resized_path
        
    except Exception as e:
        print(f"⚠️ Image resize failed: {e}. Using original image.")
        return image_path

def instagram_post_run(image_path: str, caption: str = "") -> dict:
    """
    Uploads image to Cloudinary, then posts the image to Instagram via the Graph API.
    
    Args:
        image_path: Path to the image file to upload
        caption: Caption text for the Instagram post
        
    Returns:
        dict with post_status, media_id, and image_url
    """
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")

    if not access_token or not business_account_id:
        return {"post_status": "Missing Instagram API credentials."}

    if not image_path or not os.path.exists(image_path):
        return {"post_status": f"Image file not found: {image_path}"}

    try:
        # Resize image to Instagram-compatible aspect ratio
        print(f"📐 Resizing image for Instagram compatibility...")
        resized_image_path = resize_for_instagram(image_path)
        
        print(f"📤 Uploading image to Cloudinary: {resized_image_path}")
        upload_result = cloudinary.uploader.upload(resized_image_path)
        image_url = upload_result.get("secure_url")

        if not image_url:
            return {"post_status": "Cloudinary upload failed."}

        print("Cloudinary upload successful.")
        print("Image URL:", image_url)

        # Step 1: Upload image to Instagram container
        print("Sending image to Instagram via Graph API...")
        upload_url = f"https://graph.facebook.com/v21.0/{business_account_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token
        }
        upload_response = requests.post(upload_url, data=payload)
        upload_data = upload_response.json()
        print("Upload response:", upload_data)

        if "id" not in upload_data:
            error_msg = upload_data.get("error", {}).get("message", str(upload_data))
            return {"post_status": f"Upload failed: {error_msg}"}

        container_id = upload_data["id"]

        # Step 2: Publish container
        print("Publishing post to Instagram...")
        publish_url = f"https://graph.facebook.com/v21.0/{business_account_id}/media_publish"
        publish_response = requests.post(
            publish_url,
            data={
                "creation_id": container_id,
                "access_token": access_token
            },
        )
        publish_data = publish_response.json()
        print("Publish response:", publish_data)

        if "id" not in publish_data:
            error_msg = publish_data.get("error", {}).get("message", str(publish_data))
            return {"post_status": f"Publish failed: {error_msg}"}

        # Cleanup resized image if it was created
        if resized_image_path != image_path and os.path.exists(resized_image_path):
            try:
                os.remove(resized_image_path)
                print(f"🧹 Cleaned up resized image: {resized_image_path}")
            except:
                pass

        return {
            "post_status": "Successfully posted to Instagram!",
            "media_id": publish_data["id"],
            "caption": caption,
            "image_url": image_url,
        }

    except Exception as e:
        print(f"Exception occurred: {str(e)}")
        return {"post_status": f"Exception: {str(e)}"}


insta_tool = FunctionTool(func=instagram_post_run)

instagram_poster_agent = Agent(
    name="InstagramPosterAgent",
    model="gemini-2.0-flash-exp",
    instruction="""
You are an Instagram Poster Agent.
When given an image path and caption, use the instagram_post_run tool to:
1. Upload the image to Cloudinary
2. Post it to Instagram via the Graph API
3. Return the post status, media ID, and image URL
""",
    description="Uploads image to Cloudinary and posts to Instagram via Graph API.",
    tools=[insta_tool],
)