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
                protocol TEXT,
                request TEXT,
                response TEXT
            )""")

    def log(self, event):
        cursor = self.conn.cursor()
        #if event['data_type'] == 'modbus':
        for entry in event['data'].values():
            cursor.execute("INSERT INTO events(remote, protocol, request, response) VALUES (?, ?, ?, ?)",
                (str(event["remote"]), event['data_type'], entry.get('request'), entry.get('response')))
        self.conn.commit()

    def select_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM events")
        print cursor.fetchall()