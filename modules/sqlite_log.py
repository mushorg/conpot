import sqlite3

class SQLiteLogger(object):
    def __init__(self):
        self.conn = sqlite3.connect("conpot.db")
        self._create_db()

    def _create_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS events
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remote TEXT,
                slave_id INT,
                function_code INT,
                request_pdu TEXT
            )""")

    def log(self, event):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO events(remote, slave_id, function_code, request_pdu) VALUES (?, ?, ?, ?)",
                       (str(event["remote"]), event["slave_id"], event["function_code"], event["request_pdu"]))
        self.conn.commit()

    def select_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events")
        print cursor.fetchall()