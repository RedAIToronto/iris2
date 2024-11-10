import json
import requests
import os
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key = os.getenv('CLOUDINARY_API_KEY'),
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
)

def migrate_item_format(old_item):
    """Convert old gallery item format to new format"""
    try:
        # Upload image to Cloudinary if it's a local file
        if "filename" in old_item:
            filepath = os.path.join("static/gallery", old_item["filename"])
            if os.path.exists(filepath):
                print(f"Uploading {old_item['filename']} to Cloudinary...")
                upload_result = cloudinary.uploader.upload(
                    filepath,
                    folder="iris_gallery",
                    public_id=f"drawing_{old_item['id']}"
                )
                url = upload_result['secure_url']
            else:
                print(f"Warning: File not found: {filepath}")
                return None
        else:
            print(f"Warning: No filename in item: {old_item['id']}")
            return None

        # Convert to new format
        return {
            "id": old_item["id"],
            "url": url,
            "description": old_item.get("description", "Geometric pattern"),
            "reflection": "",  # Old format didn't have reflections
            "timestamp": old_item["timestamp"],
            "votes": 0,
            "pixel_count": 0  # We don't have this for old items
        }
    except Exception as e:
        print(f"Error migrating item {old_item.get('id')}: {e}")
        return None

def export_local_gallery():
    """Export and migrate local gallery data"""
    try:
        with open("data/gallery_data.json", "r") as f:
            old_data = json.load(f)
            
        # Migrate each item
        new_data = []
        for item in old_data:
            migrated_item = migrate_item_format(item)
            if migrated_item:
                new_data.append(migrated_item)
                
        print(f"Successfully migrated {len(new_data)} items")
        return new_data
            
    except Exception as e:
        print(f"Error reading local gallery: {e}")
        return None

def upload_to_production(data, prod_url, api_key):
    """Upload gallery data to production"""
    try:
        response = requests.post(
            f"{prod_url}/api/import-gallery",
            json=data,
            headers={"X-API-Key": api_key}
        )
        response.raise_for_status()
        print("Successfully uploaded gallery data!")
        print(response.json())
    except Exception as e:
        print(f"Error uploading to production: {e}")

if __name__ == "__main__":
    # Get production URL and API key from environment or input
    prod_url = os.getenv("PRODUCTION_URL") or input("Enter production URL (e.g., https://iris.onrender.com): ")
    api_key = os.getenv("API_KEY") or input("Enter API key: ")

    # Export and migrate local data
    print("Exporting and migrating local gallery data...")
    migrated_data = export_local_gallery()
    if migrated_data:
        print(f"Found {len(migrated_data)} items to upload")
        
        # Upload to production
        print("Uploading to production...")
        upload_to_production(migrated_data, prod_url, api_key)