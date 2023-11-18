import psycopg2

def connect_db():
    return psycopg2.connect(
        dbname="botdb", 
        user="myuser", 
        password="jaido", 
        host="localhost"
    )

def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id SERIAL PRIMARY KEY,
            group_id BIGINT UNIQUE NOT NULL,
            group_name VARCHAR(255) NOT NULL
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_table()
