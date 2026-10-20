"""Emit one local setting to the clipboard pipeline; never run directly for display."""
import sys
from pathlib import Path
from dotenv import dotenv_values


def main():
    allowed={'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}
    if len(sys.argv)!=3 or sys.argv[2] not in allowed:
        print('Invalid secret selection.',file=sys.stderr)
        return 1
    value=dotenv_values(Path(sys.argv[1])).get(sys.argv[2])
    if not value or value=='replace_locally':
        print('Required local setting is missing.',file=sys.stderr)
        return 1
    sys.stdout.write(value)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
