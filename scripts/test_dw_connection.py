#!/usr/bin/env python
"""
Test script for PostgreSQL Data Warehouse connection.
Loads configuration from config.yaml and tests connectivity.

Usage:
    python scripts/test_dw_connection.py

    Or with specific config file:
    python scripts/test_dw_connection.py --config config/config.yaml
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2 import OperationalError, ProgrammingError

from src.utils.config_loader import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PostgreSQLConnectionTester:
    """Tests PostgreSQL data warehouse connection."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        Initialize tester with config file.

        Args:
            config_path: Path to config.yaml
        """
        self.config_path = config_path
        self.config = None
        self.dw_config = None
        self.connection = None

    def load_config(self, env_path: str = None) -> bool:
        """
        Load configuration from YAML with .env and ${VAR} substitution.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.config = load_config(
                config_path=self.config_path,
                env_path=env_path,
            )
            logger.info(f"✓ Configuration loaded from {self.config_path}")
            return True
        except FileNotFoundError:
            logger.error(f"✗ Configuration file not found: {self.config_path}")
            return False
        except Exception as e:
            logger.error(f"✗ Error loading config: {e}")
            return False

    def extract_dw_config(self) -> bool:
        """
        Extract data warehouse configuration.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.dw_config = self.config.get("datawarehouse", {})

            if not self.dw_config:
                logger.error("✗ No 'datawarehouse' section in config")
                return False

            dw_type = self.dw_config.get("type", "").lower()
            if dw_type != "postgresql":
                logger.error(f"✗ Expected 'postgresql', got '{dw_type}'")
                return False

            logger.info(f"✓ Data warehouse type: {dw_type}")
            return True
        except Exception as e:
            logger.error(f"✗ Error extracting DW config: {e}")
            return False

    def resolve_credentials(self) -> tuple[dict[str, str], tuple[str, str]]:
        """
        Resolve database credentials from config and environment variables.

        Returns:
            Tuple of (connection_params dict, (username, password) tuple)
        """
        conn_config = self.dw_config.get("connection", {})

        # Extract values and resolve environment variables
        host = conn_config.get("host", "localhost")
        port = conn_config.get("port", 5432)
        database = conn_config.get("database", "")
        user = conn_config.get("user", "")
        password = conn_config.get("password", "")

        # Support unresolved placeholders if config was loaded without .env
        if isinstance(user, str) and user.startswith("${") and user.endswith("}"):
            var_name = user[2:-1]
            user = os.getenv(var_name, "")
            if not user:
                logger.warning(f"⚠ Environment variable {var_name} not set")

        if isinstance(password, str) and password.startswith("${") and password.endswith("}"):
            var_name = password[2:-1]
            password = os.getenv(var_name, "")
            if not password:
                logger.warning(f"⚠ Environment variable {var_name} not set")

        connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }

        return connection_params, (user, password)

    def test_connection(self) -> bool:
        """
        Test PostgreSQL connection.

        Returns:
            True if connection successful, False otherwise
        """
        conn_params, (user, password) = self.resolve_credentials()

        logger.info("\nConnection Parameters:")
        logger.info(f"  Host: {conn_params['host']}")
        logger.info(f"  Port: {conn_params['port']}")
        logger.info(f"  Database: {conn_params['database']}")
        logger.info(f"  User: {conn_params['user'] if conn_params['user'] else '(not set)'}")
        logger.info(f"  Password: {'*' * 4 if password else '(not set)'}")

        # Validate credentials
        if not conn_params["user"] or not password:
            logger.error("✗ Database credentials not configured")
            logger.error("  Please set DW_USER and DW_PASSWORD environment variables")
            return False

        try:
            logger.info("\nAttempting connection...")
            self.connection = psycopg2.connect(
                host=conn_params["host"],
                port=conn_params["port"],
                database=conn_params["database"],
                user=conn_params["user"],
                password=password,
                connect_timeout=5,
            )
            logger.info("✓ Connection successful!")
            return True

        except OperationalError as e:
            logger.error(f"✗ Connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False

    def test_database_access(self) -> bool:
        """
        Test database access and retrieve basic info.

        Returns:
            True if successful, False otherwise
        """
        if not self.connection:
            logger.error("✗ No active connection")
            return False

        try:
            cursor = self.connection.cursor()

            # Get database version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            logger.info(f"\n✓ PostgreSQL Version: {version.split(',')[0]}")

            # Get current database
            cursor.execute("SELECT current_database();")
            current_db = cursor.fetchone()[0]
            logger.info(f"✓ Current Database: {current_db}")

            # Get current user
            cursor.execute("SELECT current_user;")
            current_user = cursor.fetchone()[0]
            logger.info(f"✓ Current User: {current_user}")

            # Get table count
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            logger.info(f"✓ Tables in public schema: {table_count}")

            # List first 5 tables
            if table_count > 0:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    LIMIT 5
                """)
                tables = [row[0] for row in cursor.fetchall()]
                logger.info(f"  Sample tables: {', '.join(tables)}")

            cursor.close()
            return True

        except ProgrammingError as e:
            logger.error(f"✗ Database query error: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Error accessing database: {e}")
            return False

    def test_schema_access(self) -> bool:
        """
        Test access to specific schema (if needed).

        Returns:
            True if successful, False otherwise
        """
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()

            # Get schemas
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
                LIMIT 10
            """)
            schemas = [row[0] for row in cursor.fetchall()]

            if schemas:
                logger.info(f"\n✓ Available schemas: {', '.join(schemas)}")
            else:
                logger.info("\n⚠ No custom schemas found")

            cursor.close()
            return True

        except Exception as e:
            logger.error(f"⚠ Could not retrieve schemas: {e}")
            return True  # Not critical

    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("\n✓ Connection closed")

    def run_all_tests(self, skip_config_load: bool = False) -> bool:
        """
        Run all connection tests.

        Returns:
            True if all tests passed, False otherwise
        """
        logger.info("=" * 60)
        logger.info("PostgreSQL Data Warehouse Connection Test")
        logger.info("=" * 60)

        if not skip_config_load and not self.load_config():
            return False

        # Step 2: Extract DW config
        if not self.extract_dw_config():
            return False

        # Step 3: Test connection
        if not self.test_connection():
            return False

        # Step 4: Test database access
        if not self.test_database_access():
            self.close()
            return False

        # Step 5: Test schema access
        self.test_schema_access()

        self.close()
        return True


def find_file(filename: str = ".env") -> str:
    """
    Find file in multiple locations.

    Args:
        filename: Filename or relative path to find (e.g., ".env", "config/config.yaml")

    Returns:
        Path to file if found, otherwise the original filename
    """
    # Check multiple possible locations
    possible_paths = [
        Path(filename),  # Current directory
        Path(__file__).parent.parent / filename,  # data-catalog-assistant/filename
        Path.cwd() / filename,  # Working directory
        Path.cwd() / "data-catalog-assistant" / filename,
    ]

    for path in possible_paths:
        if path.exists():
            logger.debug(f"Found {filename} at: {path}")
            return str(path)

    logger.debug(f"Could not find {filename} in standard locations")
    return filename


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test PostgreSQL Data Warehouse Connection")
    parser.add_argument("--config", default=None, help="Path to config.yaml (default: auto-detect)")
    parser.add_argument("--env", default=None, help="Path to .env file (default: auto-detect)")
    args = parser.parse_args()

    # Find config file if not specified
    if args.config:
        config_path = args.config
    else:
        config_path = find_file("config/config.yaml")

    if args.env:
        env_path = args.env
    else:
        env_path = find_file(".env")

    if os.path.exists(env_path):
        logger.info(f"✓ Using environment file {env_path}")
    else:
        logger.warning(f"⚠ Environment file not found: {env_path}")
        logger.info("  Continuing without .env file (using system environment variables)")

    tester = PostgreSQLConnectionTester(config_path)
    if not tester.load_config(env_path=env_path):
        return 1
    success = tester.run_all_tests(skip_config_load=True)

    logger.info("=" * 60)
    if success:
        logger.info("✓ All tests passed!")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("✗ One or more tests failed")
        logger.info("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
