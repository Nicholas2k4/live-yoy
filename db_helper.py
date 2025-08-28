import pymysql
from sshtunnel import SSHTunnelForwarder
import atexit
import time
import streamlit as st


class DBHelper:
    _tunnel = None
    _conn = None

    # Konfigurasi koneksi (bisa diganti ambil dari file config atau environment)
    ssh_conf = st.secrets["ssh"]
    mysql_conf = st.secrets["mysql"]
    local_conf = st.secrets["local"]

    @classmethod
    def init_connection(cls):
        if cls._conn and cls._tunnel:
            return  

        cls._tunnel = SSHTunnelForwarder(
            (cls.ssh_conf["host"], cls.ssh_conf["port"]),
            ssh_username=cls.ssh_conf["username"],
            ssh_password=cls.ssh_conf["password"],
            remote_bind_address=(cls.mysql_conf["host"], cls.mysql_conf["port"]),
            local_bind_address=("127.0.0.1", cls.local_conf["bind_port"])
        )
        cls._tunnel.start()
        time.sleep(0.2)

        cls._conn = pymysql.connect(
            host="127.0.0.1",
            port=cls._tunnel.local_bind_port,
            user=cls.mysql_conf["user"],
            password=cls.mysql_conf["password"],
            db=cls.mysql_conf["database"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )

        atexit.register(cls.close_connection)

    @classmethod
    def query_live_db(cls, sql, params=None):
        """Jalankan query SELECT/INSERT/UPDATE/DELETE."""
        cls.close_connection()
        cls.init_connection()
        with cls._conn.cursor() as cursor:
            cursor.execute(sql, params)
            if cursor.description:  # SELECT
                return cursor.fetchall()
            cls.close_connection()
            return {"rowcount": cursor.rowcount}

    @classmethod
    def close_connection(cls):
        """Tutup koneksi dan tunnel."""
        if cls._conn:
            try:
                cls._conn.close()
            except Exception:
                pass
        if cls._tunnel:
            try:
                cls._tunnel.stop()
            except Exception:
                pass
        cls._conn = None
        cls._tunnel = None
