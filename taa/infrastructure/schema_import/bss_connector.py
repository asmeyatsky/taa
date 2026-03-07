"""Live BSS connector — connects to a running BSS database, introspects schema, generates mappings."""

from __future__ import annotations

from dataclasses import dataclass

from taa.infrastructure.schema_import.parser import ImportedTable, ImportedColumn


@dataclass(frozen=True)
class BSSConnectionConfig:
    """Database connection configuration for a live BSS system."""

    host: str
    port: int
    database: str
    username: str
    password: str = ""
    db_type: str = "oracle"  # oracle, mysql, postgresql, mssql
    schema_filter: str = ""  # optional schema/owner filter


class BSSConnector:
    """Connects to a live BSS database and introspects the schema.

    Supports Oracle (cx_Oracle/oracledb), MySQL, PostgreSQL, and MSSQL.
    Database drivers must be installed separately:
      - Oracle: pip install oracledb
      - MySQL: pip install mysql-connector-python
      - PostgreSQL: pip install psycopg2-binary
      - MSSQL: pip install pymssql
    """

    def __init__(self, config: BSSConnectionConfig) -> None:
        self._config = config

    def introspect(self) -> tuple[ImportedTable, ...]:
        """Connect to the BSS database and extract table/column metadata."""
        if self._config.db_type == "oracle":
            return self._introspect_oracle()
        elif self._config.db_type == "mysql":
            return self._introspect_mysql()
        elif self._config.db_type == "postgresql":
            return self._introspect_postgresql()
        elif self._config.db_type == "mssql":
            return self._introspect_mssql()
        else:
            raise ValueError(f"Unsupported database type: {self._config.db_type}")

    def test_connection(self) -> bool:
        """Test if the database connection works."""
        try:
            conn = self._get_connection()
            conn.close()
            return True
        except Exception:
            return False

    def _get_connection(self):
        """Get a database connection based on db_type."""
        c = self._config
        if c.db_type == "oracle":
            try:
                import oracledb
                return oracledb.connect(
                    user=c.username, password=c.password,
                    dsn=f"{c.host}:{c.port}/{c.database}",
                )
            except ImportError:
                raise ImportError("Install oracledb: pip install oracledb")

        elif c.db_type == "mysql":
            try:
                import mysql.connector
                return mysql.connector.connect(
                    host=c.host, port=c.port, database=c.database,
                    user=c.username, password=c.password,
                )
            except ImportError:
                raise ImportError("Install mysql-connector: pip install mysql-connector-python")

        elif c.db_type == "postgresql":
            try:
                import psycopg2
                return psycopg2.connect(
                    host=c.host, port=c.port, dbname=c.database,
                    user=c.username, password=c.password,
                )
            except ImportError:
                raise ImportError("Install psycopg2: pip install psycopg2-binary")

        elif c.db_type == "mssql":
            try:
                import pymssql
                return pymssql.connect(
                    server=c.host, port=c.port, database=c.database,
                    user=c.username, password=c.password,
                )
            except ImportError:
                raise ImportError("Install pymssql: pip install pymssql")

        raise ValueError(f"Unsupported: {c.db_type}")

    def _introspect_oracle(self) -> tuple[ImportedTable, ...]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            schema_filter = self._config.schema_filter or self._config.username.upper()
            cursor.execute("""
                SELECT table_name, column_name, data_type, nullable
                FROM all_tab_columns
                WHERE owner = :owner
                ORDER BY table_name, column_id
            """, {"owner": schema_filter})
            return self._build_tables(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def _introspect_mysql(self) -> tuple[ImportedTable, ...]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            query = """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
            """
            schema = self._config.schema_filter or self._config.database
            cursor.execute(query, (schema,))
            return self._build_tables(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def _introspect_postgresql(self) -> tuple[ImportedTable, ...]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            schema = self._config.schema_filter or "public"
            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
            """, (schema,))
            return self._build_tables(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def _introspect_mssql(self) -> tuple[ImportedTable, ...]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            schema = self._config.schema_filter or "dbo"
            cursor.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
            """, (schema,))
            return self._build_tables(cursor.fetchall())
        finally:
            cursor.close()
            conn.close()

    def _build_tables(
        self, rows: list[tuple]
    ) -> tuple[ImportedTable, ...]:
        """Build ImportedTable objects from query results (table_name, column_name, data_type, nullable)."""
        tables_dict: dict[str, list[ImportedColumn]] = {}
        for row in rows:
            table_name = row[0]
            col_name = row[1]
            data_type = row[2] or "VARCHAR"
            nullable_val = row[3] if len(row) > 3 else "Y"
            nullable = str(nullable_val).upper() in ("Y", "YES", "TRUE", "1")
            tables_dict.setdefault(table_name, []).append(
                ImportedColumn(name=col_name, data_type=data_type.upper(), nullable=nullable)
            )
        return tuple(
            ImportedTable(name=name, columns=tuple(cols))
            for name, cols in tables_dict.items()
        )
