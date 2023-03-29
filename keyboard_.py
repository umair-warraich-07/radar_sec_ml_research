import time
import psycopg2
import datetime
import statistics
from pynput import keyboard

# Constants
WINDOW_SIZE = 60  # Window size in seconds
DB_HOST = "localhost"
DB_NAME = "radar_security"
DB_USER = "postgres"
DB_PASS = "12345678"

# Connect to the PostgresSQL database
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS
)

# Create a new table if it doesn't exist
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS typing_stats (
        timestamp TIMESTAMP NOT NULL,
        keystroke_counter INTEGER,
        erase_keys_counter INTEGER,
        erase_keys_percentage REAL,
        press_press_average_interval REAL,
        press_press_stddev_interval REAL,
        press_release_average_interval REAL,
        press_release_stddev_interval REAL,
        word_counter INTEGER,
        word_average_length REAL,
        word_stddev_length REAL
    );
""")
conn.commit()

# Initialize the feature counters
keystroke_counter = 0
erase_keys_counter = 0
press_press_intervals = []
press_release_intervals = []
word_lengths = []
last_timestamp = time.time()
window_start_time = time.time()
word_counter = 0



def on_keyboard_event(event):
    # Initialize the last_timestamp variable
    last_timestamp = globals().get('last_timestamp', 0)

    global keystroke_counter
    global erase_keys_counter
    global press_press_intervals
    global press_release_intervals
    global word_lengths
    global last_press_time
    global word_counter

    # Update the keystroke counter
    keystroke_counter += 1

    # Handle erase keys
    if event==keyboard.Key.backspace:
        erase_keys_counter += 1
        if len(word_lengths) > 0:
            word_lengths[-1] -= 1
            if word_lengths[-1] == 0:
                word_lengths.pop()
                word_counter -= 1
    elif  event == keyboard.Key.enter:
        if press_press_intervals:
            last_press_time = press_press_intervals[-1]
        else:
            last_press_time = 0

        # Calculate the time since the last press
        last_release_time = time.time()
        time_since_last_press = last_release_time - last_press_time

        press_release_intervals.append(time_since_last_press)

        # Calculate the length of the previous word
        try:
            last_word_length = word_lengths[-1]
            word_lengths.append(last_word_length)
        except IndexError:
            # This is the first word, so there is no previous word length
            pass

        # Increment the word counter
        word_counter += 1
    else:
        # This is a letter or symbol, so we count it as part of the current word
        if len(word_lengths) == 0:
            word_lengths.append(1)
            word_counter += 1
        else:
            word_lengths[-1] += 1

    # Calculate the press-press interval
    current_timestamp = time.time()
    if current_timestamp - last_timestamp > 0.01:
        last_timestamp = current_timestamp
        press_press_intervals.append(current_timestamp - window_start_time)
        last_press_time = current_timestamp - window_start_time


def send_data_to_db(data):
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )

        # Check if the table exists, create it if it doesn't
        cur = conn.cursor()
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='typing_stats');")
        if not cur.fetchone()[0]:
            cur.execute("""
                CREATE TABLE typing_stats (
                    timestamp TIMESTAMP NOT NULL,
                    keystroke_counter INTEGER,
                    erase_keys_counter INTEGER,
                    erase_keys_percentage REAL,
                    press_press_average_interval REAL,
                    press_press_stddev_interval REAL,
                    press_release_average_interval REAL,
                    press_release_stddev_interval REAL,
                    word_counter INTEGER,
                    word_average_length REAL,
                    word_stddev_length REAL
                );
            """)
            conn.commit()

        # Prepare the data for insertion into the database
        timestamp = datetime.datetime.now()
        keystroke_counter = data['keystroke_counter']
        erase_keys_counter = data['erase_keys_counter']
        erase_keys_percentage = (erase_keys_counter / keystroke_counter) * 100 if keystroke_counter > 0 else 0
        press_press_intervals = data['press_press_intervals']
        press_release_intervals = data['press_release_intervals']
        word_lengths = data['word_lengths']
        word_counter = len(word_lengths)
        word_average_length = statistics.mean(word_lengths) if word_counter > 0 else 0
        word_stddev_length = statistics.stdev(word_lengths) if word_counter > 1 else 0
        press_press_average_interval = statistics.mean(press_press_intervals) if len(press_press_intervals) > 0 else 0
        press_press_stddev_interval = statistics.stdev(press_press_intervals) if len(press_press_intervals) > 1 else 0
        press_release_average_interval = statistics.mean(press_release_intervals) if len(
            press_release_intervals) > 0 else 0
        press_release_stddev_interval = statistics.stdev(press_release_intervals) if len(
            press_release_intervals) > 1 else 0

        # Insert the data into the database
        cur.execute("""
            INSERT INTO typing_stats (
                timestamp,
                keystroke_counter,
                erase_keys_counter,
                erase_keys_percentage,
                press_press_average_interval,
                press_press_stddev_interval,
                press_release_average_interval,
                press_release_stddev_interval,
                word_counter,
                word_average_length,
                word_stddev_length
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            timestamp,
            keystroke_counter,
            erase_keys_counter,
            erase_keys_percentage,
            press_press_average_interval,
            press_press_stddev_interval,
            press_release_average_interval,
            press_release_stddev_interval,
            word_counter,
            word_average_length,
            word_stddev_length
        ))
        conn.commit()

        print("Data inserted successfully!")
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
def main():
    # Clear the feature counters for the next window
    global keystroke_counter
    global erase_keys_counter
    global press_press_intervals
    global press_release_intervals
    global word_lengths
    global last_timestamp
    global window_start_time
    # Initialize the keyboard listener
    with keyboard.Listener(on_press=on_keyboard_event) as listener:
        # Loop indefinitely
        while True:
            # Wait for the current window to end
            time.sleep(WINDOW_SIZE)

            # Send the collected data to the database
            data = {
                'keystroke_counter': keystroke_counter,
                'erase_keys_counter': erase_keys_counter,
                'press_press_intervals': press_press_intervals,
                'press_release_intervals': press_release_intervals,
                'word_lengths': word_lengths,
            }
            send_data_to_db(data)


            keystroke_counter = 0
            erase_keys_counter = 0
            press_press_intervals = []
            press_release_intervals = []
            word_lengths = []
            last_timestamp = time.time()
            window_start_time = time.time()
            listener.join()

if __name__ == '__main__':
    main()


