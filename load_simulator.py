import requests
import time
import random
import json

API_URL = "http://localhost:5000/items"
HEADERS = {"Content-Type": "application/json"}

def generate_load():

    item_id_counter = 1
    print("Starting load generator...")
    print(f"Targeting API at {API_URL}")
    print("Press Ctrl+C to stop.")
    
    while True:
        try:
            
            item_data = {
                "id": item_id_counter,
                "name": f"GeneratedItem-{random.randint(100, 999)}"
            }
            
            print(f"\nAttempting to create item {item_id_counter}...")
            post_response = requests.post(API_URL, headers=HEADERS, json=item_data)
            
            print(f"POST /items -> Status: {post_response.status_code}, Response: {post_response.text.strip()}")

            time.sleep(2)

            if post_response.status_code == 201:
                print(f"Attempting to retrieve item {item_id_counter}...")
                get_response = requests.get(f"{API_URL}/?item_id={item_id_counter}")
                print(f"GET  /items/?item_id={item_id_counter} -> Status: {get_response.status_code}")

            item_id_counter += 1

        except requests.exceptions.ConnectionError:
            print("\nConnection failed. Is the rest-service running and accessible at http://localhost:5000?")
            time.sleep(5)
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")

        time.sleep(2)

if __name__ == "__main__":
    try:
        generate_load()
    except KeyboardInterrupt:
        print("\nLoad generator stopped.")