import json
import os
import MySQLdb
from dotenv import load_dotenv
import certifi

load_dotenv()

def get_db_connection():
    ssl_cert = certifi.where()
    config = {
        "host": os.getenv("DATABASE_HOST"),
        "user": os.getenv("DATABASE_USERNAME"),
        "passwd": os.getenv("DATABASE_PASSWORD"),
        "db": os.getenv("DATABASE"),
        "autocommit": True,
        "ssl": {
            "ca": ssl_cert,
            "verify_mode": "VERIFY_IDENTITY"
        }
    }
    return MySQLdb.connect(**config)

def migrate_data():
    try:
        # Read local gallery data
        with open("data/gallery_data.json", "r") as f:
            items = json.load(f)
            print(f"Found {len(items)} items to migrate")

        # Connect to PlanetScale
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gallery (
                id VARCHAR(255) PRIMARY KEY,
                url TEXT NOT NULL,
                description TEXT,
                reflection TEXT,
                timestamp DATETIME NOT NULL,
                votes INT DEFAULT 0,
                pixel_count INT DEFAULT 0
            )
        """)

        # Insert items
        for item in items:
            try:
                cursor.execute("""
                    INSERT IGNORE INTO gallery 
                    (id, url, description, reflection, timestamp, votes, pixel_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    item["id"],
                    item.get("url", ""),
                    item.get("description", ""),
                    item.get("reflection", ""),
                    item["timestamp"],
                    item.get("votes", 0),
                    item.get("pixel_count", 0)
                ))
                print(f"Migrated item {item['id']}")
            except Exception as e:
                print(f"Error migrating item {item['id']}: {e}")
                continue

        print("Migration completed successfully!")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    migrate_data() 