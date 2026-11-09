"""Explicit administration of the optional PostgreSQL team schema.

DSNs are read from the environment and never printed. The migration account must
not be used by application requests. This command does not grant database roles.
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['migrate', 'ready'])
    args = parser.parse_args()
    import psycopg
    from veya.team.postgres import migrate, verify_schema

    dsn = os.environ.get('VEYA_TEAM_DATABASE_URL')
    if not dsn:
        parser.exit(1, 'VEYA_TEAM_DATABASE_URL is required\n')
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as connection:
        if args.command == 'migrate':
            migrate(connection)
        else:
            verify_schema(connection)
    print('Team database ' + args.command + ' passed')


if __name__ == '__main__':
    main()
