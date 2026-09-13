import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase, Query
from app.config import settings

def get_db_connection():
    conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=5, options="-c statement_timeout=15000")
    return conn

class Neo4jManager:
    _driver = None

    @classmethod
    def get_driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=5, max_transaction_retry_time=0,
            )
        return cls._driver

    @classmethod
    def close(cls):
        if cls._driver is not None:
            cls._driver.close()
            cls._driver = None

    @classmethod
    def execute_cypher(cls, query: str, parameters: dict = None):
        driver = cls.get_driver()
        with driver.session() as session:
            result = session.run(Query(query, timeout=15), parameters or {})
            return [record.data() for record in result]
