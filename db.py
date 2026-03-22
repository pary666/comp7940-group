from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime, timezone


class MongoLogger:
    def __init__(self, config):
        mongo_uri = config["MONGODB"]["URI"]
        db_name = config["MONGODB"].get("DB_NAME", "chatbot_db")

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

        self.logs = self.db["logs"]
        self.user_profiles = self.db["user_profiles"]

    def log_chat(
        self,
        user_id,
        username,
        user_message,
        bot_response,
        status="success",
        error_message=None,
        feature="general_chat"
    ):
        doc = {
            "user_id": str(user_id),
            "username": username,
            "user_message": user_message,
            "bot_response": bot_response,
            "status": status,
            "error_message": error_message,
            "feature": feature,
            "timestamp": datetime.now(timezone.utc),
        }

        try:
            self.logs.insert_one(doc)
            print("Chat log inserted into MongoDB")
        except PyMongoError as e:
            print(f"[MongoDB] Failed to insert chat log: {e}")

    def save_user_interests(self, user_id, username, interests):
        try:
            self.user_profiles.update_one(
                {"user_id": str(user_id)},
                {
                    "$set": {
                        "user_id": str(user_id),
                        "username": username,
                        "interests": interests,
                        "updated_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
            print("User interests saved into MongoDB")
        except PyMongoError as e:
            print(f"[MongoDB] Failed to save user interests: {e}")

    def get_user_interests(self, user_id):
        try:
            doc = self.user_profiles.find_one({"user_id": str(user_id)})
            if doc and "interests" in doc:
                return doc["interests"]
            return []
        except PyMongoError as e:
            print(f"[MongoDB] Failed to get user interests: {e}")
            return []

    def find_matching_users(self, current_user_id, interests):
        try:
            cursor = self.user_profiles.find({
                "user_id": {"$ne": str(current_user_id)},
                "interests": {"$in": interests}
            })

            results = []
            for doc in cursor:
                other_interests = doc.get("interests", [])
                overlap = [x for x in other_interests if x in interests]
                if overlap:
                    results.append({
                        "user_id": doc.get("user_id"),
                        "username": doc.get("username"),
                        "matched_interests": overlap
                    })

            # sort by number of overlapping interests descending
            results.sort(key=lambda x: len(x["matched_interests"]), reverse=True)
            return results[:5]

        except PyMongoError as e:
            print(f"[MongoDB] Failed to find matches: {e}")
            return []