import asyncio
import time
import mysql.connector  # Switching to mysql-connector for synchronous operations

connection = None
cursor = None

def setup_database():
    """Set up the database connection synchronously."""
    from Pro import set_active_users
    global connection, cursor

    # Database connection details (get these from your Railway project)
    db_config = {
        'host': "mysql.railway.internal",
        'user': "root",
        'password': "WtbBUUeagzLrnuzNWQbuQbRfAcGrYdZX",
        'database': "railway",
        'port': 3306
    }

    try:
        # Connect to the MySQL database synchronously
        connection = mysql.connector.connect(**db_config)  # Use synchronous connection
        cursor = connection.cursor()  # Synchronous cursor
        print("Database connection successful!")

        # Call the function to check for expired users
        active_users = check_and_remove_expired_users()  # Directly call the sync function
        set_active_users(active_users)

    except Exception as err:
        print(f"Error: {err}")


# Function to check all users' expiry dates and remove expired ones (synchronous)
def check_and_remove_expired_users():
    try:
        # Get current epoch time (in seconds)
        current_time = int(time.time())

        # Query to get all users and their data
        query = "SELECT user_id, transaction_sig, amount, expiry_date, fromUserAccount FROM users"

        # Use the cursor synchronously for executing the query
        cursor.execute(query)  # No await, execute synchronously
        users = cursor.fetchall()  # No await, fetch all synchronously

        active_users = {}  # To store active users as a dictionary

        for user in users:
            user_id, transaction_sig, amount, expiry_date, fromUserAccount = user
            # Ensure expiry_date is an integer representing epoch time
            expiry_date = int(expiry_date)

            # Check if the user is expired
            if expiry_date < current_time:
                print(f"User {user_id} is expired. Deleting...")

                # Delete expired user from the database
                delete_query = "DELETE FROM users WHERE user_id = %s"
                cursor.execute(delete_query, (user_id,))  # Synchronously execute delete
                connection.commit()  # Commit the transaction synchronously
                print(f"User {user_id} deleted successfully!")

            else:
                active_users[user_id] = (transaction_sig, amount, expiry_date, fromUserAccount)
                print(f"User {user_id} is still active.")

        # Return the active users dictionary
        return active_users

    except Exception as err:
        print(f"Error checking and removing expired users: {err}")
        return {}


def add_new_user(user_id, transaction_sig, amount, expiry_date, fromUserAccount):
    # Wrap the async function call inside a sync function to make sure it's handled properly.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_add_new_user(user_id, transaction_sig, amount, expiry_date, fromUserAccount))

async def _add_new_user(user_id, transaction_sig, amount, expiry_date, fromUserAccount):
    # Prepare the SQL query to insert a new user into the users table
    query = """
    INSERT INTO users (user_id, transaction_sig, amount, expiry_date, fromUserAccount)
    VALUES (%s, %s, %s, %s, %s)
    """
    # Data to be inserted
    data = (user_id, transaction_sig, amount, expiry_date, fromUserAccount)

    try:
        cursor.execute(query, data)  # Execute synchronously
        connection.commit()  # Commit synchronously
        print("New user added successfully!")
    except Exception as err:
        print(f"Error: {err}")