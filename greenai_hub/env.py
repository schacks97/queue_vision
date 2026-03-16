import json
import os
import sys


def env_verifier(credentials):
    if credentials is None:
        print('Failed to Load envs check the .env.json and whether it exists')  # Red text
        sys.exit(1)


def get_credentials():
    creds = {}
    try:
        env_file_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(env_file_dir)
        with open(os.path.join(env_file_dir, '.env.json'), 'r') as f:
            creds = json.loads(f.read())
        return creds

    except Exception as e:
        print(f'Exception occured while loading envs: {e}')
        return None


credentials = get_credentials()
